"""HTML to Markdown converter adapter module wrapping html-to-markdown."""

from __future__ import annotations

import re

import html_to_markdown
import mdformat
from bs4 import BeautifulSoup
from html_to_markdown import ConversionOptions


def _ensure_default_image_alt(parsed_soup: BeautifulSoup) -> None:
    """Ensure all img tags contain an alt attribute to avoid markdownlint MD045 warnings."""
    for image_element in parsed_soup.find_all("img"):
        if not image_element.get("alt"):
            image_element["alt"] = "image"


def _unwrap_substack_linked_images(markdown_content: str) -> str:
    """Unwrap Substack CDN zoom-wrapper links around Markdown images while keeping external links."""
    linked_image_pattern = r"\[!\[(.*?)\]\((.*?)\)\]\((.*?)\)"

    def replace_linked_image(match: re.Match[str]) -> str:
        alt_text, image_source, target_url = match.groups()
        if target_url == image_source or target_url.startswith("https://substackcdn.com/"):
            return f"![{alt_text}]({image_source})"
        return match.group(0)

    return re.sub(linked_image_pattern, replace_linked_image, markdown_content)


def _replace_substack_image_placeholder_links(markdown_content: str) -> str:
    """Replace Substack SVG placeholder links with Markdown images or cleaned links."""
    placeholder_link_pattern = r"(?<!\!)\[([^][]*?)(?:[ \t]*SVG Image)+\]\(([^\s)]+)\)"

    def replace_placeholder_link(match: re.Match[str]) -> str:
        raw_alt_text, target_url = match.groups()
        cleaned_alt_text = raw_alt_text.strip()
        normalized_alt_text = (
            "image" if not cleaned_alt_text or cleaned_alt_text.casefold() == "image" else cleaned_alt_text
        )
        if target_url.startswith("https://substackcdn.com/image/fetch/"):
            return f"![{normalized_alt_text}]({target_url})"
        return f"[{normalized_alt_text}]({target_url})"

    return re.sub(placeholder_link_pattern, replace_placeholder_link, markdown_content)


def _remove_svg_image_heading_labels(markdown_content: str) -> str:
    """Remove Substack's trailing SVG image label from Markdown headings."""
    without_empty_svg_headings = re.sub(
        r"(?m)^#{1,6}[ \t]+(?:SVG Image[ \t]*)+(?:\r?\n|$)",
        "",
        markdown_content,
    )
    return re.sub(
        r"(?m)^(#{1,6}[ \t]+[^\r\n]*?)[ \t]+(?:SVG Image[ \t]*)+(?=\r?$)",
        r"\1",
        without_empty_svg_headings,
    )


def _clean_substack_markdown_artifacts(markdown_content: str) -> str:
    """Clean Substack CDN image wrappers, SVG placeholder links, and heading SVG suffixes."""
    cleaned_content = _unwrap_substack_linked_images(markdown_content)
    cleaned_content = _replace_substack_image_placeholder_links(cleaned_content)
    return _remove_svg_image_heading_labels(cleaned_content)


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
        strip_tags=["svg"],
        keep_inline_images_in=["a"],
    )

    try:
        conversion_result = html_to_markdown.convert(
            content_to_convert,
            options=conversion_options,
        )
        converted_content = conversion_result.content
        if not converted_content or not converted_content.strip():
            return None
        cleaned_content = _clean_substack_markdown_artifacts(converted_content)
        if not cleaned_content or not cleaned_content.strip():
            return None
        return cleaned_content
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
    cleaned_markdown = _clean_substack_markdown_artifacts(markdown_text)
    if not cleaned_markdown.strip():
        return ""
    return mdformat.text(cleaned_markdown.strip(), extensions={"gfm"}).strip()
