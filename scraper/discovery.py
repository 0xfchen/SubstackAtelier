"""Substack archive post URL discovery via sitemap and RSS feeds."""

from __future__ import annotations

import logging
from xml.etree import ElementTree as ET

import requests

from .config import DEFAULT_REQUEST_TIMEOUT, EXCLUDED_URL_KEYWORDS

logger = logging.getLogger(__name__)


def _fetch_urls_from_sitemap(publication_url: str) -> list[str]:
    """Fetch post URLs declared in the publication sitemap.xml."""
    if not publication_url.endswith("/"):
        publication_url += "/"
    sitemap_url = f"{publication_url}sitemap.xml"
    try:
        response = requests.get(sitemap_url, timeout=DEFAULT_REQUEST_TIMEOUT)
    except requests.RequestException as exc:
        logger.warning("Error fetching sitemap at %s: %s", sitemap_url, exc)
        return []

    if not response.ok:
        logger.warning("Error fetching sitemap at %s: %s", sitemap_url, response.status_code)
        return []

    try:
        root = ET.fromstring(response.content)
    except ET.ParseError as exc:
        logger.warning("XML parsing error in sitemap at %s: %s", sitemap_url, exc)
        return []

    urls = [element.text for element in root.iter("{http://www.sitemaps.org/schemas/sitemap/0.9}loc") if element.text]
    return urls


def _fetch_urls_from_feed(publication_url: str) -> list[str]:
    """Fetch recent post URLs from feed.xml RSS fallback."""
    if not publication_url.endswith("/"):
        publication_url += "/"
    logger.info("Falling back to feed.xml. This will only contain up to the 22 most recent posts.")
    feed_url = f"{publication_url}feed.xml"
    try:
        response = requests.get(feed_url, timeout=DEFAULT_REQUEST_TIMEOUT)
    except requests.RequestException as exc:
        logger.warning("Error fetching feed at %s: %s", feed_url, exc)
        return []

    if not response.ok:
        logger.warning("Error fetching feed at %s: %s", feed_url, response.status_code)
        return []

    try:
        root = ET.fromstring(response.content)
    except ET.ParseError as exc:
        logger.warning("XML parsing error in feed at %s: %s", feed_url, exc)
        return []

    urls: list[str] = []
    for item in root.findall(".//item"):
        link = item.find("link")
        if link is not None and link.text:
            urls.append(link.text)

    return urls


def _filter_urls(
    urls: list[str],
    excluded_keywords: tuple[str, ...] | list[str] = EXCLUDED_URL_KEYWORDS,
) -> list[str]:
    """Exclude non-post URLs containing specific reserved keywords."""
    return [url for url in urls if all(keyword not in url for keyword in excluded_keywords)]


def discover_post_urls(
    publication_url: str,
    excluded_keywords: tuple[str, ...] = EXCLUDED_URL_KEYWORDS,
) -> list[str]:
    """Discover all published post URLs for a Substack publication.

    Attempts discovery via sitemap.xml first, falling back to feed.xml if
    sitemap is unavailable or returns no URLs, and filters out excluded keywords.

    Args:
        publication_url: Target publication root URL.
        excluded_keywords: Keywords to filter out from discovered URLs.

    Returns:
        list[str]: Filtered post URL list.
    """
    urls = _fetch_urls_from_sitemap(publication_url)
    if not urls:
        urls = _fetch_urls_from_feed(publication_url)
    return _filter_urls(urls, excluded_keywords)
