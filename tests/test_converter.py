"""Tests for HTML-to-Markdown conversion, tables, code fences, and normalization."""

from scraper.converter import convert_html_to_markdown
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
