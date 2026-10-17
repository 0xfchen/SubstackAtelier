"""Tests for Substack DOM extraction, preloads parsing, HTML cleaning, and embeds."""

from bs4 import BeautifulSoup

from scraper import extract

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


def test_clean_post_html_strips_widgets_and_footers():
    html = (
        '<div class="available-content">'
        "<p>Real content</p>"
        '<div class="subscription-widget-wrap"><input placeholder="email"/></div>'
        '<div class="post-footer"><button>Share</button></div>'
        "</div>"
    )
    soup = BeautifulSoup(html, "html.parser")
    extract._clean_post_html(soup)
    cleaned_str = str(soup)
    assert "Real content" in cleaned_str
    assert "subscription-widget-wrap" not in cleaned_str


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


def test_extract_post_body_element_and_html_fallbacks():
    """Verify _extract_post_body_element finds available-content, body.markup, or single-post."""
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


def test_extract_post_data_reports_title_and_body_found_flags():
    """Verify extract_post_data returns title_found and body_found boolean flags accurately."""
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
