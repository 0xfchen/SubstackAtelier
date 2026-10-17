"""File persistence and metadata catalog JSON operations."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


def build_file_link(markdown_filepath: str, author_dir: str) -> str:
    """Generate a relative URL-style file path for linking a post within the author catalog.

    Args:
        markdown_filepath: Target markdown file path.
        author_dir: Root directory for the author's archived content.

    Returns:
        str: Clean relative file link with forward slashes.
    """
    relative_path = os.path.relpath(markdown_filepath, author_dir)
    return relative_path.replace("\\", "/")


def get_filename_from_url(url: str, filetype: str = ".md") -> str:
    """Derive an output filename from a URL and extension.

    Args:
        url: Post or page URL.
        filetype: Desired file extension (e.g. '.md').

    Returns:
        str: Filename with extension.

    Raises:
        ValueError: If url or filetype is not a string.
    """
    if not isinstance(url, str):
        raise ValueError("url must be a string")
    if not isinstance(filetype, str):
        raise ValueError("filetype must be a string")
    if not filetype.startswith("."):
        filetype = f".{filetype}"
    return url.split("/")[-1] + filetype


def save_to_file(filepath: str, content: str, overwrite: bool = False) -> None:
    """Write content string to specified file with overwrite guard.

    Args:
        filepath: Destination file path.
        content: Text content to write.
        overwrite: If False, skip writing when file already exists.

    Raises:
        ValueError: If filepath or content is not a string.
    """
    if not isinstance(filepath, str):
        raise ValueError("filepath must be a string")
    if not isinstance(content, str):
        raise ValueError("content must be a string")
    if os.path.exists(filepath) and not overwrite:
        logger.info("File already exists: %s", filepath)
        return

    if not content.endswith("\n"):
        content += "\n"

    with open(filepath, "w", encoding="utf-8") as file:
        file.write(content)


def _get_entry_key(entry: dict[str, Any]) -> str:
    """Derive a deduplication key for a metadata catalog entry."""
    if entry.get("post_id"):
        return f"id:{entry['post_id']}"
    if entry.get("slug"):
        return f"slug:{entry['slug']}"
    file_link = entry.get("file_link", "")
    if file_link:
        base_name = os.path.splitext(os.path.basename(file_link))[0]
        return f"file:{base_name}"
    return f"title:{entry.get('title', '')}"


def save_posts_data_to_json(metadata_file_path: str, posts_data: list[dict[str, Any]]) -> None:
    """Save posts metadata records to metadata.json in the author's directory.

    Merges records in place by unique post_id first (if available), then by slug
    or file_link. Preserves original order and updates modified fields.

    Args:
        metadata_file_path: Absolute or relative path to the metadata.json file.
        posts_data: List of post metadata dictionaries to serialize.
    """
    author_dir = os.path.dirname(metadata_file_path)
    if author_dir:
        os.makedirs(author_dir, exist_ok=True)

    existing_data: list[dict[str, Any]] = []
    if os.path.exists(metadata_file_path):
        with open(metadata_file_path, encoding="utf-8") as file:
            try:
                existing_data = json.load(file)
            except (json.JSONDecodeError, ValueError):
                existing_data = []

    merged_data: list[dict[str, Any]] = []
    key_to_index: dict[str, int] = {}

    for item in existing_data:
        key = _get_entry_key(item)
        key_to_index[key] = len(merged_data)
        merged_data.append(dict(item))

    for item in posts_data:
        key = _get_entry_key(item)
        if key in key_to_index:
            index = key_to_index[key]
            merged_data[index].update(item)
        else:
            key_to_index[key] = len(merged_data)
            merged_data.append(dict(item))

    with open(metadata_file_path, "w", encoding="utf-8") as file:
        json.dump(merged_data, file, ensure_ascii=False, indent=4)
