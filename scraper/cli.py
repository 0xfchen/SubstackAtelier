import argparse
import contextlib
import logging
import sys

from scraper.config import BASE_CONTENT_DIR
from scraper.fetchers import PageFetcher, PlaywrightFetcher, RequestsFetcher
from scraper.substack import SubstackScraper
from scraper.url_utils import is_post_url

logger = logging.getLogger("scraper")


def _validate_args(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    """Validate argument combinations and enforce mutual exclusivity constraints."""
    # 1. Premium-only flags passed without --premium
    browser_flags: list[str] = []
    if args.browser is not None:
        browser_flags.append(f"--browser {args.browser}")
    if args.headless:
        browser_flags.append("--headless")
    if args.persistent_profile:
        browser_flags.append("--persistent-profile")
    if args.skip_login:
        browser_flags.append("--skip-login")
    if args.storage_state:
        browser_flags.append("--storage-state")
    if args.cdp_url:
        browser_flags.append("--cdp-url")
    if args.browser_path:
        browser_flags.append("--browser-path")
    if args.user_agent:
        browser_flags.append("--user-agent")

    if not args.premium and browser_flags:
        flags_str = ", ".join(browser_flags)
        parser.error(f"Browser automation options ({flags_str}) require the -p / --premium flag.")

    # 2. --cdp-url combined with browser launch options
    if args.cdp_url:
        incompatible_with_cdp: list[str] = []
        if args.headless:
            incompatible_with_cdp.append("--headless")
        if args.browser is not None:
            incompatible_with_cdp.append(f"--browser {args.browser}")
        if args.browser_path:
            incompatible_with_cdp.append("--browser-path")
        if args.persistent_profile:
            incompatible_with_cdp.append("--persistent-profile")
        if args.storage_state:
            incompatible_with_cdp.append("--storage-state")

        if incompatible_with_cdp:
            flags_str = ", ".join(incompatible_with_cdp)
            parser.error(
                f"--cdp-url attaches directly to an active external browser window and cannot be combined with: {flags_str}."
            )

    # 3. --persistent-profile vs --storage-state
    if args.persistent_profile and args.storage_state:
        parser.error("--persistent-profile and --storage-state are mutually exclusive session persistence strategies.")

    # 4. Single-post URL validation
    if is_post_url(args.url):
        if args.number > 1:
            parser.error(f"--number cannot be greater than 1 when scraping a single post URL ({args.url}).")

    # 5. Incremental sync validation
    if args.sync and args.number != 0:
        parser.error(
            "--sync cannot be combined with --number / -n. "
            "--sync automatically discovers and downloads all new posts published since the last sync."
        )

    if args.sync and is_post_url(args.url):
        parser.error("--sync can only be used with publication URLs, not individual post URLs.")


def parse_args(args_list: list[str] | None = None) -> argparse.Namespace:
    """Parse command line arguments for the SubstackAtelier scraper CLI.

    Args:
        args_list: Optional explicit command-line argument list (defaults to sys.argv[1:]).

    Returns:
        argparse.Namespace: Parsed command-line options and flags.
    """
    parser = argparse.ArgumentParser(
        description="Scrape a Substack site and convert posts to Markdown with author-centric storage.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Free publication
  scraper --url https://example.substack.com

  # Scrape single post
  scraper --url https://example.substack.com/p/some-post-title

  # Scrape with downloaded images
  scraper --url https://example.substack.com --images

  # Premium content using Chrome or Edge
  scraper --url https://example.substack.com --premium --browser chrome

  # First run: log in and solve CAPTCHA interactively (saved to persistent profile)
  scraper --url https://example.substack.com --premium --persistent-profile

  # Subsequent runs: reuse saved session without logging in again
  scraper --url https://example.substack.com --premium --persistent-profile --skip-login

  # Connect directly to active personal browser window (CDP)
  scraper --url https://example.substack.com --premium --cdp-url http://localhost:9222
        """,
    )

    parser.add_argument(
        "-u",
        "--url",
        type=str,
        required=True,
        help="The base URL or post URL of the Substack site to scrape (required).",
    )
    parser.add_argument(
        "-d",
        "--directory",
        type=str,
        help=f"The base directory to save scraped content (default: {BASE_CONTENT_DIR}).",
    )
    parser.add_argument(
        "-n",
        "--number",
        type=int,
        default=0,
        help="Number of posts to scrape (0 = all posts).",
    )
    parser.add_argument(
        "--images",
        action="store_true",
        help="Download images and update markdown to use local paths.",
    )
    parser.add_argument(
        "--no-clean",
        dest="clean_content",
        action="store_false",
        help="Disable HTML cleaning (keep subscription buttons, paywalls, and promo widgets).",
    )
    parser.add_argument(
        "--force",
        "--overwrite",
        dest="overwrite",
        action="store_true",
        help="Force rescraping and overwrite existing markdown files.",
    )
    parser.add_argument(
        "--sync",
        action="store_true",
        help="Incremental delta sync: scrape only posts published since the last sync.",
    )

    # Premium scraping options
    premium_group = parser.add_argument_group("Premium scraping options")
    premium_group.add_argument(
        "-p",
        "--premium",
        action="store_true",
        help="Use authenticated browser automation to scrape all posts (both free and paid subscriber-only content).",
    )
    premium_group.add_argument(
        "--browser",
        type=str,
        default=None,
        choices=["chrome", "edge"],
        help="Browser to use for premium scraping (default: chrome).",
    )
    premium_group.add_argument(
        "--headless",
        action="store_true",
        help="Run browser in headless mode (may trigger CAPTCHA).",
    )
    premium_group.add_argument(
        "--persistent-profile",
        action="store_true",
        help="Use a persistent browser profile to save login state.",
    )
    premium_group.add_argument(
        "--skip-login",
        action="store_true",
        help="Skip login (use with --persistent-profile or --storage-state).",
    )
    premium_group.add_argument(
        "--storage-state",
        type=str,
        default="",
        help="Path to storage state JSON file for saved session cookies.",
    )
    premium_group.add_argument(
        "--cdp-url",
        type=str,
        default="",
        help="Connect directly to an active browser via Chrome DevTools Protocol URL (e.g. http://localhost:9222).",
    )
    premium_group.add_argument(
        "--browser-path",
        type=str,
        default="",
        help="Explicit path to Chrome or Edge browser executable.",
    )
    premium_group.add_argument(
        "--user-agent",
        type=str,
        default="",
        help="Custom user agent string.",
    )

    verbosity_group = parser.add_mutually_exclusive_group()
    verbosity_group.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose debug logging (sets level to DEBUG).",
    )
    verbosity_group.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Silence informational output; only log warnings and errors (sets level to WARNING).",
    )

    if args_list is None:
        if len(sys.argv) == 1:
            parser.print_help(sys.stderr)
            sys.exit(1)
        args = parser.parse_args()
    else:
        args = parser.parse_args(args_list)

    _validate_args(args, parser)
    return args


def _build_page_fetcher(args: argparse.Namespace) -> PageFetcher:
    """Construct the appropriate page fetcher based on CLI options."""
    if args.premium:
        return PlaywrightFetcher(
            browser=args.browser or "chrome",
            headless=args.headless,
            browser_path=args.browser_path,
            user_agent=args.user_agent,
            use_persistent_profile=args.persistent_profile,
            skip_login=args.skip_login,
            storage_state=args.storage_state or "",
            cdp_url=args.cdp_url or "",
            start_url=args.url,
        )
    return RequestsFetcher()


def main() -> None:
    """Execute the command line interface to scrape posts and build catalogs."""
    args = parse_args()

    log_level = logging.INFO
    if args.verbose:
        log_level = logging.DEBUG
    elif args.quiet:
        log_level = logging.WARNING

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    if args.directory is None:
        args.directory = BASE_CONTENT_DIR

    page_fetcher = _build_page_fetcher(args)
    with contextlib.ExitStack() as exit_stack:
        exit_stack.callback(page_fetcher.close)
        substack_scraper = SubstackScraper(
            base_substack_url=args.url,
            fetcher=page_fetcher,
            content_save_dir=args.directory,
            download_images=args.images,
            overwrite=args.overwrite,
            clean_content=args.clean_content,
        )
        if args.sync:
            substack_scraper.sync_posts()
        else:
            substack_scraper.scrape_posts(args.number)
