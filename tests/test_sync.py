"""Tests for incremental sync cursor state and Substack API delta pagination."""

import json
import logging
from datetime import UTC, datetime
from typing import Any

import pytest
import requests

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


def test_fetch_posts_from_api_cursor_progression_and_params(monkeypatch):
    """Verify wrapped cursor pagination progresses across pages, preserves opaque cursor, and omits offset."""
    opaque_cursor = "eyJpZCI6MjAwfQ==+next/page"
    page_1 = {
        "posts": [
            {
                "id": 300,
                "slug": "post-3",
                "post_date": "2026-09-25T12:00:00.000Z",
                "canonical_url": "https://example.substack.com/p/post-3",
            },
        ],
        "nextCursor": opaque_cursor,
    }
    page_2 = {
        "posts": [
            {
                "id": 200,
                "slug": "post-2",
                "post_date": "2026-09-22T12:00:00.000Z",
                "canonical_url": "https://example.substack.com/p/post-2",
            },
            {
                "id": 100,
                "slug": "post-1",
                "post_date": "2026-09-20T12:00:00.000Z",
                "canonical_url": "https://example.substack.com/p/post-1",
            },
        ],
        "nextCursor": "cursor-unused",
    }

    recorded_requests: list[tuple[str, dict[str, Any] | None]] = []

    def fake_get(url, params=None, timeout=30):
        recorded_requests.append((url, dict(params) if params is not None else None))
        if params and params.get("cursor") == opaque_cursor:
            return FakeResponse(page_2, params=params)
        return FakeResponse(page_1, params=params)

    monkeypatch.setattr("scraper.sync.requests.get", fake_get)

    # Note: page_1 has 1 post while limit=25 (short page), testing that short pages still follow nextCursor
    delta = fetch_posts_from_api(
        "https://example.substack.com",
        since_date="2026-09-20T12:00:00.000Z",
        limit=25,
    )

    assert delta is not None
    assert [post["id"] for post in delta] == [300, 200]
    assert len(recorded_requests) == 2

    first_url, first_params = recorded_requests[0]
    second_url, second_params = recorded_requests[1]
    assert first_url == "https://example.substack.com/api/v1/posts"
    assert second_url == "https://example.substack.com/api/v1/posts"
    assert "offset" not in first_url
    assert "offset" not in second_url
    assert first_params == {"limit": 25, "sort": "new"}
    assert second_params == {"limit": 25, "sort": "new", "cursor": opaque_cursor}


@pytest.mark.parametrize(
    "cutoff_kwargs",
    [
        {"last_post_id": 200},
        {"last_post_slug": "post-2"},
        {"since_date": "2026-09-20T12:00:00.000Z"},
    ],
)
def test_fetch_posts_from_api_cutoff_stops_without_requesting_next_page(monkeypatch, cutoff_kwargs):
    """Verify cutoff by ID, slug, or date stops immediately without requesting another page."""
    page_1 = {
        "posts": [
            {"id": 300, "slug": "post-3", "post_date": "2026-09-25T12:00:00.000Z"},
            {"id": 200, "slug": "post-2", "post_date": "2026-09-20T12:00:00.000Z"},
        ],
        "nextCursor": "next-page-cursor",
    }

    recorded_calls: list[dict[str, Any] | None] = []

    def fake_get(url, params=None, timeout=30):
        recorded_calls.append(params)
        return FakeResponse(page_1, params=params)

    monkeypatch.setattr("scraper.sync.requests.get", fake_get)

    delta = fetch_posts_from_api(
        "https://example.substack.com",
        limit=2,
        **cutoff_kwargs,
    )

    assert delta is not None
    assert len(delta) == 1
    assert delta[0]["id"] == 300
    assert len(recorded_calls) == 1


@pytest.mark.parametrize(
    "final_page_payload",
    [
        {"posts": [{"id": 200, "slug": "post-2", "post_date": "2026-09-22T12:00:00.000Z"}]},
        {
            "posts": [{"id": 200, "slug": "post-2", "post_date": "2026-09-22T12:00:00.000Z"}],
            "nextCursor": None,
        },
        {
            "posts": [{"id": 200, "slug": "post-2", "post_date": "2026-09-22T12:00:00.000Z"}],
            "nextCursor": "",
        },
    ],
)
def test_fetch_posts_from_api_missing_or_empty_next_cursor_before_cutoff(
    monkeypatch,
    caplog,
    final_page_payload,
):
    """Verify missing or empty nextCursor before reaching cutoff returns collected posts and logs warning."""
    monkeypatch.setattr(
        "scraper.sync.requests.get",
        lambda url, params=None, timeout=30: FakeResponse(final_page_payload, params=params),
    )

    with caplog.at_level(logging.WARNING):
        delta = fetch_posts_from_api(
            "https://example.substack.com",
            last_post_id=999,
        )

    assert delta == [{"id": 200, "slug": "post-2", "post_date": "2026-09-22T12:00:00.000Z"}]
    assert any("end of archive" in record.message for record in caplog.records)


@pytest.mark.parametrize(
    "failure_mode",
    ["transport_error", "http_500", "http_400", "invalid_json"],
)
def test_fetch_posts_from_api_handles_first_page_failure(monkeypatch, failure_mode):
    """Verify transport error, non-OK status, or invalid JSON on page 1 returns None."""

    def fake_get(url, params=None, timeout=30):
        if failure_mode == "transport_error":
            raise requests.ConnectionError("Connection failed")
        if failure_mode == "http_500":
            return FakeResponse({}, ok=False, status_code=500, params=params)
        if failure_mode == "http_400":
            return FakeResponse({}, ok=False, status_code=400, params=params)
        return FakeResponse(json_error=ValueError("Malformed JSON"), params=params)

    monkeypatch.setattr("scraper.sync.requests.get", fake_get)

    result = fetch_posts_from_api("https://example.substack.com")
    assert result is None


@pytest.mark.parametrize(
    "second_page_failure",
    ["transport_error", "http_500", "invalid_json", "malformed_shape"],
)
def test_fetch_posts_from_api_later_page_failure_returns_none(monkeypatch, second_page_failure):
    """Verify a failure on a later page returns None rather than partial delta posts."""
    page_1 = {
        "posts": [{"id": 300, "slug": "post-3", "post_date": "2026-09-25T12:00:00.000Z"}],
        "nextCursor": "cursor-page-2",
    }

    def fake_get(url, params=None, timeout=30):
        if not params or "cursor" not in params:
            return FakeResponse(page_1, params=params)
        if second_page_failure == "transport_error":
            raise requests.Timeout("Request timed out on page 2")
        if second_page_failure == "http_500":
            return FakeResponse({}, ok=False, status_code=500, params=params)
        if second_page_failure == "invalid_json":
            return FakeResponse(json_error=ValueError("Truncated JSON"), params=params)
        return FakeResponse({"unexpected": "shape"}, params=params)

    monkeypatch.setattr("scraper.sync.requests.get", fake_get)

    result = fetch_posts_from_api(
        "https://example.substack.com",
        since_date="2026-09-01T00:00:00.000Z",
    )
    assert result is None


@pytest.mark.parametrize(
    "malformed_payload",
    [
        "unexpected-string",
        12345,
        None,
        {},
        {"nextCursor": "cursor-only"},
        {"posts": None},
        {"posts": "not-a-list"},
        {"posts": {"id": 1}},
        {"posts": [], "nextCursor": 999},
    ],
)
def test_fetch_posts_from_api_malformed_response_returns_none(monkeypatch, malformed_payload):
    """Verify non-dict response, missing posts key, or non-list posts returns None rather than []."""
    monkeypatch.setattr(
        "scraper.sync.requests.get",
        lambda url, params=None, timeout=30: FakeResponse(malformed_payload, params=params),
    )

    result = fetch_posts_from_api("https://example.substack.com")
    assert result is None


def test_fetch_posts_from_api_repeated_cursor_returns_none(monkeypatch, caplog):
    """Verify repeated nextCursor across pages logs a warning and returns None."""
    stuck_page = {
        "posts": [{"id": 300, "slug": "post-3", "post_date": "2026-09-25T12:00:00.000Z"}],
        "nextCursor": "stuck-cursor",
    }
    monkeypatch.setattr(
        "scraper.sync.requests.get",
        lambda url, params=None, timeout=30: FakeResponse(stuck_page, params=params),
    )

    with caplog.at_level(logging.WARNING):
        result = fetch_posts_from_api(
            "https://example.substack.com",
            since_date="2026-09-01T00:00:00.000Z",
        )

    assert result is None
    assert any("repeated nextCursor" in record.message for record in caplog.records)


def test_fetch_posts_from_api_empty_page_with_cursor_returns_none(monkeypatch, caplog):
    """Verify an empty posts page carrying a non-empty nextCursor logs a warning and returns None."""
    empty_page_with_cursor = {
        "posts": [],
        "nextCursor": "non-empty-cursor",
    }
    monkeypatch.setattr(
        "scraper.sync.requests.get",
        lambda url, params=None, timeout=30: FakeResponse(empty_page_with_cursor, params=params),
    )

    with caplog.at_level(logging.WARNING):
        result = fetch_posts_from_api("https://example.substack.com")

    assert result is None
    assert any("empty posts page" in record.message for record in caplog.records)


def test_fetch_posts_from_api_max_pages_exhausted_returns_none(monkeypatch, caplog):
    """Verify exhausting max_pages before reaching cutoff logs a warning and returns None."""
    call_count = 0

    def fake_get(url, params=None, timeout=30):
        nonlocal call_count
        call_count += 1
        return FakeResponse(
            {
                "posts": [
                    {
                        "id": 1000 - call_count,
                        "slug": f"post-{call_count}",
                        "post_date": "2026-09-25T12:00:00.000Z",
                    }
                ],
                "nextCursor": f"cursor-{call_count}",
            },
            params=params,
        )

    monkeypatch.setattr("scraper.sync.requests.get", fake_get)

    with caplog.at_level(logging.WARNING):
        result = fetch_posts_from_api(
            "https://example.substack.com",
            since_date="2026-09-01T00:00:00.000Z",
            max_pages=2,
        )

    assert result is None
    assert call_count == 2
    assert any("max_pages" in record.message for record in caplog.records)


def test_fetch_posts_from_api_legacy_top_level_list_response(monkeypatch):
    """Verify legacy top-level list response is accepted as a single final page."""
    legacy_payload = [
        {"id": 300, "slug": "post-3", "post_date": "2026-09-25T12:00:00.000Z"},
        {"id": 200, "slug": "post-2", "post_date": "2026-09-20T12:00:00.000Z"},
    ]
    recorded_calls: list[dict[str, Any] | None] = []

    def fake_get(url, params=None, timeout=30):
        recorded_calls.append(params)
        return FakeResponse(legacy_payload, params=params)

    monkeypatch.setattr("scraper.sync.requests.get", fake_get)

    delta = fetch_posts_from_api(
        "https://example.substack.com",
        since_date="2026-09-01T00:00:00.000Z",
        limit=2,
    )

    assert delta == legacy_payload
    assert len(recorded_calls) == 1


def test_fetch_posts_from_api_retries_on_http_429_with_backoff(monkeypatch):
    """Verify HTTP 429 response triggers jittered backoff retry before succeeding."""
    page_payload = {
        "posts": [{"id": 300, "slug": "post-3", "post_date": "2026-09-25T12:00:00.000Z"}],
        "nextCursor": None,
    }
    responses = iter(
        [
            FakeResponse({}, ok=False, status_code=429),
            FakeResponse(page_payload, ok=True, status_code=200),
        ]
    )
    slept_durations: list[float] = []

    monkeypatch.setattr(
        "scraper.sync.requests.get",
        lambda url, params=None, timeout=30: next(responses),
    )
    monkeypatch.setattr(
        "scraper.fetchers.rate_limit.sleep",
        lambda duration: slept_durations.append(duration),
    )

    delta = fetch_posts_from_api("https://example.substack.com")

    assert delta == page_payload["posts"]
    assert len(slept_durations) == 1
    assert slept_durations[0] > 0


def test_fetch_posts_from_api_persistent_http_429_returns_none(monkeypatch):
    """Verify persistent HTTP 429 across all retry attempts returns None cleanly."""
    slept_durations: list[float] = []

    monkeypatch.setattr(
        "scraper.sync.requests.get",
        lambda url, params=None, timeout=30: FakeResponse({}, ok=False, status_code=429),
    )
    monkeypatch.setattr(
        "scraper.fetchers.rate_limit.sleep",
        lambda duration: slept_durations.append(duration),
    )

    result = fetch_posts_from_api("https://example.substack.com")

    assert result is None
    assert len(slept_durations) == 4


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
