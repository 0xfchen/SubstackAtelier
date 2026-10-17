from __future__ import annotations

import logging
import os
from time import sleep

from bs4 import BeautifulSoup
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from scraper.browser import BrowserManager, PlaywrightSession
from scraper.config import (
    PLAYWRIGHT_CONTENT_RENDER_TIMEOUT_MS,
    PLAYWRIGHT_HYDRATION_TIMEOUT_MS,
    PLAYWRIGHT_LOGIN_TIMEOUT_SECONDS,
    PLAYWRIGHT_NAVIGATION_TIMEOUT_MS,
    PLAYWRIGHT_SELECTOR_TIMEOUT_MS,
    get_credentials,
)
from scraper.fetchers.rate_limit import handle_rate_limit

logger = logging.getLogger(__name__)


class PlaywrightFetcher:
    """Page fetcher implementation for authenticated / premium Substack posts using Playwright."""

    def __init__(
        self,
        browser: str = "chrome",
        headless: bool = False,
        browser_path: str = "",
        user_agent: str = "",
        use_persistent_profile: bool = False,
        skip_login: bool = False,
        storage_state: str = "",
        cdp_url: str = "",
        start_url: str = "",
    ) -> None:
        """Initialize the premium fetcher with Playwright browser automation.

        Args:
            browser: Automation browser ('chrome' or 'edge').
            headless: Whether to execute browser headlessly.
            browser_path: Optional explicit path to browser executable.
            user_agent: Custom browser user agent string.
            use_persistent_profile: Whether to save/load browser session state in profile folder.
            skip_login: Whether to bypass login when reusing authenticated profile or session.
            storage_state: Optional path to storage state JSON file for saved cookies.
            cdp_url: Optional remote debugging URL (CDP) to attach to an active browser.
            start_url: Publication or initial URL to navigate to when skipping login.

        Raises:
            ValueError: If credentials are missing when login is required.
        """
        self.email, self.password = get_credentials()
        profile_dir = BrowserManager.get_user_data_dir(browser)
        has_persistent_profile = use_persistent_profile and os.path.exists(profile_dir)
        has_storage = bool(
            storage_state
            or (
                os.path.exists(BrowserManager.DEFAULT_STORAGE_STATE_PATH)
                and os.path.getsize(BrowserManager.DEFAULT_STORAGE_STATE_PATH) > 0
            )
        )
        has_reusable_session = skip_login or has_persistent_profile or has_storage or bool(cdp_url)

        if not (self.email and self.password):
            if has_reusable_session:
                skip_login = True
                logger.info(
                    "Substack credentials not provided; automatically reusing existing persistent profile or storage state with skip_login=True."
                )
            else:
                raise ValueError(
                    "Premium scraping requires credentials. Set the SUBSTACK_EMAIL "
                    "and SUBSTACK_PASSWORD environment variables, or provide them in a "
                    ".env file in the project root:\n"
                    "    SUBSTACK_EMAIL=your-email@domain.com\n"
                    "    SUBSTACK_PASSWORD=your-password\n"
                    "If you've already logged in with a persistent profile, storage state, or CDP, "
                    "pass --persistent-profile --skip-login, --storage-state, or --cdp-url instead."
                )

        self.session: PlaywrightSession | None = BrowserManager.launch(
            browser=browser,
            headless=headless,
            browser_path=browser_path,
            user_agent=user_agent,
            use_persistent_profile=use_persistent_profile,
            storage_state=storage_state,
            cdp_url=cdp_url,
        )

        try:
            self.context = self.session.context
            self.page = self.context.pages[0] if self.context.pages else self.context.new_page()
            self.skip_login = skip_login
            self.use_persistent_profile = use_persistent_profile
            self.storage_state = storage_state or BrowserManager.DEFAULT_STORAGE_STATE_PATH

            if not skip_login and not cdp_url:
                self._login()
            else:
                logger.info("Skipping login (using existing profile or active browser session)")
                if start_url:
                    self.page.goto(start_url, wait_until="domcontentloaded")
                    sleep(2)
        except BaseException:
            self.close()
            raise

    def _save_session_state(self) -> None:
        """Persist session cookies and localStorage to storage_state.json."""
        try:
            os.makedirs(os.path.dirname(self.storage_state), exist_ok=True)
            self.context.storage_state(path=self.storage_state)
            logger.info("Session state saved to %s", self.storage_state)
        except (OSError, PlaywrightError) as exc:
            logger.warning("Could not save storage state to %s: %s", self.storage_state, exc)

    def _login(self) -> None:
        """Log into Substack via Playwright browser automation."""
        logger.info("Checking Substack login status...")
        self.page.goto("https://substack.com/sign-in", wait_until="domcontentloaded")
        sleep(2)

        # If session is already authenticated, Substack immediately redirects away from /sign-in
        if "sign-in" not in self.page.url:
            logger.info(
                "Session already authenticated (redirected to %s). Skipping login form.",
                self.page.url,
            )
            self._save_session_state()
            return

        # Click "Sign in with password" if available
        try:
            pw_button = self.page.locator("//a[contains(@class, 'substack-login__login-option')]")
            if pw_button.count() > 0:
                pw_button.first.click()
                sleep(1)
        except PlaywrightError as exc:
            logger.debug("Password login button interaction notice: %s", exc)

        # Fill credentials
        try:
            email_locator = self.page.locator("input[name='email']")
            email_locator.wait_for(state="visible", timeout=PLAYWRIGHT_SELECTOR_TIMEOUT_MS)
            email_locator.fill(self.email)
            self.page.fill("input[name='password']", self.password)
            self.page.click("button[type='submit']")
        except PlaywrightError as exc:
            logger.warning("Notice during form fill: %s", exc)

        logger.info(
            "Waiting for login to complete (this may take up to %d seconds)...",
            PLAYWRIGHT_LOGIN_TIMEOUT_SECONDS,
        )
        for _ in range(PLAYWRIGHT_LOGIN_TIMEOUT_SECONDS):
            sleep(1)
            # Check for error container
            if self.page.locator("#error-container").count() > 0 and self.page.locator("#error-container").is_visible():
                raise RuntimeError(
                    "Login unsuccessful. Please check your email and password, or your account status.\n"
                    "If you're seeing a CAPTCHA, try:\n"
                    "  1. Run without --headless to complete CAPTCHA manually\n"
                    "  2. Use --persistent-profile to save your session\n"
                    "  3. Then run with --skip-login on subsequent runs"
                )
            # Check if navigated away from sign-in
            if "sign-in" not in self.page.url:
                break

        logger.info("Login successful!")
        self._save_session_state()

    def fetch_soup(self, url: str, max_attempts: int = 5) -> BeautifulSoup | None:
        """Fetch and parse post HTML using authenticated Playwright session.

        Args:
            url: Post URL to fetch.
            max_attempts: Number of attempts on rate-limiting.

        Returns:
            BeautifulSoup | None: Parsed DOM or None if premium access denied.

        Raises:
            RuntimeError: If retry attempts are exhausted.
            ValueError: If an unexpected error occurs during fetch.
        """
        for attempt in range(1, max_attempts + 1):
            try:
                try:
                    self.page.goto(url, wait_until="domcontentloaded")
                except PlaywrightError as exc:
                    if "interrupted by another navigation" in str(exc).lower():
                        logger.debug(
                            "Navigation interrupted by redirect. Awaiting settled load state: %s",
                            exc,
                        )
                        try:
                            self.page.wait_for_load_state(
                                "domcontentloaded",
                                timeout=PLAYWRIGHT_NAVIGATION_TIMEOUT_MS,
                            )
                        except PlaywrightError:
                            pass
                    else:
                        raise

                # Wait for content or paywall selectors to be present
                try:
                    self.page.wait_for_selector(
                        "div.available-content, h1.post-title, h2.paywall-title, body > pre",
                        timeout=PLAYWRIGHT_CONTENT_RENDER_TIMEOUT_MS,
                    )
                except PlaywrightTimeoutError:
                    logger.warning("Timeout waiting for post content to render: %s", url)

                # Substack SSR initially renders h2.paywall-title on paid posts before
                # client-side hydration evaluates session auth. Wait for hydration if present.
                if self.page.locator("h2.paywall-title").count() > 0:
                    try:
                        self.page.wait_for_selector(
                            "h2.paywall-title",
                            state="detached",
                            timeout=PLAYWRIGHT_HYDRATION_TIMEOUT_MS,
                        )
                    except PlaywrightTimeoutError:
                        pass

                html_content = self.page.content()
                soup = BeautifulSoup(html_content, "html.parser")

                if handle_rate_limit(soup, attempt, max_attempts, url):
                    continue

                if soup.find("h2", class_="paywall-title"):
                    logger.info("Skipping premium article (no access): %s", url)
                    return None

                return soup
            except RuntimeError:
                raise
            except PlaywrightError as exc:
                if attempt == max_attempts:
                    raise ValueError(f"Error fetching page: {url}. Error: {exc}") from exc
                logger.warning(
                    "[%s/%s] Playwright error fetching %s: %s. Retrying in 2 seconds...",
                    attempt,
                    max_attempts,
                    url,
                    exc,
                )
                sleep(2)

        raise RuntimeError(f"Failed to fetch page after {max_attempts} attempts: {url}")

    def close(self) -> None:
        """Clean up the browser session (idempotent)."""
        session = getattr(self, "session", None)
        if session is not None:
            try:
                session.close()
            except PlaywrightError as exc:
                logger.debug("Error closing session on cleanup: %s", exc)
            finally:
                self.session = None
