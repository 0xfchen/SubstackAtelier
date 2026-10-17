# Decompose Base Scraper into Focused Modules

## Problem Description

[`scraper/scrapers/base.py`](../../scraper/scrapers/base.py) evolved into an 1,145-line god class (`BaseSubstackScraper`) that accumulated multiple independent responsibilities and dead compatibility artifacts:

1. **Monolithic Responsibilities**:
   - `BaseSubstackScraper` directly handles full-archive URL discovery (sitemap and RSS feed crawling), page HTML parsing (`window._preloads`, ld+json, body selectors, widget cleaning, YouTube embeds), HTML-to-Markdown conversion, YAML frontmatter formatting and extraction, filesystem persistence, metadata JSON merging, API pagination, and sync cursor state tracking alongside run-loop orchestration.
2. **Stateless Functions on Class**:
   - Over 16 methods were marked as `@staticmethod` or `@classmethod` without accessing `self` state.
3. **Dead Compatibility Artifacts**:
   - Unused return-type tuple branching in `_scrape_single_post`.
   - Legacy unused method alias `save_essays_data_to_json`.
   - Deprecated, unread attributes and constructor parameters (`html_save_dir`, `md_save_dir`, `base_md_dir`, `base_html_dir`, `frontmatter_format`, `like_count`).
   - Unused helper `_extract_post_body_html`.

---

## Proposed Solution / Root Cause

- **Root Cause**: Features (catalog sync, rich metadata, delta sync, content cleaning) were added incrementally onto `BaseSubstackScraper` rather than decomposed into modular domain services.
- **Resolution**:
  - Extract stateless domain responsibilities out of `BaseSubstackScraper` into five standalone modules under `scraper/`:
    - [`scraper/discovery.py`](../../scraper/discovery.py): Publication URL discovery via sitemaps and feeds with keyword filtering.
    - [`scraper/extract.py`](../../scraper/extract.py): Substack DOM extraction, ld+json parsing, promotional widget cleaning, and HTML-to-Markdown conversion.
    - [`scraper/frontmatter.py`](../../scraper/frontmatter.py): YAML frontmatter generation and extraction.
    - [`scraper/storage.py`](../../scraper/storage.py): Markdown file writes, sanitized filename generation, relative link resolution, and metadata JSON merging.
    - [`scraper/sync.py`](../../scraper/sync.py): Incremental sync state persistence, ISO 8601 parsing, cutoff checks, and API delta post fetching.
  - Move shared utilities to their respective existing modules: `get_slug_from_url()` in [`scraper/url_utils.py`](../../scraper/url_utils.py), `normalize_markdown()` in [`scraper/converter.py`](../../scraper/converter.py), and `EXCLUDED_URL_KEYWORDS` in [`scraper/config.py`](../../scraper/config.py).
  - Streamline `BaseSubstackScraper` to pure orchestration (~350 lines).
  - Remove dead compatibility code and unused constructor arguments.

---

## Verification

- **Python Test Suite**: `uv run pytest -v` (all tests passing including unit tests for discovery, extraction, frontmatter, storage, and sync modules).
- **Python Lint & Formatting**: `uv run ruff check .` and `uv run ruff format --check .`.
