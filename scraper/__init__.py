"""SubstackAtelier package.

Provides tools to scrape and archive Substack newsletters into structured Markdown format.
"""

from scraper.browser import BrowserManager
from scraper.cli import main, parse_args
from scraper.config import BASE_CONTENT_DIR, get_credentials
from scraper.converter import convert_html_to_markdown
from scraper.fetchers import (
    PageFetcher,
    PlaywrightFetcher,
    RequestsFetcher,
)
from scraper.substack import SubstackScraper

__all__ = [
    # Core Scraper & Fetchers
    "SubstackScraper",
    "PageFetcher",
    "RequestsFetcher",
    "PlaywrightFetcher",
    # Automation & Converter
    "BrowserManager",
    "convert_html_to_markdown",
    # Config & CLI
    "BASE_CONTENT_DIR",
    "get_credentials",
    "main",
    "parse_args",
]
