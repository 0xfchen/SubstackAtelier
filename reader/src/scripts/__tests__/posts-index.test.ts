import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  loadTableState,
  saveTableState,
  resolveTargetSlug,
  calculateInitialRenderCount,
  compareRows,
  matchesRow,
  matchesTimeCategory,
  calculateScrollTarget,
  syncStickyDockState,
  initReadingTable,
  POSTS_TABLE_STATE_KEY,
  type TableViewState,
  type RowSortFields,
} from '../posts-index';

describe('posts-index state caching and row restoration', () => {
  const mockStorage = new Map<string, string>();

  beforeEach(() => {
    mockStorage.clear();

    (global as any).window = {
      sessionStorage: {
        getItem: vi.fn((key: string) => mockStorage.get(key) ?? null),
        setItem: vi.fn((key: string, val: string) => {
          mockStorage.set(key, val);
        }),
        removeItem: vi.fn((key: string) => {
          mockStorage.delete(key);
        }),
        clear: vi.fn(() => {
          mockStorage.clear();
        }),
      },
      location: {
        hash: '',
        pathname: '/',
        search: '',
      },
    };
    (global as any).sessionStorage = (global as any).window.sessionStorage;
  });

  afterEach(() => {
    vi.restoreAllMocks();
    delete (global as any).window;
    delete (global as any).sessionStorage;
  });

  describe('loadTableState() and saveTableState()', () => {
    it('returns null when no session state is cached', () => {
      expect(loadTableState()).toBeNull();
    });

    it('saves and loads valid state within 2 hours', () => {
      const state: TableViewState = {
        renderedCount: 90,
        scrollY: 1450,
        statusFilter: 'in-progress',
        search: 'machine learning',
        author: 'Gergely Orosz',
        timeFilter: 'quick',
        sortColumn: 'title',
        sortAsc: true,
        timestamp: Date.now() - 5000,
      };

      saveTableState(state);
      expect(mockStorage.has(POSTS_TABLE_STATE_KEY)).toBe(true);

      const loaded = loadTableState();
      expect(loaded).toEqual(state);
    });

    it('discards and removes expired state older than 2 hours', () => {
      const expiredState: TableViewState = {
        renderedCount: 60,
        scrollY: 800,
        statusFilter: 'completed',
        search: '',
        author: 'all',
        sortColumn: 'date',
        sortAsc: false,
        timestamp: Date.now() - 3 * 60 * 60 * 1000, // 3 hours ago
      };

      mockStorage.set(POSTS_TABLE_STATE_KEY, JSON.stringify(expiredState));

      const loaded = loadTableState();
      expect(loaded).toBeNull();
      expect(mockStorage.has(POSTS_TABLE_STATE_KEY)).toBe(false);
    });

    it('handles JSON parse corruption gracefully by returning null', () => {
      mockStorage.set(POSTS_TABLE_STATE_KEY, 'invalid-json{[');
      expect(loadTableState()).toBeNull();
    });
  });

  describe('resolveTargetSlug()', () => {
    it('extracts slug from hash starting with #row-', () => {
      expect(resolveTargetSlug('#row-my-cool-post', null)).toBe('my-cool-post');
    });

    it('decodes URI encoded slug from hash', () => {
      expect(resolveTargetSlug('#row-post%20slug%2Ftest', null)).toBe('post slug/test');
    });

    it('falls back to storedSlug when hash is empty', () => {
      expect(resolveTargetSlug('', 'saved-slug-123')).toBe('saved-slug-123');
    });

    it('does not fall back to storedSlug when explicit non-row hash is present', () => {
      expect(resolveTargetSlug('#main-content', 'saved-slug-123')).toBe('');
      expect(resolveTargetSlug('#content', 'saved-slug-123')).toBe('');
      expect(resolveTargetSlug('#irrelevant', 'saved-slug-123')).toBe('');
    });

    it('returns empty string if neither hash nor storedSlug are present', () => {
      expect(resolveTargetSlug('', null)).toBe('');
      expect(resolveTargetSlug('', '')).toBe('');
    });
  });

  describe('calculateInitialRenderCount()', () => {
    it('returns default batch size (30) when no saved count exists', () => {
      expect(calculateInitialRenderCount(undefined, 200, 30)).toBe(30);
    });

    it('returns saved count when greater than default batch', () => {
      expect(calculateInitialRenderCount(95, 200, 30)).toBe(95);
    });

    it('caps saved count to total available rows', () => {
      expect(calculateInitialRenderCount(150, 80, 30)).toBe(80);
    });

    it('caps default batch to total available rows if total is smaller than batch', () => {
      expect(calculateInitialRenderCount(undefined, 15, 30)).toBe(15);
    });

    it('expands initial count to cover targetIndex + 10 when targetIndex is beyond batch', () => {
      expect(calculateInitialRenderCount(undefined, 200, 30, 45)).toBe(55);
      expect(calculateInitialRenderCount(30, 200, 30, 75)).toBe(85);
    });

    it('caps targetIndex expansion to total available rows', () => {
      expect(calculateInitialRenderCount(undefined, 60, 30, 55)).toBe(60);
    });

    it('returns 0 when total available rows count is 0', () => {
      expect(calculateInitialRenderCount(undefined, 0, 30)).toBe(0);
      expect(calculateInitialRenderCount(50, 0, 30)).toBe(0);
    });

    it('handles exact boundary conditions for batch size and target index expansion', () => {
      expect(calculateInitialRenderCount(undefined, 30, 30)).toBe(30);
      // targetIndex 19 + 10 = 29 <= 30 -> batch size unchanged (30)
      expect(calculateInitialRenderCount(undefined, 100, 30, 19)).toBe(30);
      // targetIndex 20 + 10 = 30 <= 30 -> batch size unchanged (30)
      expect(calculateInitialRenderCount(undefined, 100, 30, 20)).toBe(30);
      // targetIndex 21 + 10 = 31 > 30 -> expands to 31
      expect(calculateInitialRenderCount(undefined, 100, 30, 21)).toBe(31);
    });
  });

  describe('compareRows()', () => {
    const rowA: RowSortFields = {
      status: 'completed',
      readCount: 2,
      title: 'Alpha Post',
      author: 'Alice',
      date: '2026-01-15',
      words: 1200,
    };

    const rowB: RowSortFields = {
      status: 'pending',
      readCount: 0,
      title: 'Beta Post',
      author: 'Bob',
      date: '2026-03-20',
      words: 2500,
    };

    it('sorts by status ascending and descending', () => {
      // status order: completed (4) > in-progress (3) > pending (2) > unread (1)
      expect(compareRows(rowA, rowB, 'status', true)).toBeGreaterThan(0);
      expect(compareRows(rowA, rowB, 'status', false)).toBeLessThan(0);
    });

    it('sorts by title alphabetically ascending and descending', () => {
      expect(compareRows(rowA, rowB, 'title', true)).toBeLessThan(0);
      expect(compareRows(rowA, rowB, 'title', false)).toBeGreaterThan(0);
    });

    it('sorts by author alphabetically ascending and descending', () => {
      expect(compareRows(rowA, rowB, 'author', true)).toBeLessThan(0);
      expect(compareRows(rowA, rowB, 'author', false)).toBeGreaterThan(0);
    });

    it('sorts by date ascending and descending', () => {
      expect(compareRows(rowA, rowB, 'date', true)).toBeLessThan(0);
      expect(compareRows(rowA, rowB, 'date', false)).toBeGreaterThan(0);
    });

    it('sorts by word length ascending and descending', () => {
      expect(compareRows(rowA, rowB, 'length', true)).toBeLessThan(0);
      expect(compareRows(rowA, rowB, 'length', false)).toBeGreaterThan(0);
    });

    it('returns 0 for identical rows across all sort column fields ensuring sort stability', () => {
      const sortColumnCandidates: Array<'status' | 'title' | 'author' | 'date' | 'length'> = [
        'status',
        'title',
        'author',
        'date',
        'length',
      ];

      for (const sortColumnName of sortColumnCandidates) {
        expect(compareRows(rowA, rowA, sortColumnName, true)).toBe(0);
        expect(compareRows(rowA, rowA, sortColumnName, false)).toBe(0);
      }
    });
  });

  describe('matchesTimeCategory()', () => {
    it('returns true for any duration when filter is "all" or undefined', () => {
      expect(matchesTimeCategory(1, 'all')).toBe(true);
      expect(matchesTimeCategory(15, 'all')).toBe(true);
      expect(matchesTimeCategory(45, 'all')).toBe(true);
      expect(matchesTimeCategory(10, undefined)).toBe(true);
      expect(matchesTimeCategory(10, '')).toBe(true);
    });

    it('filters "quick" category for reading times under 5 minutes', () => {
      expect(matchesTimeCategory(1, 'quick')).toBe(true);
      expect(matchesTimeCategory(4, 'quick')).toBe(true);
      expect(matchesTimeCategory(5, 'quick')).toBe(false);
      expect(matchesTimeCategory(10, 'quick')).toBe(false);
    });

    it('filters "medium" category for reading times between 5 and 15 minutes inclusive', () => {
      expect(matchesTimeCategory(4, 'medium')).toBe(false);
      expect(matchesTimeCategory(5, 'medium')).toBe(true);
      expect(matchesTimeCategory(10, 'medium')).toBe(true);
      expect(matchesTimeCategory(15, 'medium')).toBe(true);
      expect(matchesTimeCategory(16, 'medium')).toBe(false);
    });

    it('filters "long" category for reading times between 16 and 30 minutes inclusive', () => {
      expect(matchesTimeCategory(15, 'long')).toBe(false);
      expect(matchesTimeCategory(16, 'long')).toBe(true);
      expect(matchesTimeCategory(25, 'long')).toBe(true);
      expect(matchesTimeCategory(30, 'long')).toBe(true);
      expect(matchesTimeCategory(31, 'long')).toBe(false);
    });

    it('filters "deep" category for reading times strictly greater than 30 minutes', () => {
      expect(matchesTimeCategory(15, 'deep')).toBe(false);
      expect(matchesTimeCategory(30, 'deep')).toBe(false);
      expect(matchesTimeCategory(31, 'deep')).toBe(true);
      expect(matchesTimeCategory(60, 'deep')).toBe(true);
    });
  });

  describe('matchesRow()', () => {
    const baseOptions = {
      statusFilter: 'all',
      searchQuery: '',
      authorFilter: 'all',
    };

    it('matches any row when filters are default', () => {
      expect(matchesRow('pending', 'clean code by uncle bob', 'Robert Martin', baseOptions)).toBe(true);
      expect(matchesRow('unread', 'clean code by uncle bob', 'Robert Martin', baseOptions)).toBe(true);
      expect(matchesRow('completed', 'system design bytebytego', 'Alex Xu', baseOptions)).toBe(true);
    });

    it('filters strictly by status', () => {
      const opts = { ...baseOptions, statusFilter: 'in-progress' };
      expect(matchesRow('in-progress', 'title', 'Author', opts)).toBe(true);
      expect(matchesRow('pending', 'title', 'Author', opts)).toBe(false);
      expect(matchesRow('completed', 'title', 'Author', opts)).toBe(false);
      expect(matchesRow('unread', 'title', 'Author', opts)).toBe(false);

      const pendingOpts = { ...baseOptions, statusFilter: 'pending' };
      expect(matchesRow('pending', 'title', 'Author', pendingOpts)).toBe(true);
      expect(matchesRow('unread', 'title', 'Author', pendingOpts)).toBe(false);
    });

    it('filters strictly by author', () => {
      const opts = { ...baseOptions, authorFilter: 'Alex Xu' };
      expect(matchesRow('pending', 'system design', 'Alex Xu', opts)).toBe(true);
      expect(matchesRow('pending', 'pragmatic engineer', 'Gergely Orosz', opts)).toBe(false);
    });

    it('filters by search query case-insensitively', () => {
      const opts = { ...baseOptions, searchQuery: 'redis' };
      expect(matchesRow('pending', 'deep dive into REDIS internals', 'Author', opts)).toBe(true);
      expect(matchesRow('pending', 'kafka fundamentals', 'Author', opts)).toBe(false);
    });

    it('filters by reading time category', () => {
      const quickOptions = { ...baseOptions, timeFilter: 'quick' };
      expect(matchesRow('pending', 'title', 'Author', quickOptions, 3)).toBe(true);
      expect(matchesRow('pending', 'title', 'Author', quickOptions, 12)).toBe(false);

      const deepOptions = { ...baseOptions, timeFilter: 'deep' };
      expect(matchesRow('pending', 'title', 'Author', deepOptions, 45)).toBe(true);
      expect(matchesRow('pending', 'title', 'Author', deepOptions, 20)).toBe(false);
    });

    it('matches when all combined criteria are satisfied', () => {
      const opts = {
        statusFilter: 'completed',
        searchQuery: 'architecture',
        authorFilter: 'Martin Fowler',
        timeFilter: 'medium',
      };
      expect(
        matchesRow('completed', 'software architecture guide', 'Martin Fowler', opts, 10)
      ).toBe(true);
      expect(
        matchesRow('completed', 'software architecture guide', 'Martin Fowler', opts, 35)
      ).toBe(false);
      expect(
        matchesRow('pending', 'software architecture guide', 'Martin Fowler', opts, 10)
      ).toBe(false);
    });
  });

  describe('calculateScrollTarget()', () => {
    it('prioritizes savedScrollY over element bounding rect', () => {
      const target = calculateScrollTarget(1200, 450, 0, 80);
      expect(target).toBe(1200);
    });

    it('clamps savedScrollY to 0 when negative', () => {
      const target = calculateScrollTarget(-50);
      expect(target).toBe(0);
    });

    it('computes scroll target from target element rect top and current window scroll with header offset', () => {
      // Element is at rect.top = 300, current scroll = 200, header offset = 80
      // target = 200 + 300 - 80 = 420
      const target = calculateScrollTarget(undefined, 300, 200, 80);
      expect(target).toBe(420);
    });

    it('clamps element scroll target to 0 when near the very top', () => {
      // Element at rect.top = 30, current scroll = 0, header offset = 80 -> clamp to 0
      const target = calculateScrollTarget(undefined, 30, 0, 80);
      expect(target).toBe(0);
    });

    it('returns null when neither savedScrollY nor targetRectTop are available', () => {
      expect(calculateScrollTarget()).toBeNull();
    });
  });

  describe('syncStickyDockState()', () => {
    function createFakeElement(options: {
      classes?: string[];
      rectTop?: number;
      rectHeight?: number;
    }) {
      const classSet = new Set(options.classes ?? []);
      const styleMap = new Map<string, string>();
      return {
        classList: {
          contains: (name: string) => classSet.has(name),
          toggle: (name: string, force?: boolean) => {
            if (force === undefined) {
              if (classSet.has(name)) classSet.delete(name);
              else classSet.add(name);
            } else if (force) {
              classSet.add(name);
            } else {
              classSet.delete(name);
            }
          },
        },
        style: {
          setProperty: (prop: string, value: string) => styleMap.set(prop, value),
          getPropertyValue: (prop: string) => styleMap.get(prop) ?? '',
        },
        getBoundingClientRect: () => ({
          top: options.rectTop ?? 0,
          height: options.rectHeight ?? 0,
        }),
      } as unknown as HTMLElement;
    }

    it('docks below visible site header and stays unstuck at top of page', () => {
      const stickyDock = createFakeElement({ rectTop: 180 });
      const siteHeader = createFakeElement({ rectHeight: 52 });

      syncStickyDockState(stickyDock, siteHeader, 0);

      expect(stickyDock.style.getPropertyValue('--sticky-dock-top')).toBe(
        'var(--nav-height, 52px)'
      );
      expect(stickyDock.classList.contains('is-stuck')).toBe(false);
    });

    it('marks dock as stuck when scrolled to header threshold while header is visible', () => {
      const stickyDock = createFakeElement({ rectTop: 52 });
      const siteHeader = createFakeElement({ rectHeight: 52 });

      syncStickyDockState(stickyDock, siteHeader, 240);

      expect(stickyDock.style.getPropertyValue('--sticky-dock-top')).toBe(
        'var(--nav-height, 52px)'
      );
      expect(stickyDock.classList.contains('is-stuck')).toBe(true);
    });

    it('transitions dock to 0px and marks stuck when site header is hidden', () => {
      const stickyDock = createFakeElement({ rectTop: 0 });
      const siteHeader = createFakeElement({
        classes: ['is-hidden'],
        rectHeight: 52,
      });

      syncStickyDockState(stickyDock, siteHeader, 400);

      expect(stickyDock.style.getPropertyValue('--sticky-dock-top')).toBe('0px');
      expect(stickyDock.classList.contains('is-stuck')).toBe(true);
    });

    it('keeps dock marked as stuck during the CSS top transition right after header hides', () => {
      const stickyDock = createFakeElement({ rectTop: 52 });
      const siteHeader = createFakeElement({
        classes: ['is-hidden'],
        rectHeight: 52,
      });

      syncStickyDockState(stickyDock, siteHeader, 320);

      expect(stickyDock.style.getPropertyValue('--sticky-dock-top')).toBe('0px');
      expect(stickyDock.classList.contains('is-stuck')).toBe(true);
    });

    it('does not mark dock as stuck when scrolled slightly before dock reaches threshold', () => {
      const stickyDock = createFakeElement({ rectTop: 80 });
      const siteHeader = createFakeElement({ rectHeight: 52 });

      syncStickyDockState(stickyDock, siteHeader, 40);

      expect(stickyDock.classList.contains('is-stuck')).toBe(false);
    });

    it('handles missing site header gracefully', () => {
      const stickyDock = createFakeElement({ rectTop: 0 });

      syncStickyDockState(stickyDock, null, 150);

      expect(stickyDock.style.getPropertyValue('--sticky-dock-top')).toBe(
        'var(--nav-height, 52px)'
      );
      expect(stickyDock.classList.contains('is-stuck')).toBe(true);
    });
  });

  describe('initReadingTable() resilience', () => {
    it('gracefully exits without throwing when document or table is absent', () => {
      delete (global as any).document;
      expect(() => initReadingTable()).not.toThrow();
    });
  });
});
