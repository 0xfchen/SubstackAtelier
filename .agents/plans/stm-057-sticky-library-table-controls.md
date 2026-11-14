# Sticky Library Table Controls and Stats Bar

## Goal

1. **Primary Goal**: Make the library Stats Card (`.stats-card`) and Controls Bar (`.table-controls`) persistently visible in a unified sticky dock as the user scrolls through the rows of articles in the library table.
2. **Secondary Goals**:
   - **Unified Sticky Container**: Wrap `.stats-card` and `.table-controls` in a `.library-sticky-dock` container so metrics (total articles, unread, to read, reading, completed, progress bar) and interactive controls (status tabs, search box, author dropdown, length filter) stay anchored together as a cohesive unit.
   - **Smooth Header Docking**: Seamlessly coordinate sticky positioning with the auto-hiding top navigation header (`.site-header`), docking at `top: 0` when the site header hides on scroll-down, and at `top: var(--nav-height, 52px)` when the site header is revealed on scroll-up.
   - **Frosted Glass Surface**: Provide an opaque/frosted glassmorphic background (`background: color-mix(in srgb, var(--bg-primary) 92%, transparent); backdrop-filter: blur(20px)`) with a subtle separation shadow when stuck (`.is-stuck`) so article rows scrolling underneath are cleanly occluded without visual collision.
   - **Responsive Screen Adaptation**: Keep layout clean and functional across desktop, tablet, and mobile screens.

---

## Background & Architecture

The library index page (`reader/src/pages/index.astro`) renders the archive reading list. For large collections (hundreds or thousands of articles), users scroll through many viewports of rows.
Currently, the hero title, stats card, and table controls sit statically in the page flow. Once the user scrolls past row 10, all metrics, status filters, search input, and author selectors disappear off-screen.

By grouping the **full stats card** and the **table controls** inside a persistent sticky dock, both reading progress metrics and filtering controls remain accessible while scrolling through the table rows.

### Component Structure (`reader/src/pages/index.astro`)

```html
<header class="site-header glass"> (Sticky, auto-hides on scroll down)
  ...
</header>

<main class="reading-list-main">
  <!-- Static Hero Title & Subtitle -->
  <header class="reading-header">
    <div class="reading-title-wrap">
      <h1 class="page-title">Archive Library</h1>
      <p class="page-desc">{SITE_DESCRIPTION}</p>
    </div>
  </header>

  <!-- Persistent Sticky Dock -->
  <div class="library-sticky-dock" data-sticky-dock>
    <!-- Live Stats Bar -->
    <div class="stats-card" data-stats-card>
      <div class="stat-item"><span class="stat-value" data-stat-total>...</span>...</div>
      <div class="stat-item"><span class="stat-value stat-unread" data-stat-unread>...</span>...</div>
      <div class="stat-item"><span class="stat-value stat-pending" data-stat-pending>...</span>...</div>
      <div class="stat-item"><span class="stat-value stat-reading" data-stat-reading>...</span>...</div>
      <div class="stat-item"><span class="stat-value stat-completed" data-stat-completed>...</span>...</div>
      <div class="stat-item stat-progress-wrap">...</div>
    </div>

    <!-- Controls & Filters -->
    <div class="table-controls">
      <div class="status-tabs" role="tablist">...</div>
      <div class="search-filter-row">...</div>
    </div>
  </div>

  <!-- Articles Data Table -->
  <div class="table-container">
    <table class="reading-table" data-reading-table>
      <thead> ... </thead>
      <tbody> <!-- Hundreds of article rows --> </tbody>
    </table>
  </div>
</main>
```

---

## Proposed Changes

### 1. Unified Sticky Dock Markup & Styling (`reader/src/pages/index.astro`)

- Wrap `.stats-card` and `.table-controls` in `<div class="library-sticky-dock" data-sticky-dock>`.
- Style `.library-sticky-dock`:
  ```css
  .library-sticky-dock {
    position: sticky;
    top: var(--sticky-dock-top, var(--nav-height, 52px));
    z-index: calc(var(--z-header) - 10); /* 90 */
    background: color-mix(in srgb, var(--bg-primary) 92%, transparent);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    margin-bottom: var(--space-6, 1.5rem);
    padding: var(--space-3, 0.75rem) 0 var(--space-3, 0.75rem);
    border-bottom: 1px solid var(--separator);
    transition:
      top var(--duration-normal) var(--ease-out),
      box-shadow var(--duration-fast) var(--ease-out);
  }

  .library-sticky-dock.is-stuck {
    box-shadow: 0 10px 20px -10px rgba(0, 0, 0, 0.12);
  }
  ```
- Adjust `.stats-card` margin inside the dock:
  - Change `margin-top: var(--space-6, 1.5rem)` to `margin: 0 0 var(--space-3, 0.75rem) 0;` so it sits flush at the top of the dock.
- Adjust `.table-controls`:
  - Remove redundant `border-bottom: 1px solid var(--separator);` and `margin-bottom: var(--space-6, 1.5rem);` from `.table-controls` since the enclosing dock provides the bottom boundary and spacing.

### 2. Auto-Hiding Header Coordination (`reader/src/scripts/posts-index.ts`)

In `initReadingTable()`:
- Locate the `.site-header` and `.library-sticky-dock`.
- Coordinate the `--sticky-dock-top` variable:
  - When scrolling down past threshold and `.site-header` gains `.is-hidden`, update `--sticky-dock-top: 0px`.
  - When scrolling up or near the top, update `--sticky-dock-top: var(--nav-height, 52px)`.
- Toggle `.is-stuck` on `.library-sticky-dock` whenever `scrollY > 0` and its top coordinate reaches the header sticky threshold (`<= headerHeight + 1`), keeping `.is-stuck` active across CSS `top` transitions.
- Preserve rendered batch count (`renderTable(renderedCount)`) on `READING_STATUS_CHANGE_EVENT`, align table top below the sticky dock on filter/search changes when scrolled deep into the table, and include the sticky dock height in `restoreScrollAndTarget()` offset calculations.

### 3. Responsive Adjustments (`reader/src/pages/index.astro`)

- On screens below 768px, ensure `.stats-card` and `.table-controls` maintain comfortable spacing without excessive vertical padding.
- Keep `.stats-card` gap compact (`gap: var(--space-3, 0.75rem)`) on narrow viewports.

---

## Verification Plan

1. **Sticky Dock Behavior**:
   - Scroll down through table rows; confirm `.stats-card` and `.table-controls` stick together as a unit at the top.
   - Confirm article rows scroll cleanly beneath the dock and are occluded by the frosted glass backdrop without text collision.
2. **Auto-Hiding Header Synchronization**:
   - Confirm that when scrolling down, `.site-header` slides out of view and `.library-sticky-dock` smoothly docks at `top: 0`.
   - Confirm that when scrolling up, `.site-header` slides back in and `.library-sticky-dock` transitions down to `top: 52px` without visual overlap.
3. **Interactive Control Usability While Scrolled**:
   - While scrolled down to any row (e.g. row 500):
     - Click status tabs (`To Read`, `Reading`, `Done`, `All`); verify instant filtering and row updates.
     - Search for keywords in the search input; verify real-time search filtering.
     - Filter by author and reading duration; verify instant updates.
     - Check off / change reading status using the row status button; verify that the sticky stats card values and progress bar update immediately in place.
4. **Theme Toggling**:
   - Toggle dark and light modes via `ThemeToggle`; verify frosted glass surface, borders, text, and shadows render cleanly in both modes.
5. **Automated Testing & Build**:
   ```bash
   cd reader && pnpm test
   cd reader && pnpm build
   ```
