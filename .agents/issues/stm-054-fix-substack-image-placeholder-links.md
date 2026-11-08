# Fix Substack Image Placeholder Links and Heading SVG Labels

## Problem Description

After migrating the HTML-to-Markdown engine from `html2text` to `html-to-markdown` (`stm-045`), scraped Substack posts contained two artifacts caused by inline `<svg>` icons in Substack's DOM:

1. **Images saved as broken text links (`[<alt>SVG ImageSVG Image](url)`):**
   - Substack wraps each article image in `<a class="image-link" href="https://substackcdn.com/image/fetch/...">` containing both `<picture><img src="..." alt="..."/></picture>` and `<div class="image-link-expand">` with two action buttons (`restack-image` and `view-image`), each holding an inline `<svg>`.
   - `_ensure_default_image_alt()` in `scraper/converter.py` populates empty `alt` attributes with `"image"`.
   - Inside `html_to_markdown.convert()`, each inline `<svg>` (with `capture_svg=False`) rendered as the fallback text `"SVG Image"`.
   - Because the `<a>` element had sibling text (`SVG ImageSVG Image`) alongside `<img>` and `ConversionOptions` did not set `keep_inline_images_in=["a"]`, `html-to-markdown` demoted the `<img>` inside `<a>` to its plain `alt` text and emitted `[<alt>SVG ImageSVG Image](<href>)` instead of a Markdown image.
   - Across `content/`, this produced **7,021** broken links (including both default `alt="image"` and custom author-supplied `alt` text).
   - Additionally, when `--images` was not passed, Substack CDN zoom-wrapper links (`[![alt](img)](https://substackcdn.com/...)`) were not unwrapped during HTML-to-Markdown conversion.
2. **Headings polluted with a trailing `SVG Image` suffix (`## Heading SVG Image`):**
   - Substack headings (`<h1>`–`<h6>`) include `<div class="header-anchor-widget">` containing a link-copy `<button><svg>…</svg></button>`.
   - `html-to-markdown` converted that inline `<svg>` into `"SVG Image"`, appending ` SVG Image` to **13,103** headings across `content/` and leaking into rendered titles, heading slugs, and the table of contents.

## Proposed Solution / Root Cause

### 1. Prevent `<svg>` fallback text and inline-image demotion during HTML conversion (`scraper/converter.py`, `scraper/extract.py`)

- In `ConversionOptions` (`scraper/converter.py`), set:
  - `strip_tags=["svg"]`: stops `html-to-markdown` from emitting `"SVG Image"` for inline `<svg>` icons in headings, image action buttons, and embedded cards.
  - `keep_inline_images_in=["a"]`: preserves `<img>` inside `<a>` as Markdown image syntax `[![alt](src)](href)` even when the link has sibling elements.
- In `_clean_post_html()` (`scraper/extract.py`), decompose Substack's non-content UI chrome (`div.image-link-expand`, `div.header-anchor-widget`) so image action buttons and heading anchor widgets are stripped when `clean_content=True`.
- Unwrap Substack CDN zoom-wrapper links (`[![alt](img)](https://substackcdn.com/...)` → `![alt](img)`) via `_unwrap_substack_linked_images()` during Markdown conversion while keeping external link targets (such as sponsor links or YouTube thumbnails) intact as `[![alt](img)](external_url)`.

### 2. Post-conversion Markdown normalization and archive repair (`scraper/converter.py`)

- `_replace_substack_image_placeholder_links()`: rewrites legacy `[<alt>SVG Image...](https://substackcdn.com/image/fetch/...)` links into `![<alt or 'image'>](https://substackcdn.com/image/fetch/...)` (and strips trailing `SVG Image` suffixes from non-CDN links), preserving custom author `alt` text when present and leaving ordinary links (`[Open image](https://substackcdn.com/image/fetch/...)`) untouched.
- `_remove_svg_image_heading_labels()`: removes empty `#{1,6} SVG Image` headings and strips trailing ` SVG Image` suffixes from `#{1,6}` headings without touching body paragraphs.
- `_clean_substack_markdown_artifacts()`: runs inside both `convert_html_to_markdown()` and `normalize_markdown()` so newly converted HTML and normalized Markdown both produce clean output, and was applied across `content/**/posts/*.md` to repair all 1,230 affected archive files in place.

## Changes Made

- **`scraper/converter.py`**:
  - Configured `ConversionOptions` with `strip_tags=["svg"]` and `keep_inline_images_in=["a"]`.
  - Added `_unwrap_substack_linked_images()`, `_replace_substack_image_placeholder_links()`, `_remove_svg_image_heading_labels()`, and `_clean_substack_markdown_artifacts()`, invoked by both `convert_html_to_markdown()` and `normalize_markdown()`.
- **`scraper/extract.py`**:
  - Added `div.image-link-expand` and `div.header-anchor-widget` to `_clean_post_html()` removal selectors.
- **`tests/test_converter.py` & `tests/test_extract.py`**:
  - Added unit tests covering Substack `<a class="image-link">` with `<picture><img/></picture>` and `<button><svg/></button>` (both default and custom `alt`), external linked images with `<svg>`, legacy `[<alt>SVG ImageSVG Image](...)` normalization, ordinary Substack CDN links, heading `<svg>` widgets and trailing ` SVG Image` suffixes, and `_clean_post_html()` widget removal.

## Verification

- **Unit tests (`tests/test_converter.py`, `tests/test_extract.py`)**:
  - Real Substack image link HTML (`<a class="image-link" href="https://substackcdn.com/image/fetch/...">` containing `<picture><img src="..." alt=""/></picture>` and two `<button><svg>…</svg></button>` elements) converts to `![image](...)`.
  - Real Substack image link HTML with custom `alt="Architecture diagram"` preserves `![Architecture diagram](...)`.
  - Linked image pointing to an external URL (`<a href="https://example.com/sponsor"><img src="https://substackcdn.com/..." alt="Sponsor"/><svg/></a>`) converts to `[![Sponsor](https://substackcdn.com/...)](https://example.com/sponsor)`.
  - Legacy Markdown `[imageSVG ImageSVG Image](https://substackcdn.com/image/fetch/...)` and `[Custom Alt TextSVG ImageSVG Image](https://substackcdn.com/image/fetch/...)` normalize to `![image](...)` and `![Custom Alt Text](...)`.
  - Ordinary text links to `substackcdn.com/image/fetch/` (`[Open image](...)`) remain regular links.
  - Heading with inline `<svg>` (`<h2><strong>Overview</strong><div class="header-anchor-widget"><button><svg><path d="M0 0"/></svg></button></div></h2>`) and heading with literal trailing ` SVG Image` convert cleanly without the suffix, while `<p>SVG Image</p>` in body text is preserved.
- **Archive verification**:
  - Confirmed `grep -rn "SVG ImageSVG Image\](" content/` and `grep -rn "^#.*SVG Image" content/` return 0 matches across all 1,242 archived `.md` files.
- **Test suite and linting**:
  ```bash
  uv run ruff check .
  uv run ruff format --check .
  uv run pytest
  ```
