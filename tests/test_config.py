"""Tests for configuration settings, credentials, and constants."""

from unittest.mock import patch

from scraper.config import (
    PLAYWRIGHT_CONTENT_RENDER_TIMEOUT_MS,
    PLAYWRIGHT_HYDRATION_TIMEOUT_MS,
    PLAYWRIGHT_LOGIN_TIMEOUT_SECONDS,
    PLAYWRIGHT_NAVIGATION_TIMEOUT_MS,
    PLAYWRIGHT_SELECTOR_TIMEOUT_MS,
    USE_PREMIUM,
    get_credentials,
)


def test_default_use_premium_is_false():
    assert USE_PREMIUM is False


def test_get_credentials_env_vars(monkeypatch):
    monkeypatch.setenv("SUBSTACK_EMAIL", "env@example.com")
    monkeypatch.setenv("SUBSTACK_PASSWORD", "env-secret")

    assert get_credentials() == ("env@example.com", "env-secret")


def test_get_credentials_empty_when_unconfigured(monkeypatch):
    monkeypatch.delenv("SUBSTACK_EMAIL", raising=False)
    monkeypatch.delenv("SUBSTACK_PASSWORD", raising=False)
    with patch("dotenv.find_dotenv", return_value=""):
        assert get_credentials() == ("", "")


def test_get_credentials_loads_from_env_file(tmp_path, monkeypatch):
    monkeypatch.delenv("SUBSTACK_EMAIL", raising=False)
    monkeypatch.delenv("SUBSTACK_PASSWORD", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("SUBSTACK_EMAIL=env_user@example.com\nSUBSTACK_PASSWORD=env_pass\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    email, password = get_credentials()
    assert email == "env_user@example.com"
    assert password == "env_pass"


def test_playwright_timeout_constants():
    """Verify centralized Playwright timeouts are exported and have positive values."""
    assert PLAYWRIGHT_NAVIGATION_TIMEOUT_MS > 0
    assert PLAYWRIGHT_CONTENT_RENDER_TIMEOUT_MS > 0
    assert PLAYWRIGHT_HYDRATION_TIMEOUT_MS > 0
    assert PLAYWRIGHT_SELECTOR_TIMEOUT_MS > 0
    assert PLAYWRIGHT_LOGIN_TIMEOUT_SECONDS > 0
