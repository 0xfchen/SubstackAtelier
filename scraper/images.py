import hashlib
import logging
import mimetypes
import os
import random
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from time import sleep
from urllib.parse import unquote

import requests

from scraper.config import (
    BASE_CONTENT_DIR,
    DEFAULT_REQUEST_TIMEOUT,
    MAX_IMAGE_WORKERS,
)

logger = logging.getLogger(__name__)


def resolve_image_url(url: str) -> str:
    """Extract the original source image URL from a Substack CDN URL.

    Args:
        url: URL string that might be a Substack CDN URL.

    Returns:
        str: Unquoted source URL if it was wrapped in a CDN URL, otherwise original URL.
    """
    pattern = r"https://substackcdn\.com/image/fetch/.*?/(https?%3A%2F%2F.*)"
    match = re.search(pattern, url)
    if match:
        return unquote(match.group(1))
    return url


def clean_linked_images(md_content: str) -> str:
    """Convert markdown linked images [![alt](img)](link) to ![alt](img).

    Only unwraps links that point back at the image itself or at the
    Substack CDN (Substack's zoom-view wrappers). External links (e.g.
    YouTube thumbnails linking to the video) are preserved intact.

    Args:
        md_content: Markdown content string.

    Returns:
        str: Cleaned markdown content.
    """
    pattern = r"\[!\[(.*?)\]\((.*?)\)\]\((.*?)\)"

    def replace(match: re.Match) -> str:
        alt_text, image_source, target_url = match.groups()
        if target_url == image_source or target_url.startswith("https://substackcdn.com/"):
            return f"![{alt_text}]({image_source})"
        return match.group(0)

    return re.sub(pattern, replace, md_content)


def count_images_in_markdown(md_content: str) -> int:
    """Count the total number of image references in markdown content.

    Args:
        md_content: The markdown text to inspect.

    Returns:
        int: Number of unique or repeated markdown image references.
    """
    cleaned_content = clean_linked_images(md_content)
    pattern = r"!\[.*?\]\((.*?)\)"
    matches = re.findall(pattern, cleaned_content)
    return len(matches)


def sanitize_image_filename(url: str, timeout: int = 5) -> str:
    """Create a filesystem-safe filename from an image URL.

    Args:
        url: Direct or CDN image URL.
        timeout: Network timeout in seconds when performing HEAD request to
            inspect content-type for extension fallback.

    Returns:
        str: Cleaned and sanitized image filename.
    """
    url = resolve_image_url(url)
    clean_url = url.split("?")[0]
    filename = clean_url.split("/")[-1]

    # Validate extension
    extension = os.path.splitext(filename)[1].lower()
    valid_extensions = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"}

    if extension not in valid_extensions:
        try:
            response = requests.head(url, timeout=timeout, allow_redirects=True)
            content_type = response.headers.get("content-type", "").split(";")[0].strip()
            guessed_extension = mimetypes.guess_extension(content_type)
            if guessed_extension in valid_extensions:
                extension = guessed_extension
            else:
                extension = ".jpg"
        except (requests.RequestException, OSError):
            extension = ".jpg"
        filename = f"{filename}{extension}"

    # Hash if filename is empty or excessive length
    if len(filename) > 100 or not filename:
        url_hash = hashlib.sha256(url.encode()).hexdigest()[:16]
        filename = f"img_{url_hash}{extension}"

    return filename


def download_image(
    url: str,
    save_path: Path,
    pbar=None,
    timeout: int = DEFAULT_REQUEST_TIMEOUT,
    max_retries: int = 3,
) -> str | None:
    """Download an image from a URL and save it to the specified local path.

    Retries on transient network errors or rate limits with exponential backoff.

    Args:
        url: Remote image URL.
        save_path: Target local Path where the image should be saved.
        pbar: Optional tqdm progress bar to increment upon success.
        timeout: Request timeout in seconds.
        max_retries: Maximum number of download attempts before giving up.

    Returns:
        str | None: String path to the saved file on success, or None on failure.
    """
    for attempt in range(1, max_retries + 1):
        try:
            response = requests.get(url, stream=True, timeout=timeout)
            if response.status_code == 200:
                save_path.parent.mkdir(parents=True, exist_ok=True)
                with open(save_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                if pbar:
                    pbar.update(1)
                return str(save_path)

            if response.status_code in (429, 500, 502, 503, 504) and attempt < max_retries:
                base = 2 ** (attempt - 1)
                delay = base + random.uniform(-0.2 * base, 0.2 * base)
                logger.debug(
                    "Image HTTP %s for %s. Retrying attempt %s/%s in %.2fs...",
                    response.status_code,
                    url,
                    attempt + 1,
                    max_retries,
                    delay,
                )
                sleep(delay)
                continue

            msg = f"HTTP {response.status_code} downloading image {url}"
            logger.warning(msg)
            if pbar:
                pbar.write(msg)
            return None
        except (requests.RequestException, OSError) as e:
            if attempt < max_retries:
                base = 2 ** (attempt - 1)
                delay = base + random.uniform(-0.2 * base, 0.2 * base)
                logger.debug(
                    "Error downloading image %s (%s). Retrying attempt %s/%s in %.2fs...",
                    url,
                    e,
                    attempt + 1,
                    max_retries,
                    delay,
                )
                sleep(delay)
                continue

            msg = f"Error downloading image {url}: {e!s}"
            logger.warning(msg)
            if pbar:
                pbar.write(msg)
    return None


def process_markdown_images(
    md_content: str,
    author: str,
    post_slug: str,
    pbar=None,
    max_workers: int = MAX_IMAGE_WORKERS,
    base_content_dir: str | Path | None = None,
) -> str:
    """Download Substack CDN images concurrently and update markdown references.

    Args:
        md_content: Raw post markdown content.
        author: Author or publication directory name.
        post_slug: Post slug subdirectory name.
        pbar: Optional tqdm progress bar to increment per image.
        max_workers: Maximum number of worker threads for parallel downloading.
        base_content_dir: Root content directory (defaults to BASE_CONTENT_DIR).

    Returns:
        str: Updated markdown content with CDN links replaced by relative paths.
    """
    target_content_dir = Path(base_content_dir or BASE_CONTENT_DIR)

    author_dir = target_content_dir / author
    image_dir = author_dir / "images" / post_slug
    md_dir = author_dir / "posts"
    md_content = clean_linked_images(md_content)
    pattern = r"\(https://substackcdn\.com/image/fetch/[^\s\)]+\)"

    matches = [m.group(0).strip("()") for m in re.finditer(pattern, md_content)]
    unique_urls = list(dict.fromkeys(matches))

    download_tasks = []
    for raw_url in unique_urls:
        resolved_url = resolve_image_url(raw_url)
        filename = sanitize_image_filename(raw_url)
        save_path = image_dir / filename
        if not save_path.exists():
            download_tasks.append((resolved_url, save_path))
        elif pbar:
            pbar.update(1)

    download_results = {}
    if download_tasks:
        workers = min(len(download_tasks), max(1, max_workers))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_to_path = {
                executor.submit(download_image, resolved_url, save_path, pbar): save_path
                for resolved_url, save_path in download_tasks
            }
            for future in future_to_path:
                save_path = future_to_path[future]
                try:
                    downloaded_path = future.result()
                    if downloaded_path:
                        download_results[save_path] = downloaded_path
                except (requests.RequestException, OSError) as exc:
                    logger.debug("Failed image task for %s: %s", save_path, exc)

    def replace_image(match: re.Match[str]) -> str:
        url = match.group(0).strip("()")
        filename = sanitize_image_filename(url)
        save_path = image_dir / filename
        if not save_path.exists() and save_path not in download_results:
            return match.group(0)

        rel_path = os.path.relpath(save_path, md_dir)
        rel_path = rel_path.replace("\\", "/")
        return f"({rel_path})"

    return re.sub(pattern, replace_image, md_content)
