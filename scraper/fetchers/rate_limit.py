from __future__ import annotations

import logging
import math
import random
from collections.abc import Mapping
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from time import monotonic, sleep

from bs4 import BeautifulSoup

from scraper.config import (
    DEFAULT_REQUEST_INTERVAL_SECONDS,
    MAX_REQUEST_INTERVAL_SECONDS,
    MAX_RETRY_AFTER_SECONDS,
)

logger = logging.getLogger(__name__)


class RateLimitError(RuntimeError):
    """Raised when HTTP 429 rate limiting persists across retries or exceeds the Retry-After cap."""

    def __init__(
        self,
        url: str,
        message: str | None = None,
        retry_after_seconds: float | None = None,
    ) -> None:
        """Initialize rate limit exception with request URL and optional Retry-After duration."""
        self.url: str = url
        self.retry_after_seconds: float | None = retry_after_seconds
        default_message = f"Max attempts reached for {url}. Still receiving 429 Too Many Requests."
        super().__init__(message or default_message)


class RequestThrottle:
    """Enforce a minimum interval between outbound network requests with adaptive backoff."""

    def __init__(
        self,
        interval_seconds: float = DEFAULT_REQUEST_INTERVAL_SECONDS,
        max_interval_seconds: float = MAX_REQUEST_INTERVAL_SECONDS,
    ) -> None:
        """Initialize request throttle with base and maximum intervals in seconds."""
        self.interval_seconds: float = max(0.0, float(interval_seconds))
        self.max_interval_seconds: float = float(max_interval_seconds)
        self._last_request_time: float | None = None

    def wait(self) -> None:
        """Sleep for the remaining interval since the last network request, if any."""
        if self.interval_seconds <= 0:
            return

        current_time = monotonic()
        if self._last_request_time is not None:
            elapsed = current_time - self._last_request_time
            remaining = self.interval_seconds - elapsed
            if remaining > 0:
                sleep(remaining)
                current_time = monotonic()

        self._last_request_time = current_time

    def record_rate_limit_recovery(self) -> None:
        """Double the request interval after recovering from an HTTP 429, capped at max_interval_seconds."""
        if self.interval_seconds > 0:
            self.interval_seconds = min(self.max_interval_seconds, self.interval_seconds * 2.0)


def get_retry_after_header(headers: Mapping[str, str] | None) -> str | None:
    """Extract the Retry-After header value case-insensitively from response headers."""
    if not headers:
        return None
    for key, value in headers.items():
        if key.lower() == "retry-after":
            return value
    return None


def parse_retry_after(value: str | None) -> float | None:
    """Parse an HTTP Retry-After header value into a non-negative delay in seconds.

    Accepts either delta-seconds or an HTTP-date string.

    Args:
        value: Raw Retry-After header string, or None.

    Returns:
        float | None: Delay in seconds (clamped to >= 0.0), or None if missing or invalid.
    """
    if value is None:
        return None
    stripped_value = value.strip()
    if not stripped_value:
        return None

    try:
        numeric_seconds = float(stripped_value)
        if math.isnan(numeric_seconds) or math.isinf(numeric_seconds):
            return None
        return max(0.0, numeric_seconds)
    except ValueError:
        pass

    try:
        parsed_datetime = parsedate_to_datetime(stripped_value)
    except (TypeError, ValueError, IndexError):
        return None

    if parsed_datetime is None:
        return None
    if parsed_datetime.tzinfo is None:
        parsed_datetime = parsed_datetime.replace(tzinfo=UTC)

    remaining_seconds = (parsed_datetime - datetime.now(UTC)).total_seconds()
    return max(0.0, remaining_seconds)


def is_rate_limited(soup: BeautifulSoup | None, status_code: int | None = None) -> bool:
    """Detect whether an HTTP response or parsed HTML DOM represents an HTTP 429 rate limit.

    Args:
        soup: Parsed HTML DOM to inspect.
        status_code: Optional HTTP response status code.

    Returns:
        bool: True if rate limiting indicators are present, False otherwise.
    """
    if status_code == 429:
        return True
    if soup is None:
        return False
    normalized_text = " ".join(soup.get_text().split()).casefold()
    return normalized_text in {"too many requests", "429 too many requests"}


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
    status_code: int | None = None,
    retry_after: str | None = None,
) -> bool:
    """Handle rate limit backoff delay or raise RateLimitError if max attempts or Retry-After cap reached.

    Args:
        soup: Parsed HTML DOM to inspect.
        attempt: Current attempt number (1-based).
        max_attempts: Maximum retry attempts permitted.
        url: Request URL being retried.
        status_code: Optional HTTP response status code.
        retry_after: Optional raw Retry-After header value.

    Returns:
        bool: True if rate limited and slept, False if not rate limited.

    Raises:
        RateLimitError: When rate limit persists after max_attempts or Retry-After exceeds cap.
    """
    if not is_rate_limited(soup, status_code=status_code):
        return False

    retry_after_seconds = parse_retry_after(retry_after)
    if retry_after_seconds is not None and retry_after_seconds > MAX_RETRY_AFTER_SECONDS:
        raise RateLimitError(
            url=url,
            message=(
                f"Rate limited on {url} with Retry-After={retry_after_seconds:.0f}s "
                f"(exceeds max wait of {MAX_RETRY_AFTER_SECONDS}s)."
            ),
            retry_after_seconds=retry_after_seconds,
        )

    if attempt >= max_attempts:
        raise RateLimitError(
            url=url,
            message=f"Max attempts reached for {url}. Still receiving 429 Too Many Requests.",
            retry_after_seconds=retry_after_seconds,
        )

    delay = retry_after_seconds if retry_after_seconds is not None else compute_backoff_delay(attempt)
    logger.warning(
        "[%s/%s] Too many requests. Retrying in %.2f seconds...",
        attempt,
        max_attempts,
        delay,
    )
    sleep(delay)
    return True
