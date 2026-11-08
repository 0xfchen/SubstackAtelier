"""Tests for HTML-to-Markdown conversion, tables, code fences, and normalization."""

from scraper.converter import convert_html_to_markdown, normalize_markdown
from scraper.extract import post_html_to_markdown


def test_convert_html_to_markdown_code_block_language_fences():
    """Verify code block language syntax is preserved from code class."""
    html_content = '<pre><code class="language-python">def hello():\n    return "world"</code></pre>'
    markdown_output = convert_html_to_markdown(html_content)
    assert markdown_output is not None
    assert "```python" in markdown_output
    assert 'def hello():\n    return "world"' in markdown_output
    assert markdown_output.strip().endswith("```")


def test_convert_html_to_markdown_pre_tag_language_fences():
    """Verify code block language syntax is preserved when declared on pre element."""
    html_content = '<pre class="language-typescript"><code>const value: number = 42;</code></pre>'
    markdown_output = convert_html_to_markdown(html_content)
    assert markdown_output is not None
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
    table_markdown = convert_html_to_markdown(table_html)
    assert table_markdown is not None
    assert "| Header A | Header B |" in table_markdown
    assert "| -------- | -------- |" in table_markdown
    assert "Cell 1" in table_markdown
    assert "Cell 2" in table_markdown


def test_convert_html_to_markdown_preserves_link_emphasis_boundary_whitespace():
    """Verify boundary whitespace inside emphasis around links is cleanly preserved."""
    emphasis_html = '<p>You can <em>RSVP <a href="https://example.com">via this link</a></em> today.</p>'
    emphasis_markdown = convert_html_to_markdown(emphasis_html)
    assert emphasis_markdown is not None
    assert "*RSVP [via this link](https://example.com)*" in emphasis_markdown
    assert "RSVP[" not in emphasis_markdown


def test_convert_html_to_markdown_image_alt_normalization():
    """Verify images without alt attributes receive 'image' alt for MD045 compliance."""
    image_html = '<p><img src="https://example.com/photo.png"></p>'
    image_markdown = convert_html_to_markdown(image_html)
    assert image_markdown is not None
    assert "![image](https://example.com/photo.png)" in image_markdown

    custom_alt_html = '<p><img src="https://example.com/photo.png" alt="Custom Alt"></p>'
    custom_alt_markdown = convert_html_to_markdown(custom_alt_html)
    assert custom_alt_markdown is not None
    assert "![Custom Alt](https://example.com/photo.png)" in custom_alt_markdown


def test_convert_substack_image_link_with_inline_svg_buttons_to_image():
    """Verify Substack's <a class="image-link"> with <picture><img/></picture> and SVG buttons becomes an image."""
    image_url = (
        "https://substackcdn.com/image/fetch/$s_!Patg!,f_auto,q_auto:good,"
        "fl_progressive:steep/https%3A%2F%2Fsubstack-post-media.s3.amazonaws.com%2Fphoto.png"
    )
    html_content = (
        f'<div class="captioned-image-container"><figure>'
        f'<a class="image-link" href="{image_url}">'
        f'<picture><img src="{image_url}" alt=""/></picture>'
        f'<div class="image-link-expand">'
        f'<button class="restack-image"><svg><path d="M0 0"/></svg></button>'
        f'<button class="view-image"><svg><path d="M1 1"/></svg></button>'
        f"</div></a></figure></div>"
    )

    markdown_output = convert_html_to_markdown(html_content)

    assert markdown_output is not None
    assert markdown_output.strip() == f"![image]({image_url})"


def test_convert_substack_image_link_preserves_custom_alt():
    """Verify Substack image links with author-supplied alt text preserve the custom alt."""
    image_url = (
        "https://substackcdn.com/image/fetch/$s_!Patg!,f_auto,q_auto:good,"
        "fl_progressive:steep/https%3A%2F%2Fsubstack-post-media.s3.amazonaws.com%2Fdiagram.png"
    )
    html_content = (
        f'<a class="image-link" href="{image_url}">'
        f'<picture><img src="{image_url}" alt="Architecture diagram"/></picture>'
        f'<div class="image-link-expand">'
        f'<button class="restack-image"><svg><path d="M0 0"/></svg></button>'
        f'<button class="view-image"><svg><path d="M1 1"/></svg></button>'
        f"</div></a>"
    )

    markdown_output = convert_html_to_markdown(html_content)

    assert markdown_output is not None
    assert markdown_output.strip() == f"![Architecture diagram]({image_url})"


def test_convert_preserves_external_link_wrapping_image_with_svg():
    """Verify linked images pointing to external URLs retain the outer link while stripping SVG."""
    image_url = "https://substackcdn.com/image/fetch/https%3A%2F%2Fexample.com%2Fsponsor.png"
    html_content = (
        f'<a href="https://example.com/sponsor"><img src="{image_url}" alt="Sponsor"/><svg><path d="M0 0"/></svg></a>'
    )

    markdown_output = convert_html_to_markdown(html_content)

    assert markdown_output is not None
    assert markdown_output.strip() == f"[![Sponsor]({image_url})](https://example.com/sponsor)"


def test_convert_substack_image_placeholder_link_to_image():
    """Verify Substack's legacy placeholder text on image links becomes an actual Markdown image."""
    image_url = (
        "https://substackcdn.com/image/fetch/$s_!Patg!,f_auto,q_auto:good,"
        "fl_progressive:steep/https%3A%2F%2Fsubstack-post-media.s3.amazonaws.com%2Fphoto.png"
    )
    html_content = f'<p><a href="{image_url}">imageSVG ImageSVG Image</a></p>'

    markdown_output = convert_html_to_markdown(html_content)

    assert markdown_output is not None
    assert f"![image]({image_url})" in markdown_output


def test_normalize_markdown_repairs_substack_placeholder_links_and_headings():
    """Verify normalize_markdown repairs default and custom-alt SVG placeholder links and heading suffixes."""
    image_url = "https://substackcdn.com/image/fetch/https%3A%2F%2Fexample.com%2Fchart.png"
    legacy_markdown = (
        "## Section Heading SVG Image\n\n"
        "### Sub-heading SVG ImageSVG Image\n\n"
        f"[imageSVG ImageSVG Image]({image_url})\n\n"
        f"[Custom Alt TextSVG Image]({image_url})\n\n"
        "[Listen nowSVG Image](https://example.com/podcast)\n\n"
        "[Avatar SVG Image](https://twitter.com/user)\n\n"
        "[imageSVG ImageSVG Image](https://example.com/cta)\n"
    )

    normalized_output = normalize_markdown(legacy_markdown)

    assert "## Section Heading" in normalized_output
    assert "### Sub-heading" in normalized_output
    assert "SVG Image" not in normalized_output
    assert f"![image]({image_url})" in normalized_output
    assert f"![Custom Alt Text]({image_url})" in normalized_output
    assert "[Listen now](https://example.com/podcast)" in normalized_output
    assert "[Avatar](https://twitter.com/user)" in normalized_output
    assert "[image](https://example.com/cta)" in normalized_output


def test_convert_preserves_regular_substack_image_links():
    """Verify normal image-host links retain their text rather than becoming Markdown images."""
    html_content = '<a href="https://substackcdn.com/image/fetch/example">Open image</a>'

    markdown_output = convert_html_to_markdown(html_content)

    assert markdown_output is not None
    assert "[Open image](https://substackcdn.com/image/fetch/example)" in markdown_output


def test_convert_removes_svg_image_suffix_from_headings_only():
    """Verify Substack's decorative SVG in headings and literal SVG Image heading suffix are removed."""
    html_content = (
        "<h2><strong>Overview</strong>"
        '<div class="header-anchor-widget"><button><svg><path d="M0 0"/></svg></button></div>'
        "</h2>"
        "<h3><strong>In this episode</strong> SVG Image</h3>"
        "<p>SVG Image</p>"
    )

    markdown_output = convert_html_to_markdown(html_content)

    assert markdown_output is not None
    assert "## **Overview**" in markdown_output
    assert "## **Overview** SVG Image" not in markdown_output
    assert "### **In this episode**" in markdown_output
    assert "### **In this episode** SVG Image" not in markdown_output
    assert "\nSVG Image" in markdown_output


def test_convert_html_to_markdown_empty_input():
    """Verify empty, whitespace-only, or None inputs safely return None."""
    assert convert_html_to_markdown(None) is None
    assert convert_html_to_markdown("") is None
    assert convert_html_to_markdown("   \n\t  ") is None


def test_html_to_md_empty_content():
    """Verify post_html_to_markdown safely returns empty string when content is empty or whitespace."""
    assert post_html_to_markdown("") == ""
    assert post_html_to_markdown("   ") == ""


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
    md = post_html_to_markdown(html)
    assert "- First item" in md
    assert "- Second item" in md
    assert "* First item" not in md
    assert "![image](https://example.com/photo.png)" in md
    assert "> A quote here." in md
