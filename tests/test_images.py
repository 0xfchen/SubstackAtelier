"""Tests for image URL resolution, filename sanitization, and concurrent downloads."""

from unittest.mock import Mock, patch

import pytest
import requests

from scraper import images


def test_resolve_image_url_extracts_original_url():
    cdn_url = (
        "https://substackcdn.com/image/fetch/w_1456,c_limit,f_webp,q_auto:good,"
        "fl_progressive:steep/https%3A%2F%2Fbucket.s3.us-west-2.amazonaws.com%2Fimage.jpg"
    )

    assert images.resolve_image_url(cdn_url) == "https://bucket.s3.us-west-2.amazonaws.com/image.jpg"


def test_sanitize_image_filename_uses_resolved_url_name():
    cdn_url = (
        "https://substackcdn.com/image/fetch/w_1456,c_limit,f_webp,q_auto:good,"
        "fl_progressive:steep/https%3A%2F%2Fbucket.s3.us-west-2.amazonaws.com%2Fimage.jpg%3Fv%3D1"
    )

    assert images.sanitize_image_filename(cdn_url) == "image.jpg"


def test_count_images_in_markdown_counts_cleaned_linked_images():
    markdown = "[![alt](https://cdn/a.png)](https://example.com)\n\n![plain](https://cdn/b.png)"

    assert images.count_images_in_markdown(markdown) == 2


@pytest.mark.parametrize(
    "input_md, expected",
    [
        pytest.param(
            "[![Image 1](/img/test/image1.png)](/img/test/image1.png)",
            "![Image 1](/img/test/image1.png)",
            id="basic_cleaning",
        ),
        pytest.param(
            "Check [this link](https://example.com) and [![photo](img.png)](img.png) and ![plain](other.png)",
            "Check [this link](https://example.com) and ![photo](img.png) and ![plain](other.png)",
            id="mixed_content",
        ),
        pytest.param(
            "[![CDN](https://substackcdn.com/image/fetch/w_1456/https%3A%2F%2Fexample.com%2Fphoto.jpg)](https://substackcdn.com/image/fetch/w_1456/https%3A%2F%2Fexample.com%2Fphoto.jpg)",
            "![CDN](https://substackcdn.com/image/fetch/w_1456/https%3A%2F%2Fexample.com%2Fphoto.jpg)",
            id="substack_cdn_urls",
        ),
        pytest.param(
            "![Already clean](https://example.com/img.png)",
            "![Already clean](https://example.com/img.png)",
            id="no_changes_needed",
        ),
        pytest.param(
            "",
            "",
            id="empty_content",
        ),
        pytest.param(
            "Line one\n\n[![img](a.png)](a.png)\n\nLine three",
            "Line one\n\n![img](a.png)\n\nLine three",
            id="preserve_newlines",
        ),
        pytest.param(
            '[![Image with "quotes" & special](https://example.com/img%20file.png)](https://example.com/img%20file.png)',
            '![Image with "quotes" & special](https://example.com/img%20file.png)',
            id="special_characters",
        ),
    ],
)
def test_clean_linked_images(input_md, expected):
    assert images.clean_linked_images(input_md) == expected


def test_resolve_image_url_passthrough():
    """Non-CDN URLs should pass through unchanged."""
    urls = [
        "https://example.com/photo.jpg",
        "https://bucket.s3.amazonaws.com/image.png",
        "https://i.imgur.com/abc123.gif",
        "/relative/path/image.png",
    ]
    for url in urls:
        assert images.resolve_image_url(url) == url


@patch("scraper.images.download_image")
def test_process_markdown_images(mock_download):
    """Mock requests.get and verify image download + path rewriting."""
    mock_download.return_value = "data/images/testauthor/test-post/photo.jpg"

    md_content = (
        "Some text\n"
        "![alt](https://substackcdn.com/image/fetch/w_1456,c_limit/https%3A%2F%2Fexample.com%2Fphoto.jpg)\n"
        "More text"
    )

    result = images.process_markdown_images(md_content, "testauthor", "test-post")

    # download_image should have been called once
    assert mock_download.call_count == 1

    # The CDN URL should be replaced with a local relative path
    assert "substackcdn.com" not in result
    assert "Some text" in result
    assert "More text" in result


@patch("scraper.images.requests.get")
def test_download_image_error_handling(mock_get, tmp_path):
    """Mock network error, verify graceful handling (returns None)."""
    mock_get.side_effect = ConnectionError("Network unreachable")

    result = images.download_image(
        "https://example.com/image.jpg",
        tmp_path / "image.jpg",
    )

    assert result is None


def test_clean_linked_images_preserves_youtube_thumbnail_links():
    md = "[![YouTube video](https://img.youtube.com/vi/abc/hqdefault.jpg)](https://www.youtube.com/watch?v=abc)"

    assert images.clean_linked_images(md) == md


def test_process_markdown_images_preserves_remote_url_on_download_failure(monkeypatch):
    # Mock download_image to fail (return None)
    monkeypatch.setattr("scraper.images.download_image", lambda *args, **kwargs: None)

    md = "![alt](https://substackcdn.com/image/fetch/w_1456/https%3A%2F%2Fexample.com%2Ffailed.jpg)"
    result = images.process_markdown_images(md, "test_author", "test_slug")

    # URL should be retained rather than replaced with broken local path
    assert "https://substackcdn.com/image/fetch/" in result
    assert "images" not in result


def test_download_image_uses_timeout(monkeypatch, tmp_path):
    mock_get = Mock(side_effect=requests.Timeout("Connection timed out"))
    monkeypatch.setattr("scraper.images.requests.get", mock_get)

    result = images.download_image("https://example.com/img.jpg", tmp_path / "img.jpg", timeout=12, max_retries=1)
    assert result is None
    mock_get.assert_called_once()
    assert mock_get.call_args[1]["timeout"] == 12


def test_process_markdown_images_concurrent_downloads(monkeypatch):
    downloaded_urls = []

    def mock_download(url, save_path, pbar=None, timeout=None):
        downloaded_urls.append(url)
        return str(save_path)

    monkeypatch.setattr("scraper.images.download_image", mock_download)

    md = (
        "![img1](https://substackcdn.com/image/fetch/w_1456/https%3A%2F%2Fexample.com%2F1.jpg)\n"
        "![img2](https://substackcdn.com/image/fetch/w_1456/https%3A%2F%2Fexample.com%2F2.jpg)\n"
        "![img3](https://substackcdn.com/image/fetch/w_1456/https%3A%2F%2Fexample.com%2F3.jpg)\n"
    )

    result = images.process_markdown_images(md, "author", "post", max_workers=3)

    assert len(downloaded_urls) == 3
    assert "https://example.com/1.jpg" in downloaded_urls
    assert "https://example.com/2.jpg" in downloaded_urls
    assert "https://example.com/3.jpg" in downloaded_urls
    assert "substackcdn.com" not in result


def test_download_image_retries_on_failure_and_succeeds(tmp_path):
    mock_resp_fail = Mock()
    mock_resp_fail.status_code = 503

    mock_resp_ok = Mock()
    mock_resp_ok.status_code = 200
    mock_resp_ok.iter_content = Mock(return_value=[b"fake_image_data"])

    dest = tmp_path / "retry_success.jpg"
    with (
        patch("scraper.images.requests.get", side_effect=[mock_resp_fail, mock_resp_ok]) as mock_get,
        patch("scraper.images.sleep") as mock_sleep,
    ):
        result = images.download_image("https://example.com/retry.jpg", dest, max_retries=3)

        assert result == str(dest)
        assert mock_get.call_count == 2
        assert mock_sleep.call_count == 1
        assert dest.read_bytes() == b"fake_image_data"


def test_download_image_fails_after_max_retries(tmp_path):
    mock_resp_fail = Mock()
    mock_resp_fail.status_code = 500

    dest = tmp_path / "retry_fail.jpg"
    with (
        patch("scraper.images.requests.get", side_effect=[mock_resp_fail, mock_resp_fail, mock_resp_fail]) as mock_get,
        patch("scraper.images.sleep") as mock_sleep,
    ):
        result = images.download_image("https://example.com/fail.jpg", dest, max_retries=3)

        assert result is None
        assert mock_get.call_count == 3
        assert mock_sleep.call_count == 2
        assert not dest.exists()
