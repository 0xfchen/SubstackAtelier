"""Substack post DOM parsing and HTML-to-Markdown conversion engine."""

from __future__ import annotations

import html
import json
import logging
import re
from datetime import datetime
from typing import Any

from bs4 import BeautifulSoup, Tag

from scraper.converter import convert_html_to_markdown, normalize_markdown

logger = logging.getLogger(__name__)


def _extract_post_id(html_content: str) -> int | None:
    """Extract Substack numeric post ID from HTML content."""
    match = re.search(r'\\?"post\\?":\s*\{[^}]*\\?"id\\?":\s*(\d+)', html_content)
    if match:
        return int(match.group(1))
    general_match = re.search(r'"postId":\s*(\d+)', html_content)
    if general_match:
        return int(general_match.group(1))
    id_match = re.search(r'\\?"id\\?":\s*(\d+)', html_content)
    if id_match:
        return int(id_match.group(1))
    return None


def _extract_preloaded_post_data(html_content: str) -> dict[str, Any]:
    """Extract rich post metadata from window._preloads embedded in Substack HTML.

    Returns:
        dict[str, Any]: Dictionary containing post_id, tags, description,
            wordcount, audience, and canonical_url.
    """
    metadata: dict[str, Any] = {
        "post_id": None,
        "tags": [],
        "description": "",
        "wordcount": None,
        "audience": "everyone",
        "canonical_url": "",
    }

    # 1. Attempt to find window._preloads with JSON.parse("...")
    json_match = re.search(r'JSON\.parse\("((?:[^"\\]|\\.)*)"\)', html_content)
    if json_match:
        try:
            raw_inner = json_match.group(1)
            # If raw_inner has escaped quotes (\"), unescape them
            try:
                decoded_str = raw_inner.encode("utf-8").decode("unicode_escape")
                payload = json.loads(decoded_str)
            except Exception:
                payload = json.loads(raw_inner.replace('\\"', '"'))
            post = payload.get("post") if isinstance(payload, dict) else None
            if isinstance(post, dict):
                if "id" in post:
                    metadata["post_id"] = int(post["id"])
                if "postTags" in post and isinstance(post["postTags"], list):
                    metadata["tags"] = [
                        t.get("name") for t in post["postTags"] if isinstance(t, dict) and t.get("name")
                    ]
                if "description" in post and post["description"]:
                    metadata["description"] = post["description"].strip()
                if "wordcount" in post and post["wordcount"] is not None:
                    metadata["wordcount"] = int(post["wordcount"])
                if "audience" in post and post["audience"]:
                    metadata["audience"] = post["audience"]
                if "canonical_url" in post and post["canonical_url"]:
                    metadata["canonical_url"] = post["canonical_url"]
                return metadata
        except Exception as exc:
            logger.debug("Failed parsing JSON.parse preloads: %s", exc)

    # 2. Fallback regex extraction if full JSON.parse fails or is not present
    if metadata["post_id"] is None:
        metadata["post_id"] = _extract_post_id(html_content)

    if not metadata["tags"]:
        tags_match = re.search(r'\\?"postTags\\?":\s*(\[[^\]]*\])', html_content)
        if tags_match:
            try:
                clean_tags_str = tags_match.group(1).replace('\\"', '"')
                tags_list = json.loads(clean_tags_str)
                metadata["tags"] = [t.get("name") for t in tags_list if isinstance(t, dict) and t.get("name")]
            except Exception:
                pass

    if not metadata["description"]:
        desc_match = re.search(
            r'<meta\s+(?:name|property)="(?:\w+:)?description"\s+content="([^"]*)"',
            html_content,
            re.IGNORECASE,
        )
        if desc_match:
            metadata["description"] = html.unescape(desc_match.group(1).strip())

    if metadata["wordcount"] is None:
        wc_match = re.search(r'\\?"wordcount\\?":\s*(\d+)', html_content)
        if wc_match:
            metadata["wordcount"] = int(wc_match.group(1))

    if metadata["audience"] == "everyone":
        aud_match = re.search(r'\\?"audience\\?":\s*\\?"([^\\",]+)\\?"', html_content)
        if aud_match:
            metadata["audience"] = aud_match.group(1)

    if not metadata["canonical_url"]:
        canon_match = re.search(r'<link\s+rel="canonical"\s+href="([^"]*)"', html_content, re.IGNORECASE)
        if canon_match:
            metadata["canonical_url"] = canon_match.group(1).strip()

    return metadata


def _extract_post_body_element(soup: BeautifulSoup) -> Tag | None:
    """Locate the main post body element using available selectors with fallbacks."""
    return soup.select_one("div.available-content, div.body.markup, article.single-post")


def _convert_youtube_embeds(html_content: str) -> str:
    """Replace Substack YouTube embed wrappers with linked thumbnail markdown/HTML.

    Args:
        html_content: Raw post HTML containing potential youtube-wrap divs.

    Returns:
        str: Modified HTML with clickable preview thumbnails replacing embed divs.
    """
    if "youtube-wrap" not in html_content:
        return html_content
    soup = BeautifulSoup(html_content, "html.parser")
    for wrap in soup.find_all("div", class_="youtube-wrap"):
        video_id = None
        if wrap.has_attr("data-attrs"):
            try:
                video_id = json.loads(wrap["data-attrs"]).get("videoId")
            except (KeyError, TypeError, ValueError):
                pass
        if not video_id:
            iframe = wrap.find("iframe")
            if iframe and "src" in iframe.attrs:
                match = re.search(r"embed/([a-zA-Z0-9_-]+)", iframe["src"])
                if match:
                    video_id = match.group(1)
        if not video_id:
            continue

        link = soup.new_tag("a", href=f"https://www.youtube.com/watch?v={video_id}")
        img = soup.new_tag(
            "img",
            src=f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
            alt="YouTube video",
        )
        link.append(img)
        wrap.replace_with(link)

    return str(soup)


def _clean_post_html(soup: BeautifulSoup) -> None:
    """Strip promotional widgets, subscription banners, reaction bars, and comment buttons."""
    selectors_to_remove = [
        "div.subscription-widget-wrap",
        "div.post-footer",
        "div.post-ufi",
        "div.comments-section",
        "div.caption-rec-wrap",
        "button.like-button",
        "div.like-button-container",
    ]
    for selector in selectors_to_remove:
        for element in soup.select(selector):
            element.decompose()

    # Remove "Leave a comment" and interactive engagement prompt buttons
    for element in soup.find_all(["a", "button"]):
        text = element.get_text(strip=True).lower()
        href = element.get("href", "").rstrip("/")
        if text in ("leave a comment", "subscribe", "share", "share this post") or href.endswith(
            ("/comments", "/subscribe", "/share")
        ):
            parent = element.parent
            if (
                parent
                and parent.name in ("p", "div")
                and any(cls in parent.get("class", []) for cls in ("button-wrapper", "button-wrap"))
            ):
                parent.decompose()
            elif element.name == "button" or any(cls in element.get("class", []) for cls in ("button", "primary")):
                element.decompose()


def post_html_to_markdown(html_content: str, clean_content: bool = True) -> str:
    """Convert HTML content to Markdown with code language preservation and widget cleaning.

    Args:
        html_content: Raw post body HTML.
        clean_content: Whether to strip promotional widgets and reaction bars.

    Returns:
        str: Cleaned markdown string with preserved code block languages.
    """
    html_content = _convert_youtube_embeds(html_content)
    soup = BeautifulSoup(html_content, "html.parser")

    if clean_content:
        _clean_post_html(soup)

    raw_markdown = convert_html_to_markdown(str(soup))
    if not raw_markdown or not raw_markdown.strip():
        return ""
    return normalize_markdown(raw_markdown)


def _extract_ld_json_fields(soup: BeautifulSoup) -> tuple[str, str, str]:
    """Extract publication date, author name, and cover image from JSON-LD schema."""
    date = ""
    author = ""
    cover_image = ""
    script_tag = soup.find("script", {"type": "application/ld+json"})
    if script_tag and script_tag.string:
        try:
            ld_json = json.loads(script_tag.string)
            if "datePublished" in ld_json:
                date_str = ld_json["datePublished"]
                date_obj = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                date = date_obj.strftime("%Y-%m-%d")
            if "author" in ld_json:
                authors = ld_json["author"]
                if isinstance(authors, list) and authors:
                    author = authors[0].get("name", "")
                elif isinstance(authors, dict):
                    author = authors.get("name", "")
            if "image" in ld_json:
                images = ld_json["image"]
                if isinstance(images, list) and images:
                    img = images[0]
                    cover_image = img.get("url", "") if isinstance(img, dict) else str(img)
                elif isinstance(images, dict):
                    cover_image = images.get("url", "")
        except (json.JSONDecodeError, ValueError, KeyError):
            pass

    return date, author, cover_image


def extract_post_data(
    soup: BeautifulSoup,
    url: str = "",
    clean_content: bool = True,
) -> dict[str, Any]:
    """Extract metadata and parse post body into markdown from BeautifulSoup.

    Args:
        soup: Parsed HTML DOM of the Substack post.
        url: Source post URL.
        clean_content: Whether to strip promotional widgets and reaction bars.

    Returns:
        dict[str, Any]: Dictionary containing title, subtitle, author, date,
            cover_image, post_id, tags, description, wordcount, audience,
            canonical_url, md_content, title_found, and body_found.
    """
    title_element = soup.select_one("h1.post-title, h2")
    title = title_element.text.strip() if title_element else "Untitled"
    title_found = title_element is not None

    subtitle_element = soup.select_one("h3.subtitle, div.subtitle-HEEcLo")
    subtitle = subtitle_element.text.strip() if subtitle_element else ""

    date, author, cover_image = _extract_ld_json_fields(soup)
    if not date:
        date = "Date not found"

    preloaded = _extract_preloaded_post_data(str(soup))
    post_id = preloaded.get("post_id")
    tags = preloaded.get("tags", [])
    description = preloaded.get("description", "") or subtitle
    wordcount = preloaded.get("wordcount")
    audience = preloaded.get("audience", "everyone")
    canonical_url = preloaded.get("canonical_url", "") or url

    content_element = _extract_post_body_element(soup)
    content_html = str(content_element) if content_element else ""
    md = post_html_to_markdown(content_html, clean_content=clean_content)

    if wordcount is None and md:
        wordcount = len(md.split())

    return {
        "title": title,
        "subtitle": subtitle,
        "author": author,
        "date": date,
        "cover_image": cover_image,
        "post_id": post_id,
        "tags": tags,
        "description": description,
        "wordcount": wordcount,
        "audience": audience,
        "canonical_url": canonical_url,
        "md_content": md,
        "title_found": title_found,
        "body_found": content_element is not None,
    }
