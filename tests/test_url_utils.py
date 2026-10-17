"""Tests for Substack URL parsing, publication resolution, and slug extraction."""

import pytest

from scraper.url_utils import (
    extract_main_part,
    get_post_slug,
    get_publication_url,
    get_slug_from_url,
    is_post_url,
)


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://example.substack.com/p/my-post", True),
        ("https://example.substack.com/p/another-post-slug", True),
        ("https://example.substack.com/", False),
        ("https://example.substack.com/archive", False),
        ("https://example.substack.com/about", False),
    ],
)
def test_is_post_url(url, expected):
    assert is_post_url(url) == expected


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://example.substack.com/p/my-post", "https://example.substack.com/"),
        ("https://blog.example.com/p/slug", "https://blog.example.com/"),
        ("http://test.substack.com/p/post-name", "http://test.substack.com/"),
    ],
)
def test_get_publication_url(url, expected):
    assert get_publication_url(url) == expected


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://example.substack.com/p/my-post", "my-post"),
        ("https://example.substack.com/p/another-slug", "another-slug"),
        ("https://example.substack.com/p/slug-with-123", "slug-with-123"),
        ("https://example.substack.com/archive", "unknown_post"),
    ],
)
def test_get_post_slug(url, expected):
    assert get_post_slug(url) == expected


@pytest.mark.parametrize(
    "url, expected",
    [
        # ByteByteGo
        ("https://blog.bytebytego.com/", "bytebytego"),
        ("https://blog.bytebytego.com", "bytebytego"),
        ("https://blog.bytebytego.com/p/ep1-system-design", "bytebytego"),
        ("http://blog.bytebytego.com/archive", "bytebytego"),
        ("blog.bytebytego.com", "bytebytego"),
        # The Pragmatic Engineer
        ("https://newsletter.pragmaticengineer.com/", "pragmaticengineer"),
        ("https://newsletter.pragmaticengineer.com", "pragmaticengineer"),
        ("https://newsletter.pragmaticengineer.com/p/the-pulse-100", "pragmaticengineer"),
        ("http://newsletter.pragmaticengineer.com/about", "pragmaticengineer"),
        ("newsletter.pragmaticengineer.com", "pragmaticengineer"),
        # SemiAnalysis
        ("https://newsletter.semianalysis.com/", "semianalysis"),
        ("https://newsletter.semianalysis.com", "semianalysis"),
        ("https://newsletter.semianalysis.com/p/ai-datacenter-scale", "semianalysis"),
        ("http://newsletter.semianalysis.com/archive", "semianalysis"),
        ("newsletter.semianalysis.com", "semianalysis"),
    ],
)
def test_extract_main_part_supports_custom_domains(url, expected):
    assert extract_main_part(url) == expected


def test_get_slug_from_url_handles_post_and_non_post_urls():
    """Verify get_slug_from_url extracts slug from /p/ URLs and generic URLs."""
    assert get_slug_from_url("https://example.substack.com/p/my-cool-post") == "my-cool-post"
    assert get_slug_from_url("https://example.substack.com/p/my-cool-post?r=123") == "my-cool-post"
    assert get_slug_from_url("https://example.substack.com/custom-page/") == "custom-page"
    assert get_slug_from_url("https://example.substack.com/custom-page") == "custom-page"
