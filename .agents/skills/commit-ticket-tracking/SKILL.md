---
name: commit-ticket-tracking
description: >-
  Tracks, documents, and categorizes every code change and commit in SubstackAtelier
  into unified .agents/issues/ and .agents/plans/ markdown documents, updating the
  central ticket registry in .agents/README.md. Use this skill whenever planning,
  implementing, or committing new features, fixes, or refactors.
---

# Commit & Ticket Tracking Procedure

This skill establishes the standard workflow for tracking every code change in the `SubstackAtelier` repository into `.agents/plans/` or `.agents/issues/` and maintaining the unified ticket index at `.agents/README.md`.

---

## 1. Classification & Routing Rules

Commit categorization follows the **Intent-based Conventional Commit** model (`type: summary`) **without component scopes** to keep the codebase history concise and readable. Commits are routed to either `plans/` or `issues/` based on their primary intent:

| Intent Type | Destination Directory | Document Type | What it Covers | Examples |
| :--- | :--- | :--- | :--- | :--- |
| **`feat`** | `.agents/plans/` | **Plan** | Any new capability, new CLI option/flag, format addition, or major architecture shift | `feat: make --url required`<br/>`feat: add --force rescraping`<br/>`feat: playwright migration` |
| **`fix`** | `.agents/issues/` | **Issue** | Bug fixes, crash prevention, input validation, timeout fallbacks, safe defaults | `fix: exit cleanly on missing url`<br/>`fix: add http timeouts for images` |
| **`refactor`** | `.agents/issues/` | **Issue** | Restructuring code without changing external behavior, typing, modularization, logging | `refactor: modularize package`<br/>`refactor: use logging instead of print` |
| **`security`** | `.agents/issues/` | **Issue** | Vulnerability mitigations, sanitization, XSS prevention, credential safety | `security: prevent xss in html viewer` |
| **`perf`** | `.agents/issues/` | **Issue** | Concurrency, speedups, caching, download optimization | `perf: parallelize image downloads` |

### Excluded Commit Types
Do **not** generate standalone plans or issues for:
- `test:` (pure test suite additions or test refactoring)
- `docs:` (documentation-only updates to README, etc.)
- `chore:` (minor dependency bumps or trivial config tweaks)
- `build:` (packaging or lockfile updates)

---

## 2. Ticket Numbering Convention

1. **Project Prefix & Unified Sequence**:
   - Tickets use a single, chronological sequence prefixed with `stm-` (the 3-letter short name for the **S**ubstack**T**o**M**arkdown project), followed by a three-digit zero-padded number (e.g. `stm-001`, `stm-002`, `stm-017`).
   - **Crucial**: Ticket numbers are strictly unique across the entire repository and **must never repeat between issues and plans**.
2. **Naming Pattern**:
   - Plans: `.agents/plans/stm-<number>-<short-slug>.md`
   - Issues: `.agents/issues/stm-<number>-<short-slug>.md`
3. **Next Ticket Number**:
   - To determine the next ticket number, check the highest number across both `.agents/plans/` and `.agents/issues/` (or check the latest entry in `.agents/README.md`) and increment by 1.

---

## 3. Document Templates

### Plan Template (`.agents/plans/stm-<number>-<slug>.md`)

````markdown
# [Feature Title]

## Goal

1. **Primary Goal**: Clear, high-level summary of what is added or enabled.
2. **Secondary Goal**: Additional benefits (e.g., usability, portability).

---

## Background & Architecture

Explain why this feature is needed and describe any relevant existing behavior or limitations.

---

## Proposed Changes

Group changes by module using relative repository paths:

### 1. [Module Name] (`path/to/file.py`)
- Specific changes made or proposed.

---

## Verification Plan

### Automated Tests
- Specific `pytest` commands and test cases covering the feature:
  ```bash
  uv run pytest tests/test_substack.py -k "<filter>"
  ```

### Manual Verification
- Concrete manual verification steps (e.g. CLI run commands with flags).
````

### Issue Template (`.agents/issues/stm-<number>-<slug>.md`)

````markdown
# [Issue Title]

## Problem Description

Detailed description of the bug, security vulnerability, performance bottleneck, or code smell:
- What failed or behaved unexpectedly.
- Code snippets illustrating the problematic behavior.

## Proposed Solution / Root Cause

- Explanation of the root cause.
- Technical design of the fix or refactor.

## Changes Made

- `relative/path/to/file.py`:
  - Detailed bullet points of modifications.

## Verification

- Automated test execution commands and results.
- Verification steps confirming the issue is resolved.
````

---

## 4. Documentation Standards

- **Relative Paths Only**: All file links inside markdown files must use relative paths (e.g. `substack_scraper/cli.py` or `[cli.py](substack_scraper/cli.py)`). Never use absolute filesystem paths.
- **Spell Out Identifiers**: Never use abbreviated variable names (use `destination` instead of `dest`, `response` instead of `resp`, `extension` instead of `ext`).
- **Code Standards**: Adhere to PEP 8, PEP 585 generics (`list[str]`), and PEP 604 union types (`T | None`).

---

## 5. Registry Update Workflow

Whenever a new issue or plan is created:

1. Create the markdown file under `.agents/issues/` or `.agents/plans/`.
2. Append a new row to the table in [`.agents/README.md`](../../README.md):
   ```markdown
   | **`stm-XXX`** | **[Plan|Issue]** | `[category]` | [Brief description] | [`[plans|issues]/stm-XXX-[slug].md`]([plans|issues]/stm-XXX-[slug].md) |
   ```
3. Verify that the table remains strictly ordered chronologically by commit/work sequence.
