"""Tests for sitemap and RSS feed URL discovery."""

import pytest
import requests

from scraper.discovery import discover_post_urls
from scraper.fetchers.rate_limit import RateLimitError
from tests.conftest import FakeResponse


def test_discover_post_urls_uses_sitemap_and_filters_keywords(monkeypatch):
    """Verify discover_post_urls parses sitemap XML and filters out excluded keywords."""
    sitemap_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
        <url><loc>https://example.substack.com/p/first-post</loc></url>
        <url><loc>https://example.substack.com/p/second-post</loc></url>
        <url><loc>https://example.substack.com/about</loc></url>
        <url><loc>https://example.substack.com/p/about-our-team</loc></url>
        <url><loc>https://example.substack.com/archive</loc></url>
    </urlset>
    """

    monkeypatch.setattr(
        "scraper.discovery.requests.get",
        lambda url, timeout=30: FakeResponse(content=sitemap_xml),
    )
    urls = discover_post_urls("https://example.substack.com")
    assert urls == [
        "https://example.substack.com/p/first-post",
        "https://example.substack.com/p/second-post",
    ]


def test_discover_post_urls_falls_back_to_feed_when_sitemap_fails(monkeypatch):
    """Verify discover_post_urls falls back to RSS feed XML when sitemap request returns 404."""
    feed_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
        <channel>
            <item><link>https://example.substack.com/p/feed-post-1</link></item>
            <item><link>https://example.substack.com/p/podcast-episode-1</link></item>
            <item><link>https://example.substack.com/p/feed-post-2</link></item>
        </channel>
    </rss>
    """

    def fake_get(url, timeout=30):
        if "sitemap.xml" in url:
            return FakeResponse(content=b"Not Found", ok=False, status_code=404)
        return FakeResponse(content=feed_xml, ok=True, status_code=200)

    monkeypatch.setattr("scraper.discovery.requests.get", fake_get)
    urls = discover_post_urls("https://example.substack.com")
    assert urls == [
        "https://example.substack.com/p/feed-post-1",
        "https://example.substack.com/p/feed-post-2",
    ]


def test_discover_post_urls_sitemap_429_retries_and_succeeds(monkeypatch):
    """Verify sitemap 429 backs off and returns sitemap URLs on retry."""
    sitemap_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
        <url><loc>https://example.substack.com/p/recovered-post</loc></url>
    </urlset>
    """
    responses = iter(
        [
            FakeResponse(content=b"Too Many Requests", ok=False, status_code=429),
            FakeResponse(content=sitemap_xml, ok=True, status_code=200),
        ]
    )
    slept_durations: list[float] = []
    monkeypatch.setattr("scraper.discovery.requests.get", lambda url, timeout=30: next(responses))
    monkeypatch.setattr("scraper.fetchers.rate_limit.sleep", lambda duration: slept_durations.append(duration))

    urls = discover_post_urls("https://example.substack.com")

    assert urls == ["https://example.substack.com/p/recovered-post"]
    assert len(slept_durations) == 1


def test_discover_post_urls_persistent_sitemap_429_raises_without_feed_fallback(monkeypatch):
    """Verify persistent sitemap 429 raises RateLimitError and never requests feed.xml."""
    requested_urls: list[str] = []

    def fake_get(url, timeout=30):
        requested_urls.append(url)
        return FakeResponse(content=b"Too Many Requests", ok=False, status_code=429)

    monkeypatch.setattr("scraper.discovery.requests.get", fake_get)
    monkeypatch.setattr("scraper.fetchers.rate_limit.sleep", lambda duration: None)

    with pytest.raises(RateLimitError):
        discover_post_urls("https://example.substack.com")

    assert all("feed.xml" not in url for url in requested_urls)


def test_discover_post_urls_sitemap_transient_error_retries_and_succeeds(monkeypatch):
    """Verify sitemap transient connection error retries with backoff and succeeds on next attempt."""
    sitemap_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
        <url><loc>https://example.substack.com/p/transient-recovered-post</loc></url>
    </urlset>
    """
    responses = iter(
        [
            requests.ConnectionError("Connection timed out"),
            FakeResponse(content=sitemap_xml, ok=True, status_code=200),
        ]
    )

    def fake_get(url, timeout=30):
        item = next(responses)
        if isinstance(item, Exception):
            raise item
        return item

    slept_durations: list[float] = []
    monkeypatch.setattr("scraper.discovery.requests.get", fake_get)
    monkeypatch.setattr("scraper.discovery.sleep", lambda duration: slept_durations.append(duration))

    urls = discover_post_urls("https://example.substack.com")

    assert urls == ["https://example.substack.com/p/transient-recovered-post"]
    assert len(slept_durations) == 1
