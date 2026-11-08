"""Tests for HTTP 429 rate limit detection, Retry-After parsing, and request throttling."""

from datetime import UTC, datetime, timedelta
from email.utils import format_datetime

import pytest
from bs4 import BeautifulSoup

from scraper.fetchers import rate_limit
from scraper.fetchers.rate_limit import RateLimitError, RequestThrottle


def test_is_rate_limited_detection():
    """Verify is_rate_limited detects status 429 and plain-text/pre body without false positives on articles."""
    plain_text_rate_limit = "Too Many Requests"
    plain_text_with_code = "429 Too Many Requests"
    pre_wrapped_rate_limit = "<html><body><pre>  Too Many Requests \n</pre></body></html>"
    article_with_429_code_block = (
        "<html><body><h1>System Design: Rate Limiters</h1>"
        "<pre>HTTP/1.1 429 Too Many Requests</pre><p>Body text</p></body></html>"
    )
    normal_html = "<html><body><div>content only</div></body></html>"

    # Authoritative HTTP 429 status regardless of body
    assert rate_limit.is_rate_limited(BeautifulSoup(normal_html, "html.parser"), status_code=429) is True
    assert rate_limit.is_rate_limited(None, status_code=429) is True

    # Whole-document text fallback without status code
    assert rate_limit.is_rate_limited(BeautifulSoup(plain_text_rate_limit, "html.parser")) is True
    assert rate_limit.is_rate_limited(BeautifulSoup(plain_text_with_code, "html.parser")) is True
    assert rate_limit.is_rate_limited(BeautifulSoup(pre_wrapped_rate_limit, "html.parser")) is True

    # Real article containing a <pre> code block with 429 Too Many Requests is not detected
    assert rate_limit.is_rate_limited(BeautifulSoup(article_with_429_code_block, "html.parser")) is False
    assert rate_limit.is_rate_limited(BeautifulSoup(normal_html, "html.parser")) is False
    assert rate_limit.is_rate_limited(None) is False


def test_parse_retry_after():
    """Verify parse_retry_after handles delta-seconds, HTTP-dates, past dates, and invalid values."""
    assert rate_limit.parse_retry_after("15") == 15.0
    assert rate_limit.parse_retry_after(" 2.5 ") == 2.5
    assert rate_limit.parse_retry_after("-10") == 0.0

    future_dt = datetime.now(UTC) + timedelta(seconds=60)
    future_http_date = format_datetime(future_dt, usegmt=True)
    parsed_future = rate_limit.parse_retry_after(future_http_date)
    assert parsed_future is not None
    assert 50.0 <= parsed_future <= 65.0

    past_dt = datetime.now(UTC) - timedelta(seconds=60)
    past_http_date = format_datetime(past_dt, usegmt=True)
    assert rate_limit.parse_retry_after(past_http_date) == 0.0

    assert rate_limit.parse_retry_after(None) is None
    assert rate_limit.parse_retry_after("") is None
    assert rate_limit.parse_retry_after("invalid-header-value") is None
    assert rate_limit.parse_retry_after("nan") is None
    assert rate_limit.parse_retry_after("inf") is None


def test_compute_backoff_delay_range():
    """Verify compute_backoff_delay produces values within jittered bounds."""
    for attempt in range(1, 5):
        base_delay = 2.0**attempt
        delay = rate_limit.compute_backoff_delay(attempt, jitter_ratio=0.2)
        assert 0.8 * base_delay <= delay <= 1.2 * base_delay


def test_handle_rate_limit_retry_after_and_caps(monkeypatch):
    """Verify handle_rate_limit honors Retry-After, falls back to backoff, and raises RateLimitError on caps."""
    rate_limited_soup = BeautifulSoup("<pre>Too Many Requests</pre>", "html.parser")
    normal_soup = BeautifulSoup("<div>Clean content</div>", "html.parser")

    slept_durations: list[float] = []
    monkeypatch.setattr("scraper.fetchers.rate_limit.sleep", lambda duration: slept_durations.append(duration))

    # Not rate limited returns False immediately without sleeping
    assert rate_limit.handle_rate_limit(normal_soup, attempt=1, max_attempts=3, url="https://example.com") is False
    assert len(slept_durations) == 0

    # Valid Retry-After sleeps for exact Retry-After value
    assert (
        rate_limit.handle_rate_limit(
            None,
            attempt=1,
            max_attempts=3,
            url="https://example.com",
            status_code=429,
            retry_after="7",
        )
        is True
    )
    assert slept_durations == [7.0]

    # Missing/invalid Retry-After falls back to jittered exponential backoff
    assert (
        rate_limit.handle_rate_limit(
            rate_limited_soup,
            attempt=1,
            max_attempts=3,
            url="https://example.com",
            retry_after="not-a-number",
        )
        is True
    )
    assert len(slept_durations) == 2
    assert 1.6 <= slept_durations[1] <= 2.4

    # Retry-After exceeding MAX_RETRY_AFTER_SECONDS raises RateLimitError immediately
    with pytest.raises(RateLimitError) as cap_exc_info:
        rate_limit.handle_rate_limit(
            None,
            attempt=1,
            max_attempts=3,
            url="https://example.com/post",
            status_code=429,
            retry_after="300",
        )
    assert cap_exc_info.value.url == "https://example.com/post"
    assert cap_exc_info.value.retry_after_seconds == 300.0
    assert len(slept_durations) == 2

    # Rate limited on attempt == max_attempts raises RateLimitError
    with pytest.raises(RateLimitError, match="Max attempts reached") as max_exc_info:
        rate_limit.handle_rate_limit(
            rate_limited_soup,
            attempt=3,
            max_attempts=3,
            url="https://example.com/post",
        )
    assert max_exc_info.value.url == "https://example.com/post"


def test_request_throttle_pacing_and_adaptive_recovery(monkeypatch):
    """Verify RequestThrottle sleeps only remaining interval, skips when 0, and doubles (capped) after 429."""
    slept_durations: list[float] = []
    current_clock = 100.0

    def fake_monotonic() -> float:
        return current_clock

    def fake_sleep(duration: float) -> None:
        nonlocal current_clock
        slept_durations.append(duration)
        current_clock += duration

    monkeypatch.setattr("scraper.fetchers.rate_limit.monotonic", fake_monotonic)
    monkeypatch.setattr("scraper.fetchers.rate_limit.sleep", fake_sleep)

    # Interval 0 disables waiting
    zero_throttle = RequestThrottle(interval_seconds=0.0)
    zero_throttle.wait()
    zero_throttle.wait()
    assert slept_durations == []

    # First call does not wait; second call after 0.6s waits remaining 1.4s (for 2.0s interval)
    throttle = RequestThrottle(interval_seconds=2.0, max_interval_seconds=5.0)
    throttle.wait()
    assert slept_durations == []

    current_clock += 0.6
    throttle.wait()
    assert len(slept_durations) == 1
    assert pytest.approx(slept_durations[0]) == 1.4

    # Recovery doubles interval (2.0 -> 4.0 -> capped at 5.0)
    throttle.record_rate_limit_recovery()
    assert throttle.interval_seconds == 4.0
    throttle.record_rate_limit_recovery()
    assert throttle.interval_seconds == 5.0
