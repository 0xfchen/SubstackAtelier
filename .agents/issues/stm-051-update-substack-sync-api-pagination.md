# Update Incremental Sync for Substack Cursor Pagination

## Problem Description

Incremental sync fails against the current Substack posts API pagination contract. In `scraper/sync.py`, `fetch_posts_from_api()` requests:

```text
/api/v1/posts?offset=0&limit=25&sort=new
```

The live API rejects the `offset` parameter with HTTP 400 and reports it as invalid. Without `offset`, the endpoint returns a JSON object containing a `posts` list and a `nextCursor` value, rather than the top-level list of posts expected by the current implementation. Supplying the returned cursor as the `cursor` query parameter fetches the next page.

As a result, `--sync` logs an API warning and falls back to sitemap scraping rather than using the intended incremental delta path. The current scraper then walks discovered URLs and skips already archived Markdown files.

## Proposed Solution / Root Cause

- **Root cause**: `fetch_posts_from_api()` uses numeric offset pagination and assumes each API response is a list. The endpoint now uses cursor pagination and wraps results in an object.
- **Latent data-loss bug (fixed in scope)**: When a later page fails, `fetch_posts_from_api()` currently returns the partial `delta_posts` collected so far. `SubstackScraper.sync_posts()` in `scraper/substack.py` then advances the sync cursor to `delta_posts[0]` (the newest post), so posts on the unfetched pages fall behind the cursor and are never synced. Cursor pagination increases exposure (expired cursors, mid-run 400/429), so this must be fixed together with the pagination change.

### Request construction

- Request pages via `requests.get(api_base_url, params={...}, timeout=DEFAULT_REQUEST_TIMEOUT)` instead of f-string URLs, so the opaque cursor is URL-encoded correctly (cursors may contain `+`, `/`, `=`).
- First page: `params={"limit": limit, "sort": "new"}` — no `offset`.
- Later pages: add `"cursor": next_cursor` from the previous page's `nextCursor`.
- Confirm whether the new API enforces a lower maximum `limit` than `DEFAULT_API_POST_LIMIT` (`scraper/config.py`, currently 25); adjust the default if needed.

### Response parsing

- Expect a JSON object with a `posts` list and a `nextCursor` value.
- Treat a non-dict response, or a dict whose `posts` is missing or not a list, as a **failed response** (not as an empty page). Silently returning `[]` is interpreted by the caller as "Sync up to date", which would mask future API contract changes.
- Legacy shape: accept a top-level list response as a single, final page (no further cursor requests) to tolerate custom domains that may still serve the old contract.
- Verify the wrapped `posts` items still expose `id`, `slug`, `post_date`, and `canonical_url`, which `_is_cutoff_reached()` and `sync_posts()` depend on.

### Termination rules

`fetch_posts_from_api()` returns a list **only when the delta is known to be complete**; otherwise it returns `None` so the caller falls back to sitemap discovery without advancing the cursor.

| Condition | Result |
| :--- | :--- |
| Sync cutoff (post ID, slug, or date) reached | Stop immediately (no further page request); return collected posts |
| `nextCursor` missing/empty before reaching the cutoff | Return collected posts — the full publication history was walked, so the delta is complete (e.g. the saved post was deleted); log a warning if cutoff criteria were provided |
| Transport error, non-OK status, invalid JSON, or malformed shape on **any** page | Return `None` |
| `nextCursor` equals the previously used cursor, or an empty `posts` page carries a non-empty cursor | Return `None` (stuck pagination); log a warning |
| `max_pages` exhausted before reaching the cutoff | Return `None`; log a warning |

- Remove the `len(api_posts) < limit` short-page termination heuristic; cursor APIs may return short pages while more remain. Rely solely on the cutoff and `nextCursor`.

### Rate limiting

- Per project rule #2, apply jittered backoff on HTTP 429 using the existing helpers in `scraper/fetchers/rate_limit.py` (`is_rate_limited`, `handle_rate_limit`) before treating the page as failed. Without this, a single 429 on page 1 triggers a full sitemap scrape, which issues far more requests.

### Sync position advancement in `sync_posts()`

- **Second data-loss path**: `SubstackScraper.sync_posts()` in `scraper/substack.py` currently advances the saved sync position to `delta_posts[0]` (the newest delta post) whenever at least one post succeeds, even if older delta posts failed. Failed posts then sit behind the saved position and are never retried. This is the same class of bug as the partial-results issue above, so it is fixed in this ticket.
- **Failure definition**: a delta post counts as failed if `_scrape_single_post()` raises (per-post `except` block) or returns `None`. `None` only signals a real failure (fetch returned no page, or title/body extraction failed); already-archived posts return their existing metadata entry, so they count as successes.
- **Fix**: delta posts are already processed oldest-first (`reversed(delta_posts)`). Track the newest post processed before the first failure, and advance the saved position (`last_post_date`, `last_post_id`, `last_post_slug`) only to that post. Continue scraping the remaining newer posts and still merge every successful entry into `metadata.json`.
- If the oldest delta post fails, leave the position fields unchanged (only `last_sync_at` and `total_synced_posts` update).
- On the next sync, the failed post and everything newer are back in the delta. Posts already saved are skipped cheaply via the existing-file check in `_scrape_single_post()`, so retries do not re-download them.
- Log a warning naming the blocking post when the position is held back.
- **Known trade-off**: a post that fails every time (e.g. a paywalled post scraped without `--premium`) holds the position back on every run until it succeeds. This is acceptable because nothing is lost, and the warning makes the cause visible. A persisted failed-post retry list that lets the position move past known-bad posts is deferred to a follow-up ticket.

### Out of scope (follow-up ticket)

- Persisted failed-post retry list (see trade-off above).
- Premium content retrieval remains handled by the existing authenticated page fetcher; this change only updates API-based post discovery.

## Changes Made

- [`scraper/sync.py`](../../scraper/sync.py):
  - Added `_request_api_page()` to request `/api/v1/posts` via `requests.get(api_base_url, params=request_params, timeout=DEFAULT_REQUEST_TIMEOUT)` and apply jittered HTTP 429 rate-limit backoff using `is_rate_limited()` and `handle_rate_limit()`.
  - Added `_parse_api_page_payload()` to validate and unpack wrapped `{"posts": [...], "nextCursor": ...}` responses alongside legacy top-level list responses while rejecting malformed shapes (`None`, non-dict/non-list payloads, missing/non-list `posts`, invalid `nextCursor` types).
  - Updated `fetch_posts_from_api()` to paginate via `cursor` query parameters instead of `offset`, remove the `< limit` short-page heuristic, detect stuck pagination (repeated `nextCursor` or empty `posts` page with a non-empty cursor), and return `None` whenever any page fails or `max_pages` is exhausted before reaching the sync cutoff.
- [`scraper/substack.py`](../../scraper/substack.py):
  - Updated `SubstackScraper.sync_posts()` to track the newest contiguous post processed before the first per-post failure (`last_contiguous_post`) and advance the persisted sync cursor (`last_post_date`, `last_post_id`, `last_post_slug`) only up to that post while still merging all successful entries into `metadata.json` and logging a warning naming the blocking post.
- [`tests/conftest.py`](../../tests/conftest.py):
  - Updated `FakeResponse` to accept `params` and `json_error`, and preserve explicit `None` JSON payloads.
- [`tests/test_sync.py`](../../tests/test_sync.py):
  - Added unit tests covering wrapped cursor progression, opaque cursor encoding via `params`, cutoff termination (by ID, slug, and date), missing/empty `nextCursor`, first-page and later-page failures returning `None`, malformed payloads, repeated cursors and empty pages with cursors, `max_pages` exhaustion, legacy top-level list responses, and HTTP 429 backoff retries.
- [`tests/test_substack.py`](../../tests/test_substack.py):
  - Added caller-level tests for `sync_posts()` verifying sitemap fallback when `fetch_posts_from_api()` returns `None`, cursor advancement when all delta posts succeed, cursor hold-back when a middle or oldest delta post fails (raises or returns `None`), and existing archived files counting as successes.

## Verification

- **Observed live API behavior**: A request including `offset=0` returned HTTP 400 with an invalid-`offset` validation error. A request using `limit` and `sort=new` returned an object with `posts` and `nextCursor`; using that `nextCursor` as `cursor` returned the next page.
- **Test cases to add/update in `tests/test_sync.py`** (`FakeResponse` and `fake_get` must accept `params=`):
  - Wrapped `{"posts": [...], "nextCursor": ...}` shape with cursor progression across pages; assert the cursor value is passed through `params` unchanged and no request includes `offset`.
  - Cutoff by ID, slug, and date stops without requesting another page.
  - Missing/empty `nextCursor` before cutoff returns the collected posts.
  - First-page failure (transport error, non-OK status, invalid JSON) returns `None`.
  - **Later-page failure returns `None`**, not a partial list.
  - Malformed response (non-dict, missing `posts`, non-list `posts`) returns `None`, not `[]`.
  - Repeated `nextCursor` and empty page with non-empty cursor return `None`.
  - `max_pages` exhausted before cutoff returns `None`.
  - Legacy top-level list response is treated as a single final page.
  - HTTP 429 followed by success retries with backoff (patch the sleep).
- **Caller-level tests in `tests/test_substack.py`**:
  - When `fetch_posts_from_api` returns `None`, `sync_posts()` falls back to sitemap discovery and does not advance the sync position to an API post.
  - All delta posts succeed: the position advances to the newest delta post (regression guard).
  - A middle delta post fails (raises, and separately returns `None`): the position advances only to the newest post before the failure; newer successful posts are still merged into `metadata.json`.
  - The oldest delta post fails: the position fields stay unchanged.
  - An already-archived delta post (existing file) counts as a success and does not hold the position back.
- **Automated tests to run after implementation** (full suite, since caller behavior in `tests/test_substack.py` is affected):
  ```bash
  uv run pytest
  ```
- **Lint and formatting to run after implementation**:
  ```bash
  uv run ruff check .
  uv run ruff format --check .
  ```
