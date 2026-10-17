import os
import sys
from unittest.mock import MagicMock, Mock, patch

import pytest

import scraper
from scraper import discovery, extract, frontmatter, storage, sync


class FakeScraper(scraper.BaseSubstackScraper):
    def get_url_soup(self, url: str):
        return None


# ---------------------------------------------------------------------------
# Existing tests (preserved)
# ---------------------------------------------------------------------------


def test_resolve_image_url_extracts_original_url():
    cdn_url = (
        "https://substackcdn.com/image/fetch/w_1456,c_limit,f_webp,q_auto:good,"
        "fl_progressive:steep/https%3A%2F%2Fbucket.s3.us-west-2.amazonaws.com%2Fimage.jpg"
    )

    assert scraper.resolve_image_url(cdn_url) == "https://bucket.s3.us-west-2.amazonaws.com/image.jpg"


def test_sanitize_image_filename_uses_resolved_url_name():
    cdn_url = (
        "https://substackcdn.com/image/fetch/w_1456,c_limit,f_webp,q_auto:good,"
        "fl_progressive:steep/https%3A%2F%2Fbucket.s3.us-west-2.amazonaws.com%2Fimage.jpg%3Fv%3D1"
    )

    assert scraper.sanitize_image_filename(cdn_url) == "image.jpg"


def test_count_images_in_markdown_counts_cleaned_linked_images():
    markdown = "[![alt](https://cdn/a.png)](https://example.com)\n\n![plain](https://cdn/b.png)"

    assert scraper.count_images_in_markdown(markdown) == 2


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


def test_parse_args_supports_images_flag(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        ["scraper.py", "--url", "https://example.substack.com/p/post", "--images"],
    )

    args = scraper.parse_args()

    assert args.url == "https://example.substack.com/p/post"
    assert args.images is True


# ---------------------------------------------------------------------------
# New tests
# ---------------------------------------------------------------------------


# 1. Parametrized test_clean_linked_images
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
    assert scraper.clean_linked_images(input_md) == expected


# 2. test_resolve_image_url_passthrough
def test_resolve_image_url_passthrough():
    """Non-CDN URLs should pass through unchanged."""
    urls = [
        "https://example.com/photo.jpg",
        "https://bucket.s3.amazonaws.com/image.png",
        "https://i.imgur.com/abc123.gif",
        "/relative/path/image.png",
    ]
    for url in urls:
        assert scraper.resolve_image_url(url) == url


# 3. test_is_post_url
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
    assert scraper.is_post_url(url) == expected


# 4. test_get_publication_url
@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://example.substack.com/p/my-post", "https://example.substack.com/"),
        ("https://blog.example.com/p/slug", "https://blog.example.com/"),
        ("http://test.substack.com/p/post-name", "http://test.substack.com/"),
    ],
)
def test_get_publication_url(url, expected):
    assert scraper.get_publication_url(url) == expected


# 5. test_get_post_slug
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
    assert scraper.get_post_slug(url) == expected


# 6. test_process_markdown_images
@patch("scraper.download_image")
def test_process_markdown_images(mock_download):
    """Mock requests.get and verify image download + path rewriting."""
    mock_download.return_value = "data/images/testauthor/test-post/photo.jpg"

    md_content = (
        "Some text\n"
        "![alt](https://substackcdn.com/image/fetch/w_1456,c_limit/https%3A%2F%2Fexample.com%2Fphoto.jpg)\n"
        "More text"
    )

    result = scraper.process_markdown_images(md_content, "testauthor", "test-post")

    # download_image should have been called once
    assert mock_download.call_count == 1

    # The CDN URL should be replaced with a local relative path
    assert "substackcdn.com" not in result
    assert "Some text" in result
    assert "More text" in result


# 7. test_download_image_error_handling
@patch("scraper.requests.get")
def test_download_image_error_handling(mock_get, tmp_path):
    """Mock network error, verify graceful handling (returns None)."""
    mock_get.side_effect = ConnectionError("Network unreachable")

    result = scraper.download_image(
        "https://example.com/image.jpg",
        tmp_path / "image.jpg",
    )

    assert result is None


# 8. test_scraper_initialization
def test_scraper_initialization(tmp_path):
    """Verify writer_name and author directory structure are created."""
    content_dir = str(tmp_path / "content")

    scraper = FakeScraper(
        "https://example.substack.com/p/test-post",
        content_save_dir=content_dir,
    )

    assert scraper.writer_name == "example"
    assert os.path.isdir(os.path.join(content_dir, "example", "posts"))


# 9. test_mdx_frontmatter_includes_source_url
def test_mdx_frontmatter_includes_source_url():
    """Verify the post URL is emitted as canonical_url in YAML frontmatter."""
    result = frontmatter.combine_metadata_and_content(
        title="Title",
        subtitle="Subtitle",
        date="2024-01-01",
        author="Author",
        cover_image="",
        content="Body",
        canonical_url="https://example.substack.com/p/test-post",
    )

    assert 'canonical_url: "https://example.substack.com/p/test-post"' in result
    assert result.index('author: "Author"') < result.index("canonical_url:")


# 10. get_credentials
def test_get_credentials_env_vars(monkeypatch):
    monkeypatch.setenv("SUBSTACK_EMAIL", "env@example.com")
    monkeypatch.setenv("SUBSTACK_PASSWORD", "env-secret")

    assert scraper.get_credentials() == ("env@example.com", "env-secret")


def test_get_credentials_empty_when_unconfigured(monkeypatch):
    monkeypatch.delenv("SUBSTACK_EMAIL", raising=False)
    monkeypatch.delenv("SUBSTACK_PASSWORD", raising=False)
    with patch("dotenv.find_dotenv", return_value=""):
        assert scraper.get_credentials() == ("", "")


# 11. YouTube embeds (issue #25)
YOUTUBE_EMBED_HTML = (
    '<div class="available-content"><p>Intro</p>'
    '<div id="youtube2-9FDgRXPSv3U" data-attrs="{&quot;videoId&quot;:&quot;9FDgRXPSv3U&quot;,'
    '&quot;startTime&quot;:null,&quot;endTime&quot;:null}" data-component-name="Youtube2ToDOM" '
    'class="youtube-wrap"><div class="youtube-inner">'
    '<iframe src="https://www.youtube-nocookie.com/embed/9FDgRXPSv3U?rel=0" frameborder="0">'
    "</iframe></div></div><p>Outro</p></div>"
)


def test_youtube_embed_exported_as_linked_thumbnail():
    md = extract.post_html_to_markdown(YOUTUBE_EMBED_HTML)

    assert (
        "[![YouTube video](https://img.youtube.com/vi/9FDgRXPSv3U/hqdefault.jpg)]"
        "(https://www.youtube.com/watch?v=9FDgRXPSv3U)" in md
    )
    assert "Intro" in md and "Outro" in md


def test_youtube_embed_with_malformed_attrs_is_skipped():
    html = '<div class="youtube-wrap" data-attrs="not-json"><iframe src="x"></iframe></div><p>Body</p>'

    md = extract.post_html_to_markdown(html)

    assert "Body" in md


def test_clean_linked_images_preserves_youtube_thumbnail_links():
    md = "[![YouTube video](https://img.youtube.com/vi/abc/hqdefault.jpg)](https://www.youtube.com/watch?v=abc)"

    assert scraper.clean_linked_images(md) == md


# 12. Security & XSS Prevention
def test_safe_json_embed_escapes_html_tags():
    payload = {"title": "</script><script>alert(1)</script>", "data": "a & b < c > d"}
    embedded = scraper.safe_json_embed(payload)

    assert "</script>" not in embedded
    assert "<" not in embedded
    assert ">" not in embedded
    assert "\\u003c/script\\u003e" in embedded
    assert "\\u0026" in embedded


# 13. CLI & Defaults
def test_default_use_premium_is_false():
    assert scraper.USE_PREMIUM is False


def test_main_bare_command_shows_help_and_exits(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["scraper.py"])
    with pytest.raises(SystemExit) as exc_info:
        scraper.main()
    assert exc_info.value.code != 0
    captured = capsys.readouterr()
    assert "--url" in captured.err or "--url" in captured.out
    assert "--premium" in captured.err or "--premium" in captured.out


# 14. Network Timeouts & Reliability
def test_process_markdown_images_preserves_remote_url_on_download_failure(monkeypatch):
    # Mock download_image to fail (return None)
    monkeypatch.setattr(scraper, "download_image", lambda *args, **kwargs: None)

    md = "![alt](https://substackcdn.com/image/fetch/w_1456/https%3A%2F%2Fexample.com%2Ffailed.jpg)"
    result = scraper.process_markdown_images(md, "test_author", "test_slug")

    # URL should be retained rather than replaced with broken local path
    assert "https://substackcdn.com/image/fetch/" in result
    assert "images" not in result


def test_download_image_uses_timeout(monkeypatch, tmp_path):
    mock_get = Mock(side_effect=scraper.requests.Timeout("Connection timed out"))
    monkeypatch.setattr(scraper.requests, "get", mock_get)

    result = scraper.download_image("https://example.com/img.jpg", tmp_path / "img.jpg", timeout=12, max_retries=1)
    assert result is None
    mock_get.assert_called_once()
    assert mock_get.call_args[1]["timeout"] == 12


# 15. Custom Domains & Output Directories
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
    assert scraper.extract_main_part(url) == expected


# 16. Concurrency & Performance
def test_process_markdown_images_concurrent_downloads(monkeypatch):
    downloaded_urls = []

    def mock_download(url, save_path, pbar=None, timeout=None):
        downloaded_urls.append(url)
        return str(save_path)

    monkeypatch.setattr(scraper, "download_image", mock_download)

    md = (
        "![img1](https://substackcdn.com/image/fetch/w_1456/https%3A%2F%2Fexample.com%2F1.jpg)\n"
        "![img2](https://substackcdn.com/image/fetch/w_1456/https%3A%2F%2Fexample.com%2F2.jpg)\n"
        "![img3](https://substackcdn.com/image/fetch/w_1456/https%3A%2F%2Fexample.com%2F3.jpg)\n"
    )

    result = scraper.process_markdown_images(md, "author", "post", max_workers=3)

    assert len(downloaded_urls) == 3
    assert "https://example.com/1.jpg" in downloaded_urls
    assert "https://example.com/2.jpg" in downloaded_urls
    assert "https://example.com/3.jpg" in downloaded_urls
    assert "substackcdn.com" not in result


# 17. Credentials & .env loading
def test_get_credentials_loads_from_env_file(tmp_path, monkeypatch):
    monkeypatch.delenv("SUBSTACK_EMAIL", raising=False)
    monkeypatch.delenv("SUBSTACK_PASSWORD", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("SUBSTACK_EMAIL=env_user@example.com\nSUBSTACK_PASSWORD=env_pass\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    email, password = scraper.get_credentials()
    assert email == "env_user@example.com"
    assert password == "env_pass"


# 18. Playwright BrowserManager & PremiumScraper Tests
def test_browser_manager_get_user_data_dir():
    profile_dir = scraper.BrowserManager.get_user_data_dir("chrome")
    assert "chrome_profile" in profile_dir
    assert ".substack_scraper" in profile_dir


def test_browser_manager_resolve_channel():
    mock_pw = MagicMock()
    mock_browser = MagicMock()
    mock_pw.chromium.launch.return_value = mock_browser

    resolved = scraper.BrowserManager.resolve_channel("chrome", mock_pw)
    assert resolved in ("chrome", "msedge")
    assert mock_browser.close.called


def test_browser_manager_launch_cdp():
    mock_pw_instance = MagicMock()
    mock_cdp_browser = MagicMock()
    mock_context = MagicMock()
    mock_cdp_browser.contexts = [mock_context]
    mock_pw_instance.chromium.connect_over_cdp.return_value = mock_cdp_browser

    with patch("scraper.browser.sync_playwright") as mock_sync_pw:
        mock_sync_pw.return_value.start.return_value = mock_pw_instance
        session = scraper.BrowserManager.launch(cdp_url="http://localhost:9222")
        assert session.context == mock_context
        mock_pw_instance.chromium.connect_over_cdp.assert_called_once_with("http://localhost:9222")


def test_premium_scraper_requires_credentials_when_not_skipping():
    with (
        patch("scraper.scrapers.premium.get_credentials", return_value=("", "")),
        patch(
            "scraper.scrapers.premium.BrowserManager.DEFAULT_STORAGE_STATE_PATH",
            "/nonexistent/path/storage.json",
        ),
    ):
        with pytest.raises(ValueError, match="Premium scraping requires credentials"):
            scraper.PremiumSubstackScraper(
                base_substack_url="https://example.substack.com",
                content_save_dir="content",
                skip_login=False,
            )


def test_premium_scraper_init_with_skip_login():
    mock_session = MagicMock()
    mock_context = MagicMock()
    mock_page = MagicMock()
    mock_context.pages = [mock_page]
    mock_session.context = mock_context

    with patch("scraper.scrapers.premium.BrowserManager.launch", return_value=mock_session):
        premium_scraper = scraper.PremiumSubstackScraper(
            base_substack_url="https://example.substack.com",
            content_save_dir="content",
            skip_login=True,
        )
        assert premium_scraper.skip_login is True
        mock_page.goto.assert_called_once_with("https://example.substack.com", wait_until="domcontentloaded")


# 19. Rescraping and Image Retry Tests
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
        result = scraper.download_image("https://example.com/retry.jpg", dest, max_retries=3)

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
        result = scraper.download_image("https://example.com/fail.jpg", dest, max_retries=3)

        assert result is None
        assert mock_get.call_count == 3
        assert mock_sleep.call_count == 2
        assert not dest.exists()


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
    monkeypatch.setattr("scraper.scrapers.base.extract_post_data", mock_extract)
    monkeypatch.setattr("scraper.scrapers.base.save_to_file", mock_save)

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
    scraper.get_url_soup = Mock(return_value=mock_soup)

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
    monkeypatch.setattr("scraper.scrapers.base.extract_post_data", mock_extract)
    monkeypatch.setattr("scraper.scrapers.base.save_to_file", mock_save)

    scraper.scrape_posts()

    mock_extract.assert_called_once_with(mock_soup, "https://example.substack.com/p/test-post", clean_content=True)
    mock_save.assert_called_once()
    assert mock_save.call_args[1]["overwrite"] is True


def test_cli_force_flag_sets_overwrite(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        ["scraper.py", "--url", "https://example.substack.com", "--force"],
    )
    args = scraper.parse_args()
    assert args.overwrite is True

    monkeypatch.setattr(
        sys,
        "argv",
        ["scraper.py", "--url", "https://example.substack.com", "--overwrite"],
    )
    args_alias = scraper.parse_args()
    assert args_alias.overwrite is True


# 20. Catalog & Metadata Synchronization Tests


def test_extract_post_id_from_preloads():
    html = (
        "<html><head><script>"
        'window._preloads = JSON.parse("{\\"post\\":{\\"id\\":214748970,\\"slug\\":\\"codex\\"}}");'
        "</script></head></html>"
    )
    post_id = extract._extract_post_id(html)
    assert post_id == 214748970


def test_extract_post_id_returns_none_when_missing():
    html = "<html><head><title>No post ID</title></head></html>"
    post_id = extract._extract_post_id(html)
    assert post_id is None


def test_combine_metadata_and_content_includes_post_id():
    markdown_output = frontmatter.combine_metadata_and_content(
        title="Codex Post",
        subtitle="Inside OpenAI",
        date="2026-09-09",
        author="Gergely",
        cover_image="",
        content="Post body",
        source_url="https://example.substack.com/p/codex",
        post_id=214748970,
    )
    assert "post_id: 214748970" in markdown_output
    assert 'title: "Codex Post"' in markdown_output


def test_extract_metadata_from_md_mdx_format(tmp_path):
    md_file = tmp_path / "post.md"
    md_file.write_text(
        '---\ntitle: "Codex Post"\npost_id: 214748970\ndate: "2026-09-09"\nauthor: "Gergely"\n---\n\nBody',
        encoding="utf-8",
    )
    metadata = frontmatter.extract_metadata_from_md(str(md_file))
    assert metadata is not None
    assert metadata["title"] == "Codex Post"
    assert metadata["post_id"] == 214748970
    assert metadata["date"] == "2026-09-09"
    assert metadata["author"] == "Gergely"


def test_clean_post_html_strips_widgets_and_footers():
    html = (
        '<div class="available-content">'
        "<p>Real content</p>"
        '<div class="subscription-widget-wrap"><input placeholder="email"/></div>'
        '<div class="post-footer"><button>Share</button></div>'
        "</div>"
    )
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    extract._clean_post_html(soup)
    cleaned_str = str(soup)
    assert "Real content" in cleaned_str
    assert "subscription-widget-wrap" not in cleaned_str
    assert "post-footer" not in cleaned_str


def test_convert_html_to_markdown_code_block_language_fences():
    """Verify code block language syntax is preserved from code class."""
    html_content = '<pre><code class="language-python">def hello():\n    return "world"</code></pre>'
    markdown_output = scraper.convert_html_to_markdown(html_content)
    assert "```python" in markdown_output
    assert 'def hello():\n    return "world"' in markdown_output
    assert markdown_output.strip().endswith("```")


def test_convert_html_to_markdown_pre_tag_language_fences():
    """Verify code block language syntax is preserved when declared on pre element."""
    html_content = '<pre class="language-typescript"><code>const value: number = 42;</code></pre>'
    markdown_output = scraper.convert_html_to_markdown(html_content)
    assert "```typescript" in markdown_output
    assert "const value: number = 42;" in markdown_output
    assert markdown_output.strip().endswith("```")


def test_convert_html_to_markdown_gfm_tables():
    """Verify tables are converted to GFM markdown tables with proper column delimiters."""
    table_html = """
    <table>
        <thead>
            <tr><th>Header A</th><th>Header B</th></tr>
        </thead>
        <tbody>
            <tr><td>Cell 1</td><td>Cell 2</td></tr>
        </tbody>
    </table>
    """
    table_markdown = scraper.convert_html_to_markdown(table_html)
    assert "| Header A | Header B |" in table_markdown
    assert "| -------- | -------- |" in table_markdown
    assert "Cell 1" in table_markdown
    assert "Cell 2" in table_markdown


def test_convert_html_to_markdown_preserves_link_emphasis_boundary_whitespace():
    """Verify boundary whitespace inside emphasis around links is cleanly preserved."""
    emphasis_html = '<p>You can <em>RSVP <a href="https://example.com">via this link</a></em> today.</p>'
    emphasis_markdown = scraper.convert_html_to_markdown(emphasis_html)
    assert "*RSVP [via this link](https://example.com)*" in emphasis_markdown
    assert "RSVP[" not in emphasis_markdown


def test_convert_html_to_markdown_image_alt_normalization():
    """Verify images without alt attributes receive 'image' alt for MD045 compliance."""
    image_html = '<p><img src="https://example.com/photo.png"></p>'
    image_markdown = scraper.convert_html_to_markdown(image_html)
    assert "![image](https://example.com/photo.png)" in image_markdown

    custom_alt_html = '<p><img src="https://example.com/photo.png" alt="Custom Alt"></p>'
    custom_alt_markdown = scraper.convert_html_to_markdown(custom_alt_html)
    assert "![Custom Alt](https://example.com/photo.png)" in custom_alt_markdown


def test_convert_html_to_markdown_empty_input():
    """Verify empty, whitespace-only, or None inputs safely return None."""
    assert scraper.convert_html_to_markdown(None) is None
    assert scraper.convert_html_to_markdown("") is None
    assert scraper.convert_html_to_markdown("   \n\t  ") is None


def test_html_to_md_empty_content():
    """Verify post_html_to_markdown safely returns empty string when content is empty or whitespace."""
    assert extract.post_html_to_markdown("") == ""
    assert extract.post_html_to_markdown("   ") == ""


def test_extract_preloaded_post_data():
    html = (
        "<html><head><script>"
        'window._preloads = JSON.parse("{\\"post\\":{\\"id\\":1234,\\"description\\":\\"A summary\\",\\"wordcount\\":500,\\"audience\\":\\"only_paid\\",\\"canonical_url\\":\\"https://example.com/p/test\\",\\"postTags\\":[{\\"name\\":\\"tech\\"},{\\"name\\":\\"ai\\"}]}}");'
        "</script></head></html>"
    )
    data = extract._extract_preloaded_post_data(html)
    assert data["post_id"] == 1234
    assert data["description"] == "A summary"
    assert data["wordcount"] == 500
    assert data["audience"] == "only_paid"
    assert data["canonical_url"] == "https://example.com/p/test"
    assert data["tags"] == ["tech", "ai"]


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
    storage.save_posts_data_to_json(scraper.metadata_file_path, initial_entries)

    updated_entries = [
        {
            "post_id": 12345,
            "title": "Updated Title With New Headline",
            "slug": "new-renamed-slug",
            "file_link": "posts/new-renamed-slug.md",
        }
    ]
    storage.save_posts_data_to_json(scraper.metadata_file_path, updated_entries)

    import json

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

    storage.save_posts_data_to_json(scraper.metadata_file_path, [{"post_id": 101, "title": "First"}])
    storage.save_posts_data_to_json(scraper.metadata_file_path, [{"post_id": 102, "title": "Second"}])

    import json

    with open(tmp_path / "example" / "metadata.json", encoding="utf-8") as file:
        saved_data = json.load(file)

    assert len(saved_data) == 2
    assert saved_data[0]["post_id"] == 101
    assert saved_data[1]["post_id"] == 102


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

    import json

    metadata_path = content_dir / "example" / "metadata.json"
    with open(metadata_path, encoding="utf-8") as file:
        saved_data = json.load(file)

    assert len(saved_data) == 1
    assert saved_data[0]["post_id"] == 8888
    assert saved_data[0]["title"] == "Existing Preserved"
    assert saved_data[0]["slug"] == "test-post"


def test_parse_args_verbose_and_quiet_mutually_exclusive(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        ["scraper", "--url", "https://example.substack.com", "-v", "-q"],
    )
    with pytest.raises(SystemExit):
        scraper.parse_args()


def test_parse_args_verbose_flag(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        ["scraper", "--url", "https://example.substack.com", "--verbose"],
    )
    args = scraper.parse_args()
    assert args.verbose is True
    assert args.quiet is False


def test_parse_args_quiet_flag(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        ["scraper", "--url", "https://example.substack.com", "-q"],
    )
    args = scraper.parse_args()
    assert args.quiet is True
    assert args.verbose is False


def test_premium_auto_skip_login_when_credentials_missing_but_profile_exists(tmp_path, monkeypatch):
    profile_dir = tmp_path / "chrome_profile"
    profile_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr("scraper.scrapers.premium.get_credentials", lambda: (None, None))
    monkeypatch.setattr(scraper.BrowserManager, "get_user_data_dir", lambda browser: str(profile_dir))

    fake_session = MagicMock()
    fake_session.context.pages = [MagicMock()]
    monkeypatch.setattr(scraper.BrowserManager, "launch", lambda **kwargs: fake_session)

    premium_scraper = scraper.PremiumSubstackScraper(
        base_substack_url="https://example.substack.com/p/premium-post",
        content_save_dir=str(tmp_path / "content"),
        use_persistent_profile=True,
    )
    assert premium_scraper.skip_login is True


def test_base_and_free_scrapers_use_logging(tmp_path, caplog):
    import logging

    content_dir = tmp_path / "content"

    with caplog.at_level(logging.INFO):
        scraper = FakeScraper(
            "https://example.substack.com/p/test-post",
            content_save_dir=str(content_dir),
        )

    assert scraper.writer_name == "example"
    assert any("Created posts directory" in record.message for record in caplog.records)


def test_clean_post_html_strips_comment_and_promo_buttons():
    html = """
    <div class="available-content">
        <p>This is the real article body paragraph.</p>
        <p class="button-wrapper">
            <a class="button primary" href="https://example.substack.com/p/test-slug/comments">
                <span>Leave a comment</span>
            </a>
        </p>
        <p class="button-wrapper">
            <a class="button primary" href="https://example.substack.com/subscribe">
                <span>Subscribe now</span>
            </a>
        </p>
        <p>Here is another legitimate paragraph mentioning to leave a comment if you like.</p>
        <div class="post-footer">Footer promo content</div>
    </div>
    """
    md = extract.post_html_to_markdown(html, clean_content=True)
    assert "This is the real article body paragraph." in md
    assert "Here is another legitimate paragraph mentioning to leave a comment if you like." in md
    assert "[Leave a comment]" not in md
    assert "[Subscribe now]" not in md
    assert "Footer promo content" not in md


def test_html_to_md_formats_cleanly_with_mdformat():
    """Verify html_to_md normalizes lists with dashes, default alt text, and mdformat formatting."""
    html = """
    <div class="available-content">
        <p>Introductory text.</p>
        <ul>
            <li>First item</li>
            <li>Second item</li>
        </ul>
        <img src="https://example.com/photo.png">
        <blockquote>
            <p>A quote here.</p>
        </blockquote>
    </div>
    """
    md = extract.post_html_to_markdown(html)
    assert "- First item" in md
    assert "- Second item" in md
    assert "* First item" not in md
    assert "![image](https://example.com/photo.png)" in md
    assert "> A quote here." in md


def test_combine_metadata_and_content_trailing_newline():
    """Verify combine_metadata_and_content always terminates with a newline character."""
    output = frontmatter.combine_metadata_and_content(
        title="Sample Post",
        subtitle="",
        date="2026-09-26",
        author="Author",
        cover_image="",
        content="Hello world",
    )
    assert output.endswith("\n")
    assert not output.endswith("\n\n\n")


def test_save_to_file_ensures_trailing_newline(tmp_path):
    """Verify save_to_file guarantees a trailing newline on written files."""
    file_path = str(tmp_path / "test.md")
    storage.save_to_file(file_path, "no newline at end")
    with open(file_path, encoding="utf-8") as f:
        saved_text = f.read()
    assert saved_text.endswith("\n")


def test_check_markdown_script_functions(tmp_path):
    """Verify check_markdown CLI utility formatting and violation parsing."""
    import importlib.util
    from pathlib import Path

    script_path = Path(__file__).resolve().parent.parent / "scripts" / "check_markdown.py"
    spec = importlib.util.spec_from_file_location("check_markdown", script_path)
    assert spec is not None and spec.loader is not None
    check_md = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(check_md)

    # Test parser
    raw_lines = [
        "file.md:10:1: MD007: Unordered list indentation [Expected: 0, Actual=2] (ul-indent)",
        "file.md:20:1: MD045: Images should have alternate text (alt text) (no-alt-text)",
    ]
    violations = check_md._parse_violations(raw_lines)
    assert len(violations) == 2
    assert violations[0].rule == "MD007"
    assert violations[1].rule == "MD045"

    # Test file fixing with mdformat
    sample_file = tmp_path / "sample.md"
    sample_file.write_text(
        '---\ntitle: "Test"\n---\n\n* Unordered list item 1\n* Unordered list item 2\n\n',
        encoding="utf-8",
    )
    modified, unchanged = check_md._fix_markdown_files([sample_file])
    assert modified == 1
    assert unchanged == 0
    formatted_content = sample_file.read_text(encoding="utf-8")
    assert "- Unordered list item 1" in formatted_content
    assert formatted_content.endswith("\n")


# 21. Incremental Delta Sync Tests


def test_parse_args_supports_sync_flag(monkeypatch):
    """Verify --sync flag parses successfully in CLI arguments."""
    monkeypatch.setattr(
        sys,
        "argv",
        ["scraper", "--url", "https://example.substack.com", "--sync"],
    )
    args = scraper.parse_args()
    assert args.sync is True


def test_parse_args_sync_and_number_mutually_exclusive(monkeypatch):
    """Verify --sync and -n/--number cannot be used together."""
    monkeypatch.setattr(
        sys,
        "argv",
        ["scraper", "--url", "https://example.substack.com", "--sync", "-n", "5"],
    )
    with pytest.raises(SystemExit):
        scraper.parse_args()


def test_parse_args_sync_and_single_post_mutually_exclusive(monkeypatch):
    """Verify --sync cannot be used with an individual post URL."""
    monkeypatch.setattr(
        sys,
        "argv",
        ["scraper", "--url", "https://example.substack.com/p/my-post", "--sync"],
    )
    with pytest.raises(SystemExit):
        scraper.parse_args()


def test_sync_state_load_and_save(tmp_path):
    """Verify sync state persistence and loading."""
    scraper = FakeScraper("https://example.substack.com", content_save_dir=str(tmp_path))
    assert sync.load_sync_state(scraper.author_dir, scraper.metadata_file_path) is None

    test_state = {
        "last_sync_at": "2026-09-27T10:00:00Z",
        "last_post_date": "2026-09-26T18:30:00.000Z",
        "last_post_id": 12345,
        "last_post_slug": "test-slug",
        "total_synced_posts": 10,
    }
    sync.save_sync_state(scraper.author_dir, test_state)

    loaded = sync.load_sync_state(scraper.author_dir, scraper.metadata_file_path)
    assert loaded == test_state


def test_sync_state_bootstraps_from_metadata_json(tmp_path):
    """Verify cursor bootstrapping from existing metadata.json if sync_state.json is missing."""
    import json

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
    bootstrapped = sync.load_sync_state(scraper.author_dir, scraper.metadata_file_path)

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

    class FakeResponse:
        def __init__(self, data, ok=True, status_code=200, content=b"<urlset></urlset>"):
            self._data = data
            self.ok = ok
            self.status_code = status_code
            self.content = content

        def json(self):
            return self._data

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

    monkeypatch.setattr(scraper.requests, "get", fake_get)

    fake_scraper = FakeScraper("https://example.substack.com")

    # Cutoff at post-2 (date 2026-09-20)
    delta = sync.fetch_posts_from_api(
        fake_scraper.base_substack_url,
        since_date="2026-09-20T12:00:00.000Z",
        limit=2,
    )
    assert len(delta) == 1
    assert delta[0]["id"] == 300
    assert len(api_calls) == 1


def test_fetch_posts_from_api_handles_api_failure(monkeypatch):
    """Verify API network failure or non-200 status returns None gracefully."""

    class FakeErrorResponse:
        ok = False
        status_code = 500

        def json(self):
            return {}

    monkeypatch.setattr(scraper.requests, "get", lambda url, timeout=30: FakeErrorResponse())

    fake_scraper = FakeScraper("https://example.substack.com")
    result = sync.fetch_posts_from_api(fake_scraper.base_substack_url)
    assert result is None


def test_sync_posts_raises_on_single_post():
    """Verify sync_posts raises ValueError if initialized on a single post URL."""
    scraper = FakeScraper("https://example.substack.com/p/my-post")
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

    monkeypatch.setattr("scraper.scrapers.base.fetch_posts_from_api", Mock(return_value=[]))

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
    monkeypatch.setattr("scraper.scrapers.base.fetch_posts_from_api", Mock(return_value=delta_api_posts))

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
    monkeypatch.setattr("scraper.scrapers.base.save_posts_data_to_json", save_posts_mock)

    synced_count = scraper.sync_posts()
    assert synced_count == 2
    assert scraped_urls == [
        "https://example.substack.com/p/intermediate-post",
        "https://example.substack.com/p/newest-post",
    ]

    save_posts_mock.assert_called_once()
    updated_cursor = sync.load_sync_state(scraper.author_dir, scraper.metadata_file_path)
    assert updated_cursor["last_post_date"] == "2026-09-25T15:00:00.000Z"
    assert updated_cursor["last_post_id"] == 200
    assert updated_cursor["last_post_slug"] == "newest-post"
    assert updated_cursor["total_synced_posts"] == 12


def test_is_cutoff_reached_predicate():
    """Verify _is_cutoff_reached predicate matches by post_id, slug, and timestamp comparisons."""
    from datetime import UTC, datetime

    # Exact ID match
    assert sync._is_cutoff_reached({"id": 123}, last_post_id=123) is True
    assert sync._is_cutoff_reached({"id": 456}, last_post_id=123) is False

    # Exact slug match
    assert sync._is_cutoff_reached({"slug": "target-slug"}, last_post_slug="target-slug") is True
    assert sync._is_cutoff_reached({"slug": "other-slug"}, last_post_slug="target-slug") is False

    # Timestamp comparison
    post_item = {"post_date": "2026-09-20T12:00:00.000Z"}
    datetime_same = datetime(2026, 9, 20, 12, 0, tzinfo=UTC)
    datetime_later = datetime(2026, 9, 21, 0, 0, tzinfo=UTC)
    datetime_earlier = datetime(2026, 9, 19, 0, 0, tzinfo=UTC)

    assert sync._is_cutoff_reached(post_item, since_datetime=datetime_same) is True
    assert sync._is_cutoff_reached(post_item, since_datetime=datetime_later) is True
    assert sync._is_cutoff_reached(post_item, since_datetime=datetime_earlier) is False

    # Date-only format comparison
    datetime_day_same = datetime(2026, 9, 20, tzinfo=UTC)
    datetime_day_next = datetime(2026, 9, 21, tzinfo=UTC)
    assert sync._is_cutoff_reached(post_item, since_datetime=datetime_day_same, is_date_only=True) is False
    assert sync._is_cutoff_reached(post_item, since_datetime=datetime_day_next, is_date_only=True) is True


# 22. CLI Validation & Incompatible Option Guards


@pytest.mark.parametrize(
    "flag_args",
    [
        ["--headless"],
        ["--persistent-profile"],
        ["--skip-login"],
        ["--storage-state", "cookies.json"],
        ["--cdp-url", "http://localhost:9222"],
        ["--browser-path", "/usr/bin/chrome"],
        ["--user-agent", "custom-agent"],
        ["--browser", "edge"],
    ],
)
def test_cli_validation_browser_flags_require_premium(flag_args, capsys):
    """Verify browser automation flags without -p / --premium raise an error."""
    with pytest.raises(SystemExit) as exc_info:
        scraper.parse_args(["--url", "https://example.substack.com", *flag_args])
    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert "require the -p / --premium flag" in captured.err


@pytest.mark.parametrize(
    "incompatible_args",
    [
        ["--headless"],
        ["--browser", "edge"],
        ["--browser-path", "/bin/chrome"],
        ["--persistent-profile"],
        ["--storage-state", "state.json"],
    ],
)
def test_cli_validation_cdp_url_incompatibilities(incompatible_args, capsys):
    """Verify --cdp-url cannot be combined with browser launch options."""
    cmd = [
        "--url",
        "https://example.substack.com",
        "--premium",
        "--cdp-url",
        "http://localhost:9222",
        *incompatible_args,
    ]
    with pytest.raises(SystemExit) as exc_info:
        scraper.parse_args(cmd)
    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert "--cdp-url attaches directly to an active external browser window" in captured.err


def test_cli_validation_persistent_profile_and_storage_state_mutually_exclusive(capsys):
    """Verify --persistent-profile and --storage-state cannot be used together."""
    cmd = [
        "--url",
        "https://example.substack.com",
        "--premium",
        "--persistent-profile",
        "--storage-state",
        "cookies.json",
    ]
    with pytest.raises(SystemExit) as exc_info:
        scraper.parse_args(cmd)
    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert "mutually exclusive session persistence strategies" in captured.err


def test_cli_validation_single_post_number_guard(capsys):
    """Verify scraping an individual post with --number > 1 raises an error."""
    cmd = ["--url", "https://example.substack.com/p/my-post", "--number", "5"]
    with pytest.raises(SystemExit) as exc_info:
        scraper.parse_args(cmd)
    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert "--number cannot be greater than 1 when scraping a single post URL" in captured.err


def test_cli_validation_valid_single_post_number_one():
    """Verify scraping an individual post with --number 1 or default 0 is allowed."""
    args = scraper.parse_args(["--url", "https://example.substack.com/p/my-post", "--number", "1"])
    assert args.number == 1

    args_default = scraper.parse_args(["--url", "https://example.substack.com/p/my-post"])
    assert args_default.number == 0


# 23. Python Scraper Deduplication & Rate-Limit Backoff


def test_is_rate_limited_detection():
    """Verify _is_rate_limited correctly identifies 429 pre tags."""
    from bs4 import BeautifulSoup

    from scraper.scrapers.base import BaseSubstackScraper

    rate_limited_html = "<html><body><pre>error: too many requests, please slow down</pre></body></html>"
    normal_html = "<html><body><pre>code block</pre><div>content</div></body></html>"
    empty_html = "<html><body><div>content only</div></body></html>"

    assert BaseSubstackScraper._is_rate_limited(BeautifulSoup(rate_limited_html, "html.parser")) is True
    assert BaseSubstackScraper._is_rate_limited(BeautifulSoup(normal_html, "html.parser")) is False
    assert BaseSubstackScraper._is_rate_limited(BeautifulSoup(empty_html, "html.parser")) is False


def test_compute_backoff_delay_range():
    """Verify _compute_backoff_delay produces values within jittered bounds."""
    from scraper.scrapers.base import BaseSubstackScraper

    for attempt in range(1, 5):
        base_delay = 2.0**attempt
        delay = BaseSubstackScraper._compute_backoff_delay(attempt, jitter_ratio=0.2)
        assert 0.8 * base_delay <= delay <= 1.2 * base_delay


def test_handle_rate_limit_backs_off_and_raises_at_max(monkeypatch):
    """Verify _handle_rate_limit sleeps on transient rate-limit and raises on max attempts."""
    from bs4 import BeautifulSoup

    from scraper.scrapers.base import BaseSubstackScraper

    rate_limited_soup = BeautifulSoup("<pre>Too Many Requests</pre>", "html.parser")
    normal_soup = BeautifulSoup("<div>Clean content</div>", "html.parser")

    # Not rate limited returns False immediately without sleeping
    slept_durations: list[float] = []
    monkeypatch.setattr("scraper.scrapers.base.sleep", lambda duration: slept_durations.append(duration))

    assert (
        BaseSubstackScraper._handle_rate_limit(normal_soup, attempt=1, max_attempts=3, url="https://example.com")
        is False
    )
    assert len(slept_durations) == 0

    # Rate limited on attempt 1 sleeps and returns True
    assert (
        BaseSubstackScraper._handle_rate_limit(rate_limited_soup, attempt=1, max_attempts=3, url="https://example.com")
        is True
    )
    assert len(slept_durations) == 1
    assert slept_durations[0] > 0

    # Rate limited on attempt == max_attempts raises RuntimeError
    with pytest.raises(RuntimeError, match="Max attempts reached"):
        BaseSubstackScraper._handle_rate_limit(rate_limited_soup, attempt=3, max_attempts=3, url="https://example.com")


def test_extract_post_body_element_and_html_fallbacks():
    """Verify _extract_post_body_element finds available-content, body.markup, or single-post."""
    from bs4 import BeautifulSoup

    # 1. Available content
    soup_primary = BeautifulSoup('<div class="available-content"><p>Primary</p></div>', "html.parser")
    element = extract._extract_post_body_element(soup_primary)
    assert element is not None
    assert "Primary" in element.text

    # 2. Body markup fallback
    soup_fallback_1 = BeautifulSoup('<div class="body markup"><p>Fallback 1</p></div>', "html.parser")
    element_fallback_1 = extract._extract_post_body_element(soup_fallback_1)
    assert element_fallback_1 is not None
    assert "Fallback 1" in element_fallback_1.text

    # 3. Single post fallback
    soup_fallback_2 = BeautifulSoup('<article class="single-post"><p>Fallback 2</p></article>', "html.parser")
    element_fallback_2 = extract._extract_post_body_element(soup_fallback_2)
    assert element_fallback_2 is not None
    assert "Fallback 2" in element_fallback_2.text

    # 4. None present
    soup_empty = BeautifulSoup("<div><p>Empty</p></div>", "html.parser")
    assert extract._extract_post_body_element(soup_empty) is None


def test_playwright_timeout_constants():
    """Verify centralized Playwright timeouts are exported and have positive values."""
    from scraper.config import (
        PLAYWRIGHT_CONTENT_RENDER_TIMEOUT_MS,
        PLAYWRIGHT_HYDRATION_TIMEOUT_MS,
        PLAYWRIGHT_LOGIN_TIMEOUT_SECONDS,
        PLAYWRIGHT_NAVIGATION_TIMEOUT_MS,
        PLAYWRIGHT_SELECTOR_TIMEOUT_MS,
    )

    assert PLAYWRIGHT_NAVIGATION_TIMEOUT_MS > 0
    assert PLAYWRIGHT_CONTENT_RENDER_TIMEOUT_MS > 0
    assert PLAYWRIGHT_HYDRATION_TIMEOUT_MS > 0
    assert PLAYWRIGHT_SELECTOR_TIMEOUT_MS > 0
    assert PLAYWRIGHT_LOGIN_TIMEOUT_SECONDS > 0


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

    class FakeResponse:
        ok = True
        status_code = 200
        content = sitemap_xml

    monkeypatch.setattr(scraper.requests, "get", lambda url, timeout=30: FakeResponse())
    urls = discovery.discover_post_urls("https://example.substack.com")
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
        class FakeResponse:
            def __init__(self, ok, status_code, content):
                self.ok = ok
                self.status_code = status_code
                self.content = content

        if "sitemap.xml" in url:
            return FakeResponse(False, 404, b"Not Found")
        return FakeResponse(True, 200, feed_xml)

    monkeypatch.setattr(scraper.requests, "get", fake_get)
    urls = discovery.discover_post_urls("https://example.substack.com")
    assert urls == [
        "https://example.substack.com/p/feed-post-1",
        "https://example.substack.com/p/feed-post-2",
    ]


def test_get_slug_from_url_handles_post_and_non_post_urls():
    """Verify get_slug_from_url extracts slug from /p/ URLs and generic URLs."""
    from scraper.url_utils import get_slug_from_url

    assert get_slug_from_url("https://example.substack.com/p/my-cool-post") == "my-cool-post"
    assert get_slug_from_url("https://example.substack.com/p/my-cool-post?r=123") == "my-cool-post"
    assert get_slug_from_url("https://example.substack.com/custom-page/") == "custom-page"
    assert get_slug_from_url("https://example.substack.com/custom-page") == "custom-page"


def test_extract_post_data_reports_title_and_body_found_flags():
    """Verify extract_post_data returns title_found and body_found boolean flags accurately."""
    from bs4 import BeautifulSoup

    # Valid post with title and body
    html_valid = """
    <html>
        <head><title>Page Title</title></head>
        <body>
            <h1 class="post-title">Real Title</h1>
            <div class="available-content"><p>Body text</p></div>
        </body>
    </html>
    """
    soup_valid = BeautifulSoup(html_valid, "html.parser")
    result_valid = extract.extract_post_data(soup_valid, "https://example.substack.com/p/valid")
    assert result_valid["title_found"] is True
    assert result_valid["body_found"] is True
    assert result_valid["title"] == "Real Title"
    assert "Body text" in result_valid["md_content"]

    # Post without body
    html_no_body = """
    <html>
        <head><title>Page Title</title></head>
        <body>
            <h1 class="post-title">Title Only</h1>
        </body>
    </html>
    """
    soup_no_body = BeautifulSoup(html_no_body, "html.parser")
    result_no_body = extract.extract_post_data(soup_no_body, "https://example.substack.com/p/no-body")
    assert result_no_body["title_found"] is True
    assert result_no_body["body_found"] is False


def test_scrape_single_post_dumps_debug_html_on_extraction_failure(tmp_path):
    """Verify _scrape_single_post dumps debug HTML when extraction fails."""
    scraper_instance = FakeScraper("https://example.substack.com", content_save_dir=str(tmp_path))

    from bs4 import BeautifulSoup

    invalid_soup = BeautifulSoup("<html><body><div>No body</div></body></html>", "html.parser")
    scraper_instance.get_url_soup = Mock(return_value=invalid_soup)

    result = scraper_instance._scrape_single_post("https://example.substack.com/p/bad-post")
    assert result is None

    debug_file = tmp_path / "_debug" / "example" / "bad-post.html"
    assert debug_file.exists()
    assert "No body" in debug_file.read_text(encoding="utf-8")
