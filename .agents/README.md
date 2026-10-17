# Substack2Markdown - Tickets & Plans Index

Unified, chronological index of all retroactively created issues and plans mapped to commit history.

## Ticket Registry

| Ticket | Type | Category | Description | Document Link |
| :--- | :--- | :--- | :--- | :--- |
| **`stm-001`** | **Issue** | `security` | Prevent XSS in HTML viewer and escape embedded JSON | [`issues/stm-001-xss-prevention-and-safe-json-embed.md`](issues/stm-001-xss-prevention-and-safe-json-embed.md) |
| **`stm-002`** | **Issue** | `fix` | Improve default CLI behavior and handle missing URL safely | [`issues/stm-002-cli-missing-url-handling.md`](issues/stm-002-cli-missing-url-handling.md) |
| **`stm-003`** | **Issue** | `fix` | Add HTTP timeouts and fallback for failed image downloads | [`issues/stm-003-image-download-http-timeouts.md`](issues/stm-003-image-download-http-timeouts.md) |
| **`stm-004`** | **Plan** | `feat` | Respect custom output directories and support custom Substack domains | [`plans/stm-004-custom-directories-and-domains.md`](plans/stm-004-custom-directories-and-domains.md) |
| **`stm-005`** | **Issue** | `perf` | Parallelize image downloads using ThreadPoolExecutor | [`issues/stm-005-parallelize-image-downloads.md`](issues/stm-005-parallelize-image-downloads.md) |
| **`stm-006`** | **Plan** | `feat` | Load credentials from `.env` file if present | [`plans/stm-006-dotenv-credentials-loading.md`](plans/stm-006-dotenv-credentials-loading.md) |
| **`stm-007`** | **Issue** | `refactor` | Use logging instead of print for CLI messages | [`issues/stm-007-logging-migration-for-cli.md`](issues/stm-007-logging-migration-for-cli.md) |
| **`stm-008`** | **Issue** | `refactor` | Modularize codebase into `substack_scraper/` package | [`issues/stm-008-modularize-codebase-package.md`](issues/stm-008-modularize-codebase-package.md) |
| **`stm-009`** | **Issue** | `refactor` | Move output folders into `data/` subdirectories (`md_files`, `html_pages`, `images`) | [`issues/stm-009-standardize-data-subdirectories.md`](issues/stm-009-standardize-data-subdirectories.md) |
| **`stm-010`** | **Plan** | `feat` | Migrate premium scraper from Selenium to Playwright with session reuse | [`plans/stm-010-playwright-migration.md`](plans/stm-010-playwright-migration.md) |
| **`stm-011`** | **Issue** | `refactor` | Remove `config.py` fallback for credentials in favor of `.env` and environment variables | [`issues/stm-011-remove-config-file-credential-fallback.md`](issues/stm-011-remove-config-file-credential-fallback.md) |
| **`stm-012`** | **Plan** | `feat` | Make `--url` required in CLI and display help on bare invocation | [`plans/stm-012-cli-required-url.md`](plans/stm-012-cli-required-url.md) |
| **`stm-013`** | **Plan** | `feat` | Set default frontmatter format to MDX | [`plans/stm-013-default-mdx-frontmatter.md`](plans/stm-013-default-mdx-frontmatter.md) |
| **`stm-014`** | **Issue** | `refactor` | Type `frontmatter_format` with `Literal['mdx', 'legacy']` | [`issues/stm-014-type-frontmatter-format-literal.md`](issues/stm-014-type-frontmatter-format-literal.md) |
| **`stm-015`** | **Plan** | `feat` | Add `--force` rescraping option and image download retry with backoff | [`plans/stm-015-rescraping-and-image-retry.md`](plans/stm-015-rescraping-and-image-retry.md) |
| **`stm-016`** | **Plan** | `feat` | Catalog & Metadata Synchronization (HTML `post_id` parsing, catalog deduplication) | [`plans/stm-016-catalog-and-metadata-sync.md`](plans/stm-016-catalog-and-metadata-sync.md) |
| **`stm-017`** | **Plan** | `feat` | CLI Experience & Logging (Verbosity flags, unified logger, auto profile resolution) | [`plans/stm-017-cli-experience-and-logging.md`](plans/stm-017-cli-experience-and-logging.md) |
| **`stm-018`** | **Plan** | `feat` | Author-Centric Storage, Rich Metadata, Content Cleaning, and Astro Reader | [`plans/stm-018-content-storage-and-astro-reader.md`](plans/stm-018-content-storage-and-astro-reader.md) |
| **`stm-019`** | **Issue** | `fix` | Premium Scraper Session Redirect Timeout and SSR Hydration Paywall Check | [`issues/stm-019-premium-auth-redirect-and-ssr-hydration.md`](issues/stm-019-premium-auth-redirect-and-ssr-hydration.md) |
| **`stm-020`** | **Plan** | `feat` | Todo-Style Reading Tracker and Progress Management | [`plans/stm-020-todo-style-reading-tracker.md`](plans/stm-020-todo-style-reading-tracker.md) |
| **`stm-021`** | **Issue** | `fix` | Playwright Navigation Interruption Handling and Transient Page Fetch Retry | [`issues/stm-021-playwright-navigation-interruption-and-timeout-retry.md`](issues/stm-021-playwright-navigation-interruption-and-timeout-retry.md) |
| **`stm-022`** | **Issue** | `refactor` | Rename package and CLI from `substack_scraper` to `scraper` | [`issues/stm-022-rename-package-to-scraper.md`](issues/stm-022-rename-package-to-scraper.md) |
| **`stm-023`** | **Plan** | `feat` | Restore Table View State and Row Anchor on Back-Navigation | [`plans/stm-023-restore-table-state-and-anchor.md`](plans/stm-023-restore-table-state-and-anchor.md) |
| **`stm-024`** | **Issue** | `refactor` | Streamline Library Hero Header and Eliminate Duplicate Site Title | [`issues/stm-024-streamline-library-hero-header.md`](issues/stm-024-streamline-library-hero-header.md) |
| **`stm-025`** | **Issue** | `refactor` | Remove Redundant Feed Page and Streamline Reader Navigation | [`issues/stm-025-remove-redundant-feed-page.md`](issues/stm-025-remove-redundant-feed-page.md) |
| **`stm-026`** | **Plan** | `feat` | Interactive 3D Origami Crane for 404 Page and Contrast Enhancement | [`plans/stm-026-3d-origami-crane-404-scene.md`](plans/stm-026-3d-origami-crane-404-scene.md) |
| **`stm-027`** | **Plan** | `feat` | 3D Interactive Knowledge Graph View (Constellation View) | [`plans/stm-027-3d-knowledge-graph-view.md`](plans/stm-027-3d-knowledge-graph-view.md) |
| **`stm-028`** | **Plan** | `feat` | Four-State Reading Queue with Zero-Schema-Change Persistence | [`plans/stm-028-four-state-reading-queue.md`](plans/stm-028-four-state-reading-queue.md) |
| **`stm-029`** | **Issue** | `refactor` | Consolidate Color System into Central TypeScript Registry and Tokens | [`issues/stm-029-consolidate-color-system.md`](issues/stm-029-consolidate-color-system.md) |
| **`stm-030`** | **Issue** | `fix` | Fix Systematic Markdown Lint Violations in Scraper Pipeline | [`issues/stm-030-markdown-lint-pipeline-fixes.md`](issues/stm-030-markdown-lint-pipeline-fixes.md) |
| **`stm-031`** | **Plan** | `feat` | Incremental Delta Sync via Substack API | [`plans/stm-031-incremental-delta-sync.md`](plans/stm-031-incremental-delta-sync.md) |
| **`stm-032`** | **Issue** | `fix` | CLI Flag Validation and Conflicting Option Guards | [`issues/stm-032-cli-flag-validation-and-guards.md`](issues/stm-032-cli-flag-validation-and-guards.md) |
| **`stm-033`** | **Plan** | `feat` | Inline Highlighting and Annotations | [`plans/stm-033-inline-highlighting-and-annotations.md`](plans/stm-033-inline-highlighting-and-annotations.md) |
| **`stm-034`** | **Issue** | `fix` | Three.js Animation Loop Off-Screen Pausing and Lifecycle Hardening | [`issues/stm-034-threejs-lifecycle-and-offscreen-pausing.md`](issues/stm-034-threejs-lifecycle-and-offscreen-pausing.md) |
| **`stm-035`** | **Issue** | `fix` | Build Portability via Deterministic Content Path Resolution | [`issues/stm-035-build-portability-path-resolution.md`](issues/stm-035-build-portability-path-resolution.md) |
| **`stm-036`** | **Issue** | `fix` | Strict Hex Color Parsing and 3-Digit Shorthand Expansion | [`issues/stm-036-color-hex-parsing-and-validation.md`](issues/stm-036-color-hex-parsing-and-validation.md) |
| **`stm-037`** | **Issue** | `refactor` | Centralize Z-Index Scale Tokens, Deduplicate Tag Pill CSS, and Glassmorphic Background Token | [`issues/stm-037-centralize-z-index-tokens.md`](issues/stm-037-centralize-z-index-tokens.md) |
| **`stm-038`** | **Issue** | `refactor` | Remove Dead Code, Unused Props, and Obsolete Selectors Across Reader | [`issues/stm-038-remove-dead-code.md`](issues/stm-038-remove-dead-code.md) |
| **`stm-039`** | **Issue** | `refactor` | Extract Inline Scripts from Astro Components into Dedicated Client Modules | [`issues/stm-039-extract-inline-scripts.md`](issues/stm-039-extract-inline-scripts.md) |
| **`stm-040`** | **Issue** | `fix` | Test Coverage Improvements, Edge Cases, and Weak Assertion Hardening | [`issues/stm-040-test-coverage-improvements.md`](issues/stm-040-test-coverage-improvements.md) |
| **`stm-041`** | **Issue** | `refactor` | Modularize `graph.css` Stylesheet and Clean Up Redundant CSS Declarations | [`issues/stm-041-split-graph-css.md`](issues/stm-041-split-graph-css.md) |
| **`stm-042`** | **Issue** | `refactor` | Decompose Three.js Monolithic Scenes and Extract Shared Scene Lifecycle | [`issues/stm-042-decompose-threejs.md`](issues/stm-042-decompose-threejs.md) |
| **`stm-043`** | **Plan** | `feat` | Reading Time Quick Filter and Coffee Break Mode | [`plans/stm-043-time-to-read-filter.md`](plans/stm-043-time-to-read-filter.md) |
| **`stm-044`** | **Plan** | `feat` | Graph View Search Clear Button | [`plans/stm-044-graph-search-clear-button.md`](plans/stm-044-graph-search-clear-button.md) |
| **`stm-045`** | **Plan** | `feat` | Migrate HTML-to-Markdown Engine to html-to-markdown | [`plans/stm-045-html-to-markdown-migration.md`](plans/stm-045-html-to-markdown-migration.md) |
| **`stm-046`** | **Issue** | `refactor` | Refactor Python Scraper Deduplication and Configuration Consolidation | [`issues/stm-046-refactor-python-scraper.md`](issues/stm-046-refactor-python-scraper.md) |
| **`stm-047`** | **Issue** | `refactor` | Decompose `base.py` into Discovery, Extract, Frontmatter, Storage, and Sync Modules | [`issues/stm-047-decompose-base-scraper.md`](issues/stm-047-decompose-base-scraper.md) |
| **`stm-048`** | **Issue** | `refactor` | Replace Free/Premium Scraper Inheritance with Injectable Page Fetchers | [`issues/stm-048-injectable-page-fetchers.md`](issues/stm-048-injectable-page-fetchers.md) |
| **`stm-049`** | **Issue** | `refactor` | Trim Scraper Package Exports and Remove Dead Catalog Module | [`issues/stm-049-trim-package-exports.md`](issues/stm-049-trim-package-exports.md) |

---

### Excluded Commits
- `test: use real Substack publication URLs and variations in extract_main_part tests`
- `build: add pyproject.toml and uv.lock, replace requirements.txt`
- `build: raise minimum Python requirement to 3.11+`
- `docs: modernize README.md with CLI package usage, browser options, and clean up obsolete references`
- `chore: update default BASE_SUBSTACK_URL to https://substack.com/`
