"""Tests for SubstackScraper orchestration, post scraping, sync loops, and context management."""

import json
import logging
import os
from unittest.mock import Mock, patch

import pytest
from bs4 import BeautifulSoup

from scraper import sync
from scraper.fetchers.http import RequestsFetcher
from scraper.fetchers.rate_limit import RateLimitError
from scraper.substack import SubstackScraper
from tests.conftest import FakeFetcher, FakeScraper


def test_single_post_url_initializes_without_fetching_all_posts(tmp_path):
    scraper = FakeScraper(
        "https://example.substack.com/p/my-post",
        str(tmp_path / "md"),
        download_images=True,
    )

    assert scraper.is_single_post is True
    assert scraper.post_slug == "my-post"
    assert scraper.base_substack_url == "https://example.substack.com/"
    assert scraper.post_urls == ["https://example.substack.com/p/my-post"]
    assert scraper.download_images is True


def test_scraper_initialization(tmp_path):
    """Verify writer_name and author directory structure are created."""
    content_dir = str(tmp_path / "content")

    scraper = FakeScraper(
        "https://example.substack.com/p/test-post",
        content_save_dir=content_dir,
    )

    assert scraper.writer_name == "example"
    assert os.path.isdir(os.path.join(content_dir, "example", "posts"))


def test_scrape_posts_skips_existing_when_overwrite_is_false(tmp_path, monkeypatch):
    md_dir = tmp_path / "md"
    scraper = FakeScraper(
        "https://example.substack.com/p/test-post",
        content_save_dir=str(md_dir),
        overwrite=False,
    )

    # Pre-create the markdown file in author posts directory
    author_md_dir = md_dir / "example" / "posts"
    author_md_dir.mkdir(parents=True, exist_ok=True)
    existing_md = author_md_dir / "test-post.md"
    existing_md.write_text("existing content", encoding="utf-8")

    mock_extract = Mock()
    mock_save = Mock()
    monkeypatch.setattr("scraper.substack.extract_post_data", mock_extract)
    monkeypatch.setattr("scraper.substack.save_to_file", mock_save)

    scraper.scrape_posts()

    mock_extract.assert_not_called()
    mock_save.assert_not_called()
    assert existing_md.read_text(encoding="utf-8") == "existing content"


def test_scrape_posts_rescrapes_existing_when_overwrite_is_true(tmp_path, monkeypatch):
    md_dir = tmp_path / "md"
    scraper = FakeScraper(
        "https://example.substack.com/p/test-post",
        content_save_dir=str(md_dir),
        overwrite=True,
    )

    # Pre-create the markdown file in author posts directory
    author_md_dir = md_dir / "example" / "posts"
    author_md_dir.mkdir(parents=True, exist_ok=True)
    existing_md = author_md_dir / "test-post.md"
    existing_md.write_text("old content", encoding="utf-8")

    mock_soup = Mock()
    scraper.fetcher.fetch_soup = Mock(return_value=mock_soup)

    fake_extracted = {
        "title": "Updated Title",
        "subtitle": "Updated Subtitle",
        "author": "Author",
        "date": "2026-09-13",
        "cover_image": "",
        "post_id": 10,
        "tags": [],
        "description": "",
        "wordcount": 10,
        "audience": "everyone",
        "canonical_url": "",
        "md_content": "Updated Content",
        "title_found": True,
        "body_found": True,
    }
    mock_extract = Mock(return_value=fake_extracted)
    mock_save = Mock()
    monkeypatch.setattr("scraper.substack.extract_post_data", mock_extract)
    monkeypatch.setattr("scraper.substack.save_to_file", mock_save)

    scraper.scrape_posts()

    mock_extract.assert_called_once_with(mock_soup, "https://example.substack.com/p/test-post", clean_content=True)
    mock_save.assert_called_once()
    assert mock_save.call_args[1]["overwrite"] is True


def test_scrape_posts_recovers_metadata_for_skipped_existing_files(tmp_path):
    content_dir = tmp_path / "content"
    author_posts_dir = content_dir / "example" / "posts"
    author_posts_dir.mkdir(parents=True, exist_ok=True)
    existing_file = author_posts_dir / "test-post.md"
    existing_file.write_text(
        '---\ntitle: "Existing Preserved"\npost_id: 8888\ndate: "2026-09-01"\nauthor: "Author"\n---\n\nContent',
        encoding="utf-8",
    )

    scraper = FakeScraper(
        "https://example.substack.com/p/test-post",
        content_save_dir=str(content_dir),
        overwrite=False,
    )
    scraper.scrape_posts()

    metadata_path = content_dir / "example" / "metadata.json"
    with open(metadata_path, encoding="utf-8") as file:
        saved_data = json.load(file)

    assert len(saved_data) == 1
    assert saved_data[0]["post_id"] == 8888
    assert saved_data[0]["title"] == "Existing Preserved"
    assert saved_data[0]["slug"] == "test-post"


def test_base_and_free_scrapers_use_logging(tmp_path, caplog):
    content_dir = tmp_path / "content"

    with caplog.at_level(logging.INFO):
        scraper_instance = FakeScraper(
            "https://example.substack.com/p/test-post",
            content_save_dir=str(content_dir),
            fetcher=RequestsFetcher(),
        )

    assert scraper_instance.writer_name == "example"
    assert any("Created posts directory" in record.message for record in caplog.records)


def test_sync_posts_raises_on_single_post(tmp_path):
    """Verify sync_posts raises ValueError if initialized on a single post URL."""
    scraper = FakeScraper("https://example.substack.com/p/my-post", content_save_dir=str(tmp_path))
    with pytest.raises(ValueError, match="sync_posts"):
        scraper.sync_posts()


def test_sync_posts_up_to_date_when_no_delta(tmp_path, monkeypatch):
    """Verify sync_posts returns 0 and updates last_sync_at when already up to date."""
    scraper = FakeScraper("https://example.substack.com", content_save_dir=str(tmp_path))
    initial_cursor = {
        "last_sync_at": "2026-09-20T00:00:00Z",
        "last_post_date": "2026-09-26T12:00:00.000Z",
        "last_post_id": 999,
        "last_post_slug": "latest-post",
        "total_synced_posts": 5,
    }
    sync.save_sync_state(scraper.author_dir, initial_cursor)

    monkeypatch.setattr("scraper.substack.fetch_posts_from_api", Mock(return_value=[]))

    synced_count = scraper.sync_posts()
    assert synced_count == 0

    updated_cursor = sync.load_sync_state(scraper.author_dir, scraper.metadata_file_path)
    assert updated_cursor["total_synced_posts"] == 5
    assert updated_cursor["last_post_date"] == "2026-09-26T12:00:00.000Z"
    assert updated_cursor["last_sync_at"] != "2026-09-20T00:00:00Z"


def test_sync_posts_scrapes_delta_and_updates_cursor(tmp_path, monkeypatch):
    """Verify sync_posts scrapes only newly published posts and advances cursor."""
    scraper = FakeScraper("https://example.substack.com", content_save_dir=str(tmp_path))
    initial_cursor = {
        "last_sync_at": "2026-09-20T00:00:00Z",
        "last_post_date": "2026-09-20T10:00:00.000Z",
        "last_post_id": 100,
        "last_post_slug": "post-100",
        "total_synced_posts": 10,
    }
    sync.save_sync_state(scraper.author_dir, initial_cursor)

    delta_api_posts = [
        {
            "id": 200,
            "slug": "newest-post",
            "post_date": "2026-09-25T15:00:00.000Z",
            "canonical_url": "https://example.substack.com/p/newest-post",
        },
        {
            "id": 150,
            "slug": "intermediate-post",
            "post_date": "2026-09-22T10:00:00.000Z",
            "canonical_url": "https://example.substack.com/p/intermediate-post",
        },
    ]
    monkeypatch.setattr("scraper.substack.fetch_posts_from_api", Mock(return_value=delta_api_posts))

    scraped_urls = []

    def fake_scrape_single(url, progress_bar=None):
        scraped_urls.append(url)
        slug = url.split("/")[-1]
        return {
            "title": f"Title {slug}",
            "slug": slug,
            "post_id": 200 if slug == "newest-post" else 150,
            "date": "2026-09-25" if slug == "newest-post" else "2026-09-22",
        }

    scraper._scrape_single_post = Mock(side_effect=fake_scrape_single)
    save_posts_mock = Mock()
    monkeypatch.setattr("scraper.substack.save_posts_data_to_json", save_posts_mock)

    synced_count = scraper.sync_posts()
    assert synced_count == 2
    assert scraped_urls == [
        "https://example.substack.com/p/intermediate-post",
        "https://example.substack.com/p/newest-post",
    ]

    updated_cursor = sync.load_sync_state(scraper.author_dir, scraper.metadata_file_path)
    assert updated_cursor is not None
    assert updated_cursor["last_post_id"] == 200
    assert updated_cursor["last_post_slug"] == "newest-post"
    assert updated_cursor["last_post_date"] == "2026-09-25T15:00:00.000Z"
    assert updated_cursor["total_synced_posts"] == 12


def test_sync_posts_falls_back_to_sitemap_when_api_returns_none(tmp_path, monkeypatch):
    """Verify sync_posts falls back to sitemap discovery and does not advance cursor to API post when API returns None."""
    scraper = FakeScraper(
        "https://example.substack.com",
        content_save_dir=str(tmp_path),
        post_urls=["https://example.substack.com/p/sitemap-post"],
    )
    initial_cursor = {
        "last_sync_at": "2026-09-20T00:00:00Z",
        "last_post_date": "2026-09-20T10:00:00.000Z",
        "last_post_id": 100,
        "last_post_slug": "post-100",
        "total_synced_posts": 10,
    }
    sync.save_sync_state(scraper.author_dir, initial_cursor)

    monkeypatch.setattr("scraper.substack.fetch_posts_from_api", Mock(return_value=None))
    scrape_posts_mock = Mock()
    monkeypatch.setattr(scraper, "scrape_posts", scrape_posts_mock)

    result_count = scraper.sync_posts()

    assert result_count == 1
    scrape_posts_mock.assert_called_once_with(limit=0)
    saved_cursor = sync.load_sync_state(scraper.author_dir, scraper.metadata_file_path)
    assert saved_cursor == initial_cursor


@pytest.mark.parametrize("failure_mode", ["raises_exception", "returns_none"])
def test_sync_posts_middle_delta_post_failure_holds_back_cursor(tmp_path, monkeypatch, caplog, failure_mode):
    """Verify middle delta post failure advances cursor only to last post before failure while saving all successes."""
    scraper = FakeScraper("https://example.substack.com", content_save_dir=str(tmp_path))
    initial_cursor = {
        "last_sync_at": "2026-09-20T00:00:00Z",
        "last_post_date": "2026-09-20T10:00:00.000Z",
        "last_post_id": 100,
        "last_post_slug": "post-100",
        "total_synced_posts": 10,
    }
    sync.save_sync_state(scraper.author_dir, initial_cursor)

    delta_api_posts = [
        {
            "id": 200,
            "slug": "newest-post",
            "post_date": "2026-09-25T15:00:00.000Z",
            "canonical_url": "https://example.substack.com/p/newest-post",
        },
        {
            "id": 150,
            "slug": "middle-post",
            "post_date": "2026-09-22T12:00:00.000Z",
            "canonical_url": "https://example.substack.com/p/middle-post",
        },
        {
            "id": 110,
            "slug": "oldest-post",
            "post_date": "2026-09-21T10:00:00.000Z",
            "canonical_url": "https://example.substack.com/p/oldest-post",
        },
    ]
    monkeypatch.setattr("scraper.substack.fetch_posts_from_api", Mock(return_value=delta_api_posts))

    def fake_scrape_single(url, progress_bar=None):
        slug = url.split("/")[-1]
        if slug == "middle-post":
            if failure_mode == "raises_exception":
                raise RuntimeError("Transient network error")
            return None
        return {
            "title": f"Title {slug}",
            "slug": slug,
            "post_id": 200 if slug == "newest-post" else 110,
            "date": "2026-09-25" if slug == "newest-post" else "2026-09-21",
        }

    scraper._scrape_single_post = Mock(side_effect=fake_scrape_single)

    with caplog.at_level(logging.WARNING):
        synced_count = scraper.sync_posts()

    assert synced_count == 2

    with open(scraper.metadata_file_path, encoding="utf-8") as metadata_file:
        saved_metadata = json.load(metadata_file)
    assert {entry["slug"] for entry in saved_metadata} == {"oldest-post", "newest-post"}

    updated_cursor = sync.load_sync_state(scraper.author_dir, scraper.metadata_file_path)
    assert updated_cursor is not None
    assert updated_cursor["last_post_id"] == 110
    assert updated_cursor["last_post_slug"] == "oldest-post"
    assert updated_cursor["last_post_date"] == "2026-09-21T10:00:00.000Z"
    assert updated_cursor["total_synced_posts"] == 12
    assert any("middle-post" in record.message for record in caplog.records)


@pytest.mark.parametrize("failure_mode", ["raises_exception", "returns_none"])
def test_sync_posts_oldest_delta_post_failure_leaves_position_unchanged(tmp_path, monkeypatch, caplog, failure_mode):
    """Verify failure on the oldest delta post leaves sync position fields unchanged."""
    scraper = FakeScraper("https://example.substack.com", content_save_dir=str(tmp_path))
    initial_cursor = {
        "last_sync_at": "2026-09-20T00:00:00Z",
        "last_post_date": "2026-09-20T10:00:00.000Z",
        "last_post_id": 100,
        "last_post_slug": "post-100",
        "total_synced_posts": 10,
    }
    sync.save_sync_state(scraper.author_dir, initial_cursor)

    delta_api_posts = [
        {
            "id": 200,
            "slug": "newest-post",
            "post_date": "2026-09-25T15:00:00.000Z",
            "canonical_url": "https://example.substack.com/p/newest-post",
        },
        {
            "id": 110,
            "slug": "oldest-post",
            "post_date": "2026-09-21T10:00:00.000Z",
            "canonical_url": "https://example.substack.com/p/oldest-post",
        },
    ]
    monkeypatch.setattr("scraper.substack.fetch_posts_from_api", Mock(return_value=delta_api_posts))

    def fake_scrape_single(url, progress_bar=None):
        slug = url.split("/")[-1]
        if slug == "oldest-post":
            if failure_mode == "raises_exception":
                raise RuntimeError("Extraction crash")
            return None
        return {
            "title": f"Title {slug}",
            "slug": slug,
            "post_id": 200,
            "date": "2026-09-25",
        }

    scraper._scrape_single_post = Mock(side_effect=fake_scrape_single)

    with caplog.at_level(logging.WARNING):
        synced_count = scraper.sync_posts()

    assert synced_count == 1

    with open(scraper.metadata_file_path, encoding="utf-8") as metadata_file:
        saved_metadata = json.load(metadata_file)
    assert [entry["slug"] for entry in saved_metadata] == ["newest-post"]

    updated_cursor = sync.load_sync_state(scraper.author_dir, scraper.metadata_file_path)
    assert updated_cursor is not None
    assert updated_cursor["last_post_id"] == 100
    assert updated_cursor["last_post_slug"] == "post-100"
    assert updated_cursor["last_post_date"] == "2026-09-20T10:00:00.000Z"
    assert updated_cursor["total_synced_posts"] == 11
    assert updated_cursor["last_sync_at"] != "2026-09-20T00:00:00Z"
    assert any("oldest-post" in record.message for record in caplog.records)


def test_sync_posts_already_archived_delta_post_counts_as_success(tmp_path, monkeypatch, caplog):
    """Verify an already-archived delta post on disk counts as a success and does not hold back sync position."""
    scraper = FakeScraper(
        "https://example.substack.com",
        content_save_dir=str(tmp_path),
        overwrite=False,
    )
    initial_cursor = {
        "last_sync_at": "2026-09-20T00:00:00Z",
        "last_post_date": "2026-09-20T10:00:00.000Z",
        "last_post_id": 100,
        "last_post_slug": "post-100",
        "total_synced_posts": 10,
    }
    sync.save_sync_state(scraper.author_dir, initial_cursor)

    # Pre-create the older delta post on disk
    existing_markdown_path = tmp_path / "example" / "posts" / "already-saved.md"
    existing_markdown_path.write_text(
        '---\ntitle: "Already Saved"\npost_id: 150\ndate: "2026-09-22"\nauthor: "Author"\n---\n\nExisting body',
        encoding="utf-8",
    )

    delta_api_posts = [
        {
            "id": 200,
            "slug": "brand-new",
            "post_date": "2026-09-25T15:00:00.000Z",
            "canonical_url": "https://example.substack.com/p/brand-new",
        },
        {
            "id": 150,
            "slug": "already-saved",
            "post_date": "2026-09-22T12:00:00.000Z",
            "canonical_url": "https://example.substack.com/p/already-saved",
        },
    ]
    monkeypatch.setattr("scraper.substack.fetch_posts_from_api", Mock(return_value=delta_api_posts))

    valid_soup = BeautifulSoup(
        "<html><body><h1 class='post-title'>Brand New</h1><div class='available-content'><p>Body</p></div></body></html>",
        "html.parser",
    )
    scraper.fetcher.fetch_soup = Mock(return_value=valid_soup)

    with caplog.at_level(logging.WARNING):
        synced_count = scraper.sync_posts()

    assert synced_count == 2
    scraper.fetcher.fetch_soup.assert_called_once_with("https://example.substack.com/p/brand-new")

    updated_cursor = sync.load_sync_state(scraper.author_dir, scraper.metadata_file_path)
    assert updated_cursor is not None
    assert updated_cursor["last_post_id"] == 200
    assert updated_cursor["last_post_slug"] == "brand-new"
    assert updated_cursor["last_post_date"] == "2026-09-25T15:00:00.000Z"
    assert not any("held back" in record.message for record in caplog.records)


def test_scrape_single_post_dumps_debug_html_on_extraction_failure(tmp_path):
    """Verify _scrape_single_post dumps debug HTML when extraction fails."""
    scraper_instance = FakeScraper("https://example.substack.com", content_save_dir=str(tmp_path))

    invalid_soup = BeautifulSoup("<html><body><div>No body</div></body></html>", "html.parser")
    scraper_instance.fetcher.fetch_soup = Mock(return_value=invalid_soup)

    result = scraper_instance._scrape_single_post("https://example.substack.com/p/bad-post")
    assert result is None

    debug_file = tmp_path / "_debug" / "example" / "bad-post.html"
    assert debug_file.exists()
    assert "No body" in debug_file.read_text(encoding="utf-8")


def test_substack_scraper_context_manager_closes_fetcher(tmp_path):
    """Verify SubstackScraper context manager closes its fetcher normally and on exception."""
    fake_fetcher = FakeFetcher()
    with patch("scraper.substack.discover_post_urls", return_value=[]):
        with SubstackScraper(
            "https://example.substack.com",
            fetcher=fake_fetcher,
            content_save_dir=str(tmp_path),
        ):
            assert not fake_fetcher.closed
        assert fake_fetcher.closed is True

        failing_fetcher = FakeFetcher()
        with pytest.raises(RuntimeError, match="Context error"):
            with SubstackScraper(
                "https://example.substack.com",
                fetcher=failing_fetcher,
                content_save_dir=str(tmp_path),
            ):
                raise RuntimeError("Context error")
        assert failing_fetcher.closed is True


def test_scrape_posts_stops_and_saves_progress_on_rate_limit(tmp_path):
    """Verify persistent 429 mid-scrape stops loop, skips later URLs, saves collected metadata, and re-raises."""
    urls = [
        "https://example.substack.com/p/post-1",
        "https://example.substack.com/p/post-2",
        "https://example.substack.com/p/post-3",
    ]
    scraper = FakeScraper("https://example.substack.com", content_save_dir=str(tmp_path), post_urls=urls)

    requested_urls: list[str] = []

    def fake_scrape_single(url, progress_bar=None):
        requested_urls.append(url)
        if url.endswith("post-1"):
            return {"title": "Post 1", "slug": "post-1", "post_id": 1, "date": "2026-09-20"}
        if url.endswith("post-2"):
            raise RateLimitError(url=url)
        return {"title": "Post 3", "slug": "post-3", "post_id": 3, "date": "2026-09-22"}

    scraper._scrape_single_post = Mock(side_effect=fake_scrape_single)

    with pytest.raises(RateLimitError):
        scraper.scrape_posts()

    assert requested_urls == [
        "https://example.substack.com/p/post-1",
        "https://example.substack.com/p/post-2",
    ]
    assert scraper.last_saved_count == 1
    with open(scraper.metadata_file_path, encoding="utf-8") as metadata_file:
        saved_metadata = json.load(metadata_file)
    assert [entry["slug"] for entry in saved_metadata] == ["post-1"]


def test_sync_posts_bootstrap_rate_limit_does_not_create_sync_state(tmp_path):
    """Verify a rate limit during initial sync bootstrap does not record sync_state.json."""
    urls = [
        "https://example.substack.com/p/post-1",
        "https://example.substack.com/p/post-2",
    ]
    scraper = FakeScraper("https://example.substack.com", content_save_dir=str(tmp_path), post_urls=urls)

    def fake_scrape_single(url, progress_bar=None):
        if url.endswith("post-1"):
            return {"title": "Post 1", "slug": "post-1", "post_id": 1, "date": "2026-09-25"}
        raise RateLimitError(url=url)

    scraper._scrape_single_post = Mock(side_effect=fake_scrape_single)

    with pytest.raises(RateLimitError):
        scraper.sync_posts()

    sync_state_file = tmp_path / "example" / "sync_state.json"
    assert not sync_state_file.exists()


def test_sync_posts_api_rate_limit_propagates_without_sitemap_fallback(tmp_path, monkeypatch):
    """Verify RateLimitError from fetch_posts_from_api propagates without falling back to sitemap discovery."""
    scraper = FakeScraper("https://example.substack.com", content_save_dir=str(tmp_path))
    initial_cursor = {
        "last_sync_at": "2026-09-20T00:00:00Z",
        "last_post_date": "2026-09-20T10:00:00.000Z",
        "last_post_id": 100,
        "last_post_slug": "post-100",
        "total_synced_posts": 10,
    }
    sync.save_sync_state(scraper.author_dir, initial_cursor)

    monkeypatch.setattr(
        "scraper.substack.fetch_posts_from_api",
        Mock(side_effect=RateLimitError("https://example.substack.com/api/v1/posts")),
    )
    scrape_posts_mock = Mock()
    monkeypatch.setattr(scraper, "scrape_posts", scrape_posts_mock)

    with pytest.raises(RateLimitError):
        scraper.sync_posts()

    scrape_posts_mock.assert_not_called()
    assert sync.load_sync_state(scraper.author_dir, scraper.metadata_file_path) == initial_cursor


def test_sync_posts_delta_rate_limit_stops_loop_and_holds_back_cursor(tmp_path, monkeypatch, caplog):
    """Verify RateLimitError in delta loop stops later requests, saves collected entries, and holds back cursor."""
    scraper = FakeScraper("https://example.substack.com", content_save_dir=str(tmp_path))
    initial_cursor = {
        "last_sync_at": "2026-09-20T00:00:00Z",
        "last_post_date": "2026-09-20T10:00:00.000Z",
        "last_post_id": 100,
        "last_post_slug": "post-100",
        "total_synced_posts": 10,
    }
    sync.save_sync_state(scraper.author_dir, initial_cursor)

    delta_api_posts = [
        {
            "id": 200,
            "slug": "newest-post",
            "post_date": "2026-09-25T15:00:00.000Z",
            "canonical_url": "https://example.substack.com/p/newest-post",
        },
        {
            "id": 150,
            "slug": "middle-post",
            "post_date": "2026-09-22T12:00:00.000Z",
            "canonical_url": "https://example.substack.com/p/middle-post",
        },
        {
            "id": 110,
            "slug": "oldest-post",
            "post_date": "2026-09-21T10:00:00.000Z",
            "canonical_url": "https://example.substack.com/p/oldest-post",
        },
    ]
    monkeypatch.setattr("scraper.substack.fetch_posts_from_api", Mock(return_value=delta_api_posts))

    requested_urls: list[str] = []

    def fake_scrape_single(url, progress_bar=None):
        requested_urls.append(url)
        if url.endswith("oldest-post"):
            return {"title": "Oldest", "slug": "oldest-post", "post_id": 110, "date": "2026-09-21"}
        raise RateLimitError(url=url)

    scraper._scrape_single_post = Mock(side_effect=fake_scrape_single)

    with pytest.raises(RateLimitError):
        scraper.sync_posts()

    assert requested_urls == [
        "https://example.substack.com/p/oldest-post",
        "https://example.substack.com/p/middle-post",
    ]
    with open(scraper.metadata_file_path, encoding="utf-8") as metadata_file:
        saved_metadata = json.load(metadata_file)
    assert [entry["slug"] for entry in saved_metadata] == ["oldest-post"]

    updated_cursor = sync.load_sync_state(scraper.author_dir, scraper.metadata_file_path)
    assert updated_cursor is not None
    assert updated_cursor["last_post_id"] == 110
    assert updated_cursor["last_post_slug"] == "oldest-post"
    assert updated_cursor["last_post_date"] == "2026-09-21T10:00:00.000Z"
    assert not any("Sync completed" in record.message for record in caplog.records)


def test_scrape_posts_progress_total_and_limit_semantics(tmp_path, monkeypatch):
    """Verify limit slices URLs up front and progress bar total stays fixed across success, skip, and failure."""
    urls = [
        "https://example.substack.com/p/post-1",
        "https://example.substack.com/p/post-2",
        "https://example.substack.com/p/post-3",
        "https://example.substack.com/p/post-4",
    ]
    scraper = FakeScraper("https://example.substack.com", content_save_dir=str(tmp_path), post_urls=urls)

    processed_urls: list[str] = []

    def fake_scrape_single(url, progress_bar=None):
        processed_urls.append(url)
        if url.endswith("post-1"):
            return {"title": "Post 1", "slug": "post-1", "post_id": 1, "date": "2026-09-20"}
        if url.endswith("post-2"):
            return None  # skipped
        raise ValueError("HTTP 404")  # failed

    scraper._scrape_single_post = Mock(side_effect=fake_scrape_single)

    created_bars: list[Mock] = []

    class FakeTqdm:
        def __init__(self, total: int, desc: str = "", **kwargs):
            self.total = total
            self.desc = desc
            self.updates: list[int] = []
            created_bars.append(self)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return False

        def update(self, step: int = 1):
            self.updates.append(step)

        def write(self, message: str):
            pass

    monkeypatch.setattr("scraper.substack.tqdm", FakeTqdm)

    scraper.scrape_posts(limit=3)

    assert processed_urls == urls[:3]
    assert len(created_bars) == 1
    assert created_bars[0].total == 3
    assert created_bars[0].updates == [1, 1, 1]
