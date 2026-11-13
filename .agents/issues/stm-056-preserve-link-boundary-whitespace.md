# Preserve Whitespace Around Links and Strip Phantom Whitespace Links

## Problem Description

In scraped Markdown posts (`content/<author>/posts/<slug>.md`), inline hyperlinks are frequently missing the space immediately before or after the link, or are preceded/followed by phantom `[https://...](https://...)` or `[\u2060](https://...)` links:

1. **Missing space before or after an inline link:**
   - `By early 2026,[over 30% of respondents](https://example.com/report)`
   - `As[the author notes](https://example.com/post): *"quote"* The bottleneck becomes[latency](https://example.com/latency)`
   - `**Summary sentence.**[Follow-up link](https://example.com/details)`
   - `The study [found](https://example.com/study)that performance improved.`
2. **Phantom `[url](url)` or `[\u2060](url)` link adjacent to text or an italicized/bold link:**
   - `Even in this case:[https://example.com/post](https://example.com/post)*[linked phrase](https://example.com/post).*`
   - `• **[Sponsor](https://example.com/sponsor)**[\u2060](https://example.com/sponsor) — Description.`
3. **Multi-segment links concatenated across inline emphasis:**
   - `[Part one](https://example.com)**[Part two](https://example.com)**[part three](https://example.com)`
   - `**[Part one](https://example.com)*****[part two](https://example.com)***`

## Proposed Solution / Root Cause

- **Root Cause**: In Substack's ProseMirror editor, authors often include a leading or trailing space inside a hyperlink selection, or change inline formatting (`<em>`, `<strong>`) mid-link. Unlike `<em>` and `<strong>` (where `html-to-markdown` automatically hoists leading/trailing spaces outside emphasis markers), `html-to-markdown` v3.17.0 trims `<a href="...">` text without hoisting the trimmed leading/trailing whitespace outside the `<a>` element. Furthermore, when an `<a href="url"> </a>` tag contains only whitespace (created when Substack splits formatting across a link), `html-to-markdown` trims `" "` to `""` and falls back to emitting `[url](url)` while dropping the space.

### 1. Pre-conversion HTML normalization (`scraper/converter.py`)

Add `_normalize_anchor_whitespace(parsed_soup: BeautifulSoup) -> None` and run the BeautifulSoup preprocessing pass whenever `"<img"` or `"<a"` is present in `html_content`:
- Strip zero-width characters (`\u200b`, `\u200c`, `\u200d`, `\u2060`, `\ufeff`) inside `<a>` text nodes when checking emptiness.
- For every `<a>` element that contains no `<img>` child and has no visible text (`not re.sub(r"[\s\u200b-\u200d\u2060\ufeff]+", "", link_element.get_text())`):
  - If `link_element.get_text()` contains standard whitespace, replace `link_element` with `" "` (`link_element.replace_with(" ")`).
  - Otherwise, remove `link_element` (`link_element.decompose()`).
- For every remaining `<a>` element with non-empty text:
  - If `link_element.get_text()[:1].isspace()`, strip leading whitespace from its text nodes checking `stripped = text_node.lstrip()` (breaking only when `stripped` is non-empty to handle nested elements without premature exit) and insert `" "` immediately before `link_element` (`link_element.insert_before(" ")`).
  - If `link_element.get_text()[-1:].isspace()`, strip trailing whitespace similarly using `stripped = text_node.rstrip()` and insert `" "` immediately after `link_element` (`link_element.insert_after(" ")`).
  - When `<a>` is nested inside `<strong>` or `<em>` (e.g., `<strong><a href="..."> text </a></strong>`), inserting `" "` before/after `<a>` produces `<strong> <a href="...">text</a> </strong>`, which `html-to-markdown` natively hoists outside `<strong>`/`<em>` as ` **[text](...)** `.

### 2. Post-conversion Markdown normalization and archive repair (`scraper/converter.py`)

Add `_normalize_markdown_link_spacing(markdown_content: str) -> str` inside `_clean_substack_markdown_artifacts()` (called by both `convert_html_to_markdown()` and `normalize_markdown()`) so both newly converted HTML and already-scraped `.md` files are cleaned:
- **Remove zero-width / empty phantom links**: strip `(?P<stars>\*{1,3})\[[\s\u200b-\u200d\u2060\ufeff]*\]\(https?://[^\s)]+\)(?P=stars)|\[[\s\u200b-\u200d\u2060\ufeff]*\]\(https?://[^\s)]+\)`.
- **Remove duplicate phantom `[url](url)` links adjacent to the same target URL**: match and replace `[url](url)` only when immediately preceding or following another link with the exact same target URL (e.g. `[url](url)**[Text](url)**` or `*We covered[url](url)*[topic](url)*`), preserving legitimate URL-labeled reference links, quotes, and show notes.
- **Split merged 5-asterisk emphasis bridges between adjacent links**: replace `(\[[^\]]+\]\(https?://[^\s)]+\))\*{5}(\[[^\]]+\]\(https?://[^\s)]+\))\*{5}(?=\*{0,3}\[[^\]]+\])` with `\1** ***\2*** **`, and single bridges with `\1** ***`.
- **Split adjacent links**: cleanly separate adjacent link pairs while distributing asterisks and preserving single-letter split words like `[O](url)*[Auth](url)*`.
- **Restore missing space before Markdown links**: when a non-image Markdown link is immediately preceded by word characters or clause punctuation without whitespace, insert `" "` before the link.
- **Restore missing space after Markdown links**: when a non-image Markdown link is immediately followed by `[A-Z]`, `[a-z]{4,}`, or common 1-3 letter English function words (`is`, `it`, `for`, `and`, `to`, `a`, `by`, `in`, `of`, `who`), insert `" "` after the link while preserving morphological extensions like `[note](url)d` and `[test](url)ed`.
- **One-time archive repair**: apply `_clean_substack_markdown_artifacts()` across `content/**/posts/*.md` (preserving YAML frontmatter) so existing archived posts are repaired in place without re-scraping.

## Changes Made

- [`scraper/converter.py`](../../scraper/converter.py):
  - Add `_normalize_anchor_whitespace()` to hoist leading/trailing spaces outside `<a>` elements, replace whitespace-only `<a>` elements (without `<img>`) with `" "`, decompose empty/zero-width `<a>` elements, and safely strip nested text nodes without early-exit.
  - Add `_normalize_markdown_link_spacing()` with same-URL duplicate phantom link stripping, 5-asterisk bridge splitting, short English word boundary spacing, and wire it into `_clean_substack_markdown_artifacts()`.
- [`tests/test_converter.py`](../../tests/test_converter.py):
  - Add unit tests covering leading/trailing whitespace inside `<a>`, nested `<span>` text stripping, whitespace-only `<a href="url"> </a>`, zero-width `<a href="url">\u2060</a>`, multi-segment split links, same-URL duplicate phantom link removal, legitimate URL link preservation, and short-word boundary spacing.

## Verification

- **Unit tests (`tests/test_converter.py`)**:
  - `As<a href="https://example.com"> the author notes</a>` and `becomes<a href="https://example.com"> latency</a>` convert to `As [the author notes](https://example.com)` and `becomes [latency](https://example.com)`.
  - `<p>Even in this case:<a href="https://example.com"> </a><em><a href="https://example.com">linked phrase</a>.</em></p>` converts to `Even in this case: *[linked phrase](https://example.com).*` without a phantom link.
  - Nested `<a href="..."> <span> nested text </span></a>` cleanly produces ` [nested text](url) `.
  - Legitimate reference links (`• RocksDB: [https://rocksdb.org](https://rocksdb.org)`, `Paperback edition: [https://geni.us/XxCd](https://geni.us/XxCd)`) are preserved.
  - Short-word boundary spaces are restored (`[Linear](url)for agentic` $\rightarrow$ `[Linear](url) for agentic`, `[Part 1](url)and [Part 2](url)` $\rightarrow$ `[Part 1](url) and [Part 2](url)`).
  - All 27 converter unit tests pass.
- **Archive verification**:
  - Confirmed `content/*/posts/*.md` has 0 remaining missing link boundary spaces, 0 four-asterisk bridges, and preserves all 42 legitimate URL-labeled reference links.
- **Test suite and linting**:
  ```bash
  uv run ruff check .
  uv run ruff format --check .
  uv run pytest
  cd reader && pnpm test
  ```
