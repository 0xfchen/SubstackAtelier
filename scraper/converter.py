"""HTML to Markdown converter adapter module wrapping html-to-markdown."""

from __future__ import annotations

import re

import html_to_markdown
import mdformat
from bs4 import BeautifulSoup
from html_to_markdown import ConversionOptions

ZERO_WIDTH_CHARS = "\u200b\u200c\u200d\u2060\ufeff"
_ZERO_WIDTH_PATTERN = re.compile(rf"[{ZERO_WIDTH_CHARS}]")
_INVISIBLE_CHARS_PATTERN = re.compile(rf"^[\s{ZERO_WIDTH_CHARS}]*$")
_COMMON_SHORT_WORDS = r"a|an|the|and|is|it|in|to|for|was|are|not|but|with|from|by|at|or|as|on|if|of|who"


def _ensure_default_image_alt(parsed_soup: BeautifulSoup) -> None:
    """Ensure all img tags contain an alt attribute to avoid markdownlint MD045 warnings."""
    for image_element in parsed_soup.find_all("img"):
        if not image_element.get("alt"):
            image_element["alt"] = "image"


def _normalize_anchor_whitespace(parsed_soup: BeautifulSoup) -> None:
    """Normalize whitespace and strip zero-width characters in anchor tags."""
    for link_element in list(parsed_soup.find_all("a")):
        if link_element.find("img") is not None:
            continue

        raw_anchor_text = link_element.get_text()
        if _INVISIBLE_CHARS_PATTERN.fullmatch(raw_anchor_text):
            if re.search(r"\s", raw_anchor_text):
                link_element.replace_with(" ")
            else:
                link_element.decompose()
            continue

        for text_node in list(link_element.find_all(string=True)):
            if _ZERO_WIDTH_PATTERN.search(text_node):
                text_node.replace_with(_ZERO_WIDTH_PATTERN.sub("", text_node))

        full_anchor_text = link_element.get_text()
        if full_anchor_text[:1].isspace():
            link_element.insert_before(" ")
            for text_node in link_element.find_all(string=True):
                stripped_leading_text = text_node.lstrip()
                if stripped_leading_text != text_node:
                    text_node.replace_with(stripped_leading_text)
                if stripped_leading_text:
                    break

        if full_anchor_text[-1:].isspace():
            link_element.insert_after(" ")
            for text_node in reversed(link_element.find_all(string=True)):
                stripped_trailing_text = text_node.rstrip()
                if stripped_trailing_text != text_node:
                    text_node.replace_with(stripped_trailing_text)
                if stripped_trailing_text:
                    break


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


def _normalize_markdown_link_spacing(markdown_content: str) -> str:
    """Normalize whitespace and strip phantom links in Markdown content."""
    if not markdown_content or not markdown_content.strip():
        return markdown_content

    empty_or_zero_width_pattern = re.compile(
        rf"(?P<stars>\*{{1,3}})\[[\s{ZERO_WIDTH_CHARS}]*\]\(https?://[^\s)]+\)(?P=stars)|\[[\s{ZERO_WIDTH_CHARS}]*\]\(https?://[^\s)]+\)"
    )
    normalized_content = empty_or_zero_width_pattern.sub("", markdown_content)

    normalized_content = re.sub(
        r"(\[[^\]]+\]\(https?://[^\s)]+\))\*{5}(\[[^\]]+\]\(https?://[^\s)]+\))\*{5}(?=\*{0,3}\[[^\]]+\])",
        r"\1** ***\2*** **",
        normalized_content,
    )
    normalized_content = re.sub(
        r"(\[[^\]]+\]\(https?://[^\s)]+\))\*{5}(?=\*{0,3}\[[^\]]+\])",
        r"\1** ***",
        normalized_content,
    )

    # Substack split emphasis across link:
    # *text[url](url)*[text2](url)* -> *text* *[text2](url)*
    normalized_content = re.sub(
        r"(\*[^\n*]+)\[(?P<u1>https?://[^\s\]]+)\]\((?P=u1)\)\*\[(?P<t1>[^!\]]+)\]\((?P=u1)\)\*",
        r"\1* *[\g<t1>](\g<u1>)*",
        normalized_content,
    )

    duplicate_preceding_link_pattern = re.compile(
        r"(?P<pre_stars>\*{1,3})?\[(?P<u2>https?://[^\s\]]+)\]\((?P=u2)\)(?P<mid_stars>\*{0,3})"
        r"(?P<target_open>\*{0,3})\[(?P<t2>[^!\]]+)\]\((?P=u2)\)(?P<target_close>\*{0,3})"
    )

    def replace_duplicate_preceding_link(match: re.Match[str]) -> str:
        pre_stars = match.group("pre_stars") or ""
        mid_stars = match.group("mid_stars") or ""
        target_open = match.group("target_open") or ""
        text = match.group("t2")
        url = match.group("u2")
        target_close = match.group("target_close") or ""
        stars_open = target_open or mid_stars or pre_stars
        return f"{stars_open}[{text}]({url}){target_close}"

    normalized_content = duplicate_preceding_link_pattern.sub(replace_duplicate_preceding_link, normalized_content)

    duplicate_following_link_pattern = re.compile(
        r"(?P<target_open>\*{0,3})\[(?P<t3>[^!\]]+)\]\((?P<u3>https?://[^\s)]+)\)(?P<target_close>\*{0,3})"
        r"(?P<post_stars>\*{0,3})\[(?P=u3)\]\((?P=u3)\)(?P<end_stars>\*{0,3})"
    )

    def replace_duplicate_following_link(match: re.Match[str]) -> str:
        target_open = match.group("target_open") or ""
        text = match.group("t3")
        url = match.group("u3")
        target_close = match.group("target_close") or ""
        post_stars = match.group("post_stars") or ""
        end_stars = match.group("end_stars") or ""
        stars_close = target_close or post_stars or end_stars
        return f"{target_open}[{text}]({url}){stars_close} "

    normalized_content = duplicate_following_link_pattern.sub(replace_duplicate_following_link, normalized_content)

    adjacent_links_pattern = re.compile(
        r"(?P<first_open>\*{1,3})?\[(?P<first_text>[^!\]]+)\]\((?P<first_url>https?://[^\s)]+)\)"
        r"(?P<between_stars>\*{0,6})"
        r"\[(?P<second_text>[^!\]]+)\]\((?P<second_url>https?://[^\s)]+)\)(?P<second_close>\*{1,3})?"
    )

    def replace_adjacent_links(match: re.Match[str]) -> str:
        first_open = match.group("first_open") or ""
        first_text = match.group("first_text")
        first_url = match.group("first_url")
        between_stars = match.group("between_stars") or ""
        second_text = match.group("second_text")
        second_url = match.group("second_url")
        second_close = match.group("second_close") or ""

        if len(first_text) == 1 and first_text.isalpha() and between_stars:
            return match.group(0)

        if first_open and between_stars.startswith(first_open):
            first_close = first_open
            remaining_stars = between_stars[len(first_open) :]
        elif not first_open:
            first_close = ""
            remaining_stars = between_stars
        else:
            first_close = between_stars
            remaining_stars = ""

        second_open = remaining_stars
        return (
            f"{first_open}[{first_text}]({first_url}){first_close} "
            f"{second_open}[{second_text}]({second_url}){second_close}"
        )

    while True:
        separated_content = adjacent_links_pattern.sub(replace_adjacent_links, normalized_content)
        if separated_content == normalized_content:
            break
        normalized_content = separated_content

    prefix_pattern_part = (
        r"(?P<prefix>(?<![!\[\(\"\'\“\‘])(?:(?<=[A-Za-z0-9,.;:!?\’\”\)—\-])\*{1,3}|[A-Za-z0-9,.;:?\’\”\)—\-]))"
    )
    link_pattern_part = (
        r"(?P<link>(?:\*{1,3}\[[^!\]\n]+\]\(https?://[^\s)]+\)\*{1,3}|\[[^!\]\n]+\]\(https?://[^\s)]+\)))"
    )
    before_link_pattern = re.compile(prefix_pattern_part + link_pattern_part)

    def replace_before_link(match: re.Match[str]) -> str:
        prefix = match.group("prefix")
        link = match.group("link")
        start_index = match.start()
        if prefix.endswith(")") or prefix.endswith("*"):
            preceding_context = normalized_content[max(0, start_index - 100) : start_index]
            if re.search(r"\]\([^)\s]+\)\*{0,3}\Z", preceding_context + prefix):
                return match.group(0)
        return prefix + " " + link

    normalized_content = before_link_pattern.sub(replace_before_link, normalized_content)

    after_link_pattern = re.compile(
        rf"(?P<link>(?<!\!)\[(?![‘“\(\[])[^\]\n]+\]\(https?://[^\s)]+\)(?:\*{{1,3}})?)"
        rf"(?P<suffix>[A-Z]|[a-z]{{4,}}|\b(?:{_COMMON_SHORT_WORDS})\b)"
    )
    normalized_content = after_link_pattern.sub(r"\g<link> \g<suffix>", normalized_content)

    return re.sub(r"(?<=\S) {2,}(?=\S)", " ", normalized_content)


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
    """Clean Substack CDN image wrappers, SVG placeholder links, link whitespace, and heading SVG suffixes."""
    cleaned_content = _unwrap_substack_linked_images(markdown_content)
    cleaned_content = _replace_substack_image_placeholder_links(cleaned_content)
    cleaned_content = _normalize_markdown_link_spacing(cleaned_content)
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
    needs_soup_preprocessing = (default_image_alt and "<img" in html_content) or "<a" in html_content
    if needs_soup_preprocessing:
        parsed_soup = BeautifulSoup(html_content, "html.parser")
        if default_image_alt and "<img" in html_content:
            _ensure_default_image_alt(parsed_soup)
        if "<a" in html_content:
            _normalize_anchor_whitespace(parsed_soup)
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
