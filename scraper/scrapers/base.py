"""Abstract base scraper defining Substack scraping orchestration."""

from __future__ import annotations

import logging
import os
import random
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from pathlib import Path
from time import sleep
from typing import Any

from bs4 import BeautifulSoup
from tqdm import tqdm

from ..config import BASE_CONTENT_DIR
from ..discovery import discover_post_urls
from ..extract import extract_post_data
from ..frontmatter import combine_metadata_and_content, extract_metadata_from_md
from ..images import count_images_in_markdown, process_markdown_images
from ..storage import build_file_link, get_filename_from_url, save_posts_data_to_json, save_to_file
from ..sync import fetch_posts_from_api, load_sync_state, save_sync_state
from ..url_utils import (
    extract_main_part,
    get_post_slug,
    get_publication_url,
    get_slug_from_url,
    is_post_url,
)

logger = logging.getLogger(__name__)


class BaseSubstackScraper(ABC):
    """Abstract base scraper coordinating Substack post discovery, extraction, and archiving.

    Delegates parsing, URL discovery, frontmatter, file operations, and sync logic
    to focused modules while managing the high-level scraping lifecycle.
    """

    def __init__(
        self,
        base_substack_url: str,
        content_save_dir: str = BASE_CONTENT_DIR,
        download_images: bool = False,
        overwrite: bool = False,
        clean_content: bool = True,
    ) -> None:
        """Initialize base scraper configuration and target directories.

        Args:
            base_substack_url: Publication homepage or individual post URL.
            content_save_dir: Root directory for author-centric exports (defaults to 'content').
            download_images: Whether to download CDN images locally.
            overwrite: Whether to overwrite existing files on disk when scraping.
            clean_content: Whether to strip promotional widgets and subscription CTAs.
        """
        self.overwrite: bool = overwrite
        self.clean_content: bool = clean_content
        self.is_single_post: bool = is_post_url(base_substack_url)
        self.post_slug: str | None = get_post_slug(base_substack_url) if self.is_single_post else None
        original_url = base_substack_url

        if self.is_single_post:
            base_substack_url = get_publication_url(base_substack_url)

        if not base_substack_url.endswith("/"):
            base_substack_url += "/"
        self.base_substack_url: str = base_substack_url

        self.writer_name: str = extract_main_part(base_substack_url)
        self.base_content_dir: str = content_save_dir
        self.author_dir: str = os.path.join(content_save_dir, self.writer_name)
        self.posts_save_dir: str = os.path.join(self.author_dir, "posts")
        self.images_save_dir: str = os.path.join(self.author_dir, "images")
        self.metadata_file_path: str = os.path.join(self.author_dir, "metadata.json")

        os.makedirs(self.posts_save_dir, exist_ok=True)
        logger.info("Created posts directory %s", self.posts_save_dir)

        self.download_images: bool = download_images
        self.image_dir: Path = Path(self.images_save_dir)
        if self.download_images:
            os.makedirs(self.images_save_dir, exist_ok=True)

        if self.is_single_post:
            self.post_urls: list[str] = [original_url]
        else:
            self.post_urls: list[str] = discover_post_urls(self.base_substack_url)

    @staticmethod
    def _is_rate_limited(soup: BeautifulSoup) -> bool:
        """Check whether the parsed DOM indicates a rate-limiting error."""
        pre = soup.select_one("body > pre") or soup.find("pre")
        return bool(pre and "too many requests" in pre.text.lower())

    @staticmethod
    def _compute_backoff_delay(attempt: int, jitter_ratio: float = 0.2) -> float:
        """Compute exponential backoff with jitter for a retry attempt."""
        base_delay = 2.0**attempt
        jitter_range = jitter_ratio * base_delay
        return base_delay + random.uniform(-jitter_range, jitter_range)

    @classmethod
    def _handle_rate_limit(
        cls,
        soup: BeautifulSoup,
        attempt: int,
        max_attempts: int,
        url: str,
    ) -> bool:
        """Check for rate limits and sleep with jittered exponential backoff if detected."""
        if not cls._is_rate_limited(soup):
            return False

        if attempt == max_attempts:
            raise RuntimeError(f"Max attempts reached for URL: {url}. Too many requests.")

        delay = cls._compute_backoff_delay(attempt)
        logger.warning(
            "[%s/%s] Too many requests. Retrying in %.2f seconds...",
            attempt,
            max_attempts,
            delay,
        )
        sleep(delay)
        return True

    def _dump_debug_html(self, soup: BeautifulSoup, url: str) -> None:
        """Dump raw HTML to _debug directory upon extraction failure."""
        try:
            debug_dir = os.path.join(self.base_content_dir, "_debug", self.writer_name)
            os.makedirs(debug_dir, exist_ok=True)
            slug = get_slug_from_url(url)
            debug_path = os.path.join(debug_dir, f"{slug}.html")
            with open(debug_path, "w", encoding="utf-8") as file:
                file.write(str(soup))
            logger.debug("Dumped raw HTML -> %s", debug_path)
        except OSError as dump_err:
            logger.warning("Failed to dump debug HTML: %s", dump_err)

    def _scrape_single_post(
        self,
        url: str,
        progress_bar: tqdm | None = None,
    ) -> dict[str, Any] | None:
        """Scrape an individual post, converting content to markdown and saving to disk.

        Args:
            url: Full URL of the Substack post.
            progress_bar: Optional tqdm progress bar instance.

        Returns:
            dict[str, Any] | None: Post metadata dictionary on success, or None on failure/skip.
        """
        slug = get_slug_from_url(url)
        filename = get_filename_from_url(url, filetype=".md")
        markdown_filepath = os.path.join(self.posts_save_dir, filename)

        if not self.overwrite and os.path.exists(markdown_filepath):
            existing_entry: dict[str, Any] = {
                "file_link": build_file_link(markdown_filepath, self.author_dir),
                "slug": slug,
            }
            extracted_metadata = extract_metadata_from_md(markdown_filepath)
            if extracted_metadata:
                existing_entry.update(extracted_metadata)
            return existing_entry

        soup = self.get_url_soup(url)
        if soup is None:
            return None

        extracted = extract_post_data(soup, url, clean_content=self.clean_content)

        if not extracted["title_found"] or not extracted["body_found"]:
            paywall = soup.select_one("h2.paywall-title")
            ld_script = soup.find("script", {"type": "application/ld+json"})
            logger.warning(
                "[EXTRACT FAIL] url=%s title_found=%s title=%r content_element_found=%s paywall_present=%s ld_json_present=%s date=%r author=%r",
                url,
                extracted["title_found"],
                extracted["title"],
                extracted["body_found"],
                paywall is not None,
                ld_script is not None,
                extracted["date"],
                extracted["author"],
            )
            self._dump_debug_html(soup, url)
            skip_message = (
                f"[SKIP] Extraction failed for {url} "
                f"(title={extracted['title']!r}, content_present={extracted['body_found']}). See _debug dump."
            )
            if progress_bar:
                progress_bar.write(skip_message)
            else:
                logger.warning(skip_message)
            return None

        raw_body = extracted["md_content"]
        if self.download_images:
            total_images = count_images_in_markdown(raw_body)
            with tqdm(
                total=total_images,
                desc=f"Downloading images for {slug}",
                leave=False,
                disable=progress_bar is not None,
            ) as image_progress_bar:
                raw_body = process_markdown_images(
                    md_content=raw_body,
                    author=self.writer_name,
                    post_slug=slug,
                    pbar=image_progress_bar if progress_bar is None else progress_bar,
                    base_content_dir=self.base_content_dir,
                )

        final_markdown = combine_metadata_and_content(
            title=extracted["title"],
            subtitle=extracted["subtitle"],
            date=extracted["date"],
            author=extracted["author"],
            cover_image=extracted["cover_image"],
            content=raw_body,
            post_id=extracted["post_id"],
            tags=extracted["tags"],
            description=extracted["description"],
            wordcount=extracted["wordcount"],
            audience=extracted["audience"],
            canonical_url=extracted["canonical_url"],
        )

        save_to_file(markdown_filepath, final_markdown, overwrite=self.overwrite)

        return {
            "title": extracted["title"],
            "subtitle": extracted["subtitle"],
            "description": extracted["description"],
            "author": extracted["author"],
            "date": extracted["date"],
            "cover_image": extracted["cover_image"],
            "post_id": extracted["post_id"],
            "tags": extracted["tags"],
            "wordcount": extracted["wordcount"],
            "audience": extracted["audience"],
            "canonical_url": extracted["canonical_url"],
            "file_link": build_file_link(markdown_filepath, self.author_dir),
            "slug": slug,
        }

    def scrape_posts(self, limit: int = 0) -> None:
        """Iterate over all post URLs, scraping and saving them to disk.

        Args:
            limit: Number of posts to download (0 = scrape all).
        """
        posts_data = []
        count = 0
        total = limit if limit != 0 else len(self.post_urls)
        with tqdm(total=total, desc="Scraping posts") as progress_bar:
            for url in self.post_urls:
                try:
                    entry = self._scrape_single_post(url, progress_bar=progress_bar)
                    if entry is not None:
                        posts_data.append(entry)
                    else:
                        total += 1
                        progress_bar.total = total
                        progress_bar.refresh()
                        continue
                except Exception as error:
                    progress_bar.write(f"Error scraping post: {error}")

                count += 1
                progress_bar.update(1)

                if limit != 0 and count >= limit:
                    break

        save_posts_data_to_json(self.metadata_file_path, posts_data)
        logger.info("Saved %d posts to %s", len(posts_data), self.metadata_file_path)

    def sync_posts(self) -> int:
        """Execute incremental delta synchronization for the publication.

        Discovers new posts published since the last sync using Substack's public API,
        scrapes the delta posts, updates metadata.json, and records the new sync cursor.

        Returns:
            int: Number of new posts scraped during the sync.

        Raises:
            ValueError: If invoked on an individual post URL instead of a publication.
        """
        if self.is_single_post:
            raise ValueError("sync_posts() cannot be called on a single post URL.")

        cursor = load_sync_state(self.author_dir, self.metadata_file_path)
        if cursor is None:
            logger.info("No prior sync state found. Running full scrape to initialize archive.")
            self.scrape_posts(limit=0)
            new_cursor = load_sync_state(self.author_dir, self.metadata_file_path)
            if new_cursor:
                save_sync_state(self.author_dir, new_cursor)
            return len(self.post_urls)

        since_date = cursor.get("last_post_date")
        last_post_id = cursor.get("last_post_id")
        last_post_slug = cursor.get("last_post_slug")

        logger.info("Checking for new posts since %s...", since_date)
        delta_posts = fetch_posts_from_api(
            publication_url=self.base_substack_url,
            since_date=since_date,
            last_post_id=last_post_id,
            last_post_slug=last_post_slug,
        )

        if delta_posts is None:
            logger.warning("Substack API unavailable. Falling back to sitemap discovery.")
            self.scrape_posts(limit=0)
            new_cursor = load_sync_state(self.author_dir, self.metadata_file_path)
            if new_cursor:
                save_sync_state(self.author_dir, new_cursor)
            return len(self.post_urls)

        if not delta_posts:
            logger.info("Sync up to date: 0 new posts found.")
            cursor["last_sync_at"] = datetime.now(UTC).isoformat()
            save_sync_state(self.author_dir, cursor)
            return 0

        logger.info("Found %d new post(s) to sync.", len(delta_posts))

        new_entries: list[dict[str, Any]] = []
        with tqdm(total=len(delta_posts), desc="Syncing delta posts") as progress_bar:
            for post in reversed(delta_posts):
                post_url = post.get("canonical_url")
                if not post_url:
                    slug = post.get("slug")
                    post_url = f"{self.base_substack_url}p/{slug}"

                try:
                    entry = self._scrape_single_post(post_url, progress_bar=progress_bar)
                    if entry is not None:
                        new_entries.append(entry)
                except Exception as error:
                    progress_bar.write(f"Error syncing post {post_url}: {error}")
                progress_bar.update(1)

        if new_entries:
            save_posts_data_to_json(self.metadata_file_path, posts_data=new_entries)
            newest_post = delta_posts[0]
            cursor["last_sync_at"] = datetime.now(UTC).isoformat()
            cursor["last_post_date"] = newest_post.get("post_date") or cursor.get("last_post_date")
            if newest_post.get("id"):
                cursor["last_post_id"] = newest_post["id"]
            if newest_post.get("slug"):
                cursor["last_post_slug"] = newest_post["slug"]
            cursor["total_synced_posts"] = cursor.get("total_synced_posts", 0) + len(new_entries)
            save_sync_state(self.author_dir, cursor)

        logger.info("Sync completed: %d post(s) synced successfully.", len(new_entries))
        return len(new_entries)

    @abstractmethod
    def get_url_soup(self, url: str) -> BeautifulSoup | None:
        """Fetch and parse HTML for a given post URL."""
        pass
