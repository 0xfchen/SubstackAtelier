# Handle Plain-Text Rate Limits and Preserve Scrape Progress

## Problem Description

A full scrape of `https://blog.bytebytego.com/` produced hundreds of debug HTML dumps containing only plain-text `Too Many Requests`. Because `RequestsFetcher` and `PlaywrightFetcher` did not validate HTTP response status codes and `is_rate_limited()` checked only for `<pre>` tags, rate-limited responses bypassed backoff and reached the DOM extractor as invalid article pages.

Further issues were identified along the rate-limiting path:
1. **False Positives**: `is_rate_limited()` matched any `<pre>` element, causing real articles with rate-limiting code snippets (e.g. ByteByteGo posts) to be misclassified as rate-limited.
2. **Cascading Traffic**: When the sync API or sitemap experienced rate limits, the scraper fell back to full sitemap/feed scraping, amplifying requests against an already throttled host.
3. **Archive Corruption & Progress Loss**: When a scrape stopped early due to rate limits, `sync_posts()` bootstrapped `sync_state.json` from the incomplete `metadata.json`, permanently marking missing posts as synced.
4. **Unpaced Outbound Traffic**: Requests were issued back-to-back without minimum delays, triggering rate limits rapidly.
5. **Inconsistent Progress**: The progress bar total grew dynamically on skipped posts, and exits during rate limits resulted in misleading completion logs.

## Proposed Solution / Root Cause

- **Root Cause**: Rate limiting was inferred from loose DOM tags instead of HTTP status codes, and was treated as a per-post extraction failure rather than a run-level halt.
- **Run-Level Stop**: Persistent rate limits raise `RateLimitError(RuntimeError)` to stop further requests, flush collected metadata and sync positions to disk, and exit with code `75` (`EX_TEMPFAIL`) with clear resume instructions.

### Core Strategy

1. **Authoritative Detection & Pacing**: Treat HTTP status `429` as authoritative; for status-less fallbacks (e.g., interrupted navigations), match normalized whole-document text against `too many requests` or `429 too many requests`. Support delta-seconds and HTTP-date `Retry-After` headers. Introduce `RequestThrottle` to enforce minimum inter-request delays and adaptively back off upon recovery.
2. **Status Validation**: Check rate limits and non-OK statuses before DOM extraction; retry transient 5xx and connection errors with backoff, while raising `ValueError` immediately on client errors (403, 404).
3. **Sync & Progress Preservation**: On `RateLimitError`, stop the loop, merge and persist all successfully scraped entries in `metadata.json`, and retain the last contiguous sync cursor in `sync_state.json` without bootstrapping incomplete states. Fix the progress bar total to the selected URL slice.
4. **CLI Control**: Add `--delay SECONDS` (default `1.0s`, `0` to disable) and handle `RateLimitError` gracefully at the application entrypoint.

## Changes Made

- [`scraper/config.py`](../../scraper/config.py):
  - Added request pacing and retry constants: `DEFAULT_REQUEST_INTERVAL_SECONDS = 1.0`, `MAX_REQUEST_INTERVAL_SECONDS = 10.0`, `MAX_RETRY_AFTER_SECONDS = 120`, `RATE_LIMIT_MAX_ATTEMPTS = 5`, and `RATE_LIMIT_EXIT_CODE = 75`.
- [`scraper/fetchers/rate_limit.py`](../../scraper/fetchers/rate_limit.py):
  - Added `RateLimitError(RuntimeError)` carrying request URL and `retry_after_seconds`.
  - Added `RequestThrottle` enforcing minimum intervals between requests and doubling intervals on recovery.
  - Added `parse_retry_after()` and `get_retry_after_header()` supporting delta-seconds and HTTP-dates.
  - Updated `is_rate_limited()` to treat `status_code == 429` as authoritative and match whole-document text against `"too many requests"` or `"429 too many requests"`.
  - Updated `handle_rate_limit()` to respect `Retry-After` headers and raise `RateLimitError` on caps or exhausted attempts.
- [`scraper/fetchers/http.py`](../../scraper/fetchers/http.py):
  - Paced requests with `RequestThrottle`, checked rate limits before DOM extraction, retried transient 5xx/connection errors, and raised `ValueError` on 4xx statuses.
- [`scraper/fetchers/playwright.py`](../../scraper/fetchers/playwright.py):
  - Captured HTTP status and `retry-after` from `page.goto()`, paced navigations with `RequestThrottle`, and applied 5xx retries and 4xx status handling.
- [`scraper/sync.py`](../../scraper/sync.py):
  - Forwarded HTTP status and `Retry-After` from `_request_api_page()` to `handle_rate_limit()` without DOM parsing; paced pagination pages and propagated `RateLimitError`.
- [`scraper/discovery.py`](../../scraper/discovery.py):
  - Handled 429 rate limits and transient connection/timeout retries in sitemap/feed requests without falling back when rate-limited.
- [`scraper/substack.py`](../../scraper/substack.py):
  - Sliced URLs up front (`[:limit]`) with fixed progress bar totals; caught `RateLimitError` in scrape and sync loops to flush metadata and contiguous cursors before re-raising.
- [`scraper/cli.py`](../../scraper/cli.py):
  - Added `--delay` argument validation, wired pacing to fetchers, and caught `RateLimitError` to exit with code `75` and log resume guidance.
- [`tests/`](../../tests/), [`README.md`](../../README.md), [`AGENTS.md`](../../AGENTS.md):
  - Added unit and integration tests across all affected modules (198 tests total) and updated CLI documentation.

## Verification

- **Automated Tests**:
  ```bash
  uv run pytest
  ```
  Verified 198 tests passing across `test_rate_limit.py`, `test_http_fetcher.py`, `test_playwright_fetcher.py`, `test_sync.py`, `test_discovery.py`, `test_substack.py`, and `test_cli.py`.
- **Linting & Code Style**:
  ```bash
  uv run ruff check .
  uv run ruff format --check .
  ```
- **Scenario Coverage**:
  - Authoritative 429 status and whole-document fallback without code block false positives.
  - `Retry-After` parsing (delta-seconds, HTTP-dates, caps) and adaptive throttle doubling.
  - Paced requests, transient 5xx retries, and immediate 4xx exceptions.
  - Immediate run-level halt on rate limits preserving metadata and sync state without false completion logs.
