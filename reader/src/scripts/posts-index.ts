import {
  fetchReadingState,
  getReadingStatus,
  getReadingProgressPercent,
  getReadCount,
  READING_STATUS_CHANGE_EVENT,
} from './reading-tracker';

const VIEWPORT_BATCH_SIZE = 30; // ~1-1.5 viewport heights of rows

export interface TableViewState {
  renderedCount: number;
  scrollY: number;
  statusFilter: string;
  search: string;
  author: string;
  timeFilter?: string;
  sortColumn: string;
  sortAsc: boolean;
  timestamp: number;
}

export interface RowSortFields {
  status: string;
  readCount: number;
  title: string;
  author: string;
  date: string;
  words: number;
}

export const POSTS_TABLE_STATE_KEY = 'posts_index_view_state';

/**
 * Load cached table view state from sessionStorage.
 */
export function loadTableState(): TableViewState | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = sessionStorage.getItem(POSTS_TABLE_STATE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as TableViewState;
    // Discard state older than 2 hours
    if (Date.now() - parsed.timestamp > 2 * 60 * 60 * 1000) {
      sessionStorage.removeItem(POSTS_TABLE_STATE_KEY);
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

/**
 * Save table view state to sessionStorage.
 */
export function saveTableState(state: TableViewState): void {
  if (typeof window === 'undefined') return;
  try {
    sessionStorage.setItem(POSTS_TABLE_STATE_KEY, JSON.stringify(state));
  } catch {
    // Ignore storage write errors (e.g. quota exceeded)
  }
}

/**
 * Resolve target slug from URL hash or stored session slug.
 */
export function resolveTargetSlug(hash: string, storedSlug: string | null): string {
  if (hash) {
    if (hash.startsWith('#row-')) {
      try {
        return decodeURIComponent(hash.slice(5));
      } catch {
        return hash.slice(5);
      }
    }
    // Explicit non-row hash (e.g. #main-content) takes precedence; do not hijack with storedSlug
    return '';
  }
  if (storedSlug) {
    return storedSlug.trim();
  }
  return '';
}

/**
 * Calculate the number of rows to initially render, respecting cached viewport batches
 * and target row position.
 */
export function calculateInitialRenderCount(
  savedCount: number | undefined,
  totalCount: number,
  defaultBatch = VIEWPORT_BATCH_SIZE,
  targetIndex?: number
): number {
  let count = defaultBatch;
  if (typeof savedCount === 'number' && savedCount > count) {
    count = savedCount;
  }
  if (typeof targetIndex === 'number' && targetIndex >= 0) {
    count = Math.max(count, targetIndex + 10);
  }
  return Math.min(count, totalCount);
}

/**
 * Comparator for sorting rows by status, title, author, date, or length.
 */
export function compareRows(
  a: RowSortFields,
  b: RowSortFields,
  column: string,
  asc: boolean
): number {
  if (column === 'status') {
    const statusOrder: Record<string, number> = {
      completed: 4,
      'in-progress': 3,
      pending: 2,
      unread: 1,
    };
    const statA = statusOrder[a.status || 'unread'] || 1;
    const statB = statusOrder[b.status || 'unread'] || 1;
    if (statA !== statB) {
      return asc ? statA - statB : statB - statA;
    }
    return asc ? a.readCount - b.readCount : b.readCount - a.readCount;
  }
  if (column === 'title') {
    return asc ? a.title.localeCompare(b.title) : b.title.localeCompare(a.title);
  }
  if (column === 'author') {
    return asc ? a.author.localeCompare(b.author) : b.author.localeCompare(a.author);
  }
  if (column === 'date') {
    return asc ? a.date.localeCompare(b.date) : b.date.localeCompare(a.date);
  }
  if (column === 'length') {
    return asc ? a.words - b.words : b.words - a.words;
  }
  return 0;
}

export interface RowFilterOptions {
  statusFilter: string;
  searchQuery: string;
  authorFilter: string;
  timeFilter?: string;
}

/**
 * Check if an estimated reading time in minutes matches the selected time category.
 */
export function matchesTimeCategory(
  readingDurationMinutes: number,
  selectedTimeFilter?: string
): boolean {
  if (!selectedTimeFilter || selectedTimeFilter === 'all') return true;
  if (selectedTimeFilter === 'quick') return readingDurationMinutes < 5;
  if (selectedTimeFilter === 'medium') {
    return readingDurationMinutes >= 5 && readingDurationMinutes <= 15;
  }
  if (selectedTimeFilter === 'long') {
    return readingDurationMinutes > 15 && readingDurationMinutes <= 30;
  }
  if (selectedTimeFilter === 'deep') return readingDurationMinutes > 30;
  return true;
}

/**
 * Check if a row matches the given status, author, reading time, and search query filters.
 */
export function matchesRow(
  status: string,
  searchTarget: string,
  author: string,
  options: RowFilterOptions,
  readingDurationMinutes = 0
): boolean {
  const matchesStatus =
    options.statusFilter === 'all' ||
    (options.statusFilter === 'pending' && status === 'pending') ||
    (options.statusFilter === 'unread' && status === 'unread') ||
    (options.statusFilter === 'in-progress' && status === 'in-progress') ||
    (options.statusFilter === 'completed' && status === 'completed');

  const matchesAuthor =
    options.authorFilter === 'all' || author === options.authorFilter;

  const matchesTime = matchesTimeCategory(
    readingDurationMinutes,
    options.timeFilter
  );

  const query = options.searchQuery.toLowerCase().trim();
  const matchesQuery = !query || searchTarget.toLowerCase().includes(query);

  return matchesStatus && matchesAuthor && matchesTime && matchesQuery;
}

/**
 * Calculates the target scroll coordinate for restoration.
 * Prioritizes saved exact scrollY over element bounding rect, and clamps to >= 0.
 */
export function calculateScrollTarget(
  savedScrollY?: number,
  targetRectTop?: number,
  currentWindowScrollY = 0,
  headerOffset = 80
): number | null {
  if (typeof savedScrollY === 'number' && !Number.isNaN(savedScrollY)) {
    return Math.max(0, savedScrollY);
  }
  if (typeof targetRectTop === 'number' && !Number.isNaN(targetRectTop)) {
    return Math.max(0, currentWindowScrollY + targetRectTop - headerOffset);
  }
  return null;
}

/**
 * Synchronize the sticky library dock position with the auto-hiding site header
 * and toggle `.is-stuck` when the dock is pinned at the top of the viewport.
 */
export function syncStickyDockState(
  stickyDock: HTMLElement,
  siteHeader: HTMLElement | null,
  scrollY = typeof window !== 'undefined' ? window.scrollY : 0
): void {
  const isHeaderHidden = siteHeader?.classList.contains('is-hidden') ?? false;
  stickyDock.style.setProperty(
    '--sticky-dock-top',
    isHeaderHidden ? '0px' : 'var(--nav-height, 52px)'
  );

  const headerHeight = siteHeader
    ? siteHeader.getBoundingClientRect().height || 52
    : 0;
  const stickyThreshold = siteHeader ? headerHeight : 0;
  const dockBoundingRect = stickyDock.getBoundingClientRect();
  const isStuck = scrollY > 0 && dockBoundingRect.top <= stickyThreshold + 1;
  stickyDock.classList.toggle('is-stuck', isStuck);
}

/**
 * Mount listeners and observers to coordinate `.library-sticky-dock` with `.site-header`.
 */
function mountStickyDock(): () => void {
  const stickyDock = document.querySelector<HTMLElement>('[data-sticky-dock]');
  if (!stickyDock) return () => {};

  const siteHeader = document.querySelector<HTMLElement>('.site-header');
  const syncDock = () => syncStickyDockState(stickyDock, siteHeader);

  syncDock();

  if (siteHeader && typeof MutationObserver !== 'undefined') {
    const headerObserver = new MutationObserver(() => {
      syncDock();
    });
    headerObserver.observe(siteHeader, {
      attributes: true,
      attributeFilter: ['class'],
    });
  }

  let isSyncScheduled = false;
  const scheduleDockSync = () => {
    if (!isSyncScheduled) {
      if (typeof requestAnimationFrame === 'function') {
        requestAnimationFrame(() => {
          syncDock();
          isSyncScheduled = false;
        });
      } else {
        syncDock();
        isSyncScheduled = false;
      }
      isSyncScheduled = true;
    }
  };

  window.addEventListener('scroll', scheduleDockSync, { passive: true });
  window.addEventListener('resize', scheduleDockSync, { passive: true });

  return syncDock;
}

/**
 * Initialize the reading table on the posts index page.
 * Handles status filtering, search, author filtering, sorting,
 * and lazy-loads rows dynamically as the user scrolls down the page.
 */
export function initReadingTable(): void {
  if (typeof document === 'undefined') return;

  const syncDock = mountStickyDock();
  const stickyDock = document.querySelector<HTMLElement>('[data-sticky-dock]');
  const siteHeader = document.querySelector<HTMLElement>('.site-header');

  const table = document.querySelector<HTMLTableElement>('[data-reading-table]');
  if (!table) return;

  const tbody = table.querySelector('tbody');
  if (!tbody) return;

  // Prevent browser default scroll restoration engine from scrolling smoothly or asynchronously
  if (typeof history !== 'undefined' && 'scrollRestoration' in history) {
    history.scrollRestoration = 'manual';
  }

  // Temporarily disable smooth scroll on root to guarantee instant positioning without animation
  const docEl = typeof document !== 'undefined' ? document.documentElement : null;
  if (docEl) {
    docEl.style.scrollBehavior = 'auto';
  }

  // Master collection of all rows in the dataset
  const allRows = [...table.querySelectorAll<HTMLTableRowElement>('.article-row')];
  const statusTabs = [...document.querySelectorAll<HTMLButtonElement>('[data-status-filter]')];
  const searchInput = document.querySelector<HTMLInputElement>('[data-reading-search]');
  const authorSelect = document.querySelector<HTMLSelectElement>('[data-author-filter]');
  const timeSelectElement = document.querySelector<HTMLSelectElement>('[data-time-filter]');
  const emptyState = document.querySelector<HTMLElement>('[data-table-empty]');

  let currentStatusFilter: string = 'all';
  let currentSearch: string = '';
  let currentAuthor: string = 'all';
  let currentTimeFilter: string = 'all';
  let sortColumn: string = 'date';
  let sortAsc: boolean = false; // default newest first

  let filteredRows: HTMLTableRowElement[] = [];
  let renderedCount = 0;

  function persistCurrentState(): void {
    if (typeof window === 'undefined') return;
    saveTableState({
      renderedCount,
      scrollY: window.scrollY,
      statusFilter: currentStatusFilter,
      search: currentSearch,
      author: currentAuthor,
      timeFilter: currentTimeFilter,
      sortColumn,
      sortAsc,
      timestamp: Date.now(),
    });
  }

  function appendBatch(count: number): void {
    if (!tbody || renderedCount >= filteredRows.length) return;
    const nextEnd = Math.min(renderedCount + count, filteredRows.length);
    const fragment = document.createDocumentFragment();
    for (let i = renderedCount; i < nextEnd; i++) {
      const row = filteredRows[i];
      row.hidden = false;
      fragment.appendChild(row);
    }
    tbody.appendChild(fragment);
    renderedCount = nextEnd;
  }

  function appendNextBatch(): void {
    appendBatch(VIEWPORT_BATCH_SIZE);
  }

  function updateStats(): void {
    let unread = 0;
    let pending = 0;
    let inProgress = 0;
    let completed = 0;
    let totalReads = 0;

    allRows.forEach((row) => {
      const id = row.dataset.rowId;
      if (!id) return;
      const status = getReadingStatus(id);
      const progressPct = getReadingProgressPercent(id);
      const readCount = getReadCount(id);
      totalReads += readCount;

      row.setAttribute('data-current-status', status);
      row.setAttribute('data-read-count', String(readCount));
      row.style.setProperty('--row-progress', `${progressPct}%`);
      row.setAttribute('data-has-progress', progressPct > 0 ? 'true' : 'false');

      if (status === 'completed') completed++;
      else if (status === 'in-progress') inProgress++;
      else if (status === 'pending') pending++;
      else unread++;
    });

    const total = allRows.length;
    const percent = total > 0 ? Math.round((completed / total) * 100) : 0;

    const elTotal = document.querySelector('[data-stat-total]');
    const elUnread = document.querySelector('[data-stat-unread]');
    const elPending = document.querySelector('[data-stat-pending]');
    const elReading = document.querySelector('[data-stat-reading]');
    const elCompleted = document.querySelector('[data-stat-completed]');
    const elReads = document.querySelector('[data-stat-reads]');
    const elPercent = document.querySelector('[data-stat-percent]');
    const elProgressFill = document.querySelector<HTMLElement>('[data-progress-fill]');

    if (elTotal) elTotal.textContent = String(total);
    if (elUnread) elUnread.textContent = String(unread);
    if (elPending) elPending.textContent = String(pending);
    if (elReading) elReading.textContent = String(inProgress);
    if (elCompleted) elCompleted.textContent = String(completed);
    if (elReads) elReads.textContent = String(totalReads);
    if (elPercent) elPercent.textContent = `${percent}% Completed`;
    if (elProgressFill) elProgressFill.style.width = `${percent}%`;

    // Update badge counts on tabs
    const badgeAll = document.querySelector('[data-badge-all]');
    const badgePending = document.querySelector('[data-badge-pending]');
    const badgeReading = document.querySelector('[data-badge-reading]');
    const badgeCompleted = document.querySelector('[data-badge-completed]');

    if (badgeAll) badgeAll.textContent = String(total);
    if (badgePending) badgePending.textContent = String(pending);
    if (badgeReading) badgeReading.textContent = String(inProgress);
    if (badgeCompleted) badgeCompleted.textContent = String(completed);
  }

  function renderTable(initialCount?: number): void {
    if (!tbody) return;

    filteredRows = allRows.filter((row) => {
      const id = row.dataset.rowId;
      const status = id ? getReadingStatus(id) : 'unread';
      const searchTarget = row.dataset.search || '';
      const author = row.dataset.author || '';
      const readingDurationMinutes = Number(row.dataset.minutes || 0);

      return matchesRow(
        status,
        searchTarget,
        author,
        {
          statusFilter: currentStatusFilter,
          searchQuery: currentSearch,
          authorFilter: currentAuthor,
          timeFilter: currentTimeFilter,
        },
        readingDurationMinutes
      );
    });

    // Cleanly detach child rows without parsing HTML.
    // Note for future maintainers: All row interactions (status updates, row clicks)
    // rely on event delegation on tbody or document, ensuring dynamically mounted
    // rows remain fully interactive across filtering and batch rendering.
    if (typeof tbody.replaceChildren === 'function') {
      tbody.replaceChildren();
    } else {
      while (tbody.firstChild) {
        tbody.removeChild(tbody.firstChild);
      }
    }
    renderedCount = 0;

    const countToRender =
      initialCount && initialCount > VIEWPORT_BATCH_SIZE
        ? Math.min(initialCount, filteredRows.length)
        : VIEWPORT_BATCH_SIZE;

    appendBatch(countToRender);

    // Ensure enough initial content to allow scrolling on large/tall displays
    while (
      renderedCount < filteredRows.length &&
      typeof window !== 'undefined' &&
      document.documentElement.scrollHeight <= window.innerHeight * 1.5
    ) {
      appendNextBatch();
    }

    if (emptyState) {
      emptyState.hidden = filteredRows.length > 0;
    }
  }

  function applySort(column: string, asc: boolean, doRender = true): void {
    sortColumn = column;
    sortAsc = asc;

    allRows.sort((a, b) => {
      const fieldA: RowSortFields = {
        status: a.dataset.currentStatus || 'unread',
        readCount: Number(a.dataset.readCount || 0),
        title: a.dataset.title || '',
        author: a.dataset.author || '',
        date: a.dataset.date || '',
        words: Number(a.dataset.words || 0),
      };
      const fieldB: RowSortFields = {
        status: b.dataset.currentStatus || 'unread',
        readCount: Number(b.dataset.readCount || 0),
        title: b.dataset.title || '',
        author: b.dataset.author || '',
        date: b.dataset.date || '',
        words: Number(b.dataset.words || 0),
      };
      return compareRows(fieldA, fieldB, column, asc);
    });

    // Update sort indicators
    table?.querySelectorAll<HTMLElement>('.sortable').forEach((th) => {
      const isCurrent = th.dataset.sort === sortColumn;
      const ind = th.querySelector('.sort-indicator');
      if (ind) {
        ind.textContent = isCurrent ? (sortAsc ? '▲' : '▼') : '↕';
      }
      th.classList.toggle('is-sorted', isCurrent);
    });

    if (doRender) {
      renderTable();
    }
  }

  function sortTable(column: string): void {
    if (sortColumn === column) {
      applySort(column, !sortAsc);
    } else {
      const asc = column === 'title' || column === 'author'; // text default asc, status/date/length desc
      applySort(column, asc);
    }
  }

  // --- Viewport scroll and intersection observer for infinite scroll ---
  function onScroll(): void {
    if (renderedCount >= filteredRows.length) return;
    const scrollBottom = window.scrollY + window.innerHeight;
    const docHeight = document.documentElement.scrollHeight;
    if (scrollBottom >= docHeight - 800) {
      appendNextBatch();
    }
  }

  window.addEventListener('scroll', onScroll, { passive: true });

  if (typeof window !== 'undefined' && 'IntersectionObserver' in window) {
    const sentinel = document.createElement('div');
    sentinel.style.width = '100%';
    sentinel.style.height = '1px';
    sentinel.style.pointerEvents = 'none';
    const container = table.closest('.table-container') || table.parentElement;
    if (container) {
      container.appendChild(sentinel);
      const observer = new IntersectionObserver(
        (entries) => {
          if (entries[0]?.isIntersecting) {
            appendNextBatch();
          }
        },
        { rootMargin: '800px' }
      );
      observer.observe(sentinel);
    }
  }

  // --- Event listeners ---

  function alignTableTopBelowStickyDock(): void {
    if (typeof window === 'undefined' || !stickyDock || !table) return;
    const tableContainer = table.closest<HTMLElement>('.table-container') || table;
    const tableBoundingRect = tableContainer.getBoundingClientRect();
    const dockBoundingRect = stickyDock.getBoundingClientRect();
    if (tableBoundingRect.top < dockBoundingRect.bottom) {
      const targetScrollY = Math.max(
        0,
        window.scrollY + tableBoundingRect.top - dockBoundingRect.bottom - 12
      );
      window.scrollTo({ top: targetScrollY, behavior: 'instant' });
      syncDock();
    }
  }

  statusTabs.forEach((tab) => {
    tab.addEventListener('click', () => {
      statusTabs.forEach((t) => {
        t.classList.remove('is-active');
        t.setAttribute('aria-pressed', 'false');
      });
      tab.classList.add('is-active');
      tab.setAttribute('aria-pressed', 'true');
      currentStatusFilter = tab.dataset.statusFilter || 'all';
      renderTable();
      alignTableTopBelowStickyDock();
    });
  });

  searchInput?.addEventListener('input', () => {
    currentSearch = searchInput.value.trim().toLowerCase();
    renderTable();
    alignTableTopBelowStickyDock();
  });

  authorSelect?.addEventListener('change', () => {
    currentAuthor = authorSelect.value;
    renderTable();
    alignTableTopBelowStickyDock();
  });

  timeSelectElement?.addEventListener('change', () => {
    currentTimeFilter = timeSelectElement.value;
    renderTable();
    alignTableTopBelowStickyDock();
  });

  table?.querySelectorAll<HTMLElement>('.sortable').forEach((th) => {
    th.addEventListener('click', () => {
      const col = th.dataset.sort;
      if (col) sortTable(col);
    });
  });

  window.addEventListener(READING_STATUS_CHANGE_EVENT, () => {
    updateStats();
    renderTable(renderedCount);
  });

  let hasRestoredTarget = false;
  let highlightTimer: ReturnType<typeof setTimeout> | null = null;
  let activeHighlightedRow: HTMLTableRowElement | null = null;

  function clearHighlight(): void {
    if (highlightTimer) {
      clearTimeout(highlightTimer);
      highlightTimer = null;
    }
    if (activeHighlightedRow) {
      activeHighlightedRow.removeAttribute('data-row-anchor-highlight');
      activeHighlightedRow = null;
    }
  }

  function onPageHide(): void {
    clearHighlight();
    persistCurrentState();
  }

  window.addEventListener('pagehide', onPageHide);
  window.addEventListener('beforeunload', onPageHide);
  tbody.addEventListener('click', (e) => {
    const link = (e.target as HTMLElement)?.closest('a');
    if (link) {
      const row = link.closest('.article-row') as HTMLTableRowElement | null;
      if (row?.dataset.slug) {
        try {
          sessionStorage.setItem('last_active_slug', row.dataset.slug);
        } catch {
          // ignore
        }
      }
      persistCurrentState();
    }
  });

  // Restore saved view state if available
  const savedState = loadTableState();
  const hash = typeof window !== 'undefined' ? window.location.hash : '';
  let storedSlug: string | null = null;
  if (typeof window !== 'undefined') {
    try {
      storedSlug = sessionStorage.getItem('last_active_slug');
    } catch {
      // ignore
    }
  }
  const targetSlug = resolveTargetSlug(hash, storedSlug);

  // Clean up hash and storage key without jumping scroll position
  try {
    sessionStorage.removeItem('last_active_slug');
    if (typeof window !== 'undefined' && window.location.hash) {
      history.replaceState(null, '', window.location.pathname + window.location.search);
    }
  } catch {
    // ignore
  }

  let targetIndex = -1;
  if (targetSlug) {
    targetIndex = allRows.findIndex(
      (r) => r.dataset.slug === targetSlug || r.dataset.rowId === targetSlug
    );
  }

  const initialRenderCount = calculateInitialRenderCount(
    savedState?.renderedCount,
    allRows.length,
    VIEWPORT_BATCH_SIZE,
    targetIndex
  );

  // If we have a saved scroll position, set temporary minHeight on documentElement
  // so that clearing tbody during renderTable() does NOT clamp window.scrollY to 0
  if (docEl && savedState?.scrollY) {
    docEl.style.minHeight = `${savedState.scrollY + window.innerHeight + 100}px`;
  }

  function restoreScrollAndTarget(): void {
    if (hasRestoredTarget) return;

    let targetRow: HTMLTableRowElement | null = null;

    if (targetSlug) {
      const idx = filteredRows.findIndex(
        (r) => r.dataset.slug === targetSlug || r.dataset.rowId === targetSlug
      );
      if (idx !== -1) {
        while (renderedCount <= idx + 5 && renderedCount < filteredRows.length) {
          appendNextBatch();
        }
        targetRow = filteredRows[idx] ?? null;
      }
    }

    // 1. Restore exact scroll coordinate immediately if available (Option 2)
    const stickyDockHeight = stickyDock
      ? stickyDock.getBoundingClientRect().height
      : 0;
    const visibleHeaderHeight =
      siteHeader && !siteHeader.classList.contains('is-hidden')
        ? siteHeader.getBoundingClientRect().height || 52
        : 0;
    const effectiveHeaderOffset =
      stickyDockHeight > 0 ? stickyDockHeight + visibleHeaderHeight + 16 : 80;

    const targetScroll = calculateScrollTarget(
      savedState?.scrollY,
      targetRow ? targetRow.getBoundingClientRect().top : undefined,
      typeof window !== 'undefined' ? window.scrollY : 0,
      effectiveHeaderOffset
    );

    if (targetScroll !== null && typeof window !== 'undefined') {
      window.scrollTo({ top: targetScroll, behavior: 'instant' });
      syncDock();
      hasRestoredTarget = true;
    }

    // Pulse highlight the row so the reader's gaze immediately locks onto it
    if (targetRow) {
      clearHighlight();
      activeHighlightedRow = targetRow;
      targetRow.setAttribute('data-row-anchor-highlight', 'true');
      highlightTimer = setTimeout(() => {
        clearHighlight();
      }, 2200);
    }

    // Clean up temporary styles and reveal page now that scroll position is restored
    if (docEl) {
      docEl.classList.remove('restoring-scroll');
      requestAnimationFrame(() => {
        docEl.style.minHeight = '';
        docEl.style.scrollBehavior = '';
      });
    }
  }

  if (savedState) {
    currentStatusFilter = savedState.statusFilter || 'all';
    currentSearch = savedState.search || '';
    currentAuthor = savedState.author || 'all';
    currentTimeFilter = savedState.timeFilter || 'all';

    // Restore UI controls
    if (searchInput && currentSearch) {
      searchInput.value = currentSearch;
    }
    if (authorSelect && currentAuthor !== 'all') {
      authorSelect.value = currentAuthor;
    }
    if (timeSelectElement && currentTimeFilter !== 'all') {
      timeSelectElement.value = currentTimeFilter;
    }
    if (currentStatusFilter !== 'all') {
      statusTabs.forEach((tab) => {
        const isActive = (tab.dataset.statusFilter || 'all') === currentStatusFilter;
        tab.classList.toggle('is-active', isActive);
        tab.setAttribute('aria-pressed', isActive ? 'true' : 'false');
      });
    }

    if (savedState.sortColumn) {
      applySort(savedState.sortColumn, savedState.sortAsc ?? false, false);
    }
  }

  // Immediate sync from local cache
  updateStats();
  renderTable(initialRenderCount);
  restoreScrollAndTarget();

  // Handle Back-Forward Cache (BFCache) restoration on instant navigation
  window.addEventListener('pageshow', (event) => {
    if (event.persisted) {
      clearHighlight();
      hasRestoredTarget = false;
      if (docEl) {
        docEl.style.scrollBehavior = 'auto';
      }
      updateStats();
      restoreScrollAndTarget();
    }
  });

  // Verify after server state is fetched without wiping existing DOM rows
  fetchReadingState().then(() => {
    updateStats();
    if (currentStatusFilter !== 'all' || currentTimeFilter !== 'all') {
      renderTable(renderedCount);
      restoreScrollAndTarget();
    }
  });
}
