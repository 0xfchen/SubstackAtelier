"""Tests for HTTP 429 rate limit detection and jittered exponential backoff."""

import pytest
from bs4 import BeautifulSoup

from scraper.fetchers import rate_limit


def test_is_rate_limited_detection():
    """Verify is_rate_limited correctly identifies 429 pre tags."""
    rate_limited_html = "<html><body><pre>error: too many requests, please slow down</pre></body></html>"
    normal_html = "<html><body><pre>code block</pre><div>content</div></body></html>"
    empty_html = "<html><body><div>content only</div></body></html>"

    assert rate_limit.is_rate_limited(BeautifulSoup(rate_limited_html, "html.parser")) is True
    assert rate_limit.is_rate_limited(BeautifulSoup(normal_html, "html.parser")) is False
    assert rate_limit.is_rate_limited(BeautifulSoup(empty_html, "html.parser")) is False


def test_compute_backoff_delay_range():
    """Verify compute_backoff_delay produces values within jittered bounds."""
    for attempt in range(1, 5):
        base_delay = 2.0**attempt
        delay = rate_limit.compute_backoff_delay(attempt, jitter_ratio=0.2)
        assert 0.8 * base_delay <= delay <= 1.2 * base_delay


def test_handle_rate_limit_backs_off_and_raises_at_max(monkeypatch):
    """Verify handle_rate_limit sleeps on transient rate-limit and raises on max attempts."""
    rate_limited_soup = BeautifulSoup("<pre>Too Many Requests</pre>", "html.parser")
    normal_soup = BeautifulSoup("<div>Clean content</div>", "html.parser")

    # Not rate limited returns False immediately without sleeping
    slept_durations: list[float] = []
    monkeypatch.setattr("scraper.fetchers.rate_limit.sleep", lambda duration: slept_durations.append(duration))

    assert rate_limit.handle_rate_limit(normal_soup, attempt=1, max_attempts=3, url="https://example.com") is False
    assert len(slept_durations) == 0

    # Rate limited on attempt 1 sleeps and returns True
    assert rate_limit.handle_rate_limit(rate_limited_soup, attempt=1, max_attempts=3, url="https://example.com") is True
    assert len(slept_durations) == 1
    assert slept_durations[0] > 0

    # Rate limited on attempt == max_attempts raises RuntimeError
    with pytest.raises(RuntimeError, match="Max attempts reached"):
        rate_limit.handle_rate_limit(rate_limited_soup, attempt=3, max_attempts=3, url="https://example.com")
