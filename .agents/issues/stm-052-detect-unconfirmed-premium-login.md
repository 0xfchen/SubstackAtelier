# Detect Unconfirmed Premium Login

## Problem Description

Premium scraping can proceed with an unauthenticated browser session without telling the user. Every paid post then logs "Skipping premium article (no access)" and returns `None`, so the run looks successful while archiving no premium content. There are three paths to this state:

1. **A leftover profile directory counted as a login.** When credentials are missing, `PlaywrightFetcher.__init__()` automatically enabled `skip_login` if the persistent profile directory (`~/.substack_scraper/<browser>_profile`) existed. Playwright's `launch_persistent_context()` creates that directory on the first `--persistent-profile` run, **including runs where login failed**. So the directory existing proves nothing about authentication. (`BrowserManager.get_user_data_dir()` only creates the parent `~/.substack_scraper` directory, not the profile directory itself.)
2. **A storage-state file counted as a login, even when it isn't the active session.** `has_storage` is true whenever the default `storage_state.json` exists and is non-empty. `_save_session_state()` writes that file after every login, including persistent-profile runs, but `BrowserManager.launch()` never loads it when `use_persistent_profile=True`. As a result, `--persistent-profile` without credentials still auto-skips login based on a file that is not the session in use. Files written by earlier unconfirmed logins (see 3) also still trigger the skip.
3. **Unconfirmed login reported as successful.** `_login()` waits up to `PLAYWRIGHT_LOGIN_TIMEOUT_SECONDS` for navigation away from `/sign-in`. When the wait ran out (CAPTCHA, email verification, silent form failure), it still logged "Login successful!" and saved the unauthenticated session to `storage_state.json`.

In addition, when login is skipped (explicit `--skip-login`, `--storage-state`, or `--cdp-url`), the session is never checked, so stale profiles and expired cookies fail the same silent way.

## Proposed Solution / Root Cause

- **Root cause**: session reuse and login success are inferred from indirect signals (a directory exists, a file exists, the URL no longer contains `sign-in`) instead of checking whether the browser is actually authenticated.

### 1. Require explicit session reuse when credentials are missing

- Remove the automatic `skip_login` promotion entirely. Without credentials, the fetcher proceeds only if the user explicitly passes `--skip-login`, `--storage-state`, or `--cdp-url`; otherwise raise the existing `ValueError`, whose message already lists those flags.
- This removes both the profile-directory path (1) and the storage-file path (2). It also avoids special-casing which storage file belongs to which launch mode.
- **Behavior change**: `--persistent-profile` without credentials and without `--skip-login` previously auto-skipped login and now raises `ValueError`. This matches the documented usage in `README.md` and `AGENTS.md`, which already pass `--skip-login` on subsequent runs.

### 2. Confirm authentication after login

- Keep the post-wait check that raises `RuntimeError` when the browser is still on `/sign-in`.
- Strengthen success detection: after leaving `/sign-in`, confirm that a Substack session cookie is present in `self.context.cookies()` before logging success and saving state. The expected cookie is `substack.sid`; **verify the name against a live login during implementation** and define it as a constant in `scraper/config.py`.
- Implement the check as one protected helper (e.g. `_is_authenticated()`) shared by steps 2 and 3.
- Never call `_save_session_state()` unless authentication is confirmed.

### 3. Verify reused sessions when login is skipped

- After the `skip_login` / CDP branch navigates to `start_url`, call the same `_is_authenticated()` helper.
- If it fails, raise `RuntimeError` with a clear message: the reused session (profile, storage state, or CDP browser) is not logged in. Suggest rerunning with credentials, or without `--headless` and with `--persistent-profile` to complete the login interactively.
- This catches stale profiles, expired cookies, and leftover unconfirmed storage files in one place.

### 4. Move session data out of `~/.substack_scraper/` into `content/`

The `~/.substack_scraper/` folder is retired. Its contents move into the project's `content/` folder:

| Item | Old location | New location |
| :--- | :--- | :--- |
| Storage state (cookies + localStorage) | `~/.substack_scraper/storage_state.json` | `content/storage_state.json` |
| Persistent browser profiles | `~/.substack_scraper/<browser>_profile/` | `content/.browser_profiles/<browser>/` |

- **Why profiles go in a hidden subfolder**: a Chrome/Edge profile holds thousands of files plus lock files (`SingletonLock`, etc.). The reader's content loader scans `../content` with `*/**/posts/*.{md,mdx}` (`reader/src/content.config.ts`), so a profile at the `content/` root would be walked on every build and dev-server scan and could trip the file watcher on lock files. These scans skip dot-directories by default, so `content/.browser_profiles/` keeps the reader fast and safe, and avoids a name clash with a `content/<author>/` folder. The storage file is a single JSON file at the `content/` root, which the reader's pattern never matches.
- **Single source of truth** in `scraper/config.py`:
  - `DEFAULT_STORAGE_STATE_PATH = os.path.join(BASE_CONTENT_DIR, "storage_state.json")`
  - `BROWSER_PROFILES_DIR = os.path.join(BASE_CONTENT_DIR, ".browser_profiles")`
  - `BrowserManager.DEFAULT_STORAGE_STATE_PATH` points at the config value so existing callers and test monkeypatches keep working.
  - `BrowserManager.get_user_data_dir(browser)` returns `os.path.join(BROWSER_PROFILES_DIR, browser)` and creates `BROWSER_PROFILES_DIR` instead of `~/.substack_scraper`. No code should reference `~/.substack_scraper` afterwards, apart from the legacy notice below.
- **Path resolution**: like all of `content/`, the paths are relative to the current working directory (consistent with `BASE_CONTENT_DIR`). They are tied to `BASE_CONTENT_DIR`, **not** the `--directory` CLI option, so a custom output directory does not silently drop the saved session or profile.
- **Security**: both the storage file and the profiles contain session cookies. `content/*` is already gitignored (only `content/README.md` is tracked), so neither will be committed. Create `BROWSER_PROFILES_DIR` with `0o700` and write `storage_state.json` with `0o600` where the OS supports it.
- **Legacy data, no automatic migration**: moving or copying user browser data silently is risky, and the legacy storage file may come from an unconfirmed login (path 3). Instead, if `~/.substack_scraper/` exists and the matching new path does not, log a one-time info message with the manual commands, e.g.:
  ```bash
  mv ~/.substack_scraper/storage_state.json content/storage_state.json
  mkdir -p content/.browser_profiles
  mv ~/.substack_scraper/chrome_profile content/.browser_profiles/chrome
  mv ~/.substack_scraper/edge_profile content/.browser_profiles/edge
  ```
  Moving the legacy data manually is safe because step 3 verifies every reused session, so a stale or unauthenticated profile or file fails with a clear error instead of passing silently. After moving, the empty `~/.substack_scraper/` folder can be deleted.

### Out of scope

- Following `--directory` for the session-data location.
- Automatic migration of legacy `~/.substack_scraper/` data.

## Changes Made

- [`scraper/config.py`](../../scraper/config.py):
  - Added `DEFAULT_STORAGE_STATE_PATH` (`content/storage_state.json`), `BROWSER_PROFILES_DIR` (`content/.browser_profiles`), and `SUBSTACK_SESSION_COOKIE_NAME` (`substack.sid`).
  - Increased `PLAYWRIGHT_LOGIN_TIMEOUT_SECONDS` from `30` to `180` seconds to allow interactive CAPTCHA and verification completion.
- [`scraper/browser.py`](../../scraper/browser.py):
  - Pointed `BrowserManager.DEFAULT_STORAGE_STATE_PATH` at `DEFAULT_STORAGE_STATE_PATH` from `scraper/config.py`.
  - Updated `BrowserManager.get_user_data_dir()` to return `<BROWSER_PROFILES_DIR>/<browser>` and create `BROWSER_PROFILES_DIR` with `0o700` permissions.
  - Added `_log_legacy_session_notice()` to log manual `mv` migration commands when `~/.substack_scraper/` exists and the target path under `content/` does not.
- [`scraper/fetchers/playwright.py`](../../scraper/fetchers/playwright.py):
  - Removed the automatic `skip_login` promotion based on existing profile directories or default `storage_state.json` files; when credentials are missing, only explicit `skip_login=True`, `storage_state`, or `cdp_url` proceeds.
  - Added `_is_authenticated()` to verify the presence of `SUBSTACK_SESSION_COOKIE_NAME` in `self.context.cookies()`.
  - Updated `_login()` to wait until both `"sign-in" not in self.page.url` and `self._is_authenticated()` are satisfied before breaking out of the wait loop, logging success, or calling `_save_session_state()`.
  - Updated the skipped-login / CDP branch to verify `_is_authenticated()` and raise `RuntimeError` if the reused session is unauthenticated.
  - Updated `_save_session_state()` to apply `0o600` permissions to `storage_state.json`.
- [`tests/fetchers/test_playwright_fetcher.py`](../../tests/fetchers/test_playwright_fetcher.py):
  - Added unit tests for missing credentials with existing default storage file (`use_persistent_profile=True` and default), explicit session reuse flags without credentials, unauthenticated skipped login closing the session, unconfirmed login leaving `/sign-in` without a session cookie, confirmed login with a session cookie saving state (`0o600`), and selector-mapped `locator()` mocks.
- [`tests/test_browser.py`](../../tests/test_browser.py):
  - Updated `test_browser_manager_get_user_data_dir` to verify `<BROWSER_PROFILES_DIR>/chrome`, `DEFAULT_STORAGE_STATE_PATH`, and `0o700` permissions, and added `test_browser_manager_legacy_session_dir_logs_migration_notice`.
- [`tests/test_cli.py`](../../tests/test_cli.py):
  - Configured the mock session in `test_cli_builds_playwright_fetcher_with_premium` with a `substack.sid` cookie for the skipped-login verification check.
- [`README.md`](../../README.md), [`content/README.md`](../../content/README.md), [`AGENTS.md`](../../AGENTS.md):
  - Updated session storage and profile paths to `content/storage_state.json` and `content/.browser_profiles/<browser>/`, documented session verification, and added the manual `~/.substack_scraper/` migration commands.

## Verification

- **Test cases to add/update in `tests/fetchers/test_playwright_fetcher.py`**:
  - Missing credentials + non-empty default storage file + `use_persistent_profile=True` → `ValueError` (covers path 2).
  - Missing credentials + non-empty default storage file, no explicit flags → `ValueError`.
  - Missing credentials + explicit `skip_login=True` / `storage_state` / `cdp_url` → proceeds to the skip branch.
  - Login leaves `/sign-in` but no session cookie → `RuntimeError`, state not saved.
  - Login leaves `/sign-in` with a session cookie → success, state saved.
  - Skipped login with no session cookie → `RuntimeError`, session closed.
  - Skipped login with a session cookie → proceeds.
  - Remove the now-unused `get_user_data_dir` monkeypatch from `test_premium_requires_explicit_skip_login_...`.
  - Make `test_login_rejects_unconfirmed_login...` map `locator()` selectors to mocks instead of relying on a fixed three-call `side_effect` order.
- **Test cases in `tests/test_browser.py`**:
  - Update `test_browser_manager_get_user_data_dir`: the profile path is `<BROWSER_PROFILES_DIR>/chrome` under `BASE_CONTENT_DIR`, and no longer contains `.substack_scraper` (monkeypatch `BROWSER_PROFILES_DIR` to `tmp_path` so the test does not create folders in the repo).
  - `BrowserManager.DEFAULT_STORAGE_STATE_PATH` resolves to `<BASE_CONTENT_DIR>/storage_state.json`.
  - Legacy `~/.substack_scraper/` present + new paths missing → info notice logged with the `mv` command; nothing loaded from or written to the legacy location (monkeypatch `HOME`/`expanduser`).
- **Automated tests** (full suite, since `scraper/browser.py` and `scraper/config.py` change):
  ```bash
  uv run pytest
  ```
- **Lint and formatting**:
  ```bash
  uv run ruff check .
  uv run ruff format --check .
  ```
- **Manual check**: run one premium scrape with credentials and `--persistent-profile`; confirm `content/.browser_profiles/chrome/` and `content/storage_state.json` are created (directory `0o700`, file `0o600`) and nothing new appears under `~/.substack_scraper/`. Then rerun with `--persistent-profile --skip-login` and confirm the session check passes. Finally run `pnpm build` in `reader/` and confirm the build time is unaffected by the profile folder.
