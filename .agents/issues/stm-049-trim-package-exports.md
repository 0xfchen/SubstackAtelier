# Trim Scraper Package Exports and Remove Dead Catalog Module

## Problem Description

The top-level `scraper` package exports and test mocking patterns accumulated architectural bloat and fragile indirection:

1. **Leaky Package Surface**:
   - [`scraper/__init__.py`](../../scraper/__init__.py) re-exported almost every internal utility function and constant across the codebase, obscuring the library's actual public interface.
   - `import requests  # noqa: F401` was added to `scraper/__init__.py` purely so tests could run `monkeypatch.setattr(scraper.requests, "get", ...)`.
2. **Fragile Re-Export Monkeypatching**:
   - Unit tests patched symbols at the re-export level (`scraper.requests.get`, `scraper.download_image`) rather than where the names are actually resolved and executed (`scraper.images.requests.get`, `scraper.discovery.requests.get`), risking silent failures if imports change.
3. **Test-Driven Production Indirection**:
   - [`scraper/cli.py`](../../scraper/cli.py) inspected `sys.modules.get("scraper")` via `getattr(..., "BASE_CONTENT_DIR", ...)` exclusively to support monkeypatching `scraper.BASE_CONTENT_DIR` during CLI tests.
4. **Dead Code (`scraper/catalog.py`)**:
   - `catalog.safe_json_embed()` was only used by legacy HTML catalog rendering, which was superseded by the Astro reader. It was only referenced in `__init__.py` and a single isolated unit test.

---

## Proposed Solution / Root Cause

- **Root Cause**: Package `__init__.py` was treated as a catch-all namespace for internal helpers and test hooks rather than a well-defined public contract.
- **Resolution**:
  - Delete obsolete [`scraper/catalog.py`](../../scraper/catalog.py) and remove its corresponding unit test (`test_safe_json_embed_escapes_html_tags`).
  - Trim [`scraper/__init__.py`](../../scraper/__init__.py) to expose only the public API:
    - Scraper: `SubstackScraper`
    - Fetchers: `PageFetcher`, `RequestsFetcher`, `PlaywrightFetcher`
    - Browser: `BrowserManager`
    - Converter: `convert_html_to_markdown`
    - Config: `get_credentials`, `BASE_CONTENT_DIR`
    - CLI: `main`, `parse_args`
    - Define a strict `__all__` list and remove `import requests  # noqa: F401`.
  - Remove `sys.modules.get("scraper")` indirection in [`scraper/cli.py`](../../scraper/cli.py) and [`scraper/images.py`](../../scraper/images.py), importing and using `BASE_CONTENT_DIR`, `requests`, and `download_image` directly.
  - Audit and retarget tests in [`tests/test_scraper.py`](../../tests/test_scraper.py) to patch concrete module namespaces (`scraper.images`, `scraper.discovery`, `scraper.sync`, `scraper.cli`).

---

## Verification

- **Python Test Suite**: `uv run pytest -v` (138 passed, 1 obsolete test removed and 1 CLI default directory test added).
- **Python Lint & Formatting**: `uv run ruff check .` and `uv run ruff format --check .`.
- **CLI Verification**: `uv run scraper --help` executes cleanly.
