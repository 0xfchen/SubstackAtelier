"""Tests for file writing, markdown persistence, and metadata JSON storage."""

import json

from scraper.storage import save_posts_data_to_json, save_to_file
from tests.conftest import FakeScraper


def test_save_posts_data_to_json_updates_existing_entry_by_post_id(tmp_path):
    scraper = FakeScraper("https://example.substack.com", content_save_dir=str(tmp_path))

    initial_entries = [
        {
            "post_id": 12345,
            "title": "Initial Title",
            "slug": "initial-slug",
            "file_link": "posts/initial.md",
        }
    ]
    save_posts_data_to_json(scraper.metadata_file_path, initial_entries)

    updated_entries = [
        {
            "post_id": 12345,
            "title": "Updated Title With New Headline",
            "slug": "new-renamed-slug",
            "file_link": "posts/new-renamed-slug.md",
        }
    ]
    save_posts_data_to_json(scraper.metadata_file_path, updated_entries)

    json_path = tmp_path / "example" / "metadata.json"
    with open(json_path, encoding="utf-8") as file:
        saved_data = json.load(file)

    assert len(saved_data) == 1
    assert saved_data[0]["post_id"] == 12345
    assert saved_data[0]["title"] == "Updated Title With New Headline"
    assert saved_data[0]["slug"] == "new-renamed-slug"
    assert saved_data[0]["file_link"] == "posts/new-renamed-slug.md"


def test_save_posts_data_to_json_appends_genuinely_new_posts(tmp_path):
    scraper = FakeScraper("https://example.substack.com", content_save_dir=str(tmp_path))

    save_posts_data_to_json(scraper.metadata_file_path, [{"post_id": 101, "title": "First"}])
    save_posts_data_to_json(scraper.metadata_file_path, [{"post_id": 102, "title": "Second"}])

    with open(tmp_path / "example" / "metadata.json", encoding="utf-8") as file:
        saved_data = json.load(file)

    assert len(saved_data) == 2


def test_save_to_file_ensures_trailing_newline(tmp_path):
    """Verify save_to_file guarantees a trailing newline on written files."""
    file_path = str(tmp_path / "test.md")
    save_to_file(file_path, "no newline at end")
    with open(file_path, encoding="utf-8") as f:
        saved_text = f.read()
    assert saved_text.endswith("\n")
