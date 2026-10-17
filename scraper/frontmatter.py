"""YAML frontmatter serialization and parsing utilities for markdown post files."""

from __future__ import annotations

import os
from typing import Any


def extract_metadata_from_md(md_filepath: str) -> dict[str, Any] | None:
    """Extract metadata dictionary from a local markdown file's frontmatter.

    Args:
        md_filepath: Path to the markdown file on disk.

    Returns:
        dict[str, Any] | None: Parsed frontmatter metadata or None if invalid/missing.
    """
    if not os.path.exists(md_filepath):
        return None
    try:
        with open(md_filepath, encoding="utf-8") as file:
            content = file.read()
    except OSError:
        return None

    metadata: dict[str, Any] = {}
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            frontmatter_lines = parts[1].strip().splitlines()
            current_list_key = None
            for line in frontmatter_lines:
                stripped = line.strip()
                if not stripped:
                    continue
                if stripped.startswith("- ") and current_list_key:
                    item = stripped[2:].strip().strip('"').strip("'")
                    metadata.setdefault(current_list_key, []).append(item)
                    continue
                current_list_key = None
                if ":" in line:
                    key, value = line.split(":", 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if not value:
                        current_list_key = key
                        metadata[key] = []
                    elif key in ("post_id", "wordcount") and value.isdigit():
                        metadata[key] = int(value)
                    else:
                        metadata[key] = value
    return metadata or None


def combine_metadata_and_content(
    title: str,
    subtitle: str = "",
    date: str = "",
    author: str = "",
    cover_image: str = "",
    content: str = "",
    post_id: int | None = None,
    tags: list[str] | None = None,
    description: str = "",
    wordcount: int | None = None,
    audience: str = "everyone",
    canonical_url: str = "",
    source_url: str = "",
) -> str:
    """Combine post metadata headers with markdown body using clean YAML frontmatter.

    Args:
        title: Post title.
        subtitle: Post subtitle.
        date: Publication date string (ISO or readable).
        author: Author display name.
        cover_image: Cover image URL.
        content: Main article markdown body.
        post_id: Optional Substack post ID for unique identification.
        tags: Optional list of post tag strings.
        description: Optional SEO description or article summary.
        wordcount: Optional word count integer.
        audience: Audience tier ('everyone' or 'only_paid').
        canonical_url: Permanent link back to the live Substack essay.
        source_url: Original post URL for MDX frontmatter.

    Returns:
        str: Combined markdown with YAML frontmatter.

    Raises:
        ValueError: If title or content is not a string.
    """
    if not isinstance(title, str):
        raise ValueError("title must be a string")
    if not isinstance(content, str):
        raise ValueError("content must be a string")

    safe_title = title.replace('"', '\\"')
    safe_subtitle = subtitle.replace('"', '\\"') if subtitle else ""
    safe_desc = description.replace('"', '\\"') if description else ""
    safe_author = author.replace('"', '\\"') if author else ""
    active_url = canonical_url or source_url

    frontmatter = "---\n"
    frontmatter += f'title: "{safe_title}"\n'
    if safe_subtitle:
        frontmatter += f'subtitle: "{safe_subtitle}"\n'
    if safe_desc:
        frontmatter += f'description: "{safe_desc}"\n'
    if post_id is not None:
        frontmatter += f"post_id: {post_id}\n"
    if safe_author:
        frontmatter += f'author: "{safe_author}"\n'
    if date:
        frontmatter += f'date: "{date}"\n'
    if tags:
        frontmatter += "tags:\n"
        for t in tags:
            clean_tag = t.replace('"', '\\"')
            frontmatter += f'  - "{clean_tag}"\n'
    if wordcount is not None:
        frontmatter += f"wordcount: {wordcount}\n"
    if audience:
        frontmatter += f'audience: "{audience}"\n'
    if active_url:
        frontmatter += f'canonical_url: "{active_url}"\n'
    if cover_image:
        frontmatter += f'cover_image: "{cover_image}"\n'
    frontmatter += "---\n\n"

    body = content.strip()
    if not body.startswith("# "):
        body = f"# {title}\n\n{body}"

    return frontmatter + body + "\n"
