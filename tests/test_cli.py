"""Tests for CLI argument parsing, validation, and fetcher wiring."""

import sys
from unittest.mock import MagicMock, Mock

import pytest

from scraper.cli import BASE_CONTENT_DIR, _build_page_fetcher, main, parse_args
from scraper.fetchers.http import RequestsFetcher
from scraper.fetchers.playwright import PlaywrightFetcher
from tests.conftest import FakeFetcher


def test_parse_args_supports_images_flag(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        ["scraper.py", "--url", "https://example.substack.com/p/post", "--images"],
    )

    args = parse_args()

    assert args.url == "https://example.substack.com/p/post"
    assert args.images is True


def test_main_bare_command_shows_help_and_exits(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["scraper.py"])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code != 0
    captured = capsys.readouterr()
    assert "--url" in captured.err or "--url" in captured.out
    assert "--premium" in captured.err or "--premium" in captured.out


def test_cli_force_flag_sets_overwrite(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        ["scraper.py", "--url", "https://example.substack.com", "--force"],
    )
    args = parse_args()
    assert args.overwrite is True

    monkeypatch.setattr(
        sys,
        "argv",
        ["scraper.py", "--url", "https://example.substack.com", "--overwrite"],
    )
    args_alias = parse_args()
    assert args_alias.overwrite is True


def test_parse_args_verbose_and_quiet_mutually_exclusive(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        ["scraper", "--url", "https://example.substack.com", "-v", "-q"],
    )
    with pytest.raises(SystemExit):
        parse_args()


def test_parse_args_verbose_flag(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        ["scraper", "--url", "https://example.substack.com", "--verbose"],
    )
    args = parse_args()
    assert args.verbose is True
    assert args.quiet is False


def test_parse_args_quiet_flag(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        ["scraper", "--url", "https://example.substack.com", "-q"],
    )
    args = parse_args()
    assert args.quiet is True
    assert args.verbose is False


def test_parse_args_supports_sync_flag(monkeypatch):
    """Verify --sync flag parses successfully in CLI arguments."""
    monkeypatch.setattr(
        sys,
        "argv",
        ["scraper", "--url", "https://example.substack.com", "--sync"],
    )
    args = parse_args()
    assert args.sync is True


def test_parse_args_sync_and_number_mutually_exclusive(monkeypatch):
    """Verify --sync and -n/--number cannot be used together."""
    monkeypatch.setattr(
        sys,
        "argv",
        ["scraper", "--url", "https://example.substack.com", "--sync", "-n", "5"],
    )
    with pytest.raises(SystemExit):
        parse_args()


def test_parse_args_sync_and_single_post_mutually_exclusive(monkeypatch):
    """Verify --sync cannot be used with an individual post URL."""
    monkeypatch.setattr(
        sys,
        "argv",
        ["scraper", "--url", "https://example.substack.com/p/my-post", "--sync"],
    )
    with pytest.raises(SystemExit):
        parse_args()


@pytest.mark.parametrize(
    "flag_args",
    [
        ["--headless"],
        ["--persistent-profile"],
        ["--skip-login"],
        ["--storage-state", "cookies.json"],
        ["--cdp-url", "http://localhost:9222"],
        ["--browser-path", "/usr/bin/chrome"],
        ["--user-agent", "custom-agent"],
        ["--browser", "edge"],
    ],
)
def test_cli_validation_browser_flags_require_premium(flag_args, capsys):
    """Verify browser automation flags without -p / --premium raise an error."""
    with pytest.raises(SystemExit) as exc_info:
        parse_args(["--url", "https://example.substack.com", *flag_args])
    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert "require the -p / --premium flag" in captured.err


@pytest.mark.parametrize(
    "incompatible_args",
    [
        ["--headless"],
        ["--browser", "edge"],
        ["--browser-path", "/bin/chrome"],
        ["--persistent-profile"],
        ["--storage-state", "state.json"],
    ],
)
def test_cli_validation_cdp_url_incompatibilities(incompatible_args, capsys):
    """Verify --cdp-url cannot be combined with browser launch options."""
    cmd = [
        "--url",
        "https://example.substack.com",
        "--premium",
        "--cdp-url",
        "http://localhost:9222",
        *incompatible_args,
    ]
    with pytest.raises(SystemExit) as exc_info:
        parse_args(cmd)
    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert "--cdp-url attaches directly to an active external browser window" in captured.err


def test_cli_validation_persistent_profile_and_storage_state_mutually_exclusive(capsys):
    """Verify --persistent-profile and --storage-state cannot be used together."""
    cmd = [
        "--url",
        "https://example.substack.com",
        "--premium",
        "--persistent-profile",
        "--storage-state",
        "cookies.json",
    ]
    with pytest.raises(SystemExit) as exc_info:
        parse_args(cmd)
    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert "mutually exclusive session persistence strategies" in captured.err


def test_cli_validation_single_post_number_guard(capsys):
    """Verify scraping an individual post with --number > 1 raises an error."""
    cmd = ["--url", "https://example.substack.com/p/my-post", "--number", "5"]
    with pytest.raises(SystemExit) as exc_info:
        parse_args(cmd)
    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert "--number cannot be greater than 1 when scraping a single post URL" in captured.err


def test_cli_validation_valid_single_post_number_one():
    """Verify scraping an individual post with --number 1 or default 0 is allowed."""
    args = parse_args(["--url", "https://example.substack.com/p/my-post", "--number", "1"])
    assert args.number == 1

    args_default = parse_args(["--url", "https://example.substack.com/p/my-post"])
    assert args_default.number == 0


def test_cli_builds_requests_fetcher_by_default(monkeypatch):
    """Verify CLI builds RequestsFetcher by default."""
    monkeypatch.setattr(
        sys,
        "argv",
        ["scraper", "--url", "https://example.substack.com"],
    )
    args = parse_args()
    fetcher = _build_page_fetcher(args)
    assert isinstance(fetcher, RequestsFetcher)


def test_cli_builds_playwright_fetcher_with_premium(monkeypatch):
    """Verify CLI builds PlaywrightFetcher when --premium is set."""
    monkeypatch.setattr(
        sys,
        "argv",
        ["scraper", "--url", "https://example.substack.com", "--premium", "--skip-login"],
    )
    args = parse_args()

    mock_session = MagicMock()
    monkeypatch.setattr("scraper.fetchers.playwright.BrowserManager.launch", lambda **kwargs: mock_session)
    fetcher = _build_page_fetcher(args)
    assert isinstance(fetcher, PlaywrightFetcher)


def test_cli_closes_fetcher_when_scraper_init_fails(monkeypatch):
    """Verify CLI closes the fetcher via ExitStack even if SubstackScraper.__init__ fails."""
    monkeypatch.setattr(
        sys,
        "argv",
        ["scraper", "--url", "https://example.substack.com"],
    )
    fake_fetcher = FakeFetcher()
    monkeypatch.setattr("scraper.cli._build_page_fetcher", lambda args: fake_fetcher)
    monkeypatch.setattr("scraper.cli.SubstackScraper.__init__", Mock(side_effect=RuntimeError("Init boom")))

    with pytest.raises(RuntimeError, match="Init boom"):
        main()

    assert fake_fetcher.closed is True


def test_cli_uses_base_content_dir_by_default(monkeypatch):
    """Verify CLI defaults to BASE_CONTENT_DIR when --directory is omitted."""
    monkeypatch.setattr(
        sys,
        "argv",
        ["scraper", "--url", "https://example.substack.com"],
    )
    fake_fetcher = FakeFetcher()
    monkeypatch.setattr("scraper.cli._build_page_fetcher", lambda args: fake_fetcher)

    captured_init_kwargs = {}

    def fake_init(self, **kwargs):
        captured_init_kwargs.update(kwargs)
        self.fetcher = kwargs.get("fetcher", fake_fetcher)

    monkeypatch.setattr("scraper.cli.SubstackScraper.__init__", fake_init)
    monkeypatch.setattr("scraper.cli.SubstackScraper.scrape_posts", Mock())

    main()

    assert captured_init_kwargs["content_save_dir"] == BASE_CONTENT_DIR
