# Set Default Frontmatter Format to MDX

## Goal

Switch the default frontmatter format from `legacy` to `mdx` across all scrapers, CLI defaults, and documentation, ensuring modern static site generators (Next.js, Astro, Hugo, Docusaurus) can consume scraped essays out of the box.

---

## Background & Rationale

SubstackAtelier supported two frontmatter formats:
- `legacy`: Custom text headers with markdown bold labels (e.g. `# Title`, `**Author:** ...`, `**Likes:** ...`).
- `mdx`: Standard YAML frontmatter enclosed in `---` blocks with structured metadata (`title`, `subtitle`, `date`, `author`, `source_url`).

Previously, `legacy` was the default. Modern personal blogs, knowledge bases (Obsidian), and documentation sites almost universally require standard YAML frontmatter (`mdx`). Users wanting the old markdown header format can still pass `--frontmatter legacy`.

---

## Proposed Changes

### 1. Scraper Classes Defaults (`substack_scraper/scrapers/`)

- In `BaseSubstackScraper.__init__`, `SubstackScraper.__init__`, and `PremiumSubstackScraper.__init__`:
  - Change default parameter `frontmatter_format: FrontmatterFormat = "mdx"`.

### 2. CLI Defaults (`substack_scraper/cli.py`)

- In `parse_args()`:
  - Set default value for `--frontmatter` to `"mdx"`:
    ```python
    parser.add_argument(
        "--frontmatter",
        choices=["mdx", "legacy"],
        default="mdx",
        help="Format for markdown frontmatter (default: mdx).",
    )
    ```

### 3. Documentation (`README.md` & `AGENTS.md`)

- Update usage instructions in `README.md` and `AGENTS.md` showing MDX as default and `--frontmatter legacy` as an optional flag.

---

## Verification Plan

### Automated Tests
- In `tests/test_substack_scraper.py`:
  - Verify default scraper instantiation generates YAML frontmatter (`---`) containing `title`, `author`, and `date`.
  - Verify passing `frontmatter_format="legacy"` generates legacy header markdown.

