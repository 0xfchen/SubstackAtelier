"""Tests for sitemap and RSS feed URL discovery."""

from scraper.discovery import discover_post_urls
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
    """Verify discover_post_urls falls back to RSS feed XML when sitemap request fails."""
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
