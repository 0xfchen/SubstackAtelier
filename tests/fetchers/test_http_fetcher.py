"""Tests for RequestsFetcher HTTP fetching, paywall detection, status handling, and retry backoff."""

from unittest.mock import Mock

import pytest
import requests

from scraper.fetchers import RequestsFetcher
from scraper.fetchers.rate_limit import RateLimitError
from tests.conftest import FakeHttpResponse


def test_requests_fetcher_fetch_soup_success_and_paywall_skip(monkeypatch):
    """Verify RequestsFetcher returns parsed soup for public posts and None on paywalled posts."""
    monkeypatch.setattr(
        "scraper.fetchers.http.requests.get",
        lambda url, headers=None, timeout=30: FakeHttpResponse(b"<html><body><p>Public post</p></body></html>"),
    )
    fetcher = RequestsFetcher(request_interval_seconds=0)
    public_soup = fetcher.fetch_soup("https://example.substack.com/p/public")
    assert public_soup is not None
    assert "Public post" in public_soup.text

    monkeypatch.setattr(
        "scraper.fetchers.http.requests.get",
        lambda url, headers=None, timeout=30: FakeHttpResponse(
            b'<html><body><h2 class="paywall-title">Subscribe to read</h2></body></html>'
        ),
    )
    paywall_soup = fetcher.fetch_soup("https://example.substack.com/p/paid")
    assert paywall_soup is None


def test_requests_fetcher_plain_text_429_retries_and_doubles_throttle(monkeypatch):
    """Verify 429 with plain-text body backs off, returns article soup on retry, and doubles throttle interval."""
    responses = iter(
        [
            FakeHttpResponse(b"Too Many Requests", status_code=429, ok=False),
            FakeHttpResponse(
                b"<html><body><div class='available-content'>Recovered</div></body></html>", status_code=200
            ),
        ]
    )
    monkeypatch.setattr("scraper.fetchers.http.requests.get", lambda url, headers=None, timeout=30: next(responses))
    slept_durations: list[float] = []
    current_clock = 100.0

    def fake_sleep(duration: float) -> None:
        nonlocal current_clock
        slept_durations.append(duration)
        current_clock += duration

    monkeypatch.setattr("scraper.fetchers.rate_limit.monotonic", lambda: current_clock)
    monkeypatch.setattr("scraper.fetchers.rate_limit.sleep", fake_sleep)

    fetcher = RequestsFetcher(request_interval_seconds=1.0)
    soup = fetcher.fetch_soup("https://example.substack.com/p/rate-limited", max_attempts=3)

    assert soup is not None
    assert "Recovered" in soup.text
    assert len(slept_durations) == 1
    assert fetcher.throttle.interval_seconds == 2.0


def test_requests_fetcher_persistent_429_raises_rate_limit_error(monkeypatch):
    """Verify persistent 429 raises RateLimitError."""
    monkeypatch.setattr(
        "scraper.fetchers.http.requests.get",
        lambda url, headers=None, timeout=30: FakeHttpResponse(b"Too Many Requests", status_code=429, ok=False),
    )
    monkeypatch.setattr("scraper.fetchers.rate_limit.sleep", lambda duration: None)

    fetcher = RequestsFetcher(request_interval_seconds=0)
    with pytest.raises(RateLimitError):
        fetcher.fetch_soup("https://example.substack.com/p/rate-limited", max_attempts=3)


def test_requests_fetcher_retries_5xx_and_raises_value_error_when_persistent(monkeypatch):
    """Verify 503 then 200 succeeds after backoff, while persistent 5xx raises ValueError."""
    slept_durations: list[float] = []
    monkeypatch.setattr("scraper.fetchers.http.sleep", lambda duration: slept_durations.append(duration))

    transient_responses = iter(
        [
            FakeHttpResponse(b"Service Unavailable", status_code=503, ok=False),
            FakeHttpResponse(b"<html><body><p>Recovered from 503</p></body></html>", status_code=200, ok=True),
        ]
    )
    monkeypatch.setattr(
        "scraper.fetchers.http.requests.get",
        lambda url, headers=None, timeout=30: next(transient_responses),
    )

    fetcher = RequestsFetcher(request_interval_seconds=0)
    soup = fetcher.fetch_soup("https://example.substack.com/p/transient-503", max_attempts=3)
    assert soup is not None
    assert "Recovered from 503" in soup.text
    assert len(slept_durations) == 1

    monkeypatch.setattr(
        "scraper.fetchers.http.requests.get",
        lambda url, headers=None, timeout=30: FakeHttpResponse(b"Bad Gateway", status_code=502, ok=False),
    )
    with pytest.raises(ValueError, match="HTTP 502"):
        fetcher.fetch_soup("https://example.substack.com/p/persistent-502", max_attempts=2)


def test_requests_fetcher_404_raises_value_error_without_retry(monkeypatch):
    """Verify 404 raises ValueError immediately without retrying."""
    call_count = 0

    def fake_get(url, headers=None, timeout=30):
        nonlocal call_count
        call_count += 1
        return FakeHttpResponse(b"Not Found", status_code=404, ok=False)

    monkeypatch.setattr("scraper.fetchers.http.requests.get", fake_get)

    fetcher = RequestsFetcher(request_interval_seconds=0)
    with pytest.raises(ValueError, match="HTTP 404"):
        fetcher.fetch_soup("https://example.substack.com/p/missing", max_attempts=3)

    assert call_count == 1


def test_requests_fetcher_consults_throttle_before_each_request(monkeypatch):
    """Verify RequestsFetcher waits on its RequestThrottle before each request."""
    monkeypatch.setattr(
        "scraper.fetchers.http.requests.get",
        lambda url, headers=None, timeout=30: FakeHttpResponse(b"<html><body><p>OK</p></body></html>"),
    )
    fetcher = RequestsFetcher(request_interval_seconds=1.5)
    fetcher.throttle.wait = Mock()

    fetcher.fetch_soup("https://example.substack.com/p/post-1")
    fetcher.fetch_soup("https://example.substack.com/p/post-2")

    assert fetcher.throttle.wait.call_count == 2


def test_requests_fetcher_fetch_soup_raises_value_error_on_request_exception(monkeypatch):
    """Verify RequestsFetcher retries ConnectionError and wraps into ValueError."""
    monkeypatch.setattr("scraper.fetchers.http.sleep", lambda duration: None)
    monkeypatch.setattr(
        "scraper.fetchers.http.requests.get",
        Mock(side_effect=requests.ConnectionError("Connection refused")),
    )
    fetcher = RequestsFetcher(request_interval_seconds=0)
    with pytest.raises(ValueError, match="Error fetching page"):
        fetcher.fetch_soup("https://example.substack.com/p/fail", max_attempts=2)
