from __future__ import annotations

import logging
from time import sleep

import requests
from bs4 import BeautifulSoup

from scraper.config import (
    DEFAULT_REQUEST_INTERVAL_SECONDS,
    DEFAULT_REQUEST_TIMEOUT,
    RATE_LIMIT_MAX_ATTEMPTS,
)
from scraper.fetchers.rate_limit import (
    RequestThrottle,
    compute_backoff_delay,
    get_retry_after_header,
    handle_rate_limit,
)

logger = logging.getLogger(__name__)


class RequestsFetcher:
    """Page fetcher implementation for public Substack posts via HTTP requests."""

    def __init__(
        self,
        timeout: int = DEFAULT_REQUEST_TIMEOUT,
        request_interval_seconds: float = DEFAULT_REQUEST_INTERVAL_SECONDS,
    ) -> None:
        """Initialize requests page fetcher.

        Args:
            timeout: HTTP request timeout duration in seconds.
            request_interval_seconds: Minimum delay in seconds between network requests.
        """
        self.timeout = timeout
        self.request_interval_seconds = request_interval_seconds
        self.throttle = RequestThrottle(request_interval_seconds)

    def fetch_soup(self, url: str, max_attempts: int = RATE_LIMIT_MAX_ATTEMPTS) -> BeautifulSoup | None:
        """Fetch and parse HTML for a URL using requests with exponential backoff retry.

        Args:
            url: Post URL to fetch.
            max_attempts: Number of retry attempts on rate limiting (HTTP 429) or transient errors.

        Returns:
            BeautifulSoup | None: Parsed DOM, or None if skipped (e.g. premium paywall).

        Raises:
            RateLimitError: If HTTP 429 rate limiting persists after max_attempts.
            ValueError: If fetching page encounters a non-OK HTTP status or network error.
        """
        had_rate_limit = False
        for attempt in range(1, max_attempts + 1):
            self.throttle.wait()
            try:
                page = requests.get(url, headers=None, timeout=self.timeout)
            except (requests.ConnectionError, requests.Timeout) as transient_error:
                if attempt >= max_attempts:
                    raise ValueError(f"Error fetching page: {transient_error}") from transient_error
                delay = compute_backoff_delay(attempt)
                logger.warning(
                    "[%s/%s] Transient error fetching %s: %s. Retrying in %.2f seconds...",
                    attempt,
                    max_attempts,
                    url,
                    transient_error,
                    delay,
                )
                sleep(delay)
                continue
            except requests.RequestException as exc:
                raise ValueError(f"Error fetching page: {exc}") from exc

            soup = BeautifulSoup(page.content, "html.parser")
            retry_after = get_retry_after_header(getattr(page, "headers", None))

            if handle_rate_limit(
                soup,
                attempt,
                max_attempts,
                url,
                status_code=page.status_code,
                retry_after=retry_after,
            ):
                had_rate_limit = True
                continue

            if 500 <= page.status_code < 600:
                if attempt >= max_attempts:
                    raise ValueError(f"HTTP {page.status_code} for {url}")
                delay = compute_backoff_delay(attempt)
                logger.warning(
                    "[%s/%s] HTTP %s for %s. Retrying in %.2f seconds...",
                    attempt,
                    max_attempts,
                    page.status_code,
                    url,
                    delay,
                )
                sleep(delay)
                continue

            if not (200 <= page.status_code < 300):
                raise ValueError(f"HTTP {page.status_code} for {url}")

            if had_rate_limit:
                self.throttle.record_rate_limit_recovery()

            if soup.find("h2", class_="paywall-title"):
                logger.info("Skipping premium article: %s", url)
                return None

            return soup

        raise RuntimeError(f"Failed to fetch page after {max_attempts} attempts: {url}")

    def close(self) -> None:
        """Close fetcher resources (no-op for stateless requests)."""
        pass
