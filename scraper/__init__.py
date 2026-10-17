"""Substack2Markdown package.

Provides tools to scrape and archive Substack newsletters into structured Markdown format.
"""

# Re-export requests so monkeypatches like `monkeypatch.setattr(ss.requests, ...)` work
import requests  # noqa: F401

# Import browser manager
from scraper.browser import BrowserManager

# Import catalog & JSON embed
from scraper.catalog import safe_json_embed

# Import CLI
from scraper.cli import (
    logger,
    main,
    parse_args,
)

# Import config constants & credentials
from scraper.config import (
    BASE_CONTENT_DIR,
    BASE_SUBSTACK_URL,
    DEFAULT_API_POST_LIMIT,
    DEFAULT_REQUEST_TIMEOUT,
    MAX_API_SYNC_PAGES,
    MAX_IMAGE_WORKERS,
    NUM_POSTS_TO_SCRAPE,
    USE_PREMIUM,
    get_credentials,
)

# Import HTML-to-Markdown converter
from scraper.converter import convert_html_to_markdown

# Import page fetchers
from scraper.fetchers import (
    PageFetcher,
    PlaywrightFetcher,
    RequestsFetcher,
)

# Import image processing helpers
from scraper.images import (
    clean_linked_images,
    count_images_in_markdown,
    download_image,
    process_markdown_images,
    resolve_image_url,
    sanitize_image_filename,
)

# Import scraper classes
from scraper.substack import SubstackScraper

# Import URL helpers
from scraper.url_utils import (
    extract_main_part,
    get_post_slug,
    get_publication_url,
    is_post_url,
)

__all__ = [
    # Config
    "BASE_CONTENT_DIR",
    "BASE_SUBSTACK_URL",
    "DEFAULT_API_POST_LIMIT",
    "DEFAULT_REQUEST_TIMEOUT",
    "MAX_API_SYNC_PAGES",
    "MAX_IMAGE_WORKERS",
    "NUM_POSTS_TO_SCRAPE",
    "USE_PREMIUM",
    "get_credentials",
    # URLs
    "extract_main_part",
    "get_post_slug",
    "get_publication_url",
    "is_post_url",
    # Catalog
    "safe_json_embed",
    # Converter
    "convert_html_to_markdown",
    # Images
    "clean_linked_images",
    "count_images_in_markdown",
    "download_image",
    "process_markdown_images",
    "resolve_image_url",
    "sanitize_image_filename",
    # Browser
    "BrowserManager",
    # Fetchers
    "PageFetcher",
    "RequestsFetcher",
    "PlaywrightFetcher",
    # Scrapers
    "SubstackScraper",
    # CLI
    "logger",
    "main",
    "parse_args",
]
