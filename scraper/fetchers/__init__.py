"""SubstackAtelier fetchers package.

Provides page fetcher implementations conforming to the PageFetcher protocol.
"""

from scraper.fetchers.base import PageFetcher
from scraper.fetchers.http import RequestsFetcher
from scraper.fetchers.playwright import PlaywrightFetcher

__all__ = [
    "PageFetcher",
    "RequestsFetcher",
    "PlaywrightFetcher",
]
