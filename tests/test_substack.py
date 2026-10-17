"""Tests for SubstackScraper orchestration, post scraping, sync loops, and context management."""

import json
import logging
import os
from unittest.mock import Mock, patch

import pytest
from bs4 import BeautifulSoup

from scraper import sync
from scraper.fetchers.http import RequestsFetcher
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
