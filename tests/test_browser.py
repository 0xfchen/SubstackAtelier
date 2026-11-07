"""Tests for BrowserManager and browser process automation."""

import logging
import os
import stat
from unittest.mock import MagicMock, patch

from scraper.browser import BrowserManager
from scraper.config import BASE_CONTENT_DIR, BROWSER_PROFILES_DIR, DEFAULT_STORAGE_STATE_PATH


def test_browser_manager_get_user_data_dir(tmp_path, monkeypatch):
    """Verify get_user_data_dir resolves under BROWSER_PROFILES_DIR/<browser> with 0o700 permissions."""
    assert BROWSER_PROFILES_DIR == os.path.join(BASE_CONTENT_DIR, ".browser_profiles")
    assert BrowserManager.DEFAULT_STORAGE_STATE_PATH == os.path.join(BASE_CONTENT_DIR, "storage_state.json")
    assert BrowserManager.DEFAULT_STORAGE_STATE_PATH == DEFAULT_STORAGE_STATE_PATH

    fake_profiles_dir = tmp_path / "content" / ".browser_profiles"
    monkeypatch.setattr("scraper.browser.BROWSER_PROFILES_DIR", str(fake_profiles_dir))
    monkeypatch.setenv("HOME", str(tmp_path))

    profile_dir = BrowserManager.get_user_data_dir("chrome")

    assert profile_dir == os.path.join(str(fake_profiles_dir), "chrome")
    assert ".substack_scraper" not in profile_dir
    assert fake_profiles_dir.is_dir()
    if os.name != "nt":
        assert stat.S_IMODE(fake_profiles_dir.stat().st_mode) == 0o700


def test_browser_manager_legacy_session_dir_logs_migration_notice(tmp_path, monkeypatch, caplog):
    """Verify legacy ~/.substack_scraper/ triggers an info migration notice when new paths are missing."""
    legacy_dir = tmp_path / ".substack_scraper"
    legacy_dir.mkdir(parents=True, exist_ok=True)
    legacy_storage = legacy_dir / "storage_state.json"
    legacy_storage.write_text('{"cookies": []}', encoding="utf-8")

    fake_profiles_dir = tmp_path / "content" / ".browser_profiles"
    fake_storage_path = tmp_path / "content" / "storage_state.json"
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(os.path, "expanduser", lambda path: str(tmp_path) if path == "~" else path)
    monkeypatch.setattr("scraper.browser.BROWSER_PROFILES_DIR", str(fake_profiles_dir))
    monkeypatch.setattr(BrowserManager, "DEFAULT_STORAGE_STATE_PATH", str(fake_storage_path))

    with caplog.at_level(logging.INFO):
        profile_dir = BrowserManager.get_user_data_dir("chrome")

    assert profile_dir == os.path.join(str(fake_profiles_dir), "chrome")
    assert any("mv ~/.substack_scraper/" in record.message for record in caplog.records)
    assert not fake_storage_path.exists()
    assert list(legacy_dir.iterdir()) == [legacy_storage]


def test_browser_manager_resolve_channel():
    mock_pw = MagicMock()
    mock_browser = MagicMock()
    mock_pw.chromium.launch.return_value = mock_browser

    resolved = BrowserManager.resolve_channel("chrome", mock_pw)
    assert resolved in ("chrome", "msedge")
    assert mock_browser.close.called


def test_browser_manager_launch_cdp():
    mock_pw_instance = MagicMock()
    mock_cdp_browser = MagicMock()
    mock_context = MagicMock()
    mock_cdp_browser.contexts = [mock_context]
    mock_pw_instance.chromium.connect_over_cdp.return_value = mock_cdp_browser

    with patch("scraper.browser.sync_playwright") as mock_sync_pw:
        mock_sync_pw.return_value.start.return_value = mock_pw_instance
        session = BrowserManager.launch(cdp_url="http://localhost:9222")
        assert session.context == mock_context
        mock_pw_instance.chromium.connect_over_cdp.assert_called_once_with("http://localhost:9222")
