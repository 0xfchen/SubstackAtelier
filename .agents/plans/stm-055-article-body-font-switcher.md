# Article Body Font Switcher (`FontToggle`)

## Goal

1. **Primary Goal**: Add a font switcher control next to the theme toggle in the reader header allowing readers to switch the article body typeface across curated long-form reading presets (`Pretendard Sans`, `Source Serif 4`, `Literata`, `Inter`, and `System Serif`).
2. **Secondary Goals**:
   - **Body-Prose Scoping**: Apply the selected font strictly to article body prose (`.prose` paragraphs, lists, blockquotes, and table cells) while keeping `.prose` headings (`h1`–`h6`), post title/subtitle, table headers, callout labels, and site UI chrome in `Pretendard` (`--font-sans`), and code/keyboard elements in `Tone Mono` (`--font-mono`).
   - **Zero-FOUC Persistence**: Persist the selected font in `localStorage` (`proseFont`) and restore `data-prose-font` on `<html>` inside `BaseHead.astro`'s inline bootstrap script before first paint.
   - **On-Demand Self-Hosted Fonts**: Bundle variable `.woff2` font files locally under `reader/src/assets/fonts/` so the reader works fully offline and browsers only download a font file when its preset is selected.

---

## Background & Architecture

Currently, the reader sets `font-family: var(--font-sans)` (`Pretendard Variable`) globally on `body` in [`reader/src/styles/base.css`](../../reader/src/styles/base.css), and `.prose` in [`reader/src/styles/prose.css`](../../reader/src/styles/prose.css) inherits that font for all article content. While `Pretendard` works well for UI chrome, navigation, and headings, long-form newsletter essays (often 3,000–6,000+ words) benefit from dedicated editorial typefaces:

- Some readers prefer a crisp editorial serif (**Source Serif 4**), similar to Substack's default serif or newspaper long-form layouts.
- Others prefer a warm book/e-reader serif (**Literata**, designed for long-form digital reading, or **System Serif** using `Iowan Old Style` / `Charter` on macOS/iOS and `Georgia` on Windows).
- Others prefer a humanist sans-serif (**Inter**) or the default **Pretendard**.

By scoping a `--font-prose` CSS custom property to `.prose` body text while pinning `.prose :is(h1, h2, h3, h4, h5, h6)` to `var(--font-sans)`, the reader achieves classic editorial contrast (sans-serif headings + customizable body prose) without layout shift in the header, sidebar, or reading rail.

### Supported Font Presets

| Preset Key | UI Label | Preview Glyph | CSS Font Stack | Asset Strategy |
| :--- | :--- | :--- | :--- | :--- |
| `sans` *(default)* | **Pretendard** (Default Sans) | Sans `Aa` | `var(--font-sans)` | Already preloaded (`pretendard-variable.woff2`) |
| `serif` | **Source Serif 4** (Editorial) | Serif `Aa` | `'Source Serif 4 Variable', 'Source Serif 4', Georgia, serif` | Self-hosted variable `.woff2` (`font-display: swap`) |
| `book` | **Literata** (Book Serif) | Book `Aa` | `'Literata Variable', 'Literata', Charter, Georgia, serif` | Self-hosted variable `.woff2` (`font-display: swap`) |
| `inter` | **Inter** (Humanist Sans) | Clean `Aa` | `'Inter Variable', 'Inter', system-ui, sans-serif` | Self-hosted variable `.woff2` (`font-display: swap`) |
| `system-serif` | **Charter / Iowan** (System Serif) | Native `Aa` | `'Iowan Old Style', Charter, 'Apple Garamond', 'Sitka Text', Georgia, ui-serif, serif` | Zero-download OS native editorial serif stack |

---

## Proposed Changes

### 1. Self-Hosted Font Assets & Design Tokens (`reader/src/assets/fonts/`, `reader/src/styles/tokens.css`)

- Add subsetted Latin variable `.woff2` files under `reader/src/assets/fonts/`:
  - `source-serif-4-latin-wght-normal.woff2` (and italic if desired, or variable roman)
  - `literata-latin-wght-normal.woff2`
  - `inter-latin-wght-normal.woff2`
- Register `@font-face` rules in [`reader/src/styles/tokens.css`](../../reader/src/styles/tokens.css) with `font-display: swap`. Because browsers only fetch `@font-face` URLs when a matching selector is active in the DOM, non-default fonts incur **0 KB** network overhead until selected by the user.
- Define prose font family tokens and `data-prose-font` root selectors in [`reader/src/styles/tokens.css`](../../reader/src/styles/tokens.css):
  ```css
  :root {
    --font-prose-sans: var(--font-sans);
    --font-prose-serif:
      'Source Serif 4 Variable', 'Source Serif 4', 'Iowan Old Style', Charter, Georgia, serif;
    --font-prose-book:
      'Literata Variable', 'Literata', 'Iowan Old Style', Charter, Georgia, serif;
    --font-prose-inter:
      'Inter Variable', Inter, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;
    --font-prose-system-serif:
      'Iowan Old Style', Charter, 'Apple Garamond', Baskerville, 'Sitka Text', Cambria, Georgia,
      ui-serif, serif;

    --font-prose: var(--font-prose-sans);
  }

  :root[data-prose-font='serif'] {
    --font-prose: var(--font-prose-serif);
  }

  :root[data-prose-font='book'] {
    --font-prose: var(--font-prose-book);
  }

  :root[data-prose-font='inter'] {
    --font-prose: var(--font-prose-inter);
  }

  :root[data-prose-font='system-serif'] {
    --font-prose: var(--font-prose-system-serif);
  }
  ```

### 2. Body-Prose Scoped Typography (`reader/src/styles/prose.css`)

- Update `.prose` in [`reader/src/styles/prose.css`](../../reader/src/styles/prose.css) to use `font-family: var(--font-prose);` and `font-synthesis: style;` so paragraphs (`p`), list items (`li`), blockquotes (`blockquote`), table cells (`td`), and emphasized text (`em`, `i`) render properly in the chosen article body font.
- Explicitly pin non-body elements inside `.prose` to `var(--font-sans)` and `font-synthesis: none;` so headings and UI metadata keep their sharp sans-serif styling:
  ```css
  .prose {
    font-family: var(--font-prose);
    font-synthesis: style;
    font-size: clamp(1rem, 0.99rem + 0.04vw, 1.0156rem);
    line-height: 1.76;
    color: var(--label-primary);
  }

  .prose h1,
  .prose h2,
  .prose h3,
  .prose h4,
  .prose h5,
  .prose h6,
  .prose th,
  .prose .callout::before,
  .prose img + em {
    font-family: var(--font-sans);
    font-synthesis: none;
  }
  ```
- Code blocks (`pre`, `code`) and `<kbd>` already declare `font-family: var(--font-mono)` and remain unchanged.
- Inline highlight annotations (`mark.annotation-highlight`) inherit `var(--font-prose)` seamlessly, while the annotation toolbar and side panel (`reader/src/styles/components/annotations.css`) already explicitly declare `font-family: var(--font-sans)`.

### 3. Early Bootstrap in Head (`reader/src/components/BaseHead.astro`)

- Extend the inline theme initialization script in [`reader/src/components/BaseHead.astro`](../../reader/src/components/BaseHead.astro) so `data-prose-font` is applied before first paint alongside `data-theme`:
  ```javascript
  let proseFont = 'sans';
  try {
    const storedFont = localStorage.getItem('proseFont');
    if (
      storedFont === 'sans' ||
      storedFont === 'serif' ||
      storedFont === 'book' ||
      storedFont === 'inter' ||
      storedFont === 'system-serif'
    ) {
      proseFont = storedFont;
    }
  } catch {}
  el.setAttribute('data-prose-font', proseFont);
  ```

### 4. Font Switcher Component & Header Placement (`reader/src/components/FontToggle.astro`, `reader/src/components/Header.astro`)

- Create [`reader/src/components/FontToggle.astro`](../../reader/src/components/FontToggle.astro) and mount it immediately next to `<ThemeToggle />` inside `.nav-right` in [`reader/src/components/Header.astro`](../../reader/src/components/Header.astro):
  - **Trigger button**: A compact `2rem × 2rem` button (matching `.theme-toggle` styling and hover/focus states) displaying an `Aa` typography icon/label that reflects whether a serif or sans preset is active.
  - **Popover menu**: Clicking the button toggles a compact glassmorphic dropdown (`role="menu"` / `aria-label="Article body font"`) anchored below the button with the 5 presets (`Pretendard`, `Source Serif 4`, `Literata`, `Inter`, `System Serif`).
  - Each option renders its title in its own font stack so the user can preview the typeface before clicking, with an active indicator on the current preset.
  - Supports keyboard navigation (`Escape` closes and returns focus to the trigger button; `ArrowDown`/`ArrowUp` moves between options; clicking outside dismisses the menu).

### 5. Client Controller & Unit Tests (`reader/src/scripts/font-toggle.ts`, `reader/src/scripts/__tests__/font-toggle.test.ts`)

- Following the `stm-039` convention, implement the state, validation, DOM synchronization, and keyboard/outside-click handlers in [`reader/src/scripts/font-toggle.ts`](../../reader/src/scripts/font-toggle.ts):
  - `PROSE_FONT_PRESETS`: typed constant list of valid preset IDs (`'sans' | 'serif' | 'book' | 'inter' | 'system-serif'`).
  - `isValidProseFont(value: unknown): value is ProseFontPreset`: type guard defaulting invalid/missing values to `'sans'`.
  - `applyProseFont(font: ProseFontPreset, rootElement?: HTMLElement, storage?: Storage)`: sets `data-prose-font` on `document.documentElement`, persists to `localStorage.setItem('proseFont', font)` (with `try/catch` for restricted storage), and updates `aria-checked` / active classes on the menu buttons.
  - `mountFontToggle()`: wires button click, option selection, outside click, `Escape` key, and `MutationObserver` on `data-prose-font`.
- Add unit tests in [`reader/src/scripts/__tests__/font-toggle.test.ts`](../../reader/src/scripts/__tests__/font-toggle.test.ts) covering preset validation, `localStorage` persistence and fallback when storage throws, popover open/close lifecycle, and `data-prose-font` attribute updates.

---

## Verification Plan

### Automated Tests
```bash
cd reader
pnpm test
pnpm build
```

### Manual Verification
1. Start the reader dev server (`cd reader && pnpm dev`) and open any article page.
2. Click the `Aa` font toggle button next to the theme toggle in the top-right header:
   - Confirm the popover menu opens and previews all 5 font options (`Pretendard`, `Source Serif 4`, `Literata`, `Inter`, `Charter / Iowan`).
3. Select each preset and verify:
   - Paragraph text (`p`), lists (`ul`/`ol`), blockquotes, and table cells inside `.prose` immediately switch to the selected font.
   - Article headings (`.prose h1`–`h6`), `.post-title`, `.post-description`, the right-hand TOC reading rail, and the header remain in `Pretendard`.
   - Code blocks and inline `code`/`kbd` remain in `Tone Mono`.
4. Reload the page and navigate to another article:
   - Confirm the selected font persists via `localStorage` with no flash of default font on load.
5. Toggle between Light and Dark mode and verify both controls sit cleanly side-by-side on desktop and mobile widths (`<= 600px`).
