# Replace Free/Premium Scraper Inheritance with Injectable Page Fetchers

## Problem Description

The scraper engine relied on inheritance for transport selection (`BaseSubstackScraper` ABC -> `SubstackScraper` / `PremiumSubstackScraper`), causing architectural coupling and lifecycle management issues:

1. **Transport Bound to Scraper Subclasses**:
   - `SubstackScraper` (`free.py`) and `PremiumSubstackScraper` (`premium.py`) differed almost exclusively in how a URL was converted into a `BeautifulSoup` instance (`get_url_soup`), but required separate class hierarchies and constructors.
2. **Rate-Limiting Helpers Tied to Base Scraper**:
   - Exponential backoff calculation and HTTP 429 rate limit detection lived on `BaseSubstackScraper`, despite only being required by transport page-fetching routines.
3. **Non-Deterministic Browser Process Cleanup**:
   - `PremiumSubstackScraper` closed its Playwright session via `__del__`, which cannot guarantee timely execution during interpreter shutdown or reference cycles, risking orphaned Chrome or Edge processes.
4. **Transport Initialization Mixed with Scraper Setup**:
   - Credential validation, browser launch, and authentication navigation occurred inside `PremiumSubstackScraper.__init__` before calling `super().__init__`, tightly coupling transport initialization with scraper configuration.

---

## Proposed Solution / Root Cause

- **Root Cause**: Transport mechanics (`requests` vs `playwright`) were implemented via subclassing rather than composition and dependency injection.
- **Resolution**:
  - Introduce a dedicated fetcher subsystem under [`scraper/fetchers/`](../../scraper/fetchers/):
    - [`scraper/fetchers/base.py`](../../scraper/fetchers/base.py): `PageFetcher` protocol defining `fetch_soup()` and `close()`.
    - [`scraper/fetchers/rate_limit.py`](../../scraper/fetchers/rate_limit.py): Standalone rate limit detection and jittered exponential backoff helpers (`is_rate_limited`, `compute_backoff_delay`, `handle_rate_limit`).
    - [`scraper/fetchers/http.py`](../../scraper/fetchers/http.py): `RequestsFetcher` for public articles using `requests` with 429 retry backoff.
    - [`scraper/fetchers/playwright.py`](../../scraper/fetchers/playwright.py): `PlaywrightFetcher` managing browser automation, session reuse, SSR hydration waits, and idempotent `close()`.
  - Unify scraping into a single concrete [`scraper/substack.py`](../../scraper/substack.py) (`SubstackScraper`) that accepts an injected `PageFetcher`.
  - Update [`scraper/cli.py`](../../scraper/cli.py) with `_build_page_fetcher(args)` and use `contextlib.ExitStack` to guarantee deterministic fetcher teardown even if scraper initialization fails.
  - Delete obsolete `scrapers/` directory (`base.py`, `free.py`, and `premium.py`).

---

## Verification

- **Python Test Suite**: `uv run pytest -v` (138 passed, covering `PageFetcher` implementations, context manager lifecycle, idempotent teardown, init failure cleanup, and CLI fetcher injection).
- **Python Lint & Formatting**: `uv run ruff check .` and `uv run ruff format --check .`.
