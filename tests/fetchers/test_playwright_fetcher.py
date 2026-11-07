"""Tests for PlaywrightFetcher automation, credential validation, and session lifecycle."""

import os
import stat
from typing import Any
from unittest.mock import MagicMock, Mock, patch

import pytest

from scraper.browser import BrowserManager
from scraper.config import SUBSTACK_SESSION_COOKIE_NAME
from scraper.fetchers import PlaywrightFetcher


def _build_login_locator_map() -> dict[str, MagicMock]:
    """Return a selector-to-mock mapping for PlaywrightFetcher._login() interactions."""
    return {
        "//a[contains(@class, 'substack-login__login-option')]": MagicMock(count=Mock(return_value=0)),
        "input[name='email']": MagicMock(),
        "#error-container": MagicMock(count=Mock(return_value=0)),
    }


def test_premium_scraper_requires_credentials_when_not_skipping(tmp_path, monkeypatch):
    """Verify missing credentials with a non-empty default storage file and no explicit flags raises ValueError."""
    default_storage_file = tmp_path / "storage_state.json"
    default_storage_file.write_text('{"cookies": [{"name": "substack.sid", "value": "abc"}]}', encoding="utf-8")

    monkeypatch.setattr("scraper.fetchers.playwright.get_credentials", lambda: ("", ""))
    monkeypatch.setattr(BrowserManager, "DEFAULT_STORAGE_STATE_PATH", str(default_storage_file))

    with pytest.raises(ValueError, match="Premium scraping requires credentials"):
        PlaywrightFetcher(
            start_url="https://example.substack.com",
            skip_login=False,
        )


def test_premium_requires_explicit_skip_login_when_credentials_missing_but_profile_exists(tmp_path, monkeypatch):
    """Verify missing credentials + non-empty default storage file + use_persistent_profile=True raises ValueError."""
    profile_dir = tmp_path / "chrome"
    profile_dir.mkdir(parents=True, exist_ok=True)
    default_storage_file = tmp_path / "storage_state.json"
    default_storage_file.write_text('{"cookies": [{"name": "substack.sid", "value": "abc"}]}', encoding="utf-8")

    monkeypatch.setattr("scraper.fetchers.playwright.get_credentials", lambda: ("", ""))
    monkeypatch.setattr(BrowserManager, "DEFAULT_STORAGE_STATE_PATH", str(default_storage_file))

    with pytest.raises(ValueError, match="Premium scraping requires credentials"):
        PlaywrightFetcher(use_persistent_profile=True)


@pytest.mark.parametrize(
    "explicit_kwargs",
    [
        {"skip_login": True},
        {"storage_state": "custom_state.json"},
        {"cdp_url": "http://localhost:9222"},
    ],
)
def test_premium_scraper_init_with_explicit_reuse_options(monkeypatch, explicit_kwargs: dict[str, Any]):
    """Verify missing credentials with explicit skip_login, storage_state, or cdp_url proceeds to the skip branch."""
    mock_session = MagicMock()
    mock_context = MagicMock()
    mock_page = MagicMock()
    mock_context.pages = [mock_page]
    mock_context.cookies.return_value = [{"name": SUBSTACK_SESSION_COOKIE_NAME, "value": "valid-cookie"}]
    mock_session.context = mock_context

    monkeypatch.setattr("scraper.fetchers.playwright.get_credentials", lambda: ("", ""))
    monkeypatch.setattr("scraper.fetchers.playwright.sleep", Mock())

    with patch("scraper.fetchers.playwright.BrowserManager.launch", return_value=mock_session):
        fetcher = PlaywrightFetcher(
            start_url="https://example.substack.com",
            **explicit_kwargs,
        )
        assert fetcher.skip_login is True
        mock_page.goto.assert_called_once_with("https://example.substack.com", wait_until="domcontentloaded")


def test_skipped_login_rejects_unauthenticated_session_and_closes_browser(monkeypatch):
    """Verify skipped login without a Substack session cookie raises RuntimeError and closes the session."""
    mock_session = MagicMock()
    mock_context = MagicMock()
    mock_page = MagicMock()
    mock_context.pages = [mock_page]
    mock_context.cookies.return_value = []
    mock_session.context = mock_context

    monkeypatch.setattr("scraper.fetchers.playwright.get_credentials", lambda: ("", ""))
    monkeypatch.setattr("scraper.fetchers.playwright.sleep", Mock())

    with (
        patch("scraper.fetchers.playwright.BrowserManager.launch", return_value=mock_session),
        pytest.raises(RuntimeError, match="not authenticated"),
    ):
        PlaywrightFetcher(
            start_url="https://example.substack.com",
            skip_login=True,
        )

    mock_session.close.assert_called_once()


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


def test_login_rejects_unconfirmed_login_and_does_not_save_profile(monkeypatch):
    """Verify _login raises RuntimeError and does not save state when still on /sign-in."""
    fetcher = PlaywrightFetcher.__new__(PlaywrightFetcher)
    fetcher.email = "user@example.com"
    fetcher.password = "secret"
    fetcher.context = MagicMock()
    fetcher.context.cookies.return_value = []
    fetcher.page = MagicMock()
    fetcher.page.url = "https://substack.com/sign-in"
    locators = _build_login_locator_map()
    fetcher.page.locator.side_effect = lambda selector: locators[selector]
    fetcher._save_session_state = Mock()
    monkeypatch.setattr("scraper.fetchers.playwright.sleep", Mock())
    monkeypatch.setattr("scraper.fetchers.playwright.PLAYWRIGHT_LOGIN_TIMEOUT_SECONDS", 1)

    with pytest.raises(RuntimeError, match="Login was not confirmed"):
        fetcher._login()

    fetcher._save_session_state.assert_not_called()


def test_login_rejects_redirect_without_session_cookie(monkeypatch):
    """Verify _login raises RuntimeError and does not save state when leaving /sign-in without session cookie."""
    fetcher = PlaywrightFetcher.__new__(PlaywrightFetcher)
    fetcher.email = "user@example.com"
    fetcher.password = "secret"
    fetcher.context = MagicMock()
    fetcher.context.cookies.return_value = [{"name": "other_cookie", "value": "123"}]
    fetcher.page = MagicMock()
    fetcher.page.url = "https://substack.com/sign-in"
    locators = _build_login_locator_map()
    fetcher.page.locator.side_effect = lambda selector: locators[selector]
    fetcher.page.click.side_effect = lambda selector: setattr(fetcher.page, "url", "https://substack.com/home")
    fetcher._save_session_state = Mock()
    monkeypatch.setattr("scraper.fetchers.playwright.sleep", Mock())
    monkeypatch.setattr("scraper.fetchers.playwright.PLAYWRIGHT_LOGIN_TIMEOUT_SECONDS", 1)

    with pytest.raises(RuntimeError, match="Login was not confirmed"):
        fetcher._login()

    fetcher._save_session_state.assert_not_called()


def test_login_succeeds_and_saves_state_when_session_cookie_present(tmp_path, monkeypatch):
    """Verify _login succeeds and saves storage state with 0o600 permissions when session cookie is present."""
    storage_file = tmp_path / "storage_state.json"
    fetcher = PlaywrightFetcher.__new__(PlaywrightFetcher)
    fetcher.email = "user@example.com"
    fetcher.password = "secret"
    fetcher.storage_state = str(storage_file)
    fetcher.context = MagicMock()
    fetcher.context.cookies.return_value = [{"name": SUBSTACK_SESSION_COOKIE_NAME, "value": "authenticated-sid"}]
    fetcher.context.storage_state.side_effect = lambda path: storage_file.write_text("{}", encoding="utf-8")
    fetcher.page = MagicMock()
    fetcher.page.url = "https://substack.com/sign-in"
    locators = _build_login_locator_map()
    fetcher.page.locator.side_effect = lambda selector: locators[selector]
    fetcher.page.click.side_effect = lambda selector: setattr(fetcher.page, "url", "https://substack.com/home")
    monkeypatch.setattr("scraper.fetchers.playwright.sleep", Mock())
    monkeypatch.setattr("scraper.fetchers.playwright.PLAYWRIGHT_LOGIN_TIMEOUT_SECONDS", 1)

    fetcher._login()

    fetcher.context.storage_state.assert_called_once_with(path=str(storage_file))
    if os.name != "nt":
        assert stat.S_IMODE(storage_file.stat().st_mode) == 0o600
