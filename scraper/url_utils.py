import re
from urllib.parse import urlparse


def is_post_url(url: str) -> bool:
    """Determine whether a URL points to a specific Substack post.

    Args:
        url: The URL string to evaluate.

    Returns:
        bool: True if the URL points to an individual post, False otherwise.
    """
    return "/p/" in url


def get_publication_url(url: str) -> str:
    """Extract the base publication root URL from any post or page URL.

    Args:
        url: The full URL of the post or page.

    Returns:
        str: The publication root URL ending in a trailing slash.
    """
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}/"


def get_post_slug(url: str) -> str:
    """Extract the post slug identifier from a Substack post URL.

    Args:
        url: The full URL of the post.

    Returns:
        str: The post slug, or 'unknown_post' if not detected.
    """
    clean_url = url.split("?")[0].split("#")[0]
    match = re.search(r"/p/([^/]+)", clean_url)
    return match.group(1) if match else "unknown_post"


def get_slug_from_url(url: str) -> str:
    """Extract the post slug from a URL, falling back to the last path segment.

    Args:
        url: The full or partial URL of the post or page.

    Returns:
        str: Extracted slug or 'unknown' if empty.
    """
    clean_url = url.split("?")[0].split("#")[0]
    if is_post_url(clean_url):
        return get_post_slug(clean_url)
    return clean_url.rstrip("/").split("/")[-1] or "unknown"


def extract_main_part(url: str) -> str:
    """Extract author or publication identifier from a Substack or custom domain URL.

    Args:
        url: The publication or post URL.

    Returns:
        str: The publication subdomain or custom domain primary slug.
    """
    netloc = urlparse(url).netloc.lower().split(":")[0]
    if not netloc:
        netloc = urlparse("https://" + url).netloc.lower().split(":")[0]
    if netloc.endswith(".substack.com"):
        sub = netloc[: -len(".substack.com")]
        return sub.split(".")[-1] if sub else "substack"
    parts = [p for p in netloc.split(".") if p]
    if len(parts) >= 2:
        if parts[0] in ("www", "blog", "news", "newsletter"):
            return parts[1]
        return parts[0]
    return parts[0] if parts else "substack"
