from __future__ import annotations

import logging

import requests
from bs4 import BeautifulSoup

from scraper.config import DEFAULT_REQUEST_TIMEOUT
from scraper.fetchers.rate_limit import handle_rate_limit

logger = logging.getLogger(__name__)


class RequestsFetcher:
    """Page fetcher implementation for public Substack posts via HTTP requests."""

    def __init__(self, timeout: int = DEFAULT_REQUEST_TIMEOUT) -> None:
        """Initialize requests page fetcher.

        Args:
            timeout: HTTP request timeout duration in seconds.
        """
        self.timeout = timeout

    def fetch_soup(self, url: str, max_attempts: int = 5) -> BeautifulSoup | None:
        """Fetch and parse HTML for a URL using requests with exponential backoff retry.

        Args:
            url: Post URL to fetch.
            max_attempts: Number of retry attempts on rate limiting (HTTP 429).

        Returns:
            BeautifulSoup | None: Parsed DOM, or None if skipped (e.g. premium paywall).

        Raises:
            RuntimeError: If maximum retry attempts are exhausted or network fails.
            ValueError: If fetching page encounters a generic request error.
        """
        for attempt in range(1, max_attempts + 1):
            try:
                page = requests.get(url, headers=None, timeout=self.timeout)
                soup = BeautifulSoup(page.content, "html.parser")

                if soup.find("h2", class_="paywall-title"):
                    logger.info("Skipping premium article: %s", url)
                    return None

                if handle_rate_limit(soup, attempt, max_attempts, url):
                    continue

                return soup
            except RuntimeError:
                raise
            except requests.RequestException as exc:
                raise ValueError(f"Error fetching page: {exc}") from exc

        raise RuntimeError(f"Failed to fetch page after {max_attempts} attempts: {url}")

    def close(self) -> None:
        """Close fetcher resources (no-op for stateless requests)."""
        pass
