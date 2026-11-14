import { withBase } from '../utils/paths';

type PagefindUIOptions = {
  element: string;
  showSubResults: boolean;
  translations: {
    placeholder: string;
    zero_results: string;
  };
};

declare global {
  interface Window {
    PagefindUI?: new (options: PagefindUIOptions) => unknown;
  }
}


function loadPagefindCss() {
  if (document.querySelector('link[data-pagefind-ui-css]')) return;

  const stylesheetLink = document.createElement('link');
  stylesheetLink.href = withBase('/pagefind/pagefind-ui.css');
  stylesheetLink.rel = 'stylesheet';
  stylesheetLink.dataset.pagefindUiCss = 'true';

  const firstStyleElement = document.head.querySelector('link[rel="stylesheet"], style');
  if (firstStyleElement) {
    document.head.insertBefore(stylesheetLink, firstStyleElement);
  } else {
    document.head.append(stylesheetLink);
  }
}

async function loadPagefindUi() {
  if (window.PagefindUI) return Promise.resolve();

  loadPagefindCss();

  const existing = document.querySelector<HTMLScriptElement>('script[data-pagefind-ui]');
  if (existing) {
    return new Promise<void>((resolve, reject) => {
      existing.addEventListener('load', () => resolve(), { once: true });
      existing.addEventListener('error', reject, { once: true });
    });
  }

  return new Promise<void>((resolve, reject) => {
    const script = document.createElement('script');
    script.src = withBase('/pagefind/pagefind-ui.js');
    script.dataset.pagefindUi = 'true';
    script.onload = () => resolve();
    script.onerror = reject;
    document.head.append(script);
  });
}

export function bindSearchInputInteractions(searchRootElement: ParentNode) {
  const searchInputElement = searchRootElement.querySelector<HTMLInputElement>(
    '.pagefind-ui__search-input',
  );
  const clearButtonElement = searchRootElement.querySelector<HTMLButtonElement>(
    '.pagefind-ui__search-clear',
  );
  if (!searchInputElement || !clearButtonElement) return;

  clearButtonElement.setAttribute('aria-label', 'Clear search');

  searchInputElement.addEventListener(
    'keydown',
    (keyboardEvent: KeyboardEvent) => {
      if (keyboardEvent.key !== 'Escape' || searchInputElement.value === '') return;

      keyboardEvent.preventDefault();
      keyboardEvent.stopPropagation();
      keyboardEvent.stopImmediatePropagation?.();
      clearButtonElement.click();
      searchInputElement.value = '';
      searchInputElement.focus();
    },
    { capture: true },
  );

  clearButtonElement.addEventListener('click', () => {
    searchInputElement.value = '';
    searchInputElement.focus();
  });
}

async function initSearchPage() {
  const searchRootElement = document.getElementById('search');
  if (!searchRootElement || searchRootElement.dataset.pagefindReady === 'true') return;
  searchRootElement.dataset.pagefindReady = 'true';
  try {
    await loadPagefindUi();
    if (!window.PagefindUI) throw new Error('Pagefind UI failed to load');
    searchRootElement.replaceChildren();
    new window.PagefindUI({
      element: '#search',
      showSubResults: true,
      translations: {
        placeholder: 'Search articles or topics...',
        zero_results: 'No results for [SEARCH_TERM]',
      },
    });
    bindSearchInputInteractions(searchRootElement);
    searchRootElement.setAttribute('aria-busy', 'false');
  } catch {
    searchRootElement.setAttribute('aria-busy', 'false');
    searchRootElement.textContent = 'Search is available after a production build.';
  }
}

export function mountSearchPage() {
  void initSearchPage();
}
