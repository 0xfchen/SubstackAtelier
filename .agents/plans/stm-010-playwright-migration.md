# Playwright Migration & Session Reuse

## Goal

Migrate `SubstackAtelier` from Selenium to Playwright to:
1. **Eliminate WebDrivers completely**: No `chromedriver`, `msedgedriver`, or driver version mismatch issues.
2. **Zero Extra Browser Downloads**: Use the already-installed system Google Chrome or Microsoft Edge directly via Playwright browser channels (`channel="chrome"`, `channel="msedge"`). Do NOT download or install Playwright's bundled Chromium if Chrome/Edge is present on the computer.
3. **Seamless Session Reuse**: Re-use your authenticated Substack session (cookies, localStorage, and tokens) so you don't have to manually log in repeatedly or deal with recurring CAPTCHAs.

---

## Part 1: Zero Browser Downloads via Native System Channels

Playwright can directly launch the browsers already installed on your machine using the `channel` option. This eliminates the need to run `playwright install chromium` (~300–400 MB download):

```python
# Launch existing system Google Chrome:
playwright.chromium.launch(channel="chrome")

# Launch existing system Microsoft Edge (pre-installed on Windows):
playwright.chromium.launch(channel="msedge")
```

### Auto-Detection & Fallback Strategy:
1. Try the user's selected `--browser` (`chrome` by default).
2. If `chrome` is not found, automatically check and fall back to `msedge` (always present on Windows).
3. If neither is found and the user explicitly provides `--browser-path`, use that executable.
4. Only suggest `playwright install chromium` as an absolute last resort if no system browser exists.

---

## Part 2: How Session Reuse Works in Playwright

### Option A: Playwright Persistent Profile (Default & Recommended)
Playwright provides `launch_persistent_context(user_data_dir=..., channel="chrome")`:
- Uses a dedicated directory at `~/.substack_scraper/<browser>_profile`.
- **First run**: Opens your real Chrome/Edge. You log in once (or let the script log in / solve any CAPTCHA).
- **Subsequent runs**: Playwright reuses all saved cookies, localStorage, and session tokens. With `--skip-login`, it is immediately authenticated without any prompts.
- **Advantage**: It never conflicts with your currently open personal Chrome windows (no profile-lock conflicts).

### Option B: Storage State Export & Reuse (`storage_state.json`)
Playwright can export cookies and localStorage into a single JSON file:
```python
# Save state after login:
context.storage_state(path="~/.substack_scraper/auth_state.json")

# Restore state on subsequent runs (even in headless mode):
context = browser.new_context(storage_state="~/.substack_scraper/auth_state.json")
```
- Completely portable, lightweight, and works seamlessly headlessly.
- Automatically generated and updated upon successful login.

### Option C: Attaching to an Active Chrome/Edge Browser (CDP / Remote Debugging)
If you want to attach directly to your **already running personal Chrome/Edge window** with zero extra login:
- Chrome/Edge locks its primary user data folder with a process lock (`SingletonLock`) while open.
- However, starting Chrome with remote debugging enabled (`chrome.exe --remote-debugging-port=9222`) allows Playwright to connect directly over CDP:
  ```python
  browser = playwright.chromium.connect_over_cdp("http://localhost:9222")
  ```
- **Advantage**: Instant reuse of your active personal tabs, cookies, and subscriptions without logging in again.

---

## Part 3: Architecture & Module Changes

### 1. Dependencies (`pyproject.toml`)
- Remove `selenium>=4.16.0` and `webdriver-manager>=4.0.1`.
- Add `playwright>=1.40.0`.
- Users run `uv sync` and can immediately start scraping with their existing Chrome or Edge.

### 2. Browser Management (`substack_scraper/browser.py`)
- Replace the 560-line Selenium driver downloader and version matcher with a clean, lightweight helper:
  - `launch_browser_context(browser='chrome', headless=False, persistent=True, user_data_dir=None, cdp_url=None, storage_state=None, executable_path=None)`
  - Direct channel dispatching (`channel="chrome"`, `channel="msedge"`).
  - Auto-fallback from `chrome` to `msedge` if Chrome is absent.
  - Native persistent context support (`launch_persistent_context`).
  - Native CDP support (`connect_over_cdp`).
  - Native storage state support (`storage_state`), defaulting to standard location `~/.substack_scraper/storage_state.json`.

### 3. Premium Scraper (`substack_scraper/scrapers/premium.py`)
- Refactor to use Playwright sync API:
  - `_login()`: Automatically fills credentials if provided, waits for session, and provides interactive manual fallback for CAPTCHAs.
  - `get_url_soup()`: Uses `page.goto(url)` and waits for post content or paywall selectors without DOM stale element exceptions.
  - Automatic session saving: On successful login, automatically writes/updates `~/.substack_scraper/storage_state.json` and persistent profile.
  - Clean resource shutdown.

### 4. CLI Arguments (`substack_scraper/cli.py`)
- Remove obsolete driver flags: `--chrome-driver-path` and `--edge-driver-path`.
- Keep `--browser {chrome,edge}` and `--browser-path`.
- Keep `--persistent-profile` and `--skip-login`.
- Add `--cdp-url` (e.g. `http://localhost:9222`) for attaching directly to an existing browser window.
- Add `--storage-state` for custom auth state JSON path (defaults to `~/.substack_scraper/storage_state.json`).

### 5. Documentation Updates
- Update `README.md`:
  - Document Playwright automation with zero driver setup.
  - Document session reuse options (`--persistent-profile`, `--storage-state`, and `--cdp-url`).
  - Remove all remaining references to WebDrivers.
- Update `AGENTS.md`:
  - Update Tech Stack: replace `selenium` and `webdriver_manager` with `playwright`.
  - Update Architecture and Module Responsibilities mermaid diagrams.
  - Update command examples and module descriptions.

### 6. Verification & Tests
- Ensure all existing unit tests (59 tests) pass.
- Add mock tests for `PremiumSubstackScraper` and Playwright context creation.

