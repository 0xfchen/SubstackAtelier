"""Shared test fixtures and stubs for SubstackAtelier test suite."""

from __future__ import annotations

import socket
from typing import Any
from unittest.mock import patch

import pytest

import scraper
from scraper import url_utils
from scraper.fetchers import PageFetcher


@pytest.fixture(autouse=True)
def block_external_sockets(monkeypatch):
    """Hermetic guard preventing test suite from making real outbound network calls."""

    def guarded_connect(self, *args, **kwargs):
        raise RuntimeError("Outbound network connections are forbidden in unit tests!")

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)


class FakeFetcher:
    """Fake PageFetcher for testing without network or browser."""

    def __init__(self, canned_soup: Any = None) -> None:
        self.canned_soup = canned_soup
        self.closed: bool = False

    def fetch_soup(self, url: str, max_attempts: int = 5) -> Any:
        return self.canned_soup

    def close(self) -> None:
        self.closed = True


class FakeScraper(scraper.SubstackScraper):
    """Test scraper stub injecting FakeFetcher by default and guarding against network calls."""

    def __init__(
        self,
        base_substack_url: str,
        content_save_dir: str = "content",
        download_images: bool = False,
        overwrite: bool = False,
        clean_content: bool = True,
        fetcher: PageFetcher | None = None,
        post_urls: list[str] | None = None,
    ) -> None:
        if not url_utils.is_post_url(base_substack_url):
            with patch("scraper.substack.discover_post_urls", return_value=post_urls or []):
                super().__init__(
                    base_substack_url=base_substack_url,
                    fetcher=fetcher if fetcher is not None else FakeFetcher(),
                    content_save_dir=content_save_dir,
                    download_images=download_images,
                    overwrite=overwrite,
                    clean_content=clean_content,
                )
        else:
            super().__init__(
                base_substack_url=base_substack_url,
                fetcher=fetcher if fetcher is not None else FakeFetcher(),
                content_save_dir=content_save_dir,
                download_images=download_images,
                overwrite=overwrite,
                clean_content=clean_content,
            )
        if post_urls is not None:
            self.post_urls = post_urls


class FakeResponse:
    """Fake requests.Response for sitemap, feed, and API tests."""

    def __init__(
        self,
        json_data: Any = None,
        content: bytes = b"",
        ok: bool = True,
        status_code: int = 200,
    ) -> None:
        self._json_data = json_data if json_data is not None else []
        self.content = content
        self.ok = ok
        self.status_code = status_code

    def json(self) -> Any:
        return self._json_data


class FakeHttpResponse:
    """Fake response specifically simulating raw bytes content."""

    def __init__(self, content: bytes, status_code: int = 200, ok: bool = True) -> None:
        self.content = content
        self.status_code = status_code
        self.ok = ok
