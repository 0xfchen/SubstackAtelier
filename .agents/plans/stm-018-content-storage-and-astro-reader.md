# Author-Centric Storage, Rich Metadata, Content Cleaning, and Astro Reader

## Goal

1. **Primary Goal**: Modernize the output architecture by migrating scraped essays into an author-centric directory structure (`content/<author>/`), standardizing exclusively on clean YAML frontmatter with rich embedded metadata (`tags`, `description`, `wordcount`, `audience`, `canonical_url`), and scaffolding a modern local reading application in `reader/` powered by Astro.
2. **Secondary Goal**: Elevate Markdown body quality by preserving programming language tags on code blocks (for code syntax highlighting), stripping repetitive promotional widgets and subscription CTAs (with a `--no-clean` opt-out), and eliminating redundant per-post HTML generation and legacy template assets.

---

## Background & Architecture

### 1. Author-Centric Content Storage (`content/<author>/`)

Currently, scraped Markdown files are stored under `data/md_files/<author>/`, downloaded images in `data/images/<author>/<post_slug>/`, HTML catalogs in `data/html_pages/<author>.html`, and metadata in `data/<author>.json`. This split makes individual authors difficult to export, sync, or consume in modern static site generators and content management systems.

All newsletter assets will be co-located under a root `content/` directory organized by author/publication:

```
content/
└── <author>/
    ├── posts/
    │   ├── <post_slug>.md
    │   └── ...
    ├── images/
    │   └── <post_slug>/
    │       ├── image_01.jpg
    │       └── ...
    └── metadata.json
```

#### Architectural Justification

1. **Universal Framework & SSG Interoperability**:
   - **Astro**: Ingests Markdown/MDX collections natively using the Content Layer API (`glob({ base: '../content', pattern: '*/**/posts/*.{md,mdx}' })`). Author subdirectories act naturally as route parameters or collection tags.
   - **Next.js (App Router / Velite / Contentlayer)**: Directly maps `content/` into dynamic route segments (`app/[author]/[slug]/page.tsx`).
   - **Nuxt Content / Hugo / 11ty / Docusaurus**: Standard site generators default to a top-level `content/` root.
2. **Headless & Local-First CMS Readiness**:
   - File-based CMS platforms (e.g. Decap CMS, TinaCMS, Keystatic, Obsidian) require co-located directories where documents and media share a clean relative boundary.
3. **Atomic Author Portability**:
   - Archiving, syncing (via Git submodules or S3 buckets), or deleting an author is an atomic folder operation: `content/<author>/` encapsulates all posts, downloaded images, and catalog metadata without orphaned files.
4. **Deterministic Relative Media Paths**:
   - Images stored in `content/<author>/images/<post_slug>/` are referenced in Markdown via `../images/<post_slug>/...`. Images render identically in IDE previews, Obsidian, GitHub web views, and static site generators without CDN dependencies or URL rewrites.

---

### 2. Standardizing Frontmatter & Rich Metadata

#### Retiring Legacy Frontmatter & `like_count`
- The legacy frontmatter format emits raw heading strings (`# Title`, `#### Subtitle`) that break standard Markdown parsers, SSGs, and frontmatter extraction libraries.
- The `like_count` field is an ephemeral social counter that creates noisy diffs across scraping runs without providing archival reading value.
- Frontmatter will be standardized strictly on clean YAML.

#### Extracting Rich Metadata from Preloads
Substack embeds the entire post state in page HTML via `window._preloads`. We can parse these fields with zero additional HTTP requests:
- **`tags`** (`list[str]`): Parsed from `post.postTags` (e.g. `["Industry Practice Deepdive", "Industry trends"]`). Powers tag pills, category filtering, and `/tags/[tag]` archives in Astro.
- **`description`** (`str`): Meta and SEO description, providing a rich summary snippet for article preview cards even when `subtitle` is blank.
- **`wordcount`** (`int`): Word count used to compute reading time badges (`round(wordcount / 200)` min read).
- **`audience`** (`str`): `"everyone"` vs `"only_paid"`. Badges articles as Free vs. Premium / Subscriber-Only.
- **`canonical_url`** (`str`): Permanent link back to the live Substack essay.

```markdown
---
title: "What is happening with code reviews?"
subtitle: "AI generates more code than devs can track..."
description: "AI generates more code than devs can track in 2026, so will the code review process have to adapt – or is it doomed? A look into this decades-old practice..."
post_id: 172985834
author: "Gergely Orosz"
date: "2026-09-09"
tags:
  - "Industry Practice Deepdive"
  - "Industry trends"
wordcount: 3895
audience: "only_paid"
canonical_url: "https://newsletter.pragmaticengineer.com/p/what-is-happening-with-code-reviews"
cover_image: "https://substackcdn.com/..."
---

# What is happening with code reviews?
...
```

---

### 3. Content Cleaning & Code Syntax Highlighting

Substack post bodies contain interactive promotional widgets, subscription banners, and untyped code fences:
1. **Code Syntax Highlighting**: Substack renders code blocks as `<pre class="language-<lang>"><code>...</code></pre>`. Standard `html2text` discards the language class and emits untyped fences (```` ``` ````). Preprocessing `<pre>` / `<code>` elements before conversion preserves the language identifier (```` ```python ````, ```` ```typescript ````), enabling Astro Tone's **Expressive Code** engine to syntax-highlight snippets.
2. **Boilerplate Stripping**: Promotional elements produce repetitive text junk in Markdown (e.g. *"Thanks for reading! Subscribe for free..."*, *"Leave a comment"*). An automated cleaner decomposes:
   - `div.subscription-widget-wrap` (Subscribe buttons and email inputs)
   - `p.button-wrapper` / `div.button-wrapper` containing "Leave a comment", "Subscribe", or "Share" buttons
   - `div.post-footer` (Footer like/share prompts)
   - `div.post-ufi` / `div.comments-section` (Comment boxes and reaction bars)
   - `div.caption-rec-wrap` (Publication recommendation cards)
   - `button.like-button` and `div.like-button-container`
   A `--no-clean` CLI flag allows users to opt out and preserve raw DOM output.

---

### 4. Astro Reader Architecture (`hanityx/astro-tone`)

Rather than maintaining a custom Markdown-to-HTML compilation pipeline, CSS styles, and legacy HTML templates, all reading and catalog UI is delegated to a local Astro application in `reader/` based on [`hanityx/astro-tone`](https://github.com/hanityx/astro-tone).

#### Features Provided Out-of-the-Box
- **Typography-first quiet layout** optimized for long-form reading.
- **Pagefind full-text static search** with `Cmd`/`Ctrl` + `K` command palette.
- **Expressive Code** for code block styling, copy buttons, and syntax highlighting.
- **Tag and category filtering** powered by our scraped `tags`.
- **Dark mode tokens** with system preference synchronization.

#### Monorepo Architecture
```
SubstackAtelier/
├── substack_scraper/          # Python scraper CLI
├── content/                   # Author-centric content archive
│   └── <author>/
│       ├── posts/*.md
│       ├── images/
│       └── metadata.json
└── reader/                    # Astro Reader (based on hanityx/astro-tone)
    ├── package.json
    ├── astro.config.mjs
    ├── src/
    │   ├── content.config.ts  # Pointed to ../content root with Substack schema
    │   ├── pages/             # Author routing, essay reader, and search
    │   └── components/
```

#### Content Layer Integration
`reader/src/content.config.ts` connects directly to the root `content/` folder:
```typescript
import { defineCollection } from 'astro:content';
import { glob } from 'astro/loaders';
import { z } from 'astro/zod';

const posts = defineCollection({
  loader: glob({ base: '../content', pattern: '*/**/posts/*.{md,mdx}' }),
  schema: ({ image }) =>
    z.object({
      title: z.string(),
      subtitle: z.string().optional(),
      description: z.string().optional(),
      post_id: z.number().optional(),
      author: z.string().optional(),
      date: z.string().or(z.date()).optional(),
      tags: z.array(z.string()).default([]),
      wordcount: z.number().optional(),
      audience: z.string().optional(),
      canonical_url: z.string().optional(),
      cover_image: z.string().optional(),
    }),
});

export const collections = { posts };
```

---

## Proposed Changes

### 1. Scraper Configuration ([`substack_scraper/config.py`](substack_scraper/config.py))
- Replace `BASE_MD_DIR = "data/md_files"` and `BASE_HTML_DIR = "data/html_pages"` with:
  ```python
  BASE_CONTENT_DIR = "content"
  ```
- Remove obsolete constants: `HTML_TEMPLATE = "author_template.html"` and `BASE_DATA_DIR = "data"`.

### 2. Base Scraper Engine ([`substack_scraper/scrapers/base.py`](substack_scraper/scrapers/base.py))
- **Output Paths**:
  - Posts: `content/<author>/posts/<post_slug>.md`
  - Images: `content/<author>/images/<post_slug>/`
  - Metadata: `content/<author>/metadata.json`
- **Rich Metadata Extraction**:
  - Implement `_extract_preloaded_post_data(html_content: str) -> dict[str, Any]` to parse `post_id`, `tags` (`postTags`), `description`, `wordcount`, `audience`, and `canonical_url` from `window._preloads`.
- **Content Cleaning**:
  - Implement `_clean_post_html(soup: BeautifulSoup) -> None` to decompose `.subscription-widget-wrap`, `.post-footer`, `.post-ufi`, `.caption-rec-wrap`, and `button.like-button`.
  - Update `html_to_md()` to detect language classes on `<pre>` / `<code>` tags and emit fenced blocks with language identifiers.
  - Add `clean_content: bool = True` parameter to `BaseSubstackScraper.__init__`.
- **Frontmatter Standardization**:
  - Refactor `combine_metadata_and_content()` to emit rich YAML/MDX frontmatter containing `tags`, `description`, `wordcount`, `audience`, and `canonical_url`.
  - Delete `combine_metadata_and_content_legacy()`.
- **HTML Retirement**:
  - Delete `save_to_html_file()` and `md_to_html()`.
  - Remove HTML writing and link injection from `scrape_posts()`.
  - Remove `like_count` extraction and property.

### 3. Free Scraper ([`substack_scraper/scrapers/free.py`](substack_scraper/scrapers/free.py))
- Remove `like_count` DOM selector (`div.like-button-container button div.label`).
- Pass `clean_content` parameter to `super().__init__()`.

### 4. CLI Entrypoint ([`substack_scraper/cli.py`](substack_scraper/cli.py))
- Remove `--html-directory` and `--frontmatter` CLI arguments.
- Add `--no-clean` flag (`action="store_false"`, `dest="clean_content"`, default `True`).
- Update default `--directory` to `BASE_CONTENT_DIR` (`content`).
- Pass `clean_content=args.clean_content` to scraper initializers.

### 5. Repository Assets & Git Rules
- **[`.gitignore`](.gitignore)**:
  - Exclude scraped content while preserving the documentation anchor:
    ```gitignore
    # Scraped content
    content/*
    !content/README.md

    # Astro Reader
    reader/node_modules/
    reader/.astro/
    reader/dist/
    ```
- **[`content/README.md`](content/README.md)**: Add documentation explaining the layout (`posts/`, `images/`, `metadata.json`) for downstream consumers.
- **Delete Obsolete Files & Retire `data/`**:
  - `data/README.md` and retire the `data/` folder entirely (replaced by `content/`)
  - `author_template.html`
  - Entire `assets/` directory (`assets/css/`, `assets/js/`, and `assets/images/screenshot.png`)
  - Remove legacy screenshot reference (`./assets/images/screenshot.png`) from root `README.md`
  - `substack_html_pages/` directory
- **[`pyproject.toml`](pyproject.toml)**:
  - Remove `markdown>=3.7` dependency.
  - Run `uv sync` to update `uv.lock`.

### 6. Astro Tone Reader Scaffolding ([`reader/`](reader/))
- Scaffold application using Node LTS (`nvs use lts`) and `pnpm` via corepack:
  ```powershell
  pnpm create astro reader --template hanityx/astro-tone --no-install --no-git
  cd reader
  pnpm install
  ```
- Configure `reader/src/content.config.ts` with `glob({ base: '../content', pattern: '*/**/posts/*.{md,mdx}' })` and the Substack frontmatter schema.
- Update routes in `reader/src/pages/` to support multi-publication browsing, tag filtering, Pagefind search, and reading views.

---

## Verification Plan

### Automated Tests
1. **Pytest Suite**:
   ```bash
   uv run pytest -v
   ```
   - Verify all tests pass with updated fixtures targeting `content/<author>/posts/` and `content/<author>/metadata.json`.
   - Add tests for `_extract_preloaded_post_data` validating `tags`, `description`, `wordcount`, `audience`, and `canonical_url`.
   - Add tests for `_clean_post_html` verifying subscription widgets and post footers are stripped.
   - Add tests for code block syntax preservation verifying language tags on code fences.
   - Add tests verifying `--no-clean` retains raw promotional widgets.
   - Verify removal of legacy frontmatter and HTML compilation tests.
2. **Code Style & Formatting**:
   ```bash
   uv run ruff check .
   uv run ruff format --check .
   ```
3. **Astro Reader Build & Typecheck**:
   ```bash
   nvs use lts  # If Node is not active in current shell
   cd reader
   pnpm check
   pnpm build
   ```

### Manual Verification
1. **Scraping Verification**:
   - Run scraper on a few live test posts:
     ```bash
     # Free Article:
     uv run substack_scraper --url https://newsletter.pragmaticengineer.com/p/designing-data-intensive-applications-book-excerpt
     # Paid Article:
     uv run substack_scraper --url https://newsletter.pragmaticengineer.com/p/what-is-happening-with-code-reviews --premium
     ```
   - Verify files are written to `content/pragmaticengineer/posts/*.md`.
   - Inspect YAML frontmatter for `tags`, `description`, `wordcount`, and `audience`.
   - Verify code blocks have typed language tags (```` ```python ````).
   - Verify subscribe buttons and promotional footers are stripped.
2. **Reader Development Verification**:
   - Start the Astro dev server:
     ```bash
     cd reader
     nvs use lts  # If Node is not active in current shell
     pnpm dev
     ```
   - Open `http://localhost:4321` in browser.
   - Verify post appears in index, tag pills filter correctly, `Cmd`/`Ctrl` + `K` search finds the article, and reading view renders typography, dark mode, and syntax highlighting cleanly.
