from __future__ import annotations

from typing import Protocol, runtime_checkable

from bs4 import BeautifulSoup


@runtime_checkable
class PageFetcher(Protocol):
    """Protocol for fetching parsed HTML documents across transport layers."""

    def fetch_soup(self, url: str, max_attempts: int = 5) -> BeautifulSoup | None:
        """Fetch and parse HTML for a given URL into a BeautifulSoup DOM.

        Args:
            url: Post or page URL to fetch.
            max_attempts: Maximum retry attempts on rate limiting or transient errors.

        Returns:
            BeautifulSoup | None: Parsed DOM if successful, or None if skipped (e.g. paywall).
        """
        ...

    def close(self) -> None:
        """Release underlying resources, browser contexts, or network sessions."""
        ...
