"""Tests for PlaywrightFetcher automation, credential validation, and session lifecycle."""

from unittest.mock import MagicMock, Mock, patch

import pytest

from scraper.browser import BrowserManager
from scraper.fetchers import PlaywrightFetcher


def test_premium_scraper_requires_credentials_when_not_skipping():
    with (
        patch("scraper.fetchers.playwright.get_credentials", return_value=("", "")),
        patch(
            "scraper.fetchers.playwright.BrowserManager.DEFAULT_STORAGE_STATE_PATH",
            "/nonexistent/path/storage.json",
        ),
    ):
        with pytest.raises(ValueError, match="Premium scraping requires credentials"):
            PlaywrightFetcher(
                start_url="https://example.substack.com",
                skip_login=False,
            )


def test_premium_scraper_init_with_skip_login():
    mock_session = MagicMock()
    mock_context = MagicMock()
    mock_page = MagicMock()
    mock_context.pages = [mock_page]
    mock_session.context = mock_context

    with patch("scraper.fetchers.playwright.BrowserManager.launch", return_value=mock_session):
        fetcher = PlaywrightFetcher(
            start_url="https://example.substack.com",
            skip_login=True,
        )
        assert fetcher.skip_login is True
        mock_page.goto.assert_called_once_with("https://example.substack.com", wait_until="domcontentloaded")


def test_premium_auto_skip_login_when_credentials_missing_but_profile_exists(tmp_path, monkeypatch):
    profile_dir = tmp_path / "chrome_profile"
    profile_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr("scraper.fetchers.playwright.get_credentials", lambda: (None, None))
    monkeypatch.setattr(BrowserManager, "get_user_data_dir", lambda browser: str(profile_dir))

    fake_session = MagicMock()
    fake_session.context.pages = [MagicMock()]
    monkeypatch.setattr(BrowserManager, "launch", lambda **kwargs: fake_session)

    fetcher = PlaywrightFetcher(
        start_url="https://example.substack.com/p/premium-post",
        use_persistent_profile=True,
    )
    assert fetcher.skip_login is True


def test_playwright_fetcher_close_is_idempotent():
    """Verify closing PlaywrightFetcher multiple times does not raise."""
    fetcher = PlaywrightFetcher.__new__(PlaywrightFetcher)
    mock_session = MagicMock()
    fetcher.session = mock_session
    fetcher.close()
    mock_session.close.assert_called_once()
    assert fetcher.session is None

    # Second call should be a safe no-op
    fetcher.close()
    assert mock_session.close.call_count == 1


def test_playwright_fetcher_closes_session_when_login_fails(monkeypatch):
    """Verify PlaywrightFetcher closes the launched browser session if _login raises."""
    mock_session = MagicMock()
    mock_session.context.pages = [MagicMock()]
    monkeypatch.setattr("scraper.fetchers.playwright.get_credentials", lambda: ("user@example.com", "secret"))
    monkeypatch.setattr("scraper.fetchers.playwright.BrowserManager.launch", lambda **kwargs: mock_session)
    monkeypatch.setattr(
        PlaywrightFetcher,
        "_login",
        Mock(side_effect=RuntimeError("Login unsuccessful")),
    )

    with pytest.raises(RuntimeError, match="Login unsuccessful"):
        PlaywrightFetcher(skip_login=False)

    mock_session.close.assert_called_once()
