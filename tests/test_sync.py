"""Tests for incremental sync cursor state and Substack API delta pagination."""

import json
from datetime import UTC, datetime

from scraper.sync import (
    _is_cutoff_reached,
    fetch_posts_from_api,
    load_sync_state,
    save_sync_state,
)
from tests.conftest import FakeResponse, FakeScraper


def test_sync_state_load_and_save(tmp_path):
    """Verify sync state persistence and loading."""
    scraper = FakeScraper("https://example.substack.com", content_save_dir=str(tmp_path))
    assert load_sync_state(scraper.author_dir, scraper.metadata_file_path) is None

    test_state = {
        "last_sync_at": "2026-09-27T10:00:00Z",
        "last_post_date": "2026-09-26T18:30:00.000Z",
        "last_post_id": 12345,
        "last_post_slug": "test-slug",
        "total_synced_posts": 10,
    }
    save_sync_state(scraper.author_dir, test_state)

    loaded = load_sync_state(scraper.author_dir, scraper.metadata_file_path)
    assert loaded == test_state


def test_sync_state_bootstraps_from_metadata_json(tmp_path):
    """Verify cursor bootstrapping from existing metadata.json if sync_state.json is missing."""
    author_dir = tmp_path / "example"
    author_dir.mkdir(parents=True, exist_ok=True)
    metadata_file = author_dir / "metadata.json"

    metadata_data = [
        {"slug": "older-post", "date": "2026-08-01", "post_id": 111},
        {"slug": "newest-post", "date": "2026-09-20", "post_id": 222},
        {"slug": "middle-post", "date": "2026-09-10", "post_id": 333},
    ]
    metadata_file.write_text(json.dumps(metadata_data), encoding="utf-8")

    scraper = FakeScraper("https://example.substack.com", content_save_dir=str(tmp_path))
    bootstrapped = load_sync_state(scraper.author_dir, scraper.metadata_file_path)

    assert bootstrapped is not None
    assert bootstrapped["last_post_date"] == "2026-09-20"
    assert bootstrapped["last_post_id"] == 222
    assert bootstrapped["last_post_slug"] == "newest-post"
    assert bootstrapped["total_synced_posts"] == 3


def test_fetch_posts_from_api_pagination_and_cutoff(monkeypatch):
    """Verify API pagination terminates upon encountering cutoff date, id, or slug."""
    page_1 = [
        {"id": 300, "slug": "post-3", "post_date": "2026-09-25T12:00:00.000Z"},
        {"id": 200, "slug": "post-2", "post_date": "2026-09-20T12:00:00.000Z"},
    ]
    page_2 = [
        {"id": 100, "slug": "post-1", "post_date": "2026-09-15T12:00:00.000Z"},
    ]

    api_calls = []

    def fake_get(url, timeout=30):
        if "api/v1/posts" in url:
            api_calls.append(url)
            if "offset=0" in url:
                return FakeResponse(page_1)
            elif "offset=2" in url:
                return FakeResponse(page_2)
            return FakeResponse([])
        return FakeResponse([], content=b"<urlset></urlset>")

    monkeypatch.setattr("scraper.sync.requests.get", fake_get)

    # Cutoff at post-2 (date 2026-09-20)
    delta = fetch_posts_from_api(
        "https://example.substack.com",
        since_date="2026-09-20T12:00:00.000Z",
        limit=2,
    )
    assert len(delta) == 1
    assert delta[0]["id"] == 300
    assert len(api_calls) == 1


def test_fetch_posts_from_api_handles_api_failure(monkeypatch):
    """Verify API network failure or non-200 status returns None gracefully."""
    monkeypatch.setattr(
        "scraper.sync.requests.get",
        lambda url, timeout=30: FakeResponse({}, ok=False, status_code=500),
    )

    result = fetch_posts_from_api("https://example.substack.com")
    assert result is None


def test_is_cutoff_reached_predicate():
    """Verify _is_cutoff_reached predicate matches by post_id, slug, and timestamp comparisons."""
    # Exact ID match
    assert _is_cutoff_reached({"id": 123}, last_post_id=123) is True
    assert _is_cutoff_reached({"id": 456}, last_post_id=123) is False

    # Exact slug match
    assert _is_cutoff_reached({"slug": "target-slug"}, last_post_slug="target-slug") is True
    assert _is_cutoff_reached({"slug": "other-slug"}, last_post_slug="target-slug") is False

    # Timestamp comparison
    post_item = {"post_date": "2026-09-20T12:00:00.000Z"}
    datetime_same = datetime(2026, 9, 20, 12, 0, tzinfo=UTC)
    datetime_later = datetime(2026, 9, 21, 0, 0, tzinfo=UTC)
    datetime_earlier = datetime(2026, 9, 19, 0, 0, tzinfo=UTC)

    assert _is_cutoff_reached(post_item, since_datetime=datetime_same) is True
    assert _is_cutoff_reached(post_item, since_datetime=datetime_later) is True
    assert _is_cutoff_reached(post_item, since_datetime=datetime_earlier) is False

    # Date-only format comparison
    datetime_day_same = datetime(2026, 9, 20, tzinfo=UTC)
    datetime_day_next = datetime(2026, 9, 21, tzinfo=UTC)
    assert _is_cutoff_reached(post_item, since_datetime=datetime_day_same, is_date_only=True) is False
    assert _is_cutoff_reached(post_item, since_datetime=datetime_day_next, is_date_only=True) is True
