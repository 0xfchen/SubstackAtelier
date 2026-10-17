# Split Monolithic `test_scraper.py` into Per-Module Test Files

## Problem Description

The Python test suite was concentrated in a single monolithic test file (`tests/test_scraper.py`) spanning ~1,750 lines and 138 test cases:

1. **High File Surface & Maintenance Overhead**:
   - Tests for CLI parsing, configuration, HTML extraction, Markdown conversion, storage, sync, fetchers, and browser automation were commingled in one file.
   - Finding which tests belong to a given module required scrolling through numbered comment headers and unrelated tests.
2. **Duplicated Test Stubs**:
   - Test mocks and stubs (`FakeFetcher`, `FakeScraper`, `FakeResponse`) were defined and redefined inline across multiple tests.
3. **Mismatched Structure**:
   - The test directory did not mirror the decomposed architecture of `scraper/`, obscuring module-level test coverage.

---

## Proposed Solution / Root Cause

- **Root Cause**: Test cases were accumulated historically in a single file across 49 previous tickets without modular test organization.
- **Resolution**:
  - Extract shared test stubs and fixtures into [`tests/conftest.py`](../../tests/conftest.py) (`block_external_sockets`, `FakeFetcher`, `FakeScraper`, `FakeResponse`, `FakeHttpResponse`).
  - Decompose `tests/test_scraper.py` into dedicated test modules mirroring `scraper/`:
    - [`tests/test_browser.py`](../../tests/test_browser.py): BrowserManager and Playwright launch channel tests.
    - [`tests/test_cli.py`](../../tests/test_cli.py): Argument parsing, flag validation, and CLI orchestration tests.
    - [`tests/test_config.py`](../../tests/test_config.py): Credential resolution and configuration constants tests.
    - [`tests/test_converter.py`](../../tests/test_converter.py): HTML-to-Markdown conversion, table formatting, and normalization tests.
    - [`tests/test_discovery.py`](../../tests/test_discovery.py): Sitemap crawling, RSS feed fallback, and URL discovery tests.
    - [`tests/test_extract.py`](../../tests/test_extract.py): Preloads extraction, post ID parsing, content cleaning, and YouTube embeds.
    - [`tests/test_frontmatter.py`](../../tests/test_frontmatter.py): Frontmatter formatting and extraction tests.
    - [`tests/test_images.py`](../../tests/test_images.py): Image URL resolution, sanitization, markdown rewrites, and retry downloads.
    - [`tests/test_storage.py`](../../tests/test_storage.py): Markdown file persistence, relative link resolution, and metadata merging.
    - [`tests/test_substack.py`](../../tests/test_substack.py): `SubstackScraper` orchestration, scrape loops, sync execution, and context management.
    - [`tests/test_sync.py`](../../tests/test_sync.py): Incremental sync cursor persistence and Substack API delta pagination.
    - [`tests/test_url_utils.py`](../../tests/test_url_utils.py): URL classification, publication URL extraction, and custom domain parsing.
    - [`tests/test_scripts.py`](../../tests/test_scripts.py): `scripts/check_markdown.py` test suite.
    - [`tests/fetchers/test_http_fetcher.py`](../../tests/fetchers/test_http_fetcher.py): `RequestsFetcher` HTTP fetching and paywall skipping.
    - [`tests/fetchers/test_playwright_fetcher.py`](../../tests/fetchers/test_playwright_fetcher.py): `PlaywrightFetcher` automation and session reuse.
    - [`tests/fetchers/test_rate_limit.py`](../../tests/fetchers/test_rate_limit.py): Rate limit detection and jittered backoff delay calculations.
  - Delete `tests/test_scraper.py`.

---

## Verification

- **Python Test Suite**: `uv run pytest -v` (138 passed across 16 modular test files).
- **Python Lint & Formatting**: `uv run ruff check .` and `uv run ruff format --check .`.
- **Hermeticity**: Offline guard check passes with blocked network sockets.

