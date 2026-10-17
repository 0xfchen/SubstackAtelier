"""Synchronization state management and Substack API delta fetching."""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime
from typing import Any

import requests

from scraper.config import (
    DEFAULT_API_POST_LIMIT,
    DEFAULT_REQUEST_TIMEOUT,
    MAX_API_SYNC_PAGES,
)

logger = logging.getLogger(__name__)


def _get_sync_state_path(author_dir: str) -> str:
    """Return the absolute path to sync_state.json in author directory."""
    return os.path.join(author_dir, "sync_state.json")


def _parse_iso_datetime(date_string: str | None) -> datetime | None:
    """Parse an ISO date/time string into a UTC-aware datetime object."""
    if not date_string or date_string == "Date not found":
        return None
    try:
        clean_date_string = date_string.replace("Z", "+00:00")
        parsed_datetime = datetime.fromisoformat(clean_date_string)
        if parsed_datetime.tzinfo is None:
            parsed_datetime = parsed_datetime.replace(tzinfo=UTC)
        return parsed_datetime
    except (ValueError, TypeError):
        return None


def _is_cutoff_reached(
    post: dict[str, Any],
    last_post_id: int | None = None,
    last_post_slug: str | None = None,
    since_datetime: datetime | None = None,
    is_date_only: bool = False,
) -> bool:
    """Evaluate whether an API post record matches or precedes the sync cursor."""
    post_id = post.get("id")
    post_slug = post.get("slug")
    if last_post_id is not None and post_id == last_post_id:
        return True
    if last_post_slug is not None and post_slug == last_post_slug:
        return True
    if since_datetime is None:
        return False

    post_datetime = _parse_iso_datetime(post.get("post_date"))
    if post_datetime is None:
        return False

    if is_date_only:
        return post_datetime.date() < since_datetime.date()
    return post_datetime <= since_datetime


def _bootstrap_sync_state_from_metadata(metadata_file_path: str) -> dict[str, Any] | None:
    """Bootstrap initial sync state from an existing metadata.json catalog."""
    if not os.path.exists(metadata_file_path):
        return None

    try:
        with open(metadata_file_path, encoding="utf-8") as file:
            entries = json.load(file)
    except (json.JSONDecodeError, OSError) as error:
        logger.warning("Failed to bootstrap sync state from metadata.json: %s", error)
        return None

    if not isinstance(entries, list) or not entries:
        return None

    dated_entries = [
        entry
        for entry in entries
        if isinstance(entry, dict) and entry.get("date") and entry.get("date") != "Date not found"
    ]
    if not dated_entries:
        return None

    dated_entries.sort(key=lambda entry: str(entry.get("date", "")), reverse=True)
    newest_entry = dated_entries[0]
    logger.info(
        "Bootstrapping sync state from existing metadata.json (last post date: %s)",
        newest_entry.get("date"),
    )
    return {
        "last_sync_at": datetime.now(UTC).isoformat(),
        "last_post_date": newest_entry.get("date"),
        "last_post_id": newest_entry.get("post_id"),
        "last_post_slug": newest_entry.get("slug"),
        "total_synced_posts": len(entries),
    }


def load_sync_state(author_dir: str, metadata_file_path: str) -> dict[str, Any] | None:
    """Load sync state from disk or bootstrap from metadata.json if missing.

    Args:
        author_dir: Directory path for the author's saved content.
        metadata_file_path: Path to the author's metadata.json catalog file.

    Returns:
        dict[str, Any] | None: Loaded sync state dictionary or None if uninitialized.
    """
    sync_state_path = _get_sync_state_path(author_dir)
    if os.path.exists(sync_state_path):
        try:
            with open(sync_state_path, encoding="utf-8") as file:
                data = json.load(file)
                if isinstance(data, dict):
                    return data
        except (json.JSONDecodeError, OSError) as error:
            logger.warning("Failed to read %s: %s", sync_state_path, error)

    return _bootstrap_sync_state_from_metadata(metadata_file_path)


def save_sync_state(author_dir: str, state: dict[str, Any]) -> None:
    """Save sync state dictionary to sync_state.json atomically.

    Args:
        author_dir: Directory path for the author's saved content.
        state: State dictionary to persist.
    """
    os.makedirs(author_dir, exist_ok=True)
    sync_state_path = _get_sync_state_path(author_dir)
    temporary_path = f"{sync_state_path}.tmp"
    with open(temporary_path, "w", encoding="utf-8") as file:
        json.dump(state, file, ensure_ascii=False, indent=4)
    os.replace(temporary_path, sync_state_path)


def fetch_posts_from_api(
    publication_url: str,
    since_date: str | None = None,
    last_post_id: int | None = None,
    last_post_slug: str | None = None,
    limit: int = DEFAULT_API_POST_LIMIT,
    max_pages: int = MAX_API_SYNC_PAGES,
) -> list[dict[str, Any]] | None:
    """Fetch post metadata records from Substack API until cutoff is reached.

    Args:
        publication_url: Root publication URL.
        since_date: ISO date/time string cutoff.
        last_post_id: Numeric post ID cutoff.
        last_post_slug: Post slug cutoff.
        limit: Page size limit for API requests.
        max_pages: Maximum number of pages to request.

    Returns:
        list[dict[str, Any]] | None: List of new post metadata dictionaries, or None on failure.
    """
    if not publication_url.endswith("/"):
        publication_url += "/"

    delta_posts: list[dict[str, Any]] = []
    since_datetime = _parse_iso_datetime(since_date) if since_date else None
    is_date_only = bool(since_date and len(since_date.strip()) == 10)

    api_base_url = f"{publication_url}api/v1/posts"
    offset = 0

    for _ in range(max_pages):
        api_page_url = f"{api_base_url}?offset={offset}&limit={limit}&sort=new"
        try:
            response = requests.get(api_page_url, timeout=DEFAULT_REQUEST_TIMEOUT)
        except requests.RequestException as request_error:
            logger.warning("Error requesting Substack API %s: %s", api_page_url, request_error)
            return None if offset == 0 else delta_posts

        if not response.ok:
            logger.warning("Substack API returned status %s for %s", response.status_code, api_page_url)
            return None if offset == 0 else delta_posts

        try:
            api_posts = response.json()
        except (json.JSONDecodeError, ValueError) as json_error:
            logger.warning("Failed to decode JSON from Substack API %s: %s", api_page_url, json_error)
            return None if offset == 0 else delta_posts

        if not isinstance(api_posts, list) or not api_posts:
            break

        stopped = False
        for post in api_posts:
            if not isinstance(post, dict):
                continue

            if _is_cutoff_reached(
                post=post,
                last_post_id=last_post_id,
                last_post_slug=last_post_slug,
                since_datetime=since_datetime,
                is_date_only=is_date_only,
            ):
                stopped = True
                break

            delta_posts.append(post)

        if stopped or len(api_posts) < limit:
            break

        offset += limit

    return delta_posts
