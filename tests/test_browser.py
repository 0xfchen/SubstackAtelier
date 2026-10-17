"""Tests for BrowserManager and browser process automation."""

from unittest.mock import MagicMock, patch

from scraper.browser import BrowserManager


def test_browser_manager_get_user_data_dir():
    profile_dir = BrowserManager.get_user_data_dir("chrome")
    assert "chrome_profile" in profile_dir
    assert ".substack_scraper" in profile_dir


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
