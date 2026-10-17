from __future__ import annotations

import logging
import random
from time import sleep

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def is_rate_limited(soup: BeautifulSoup | None) -> bool:
    """Detect whether a parsed HTML page represents an HTTP 429 rate limit response.

    Args:
        soup: Parsed HTML DOM to inspect.

    Returns:
        bool: True if rate limiting indicators are present, False otherwise.
    """
    if soup is None:
        return False
    rate_limit_tag = soup.select_one("body > pre") or soup.find("pre")
    return rate_limit_tag is not None and "too many requests" in rate_limit_tag.text.lower()


def compute_backoff_delay(attempt: int, jitter_ratio: float = 0.2) -> float:
    """Compute jittered exponential backoff delay in seconds.

    Delay formula: base = 2**attempt; delay = base + uniform(-jitter, +jitter).

    Args:
        attempt: Zero-indexed or one-indexed attempt counter (positive integer).
        jitter_ratio: Fractional amplitude of uniform random jitter relative to base.

    Returns:
        float: Backoff duration in seconds.
    """
    base_delay = 2**attempt
    jitter = random.uniform(-jitter_ratio * base_delay, jitter_ratio * base_delay)
    return base_delay + jitter


def handle_rate_limit(
    soup: BeautifulSoup | None,
    attempt: int,
    max_attempts: int,
    url: str,
) -> bool:
    """Handle rate limit backoff delay or raise an exception if max attempts reached.

    Args:
        soup: Parsed HTML DOM to inspect.
        attempt: Current attempt number (1-based).
        max_attempts: Maximum retry attempts permitted.
        url: Request URL being retried.

    Returns:
        bool: True if rate limited and slept, False if not rate limited.

    Raises:
        RuntimeError: When rate limit persists after max_attempts.
    """
    if not is_rate_limited(soup):
        return False

    if attempt >= max_attempts:
        raise RuntimeError(f"Max attempts reached for {url}. Still receiving 429 Too Many Requests.")

    delay = compute_backoff_delay(attempt)
    logger.warning(
        "[%s/%s] Too many requests. Retrying in %.2f seconds...",
        attempt,
        max_attempts,
        delay,
    )
    sleep(delay)
    return True
