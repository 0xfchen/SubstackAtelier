# Substack2Markdown - Project Guidelines & Context

## Project Overview
Substack2Markdown is a modular Python package designed to scrape and archive Substack newsletters (both free and premium subscriber-only content) into Markdown and HTML formats. It also provides a local Astro reader interface with full-text search and downloads images locally when requested.

## Tech Stack & Architecture
- **Language & Standards**: Python 3.11+, PEP 8, PEP 585 (built-in generics), PEP 604 (union syntax `|`)
- **HTTP & Parsing**: `requests`, `BeautifulSoup` (bs4), `html-to-markdown` (Rust core), `mdformat`, `python-dotenv`
- **Automation / Headless Browser**: `playwright` (native Chrome and Edge channels, persistent sessions, CDP)
- **Testing**: `pytest`
- **Progress Tracking & Concurrency**: `tqdm`, `concurrent.futures.ThreadPoolExecutor`
- **Package Management**: `uv` with `pyproject.toml` and `uv.lock`

### Architecture & Module Interactions

```mermaid
flowchart LR
    CLI["CLI Entrypoint<br/><code>scraper/__main__.py</code><br/><code>scraper/cli.py</code>"]
    Config["Configuration & Credentials<br/><code>scraper/config.py</code>"]
    URLUtils["URL Parsing & Slug Utilities<br/><code>scraper/url_utils.py</code>"]
    Converter["HTML to Markdown Engine<br/><code>scraper/converter.py</code>"]
    Images["Image Pipeline & ThreadPoolExecutor<br/><code>scraper/images.py</code>"]
    Browser["Playwright Browser Manager<br/><code>scraper/browser.py</code>"]
    Discovery["URL Discovery Engine<br/><code>scraper/discovery.py</code>"]
    Extract["DOM Extraction & Parsing<br/><code>scraper/extract.py</code>"]
    Frontmatter["YAML Frontmatter Service<br/><code>scraper/frontmatter.py</code>"]
    Storage["Storage & Metadata Merging<br/><code>scraper/storage.py</code>"]
    Sync["Incremental Sync State & Delta API<br/><code>scraper/sync.py</code>"]

    subgraph Fetchers ["Fetchers Subpackage (scraper/fetchers/)"]
        PageFetcher["PageFetcher (Protocol)<br/><code>fetchers/base.py</code>"]
        RequestsFetcher["RequestsFetcher<br/><code>fetchers/http.py</code>"]
        PlaywrightFetcher["PlaywrightFetcher<br/><code>fetchers/playwright.py</code>"]
        RateLimit["Rate Limiting & Backoff<br/><code>fetchers/rate_limit.py</code>"]
    end

    SubstackScraper["SubstackScraper<br/><code>scraper/substack.py</code>"]

    CLI --> Config
    CLI --> Fetchers
    CLI --> SubstackScraper
    
    SubstackScraper --> PageFetcher
    RequestsFetcher -- implements --> PageFetcher
    PlaywrightFetcher -- implements --> PageFetcher
    RequestsFetcher --> RateLimit
    PlaywrightFetcher --> RateLimit
    
    SubstackScraper --> Discovery & Extract & Frontmatter & Storage & Sync & Images & Config & URLUtils
    Extract --> Converter
    Discovery --> Config
    Sync --> Config
    
    PlaywrightFetcher --> Browser
    PlaywrightFetcher --> Config
```

### Module Responsibilities

```mermaid
flowchart LR
    subgraph Entrypoints ["Entrypoints"]
        main["__main__.py"]
        cli["cli.py"]
        init["__init__.py"]
    end

    subgraph CoreEngine ["Scraping Engine & Fetchers"]
        scrp["substack.py<br/>SubstackScraper"]
        ftch["fetchers/http.py & playwright.py<br/>Requests & Playwright Fetchers"]
        rlmt["fetchers/rate_limit.py<br/>Backoff & 429 Retry"]
    end

    subgraph Services ["Support Modules"]
        cfg["config.py<br/>Settings & Auth"]
        url["url_utils.py<br/>Domain & Slug Parsing"]
        dsc["discovery.py<br/>Sitemap & Feed Discovery"]
        ext["extract.py<br/>DOM & Markdown Parsing"]
        fmt["frontmatter.py<br/>YAML Metadata"]
        strg["storage.py<br/>Files & Metadata JSON"]
        snc["sync.py<br/>Cursor & API Delta"]
        cnv["converter.py<br/>HTML to Markdown Engine"]
        img["images.py<br/>Async Download Pipeline"]
        brw["browser.py<br/>Playwright Session Manager"]
    end

    main --> cli
    cli --> scrp & ftch
    init --> cli & scrp & ftch
    
    scrp --> ftch
    ftch --> rlmt
    
    scrp --> cfg & url & dsc & ext & fmt & strg & snc & img
    ext --> cnv
    ftch --> brw
```

- [`scraper/config.py`](scraper/config.py): Global scraping constants, root content directory (`BASE_CONTENT_DIR = "content"`), `EXCLUDED_URL_KEYWORDS`, timeouts, and `get_credentials()` which loads from `.env` or environment variables.
- [`scraper/url_utils.py`](scraper/url_utils.py): URL validation, publication URL extraction, `get_slug_from_url()`, and `extract_main_part()` supporting custom Substack domains (e.g. `blog.bytebytego.com`, `newsletter.pragmaticengineer.com`).
- [`scraper/discovery.py`](scraper/discovery.py): Publication URL discovery via sitemap and RSS feed crawling (`discover_post_urls`) with keyword filtering.
- [`scraper/extract.py`](scraper/extract.py): Substack DOM extraction, ld+json parsing, promotional widget cleaning, YouTube embed transformations, and post HTML-to-Markdown conversion (`extract_post_data`, `post_html_to_markdown`).
- [`scraper/frontmatter.py`](scraper/frontmatter.py): YAML frontmatter formatting (`combine_metadata_and_content`) and read-back (`extract_metadata_from_md`).
- [`scraper/storage.py`](scraper/storage.py): Markdown file writes (`save_to_file`), sanitized filename generation, relative link resolution (`build_file_link`), and metadata JSON merging (`save_posts_data_to_json`).
- [`scraper/sync.py`](scraper/sync.py): Incremental sync state persistence (`load_sync_state`, `save_sync_state`), ISO 8601 parsing, cutoff checks, and API delta post fetching (`fetch_posts_from_api`).
- [`scraper/__init__.py`](scraper/__init__.py): Exposes clean public API (`SubstackScraper`, `PageFetcher`, `RequestsFetcher`, `PlaywrightFetcher`, `BrowserManager`, `convert_html_to_markdown`, `get_credentials`, `BASE_CONTENT_DIR`, `main`, `parse_args`).
- [`scraper/converter.py`](scraper/converter.py): High-performance CommonMark/GFM conversion adapter wrapping `html-to-markdown` with syntax highlighting language preservation, GFM tables, missing image alt normalization, and `normalize_markdown()`.
- [`scraper/images.py`](scraper/images.py): Image URL resolution, filename sanitization, linked image cleanup, and parallel downloads into `content/<author>/images/<slug>/` via `ThreadPoolExecutor`.
- [`scraper/browser.py`](scraper/browser.py): `BrowserManager` launching system Chrome and Edge directly via Playwright channels (`channel="chrome"`, `channel="msedge"`), persistent profiles, and CDP attach.
- [`scraper/fetchers/base.py`](scraper/fetchers/base.py): `PageFetcher` protocol (`fetch_soup`, `close`).
- [`scraper/fetchers/rate_limit.py`](scraper/fetchers/rate_limit.py): Jittered exponential backoff and HTTP 429 rate limit detection (`is_rate_limited`, `compute_backoff_delay`, `handle_rate_limit`).
- [`scraper/fetchers/http.py`](scraper/fetchers/http.py): `RequestsFetcher` for free / public Substack posts via `requests` and `BeautifulSoup`.
- [`scraper/fetchers/playwright.py`](scraper/fetchers/playwright.py): `PlaywrightFetcher` for authenticated / premium Substack posts using Playwright with session reuse and retry handling.
- [`scraper/substack.py`](scraper/substack.py): Concrete `SubstackScraper` class receiving an injected `PageFetcher` and coordinating post scraping and sync loops.
- [`scraper/cli.py`](scraper/cli.py): CLI argument parser, `_build_page_fetcher`, and execution coordinator managing deterministic cleanup via `contextlib.ExitStack`.
- [`reader/`](reader/): Static Astro reader based on Astro Tone, ingesting `../content/**/posts/*.{md,mdx}` with full-text search (Pagefind), tag filtering, syntax highlighting, and dark mode.
- [`tests/test_scraper.py`](tests/test_scraper.py): Comprehensive unit and integration test suite (138 tests).

## Project Structure & Outputs
- `content/<author>/posts/<slug>.md`: Scraped markdown files with rich YAML frontmatter.
- `content/<author>/images/<slug>/`: Downloaded post images (when `--images` is passed).
- `content/<author>/metadata.json`: Stored metadata (title, subtitle, author, date, cover image, post_id, tags, wordcount, audience, canonical_url).
- `reader/`: Local Astro static site reader.

## Setup & Environment
- Virtual environment is located at `.venv/`.
- Activate virtual environment:
  - Windows: `.\.venv\Scripts\activate`
  - POSIX: `source .venv/bin/activate`
- Install dependencies:
  ```bash
  uv sync
  # Or with pip: pip install .
  ```
- Substack credentials (for premium content):
  - Provide a `.env` file in the root (copy from `.env.example`), OR
  - Set environment variables `SUBSTACK_EMAIL` and `SUBSTACK_PASSWORD`.

## Common Commands
### Running the Scraper
- **Scrape free publication**:
  ```bash
  uv run scraper --url https://example.substack.com
  # Or: python -m scraper --url https://example.substack.com
  ```
- **Scrape single post**:
  ```bash
  uv run scraper --url https://example.substack.com/p/post-slug
  ```
- **Scrape with images downloaded locally**:
  ```bash
  uv run scraper --url https://example.substack.com --images
  ```
- **Scrape with raw promotional widgets (skip cleaning)**:
  ```bash
  uv run scraper --url https://example.substack.com --no-clean
  ```
- **Scrape premium publication**:
  ```bash
  uv run scraper --url https://example.substack.com --premium --browser chrome
  ```
- **Scrape premium with persistent profile (saves login/CAPTCHA state)**:
  ```bash
  # First run: log in or solve CAPTCHA interactively
  uv run scraper --url https://example.substack.com --premium --persistent-profile
  # Subsequent runs:
  uv run scraper --url https://example.substack.com --premium --persistent-profile --skip-login
  ```
- **Scrape premium by attaching directly to active browser (CDP)**:
  ```bash
  # Start Chrome with remote debugging: chrome.exe --remote-debugging-port=9222
  uv run scraper --url https://example.substack.com --premium --cdp-url http://localhost:9222
  ```

### Running the Local Reader
- Start the Astro reader dev server:
  ```bash
  nvs use lts
  cd reader
  pnpm dev
  ```
- Build static reader and Pagefind search index:
  ```bash
  cd reader
  pnpm build
  pnpm preview
  ```

### Running Tests
- Execute test suite with pytest:
  ```bash
  uv run pytest -v
  # Or using venv directly
  .\.venv\Scripts\pytest
  ```

## Development Guidelines & Rules
1. **Preserve Compatibility**: Support both Chrome and Edge browser channels with automatic fallback, and both Windows and Unix path handling.
2. **Rate Limiting & Resilience**: Respect exponential backoff on HTTP 429 errors when requesting Substack endpoints.
3. **Security & Credentials**: Never hardcode or commit credentials. Maintain `.env` and `config.py` in `.gitignore`.
4. **Code Quality & Typing**: Follow PEP 8 guidelines, PEP 585 built-in generics (`list`, `dict`, `tuple`), and PEP 604 union types (`T | None`).
5. **Docstrings & Scope Visibility**: Any function or method whose caller is only within the same module or class must by default be protected with a `_` prefix (e.g. `_extract_post_id`, `_extract_metadata_from_md`). Only expose functions/methods as public (no `_` prefix) if they are intended to be called from another module. Use Google-style docstrings for public classes and functions, and concise one-line docstrings for protected (`_` prefixed) methods. Maintain callee-above-caller ordering.
6. **Documentation Integrity**: Use relative repository file paths in documentation (never absolute paths). Keep tests in `tests/test_scraper.py` synchronized with all features and bugfixes.
7. **Test Mocking Conventions**: Use `Fake` as the naming prefix for test mock or stub classes rather than `Dummy` (e.g. `FakeScraper`).
8. **Linting and Formatting**: Always run `uv run ruff check .` and `uv run ruff format .` (or verify with `--check`) after making Python code changes to ensure linting and formatting compliance before proceeding.
9. **Commit Message Format**: Follow the standard Conventional Commit prefixes without component scopes (`type: description` instead of `type(scope): description`):
   - `feat:` New capabilities or user-facing features (routes to `.agents/plans/`).
   - `fix:` Bug fixes, crash prevention, input validation, safe defaults (routes to `.agents/issues/`).
   - `refactor:` Code reorganization without behavioral change (routes to `.agents/issues/`).
   - `perf:` Performance improvements, concurrency, caching (routes to `.agents/issues/`).
   - `security:` Security hardening, XSS prevention, credential safety (routes to `.agents/issues/`).
   - `docs:` Documentation changes only.
   - `test:` Test additions or test refactoring.
   - `build:` Dependencies, packaging, `pyproject.toml`, or `uv.lock`.
   - `chore:` Routine repository maintenance or configuration tweaks.
10. **Descriptive Variable Naming**: Variable names must always be clear, self-documenting noun phrases that describe the entity or data they represent, following each language's standard casing conventions (`snake_case` in Python, `camelCase` in TypeScript/JavaScript). Never use standalone adjectives or cryptic abbreviations as variable names. Adjectives should only serve as qualifiers to a noun when necessary to provide specific context or differentiation.


