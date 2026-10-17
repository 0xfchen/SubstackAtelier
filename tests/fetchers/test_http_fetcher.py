"""Tests for RequestsFetcher HTTP fetching, paywall detection, and retry backoff."""

from unittest.mock import Mock

import pytest

from scraper.fetchers import RequestsFetcher
from tests.conftest import FakeHttpResponse


def test_requests_fetcher_fetch_soup_success_and_paywall_skip(monkeypatch):
    """Verify RequestsFetcher returns parsed soup for public posts and None on paywalled posts."""
    monkeypatch.setattr(
        "scraper.fetchers.http.requests.get",
        lambda url, headers=None, timeout=30: FakeHttpResponse(b"<html><body><p>Public post</p></body></html>"),
    )
    fetcher = RequestsFetcher()
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


def test_requests_fetcher_fetch_soup_retries_on_rate_limit(monkeypatch):
    """Verify RequestsFetcher backs off on 429 rate limits and succeeds on retry."""
    responses = iter(
        [
            FakeHttpResponse(b"<html><body><pre>Too Many Requests</pre></body></html>"),
            FakeHttpResponse(b"<html><body><div class='available-content'>Recovered</div></body></html>"),
        ]
    )
    monkeypatch.setattr("scraper.fetchers.http.requests.get", lambda url, headers=None, timeout=30: next(responses))
    slept_durations: list[float] = []
    monkeypatch.setattr("scraper.fetchers.rate_limit.sleep", lambda duration: slept_durations.append(duration))

    fetcher = RequestsFetcher()
    soup = fetcher.fetch_soup("https://example.substack.com/p/rate-limited", max_attempts=3)
    assert soup is not None
    assert "Recovered" in soup.text
    assert len(slept_durations) == 1


def test_requests_fetcher_fetch_soup_raises_value_error_on_request_exception(monkeypatch):
    """Verify RequestsFetcher wraps requests.RequestException into ValueError."""
    import requests as req

    monkeypatch.setattr(
        "scraper.fetchers.http.requests.get",
        Mock(side_effect=req.ConnectionError("Connection refused")),
    )
    fetcher = RequestsFetcher()
    with pytest.raises(ValueError, match="Error fetching page"):
        fetcher.fetch_soup("https://example.substack.com/p/fail")
