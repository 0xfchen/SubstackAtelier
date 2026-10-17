"""HTML to Markdown converter adapter module wrapping html-to-markdown."""

from __future__ import annotations

import html_to_markdown
import mdformat
from bs4 import BeautifulSoup
from html_to_markdown import ConversionOptions


def _ensure_default_image_alt(parsed_soup: BeautifulSoup) -> None:
    """Ensure all img tags contain an alt attribute to avoid markdownlint MD045 warnings."""
    for image_element in parsed_soup.find_all("img"):
        if not image_element.get("alt"):
            image_element["alt"] = "image"


def convert_html_to_markdown(html_content: str | None, default_image_alt: bool = True) -> str | None:
    """Convert an HTML string into CommonMark and GFM-compliant markdown.

    Uses the high-performance html-to-markdown Rust core to handle code syntax
    highlighting language fences, GFM tables, and clean boundary spacing around links.

    Args:
        html_content: Raw or cleaned HTML markup to convert.
        default_image_alt: If True, populates missing img alt attributes with 'image'.

    Returns:
        str | None: Converted markdown content string, or None if input is empty or invalid.
    """
    if html_content is None or not html_content.strip():
        return None

    content_to_convert = html_content
    if default_image_alt and "<img" in html_content:
        parsed_soup = BeautifulSoup(html_content, "html.parser")
        _ensure_default_image_alt(parsed_soup)
        content_to_convert = str(parsed_soup)

    conversion_options = ConversionOptions(
        heading_style="atx",
        code_block_style="backticks",
        wrap=False,
        autolinks=True,
    )

    try:
        conversion_result = html_to_markdown.convert(
            content_to_convert,
            options=conversion_options,
        )
        converted_content = conversion_result.content
        if not converted_content or not converted_content.strip():
            return None
        return converted_content
    except Exception:
        return None


def normalize_markdown(markdown_text: str) -> str:
    """Format markdown content using mdformat with GitHub Flavored Markdown extensions.

    Args:
        markdown_text: Unformatted markdown string.

    Returns:
        str: Cleanly formatted GFM markdown string.
    """
    if not markdown_text or not markdown_text.strip():
        return ""
    return mdformat.text(markdown_text.strip(), extensions={"gfm"}).strip()
