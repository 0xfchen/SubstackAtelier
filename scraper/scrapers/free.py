import logging

import requests
from bs4 import BeautifulSoup

from ..config import BASE_CONTENT_DIR, DEFAULT_REQUEST_TIMEOUT
from .base import BaseSubstackScraper

logger = logging.getLogger(__name__)


class SubstackScraper(BaseSubstackScraper):
    """Scraper implementation for free and public Substack posts via HTTP requests."""

    def __init__(
        self,
        base_substack_url: str,
        content_save_dir: str = BASE_CONTENT_DIR,
        download_images: bool = False,
        overwrite: bool = False,
        clean_content: bool = True,
    ) -> None:
        """Initialize free Substack scraper.

        Args:
            base_substack_url: Target Substack publication or post URL.
            content_save_dir: Root directory for author-centric content (defaults to 'content').
            download_images: Whether to download images locally.
            overwrite: Whether to overwrite existing files on disk when scraping.
            clean_content: Whether to strip promotional widgets and subscription CTAs.
        """
        super().__init__(
            base_substack_url=base_substack_url,
            content_save_dir=content_save_dir,
            download_images=download_images,
            overwrite=overwrite,
            clean_content=clean_content,
        )

    def get_url_soup(self, url: str, max_attempts: int = 5) -> BeautifulSoup | None:
        """Fetch and parse HTML for a URL using requests with exponential backoff retry.

        Args:
            url: Post URL to fetch.
            max_attempts: Number of retry attempts on rate limiting (HTTP 429).

        Returns:
            BeautifulSoup | None: Parsed DOM, or None if skipped (e.g. premium paywall).

        Raises:
            RuntimeError: If maximum retry attempts are exhausted or network fails.
            ValueError: If fetching page encounters a generic error.
        """
        for attempt in range(1, max_attempts + 1):
            try:
                page = requests.get(url, headers=None, timeout=DEFAULT_REQUEST_TIMEOUT)
                soup = BeautifulSoup(page.content, "html.parser")

                if soup.find("h2", class_="paywall-title"):
                    logger.info("Skipping premium article: %s", url)
                    return None

                if self._handle_rate_limit(soup, attempt, max_attempts, url):
                    continue

                return soup
            except RuntimeError:
                raise
            except requests.RequestException as e:
                raise ValueError(f"Error fetching page: {e}") from e

        raise RuntimeError(f"Failed to fetch page after {max_attempts} attempts: {url}")
