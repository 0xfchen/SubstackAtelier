/**
 * Client-side controller for the article body font switcher (FontToggle).
 * Manages preset validation, root attribute synchronization, localStorage persistence,
 * and accessible popover menu interactions.
 */

export const PROSE_FONT_STORAGE_KEY = 'proseFont';

export const PROSE_FONT_PRESETS = [
  'sans',
  'serif',
  'book',
  'inter',
  'system-serif',
] as const;

export type ProseFontPreset = (typeof PROSE_FONT_PRESETS)[number];

export interface ProseFontOptionMetadata {
  id: ProseFontPreset;
  label: string;
  description: string;
  category: 'sans' | 'serif';
}

export const PROSE_FONT_OPTIONS: readonly ProseFontOptionMetadata[] = [
  {
    id: 'sans',
    label: 'Pretendard',
    description: 'Default Sans',
    category: 'sans',
  },
  {
    id: 'serif',
    label: 'Source Serif 4',
    description: 'Editorial Serif',
    category: 'serif',
  },
  {
    id: 'book',
    label: 'Literata',
    description: 'Warm Book Serif',
    category: 'serif',
  },
  {
    id: 'inter',
    label: 'Inter',
    description: 'Humanist Sans',
    category: 'sans',
  },
  {
    id: 'system-serif',
    label: 'Charter / Iowan',
    description: 'System Serif',
    category: 'serif',
  },
];

export function isValidProseFont(candidateValue: unknown): candidateValue is ProseFontPreset {
  return (
    typeof candidateValue === 'string' &&
    (PROSE_FONT_PRESETS as readonly string[]).includes(candidateValue)
  );
}

export function resolveProseFontPreset(candidateValue: unknown): ProseFontPreset {
  return isValidProseFont(candidateValue) ? candidateValue : 'sans';
}

function getOptionMetadata(preset: ProseFontPreset): ProseFontOptionMetadata {
  return PROSE_FONT_OPTIONS.find((optionItem) => optionItem.id === preset) ?? PROSE_FONT_OPTIONS[0];
}

export function syncFontToggleElementState(
  containerElement: HTMLElement,
  activePreset: ProseFontPreset
): void {
  const triggerButton = containerElement.querySelector<HTMLButtonElement>('[data-font-toggle-btn]');
  const optionButtons =
    containerElement.querySelectorAll<HTMLButtonElement>('[data-font-option]');
  const activeOptionMetadata = getOptionMetadata(activePreset);

  if (triggerButton) {
    triggerButton.dataset.activeFont = activePreset;
    triggerButton.dataset.fontCategory = activeOptionMetadata.category;
    triggerButton.setAttribute(
      'aria-label',
      `Article font: ${activeOptionMetadata.label}. Click to change font`
    );
    triggerButton.setAttribute('title', `Article font: ${activeOptionMetadata.label}`);
  }

  optionButtons.forEach((optionButton) => {
    const isSelected = optionButton.dataset.fontOption === activePreset;
    optionButton.setAttribute('aria-checked', String(isSelected));
    optionButton.classList.toggle('is-active', isSelected);
  });
}

function getDefaultBrowserStorage(): Pick<Storage, 'setItem'> | null {
  if (typeof window === 'undefined') return null;
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

export function applyProseFont(
  preset: ProseFontPreset,
  rootElement: HTMLElement = document.documentElement,
  storage: Pick<Storage, 'setItem'> | null = getDefaultBrowserStorage()
): ProseFontPreset {
  const validatedPreset = resolveProseFontPreset(preset);
  rootElement.setAttribute('data-prose-font', validatedPreset);

  if (storage) {
    try {
      storage.setItem(PROSE_FONT_STORAGE_KEY, validatedPreset);
    } catch {
      // Keep the visible font switcher functional when storage is unavailable.
    }
  }

  return validatedPreset;
}

function setMenuOpenState(containerElement: HTMLElement, isOpen: boolean): void {
  const triggerButton = containerElement.querySelector<HTMLButtonElement>('[data-font-toggle-btn]');
  const popoverMenu = containerElement.querySelector<HTMLElement>('[data-font-toggle-menu]');
  if (!triggerButton || !popoverMenu) return;

  containerElement.classList.toggle('is-open', isOpen);
  triggerButton.setAttribute('aria-expanded', String(isOpen));
  popoverMenu.hidden = !isOpen;
}

export function mountFontToggle(
  rootElement: HTMLElement = document.documentElement,
  documentNode: Document = document
): void {
  const containerElement = documentNode.getElementById('font-toggle-container');
  if (!containerElement || containerElement.dataset.fontToggleReady === 'true') {
    return;
  }
  containerElement.dataset.fontToggleReady = 'true';

  const triggerButton = containerElement.querySelector<HTMLButtonElement>('[data-font-toggle-btn]');
  const popoverMenu = containerElement.querySelector<HTMLElement>('[data-font-toggle-menu]');
  const optionButtons = Array.from(
    containerElement.querySelectorAll<HTMLButtonElement>('[data-font-option]')
  );

  if (!triggerButton || !popoverMenu || optionButtons.length === 0) return;

  const currentPreset = resolveProseFontPreset(rootElement.getAttribute('data-prose-font'));
  if (!rootElement.hasAttribute('data-prose-font')) {
    rootElement.setAttribute('data-prose-font', currentPreset);
  }
  syncFontToggleElementState(containerElement, currentPreset);

  if (typeof MutationObserver !== 'undefined') {
    const attributeObserver = new MutationObserver(() => {
      const updatedPreset = resolveProseFontPreset(rootElement.getAttribute('data-prose-font'));
      syncFontToggleElementState(containerElement, updatedPreset);
    });
    attributeObserver.observe(rootElement, {
      attributes: true,
      attributeFilter: ['data-prose-font'],
    });
  }

  triggerButton.addEventListener('click', (clickEvent) => {
    clickEvent.stopPropagation();
    const nextOpenState = !containerElement.classList.contains('is-open');
    setMenuOpenState(containerElement, nextOpenState);
  });

  triggerButton.addEventListener('keydown', (keyboardEvent) => {
    if (keyboardEvent.key === 'ArrowDown' || keyboardEvent.key === 'ArrowUp') {
      keyboardEvent.preventDefault();
      setMenuOpenState(containerElement, true);
      const activePreset = resolveProseFontPreset(rootElement.getAttribute('data-prose-font'));
      const activeOptionButton =
        optionButtons.find((optionButton) => optionButton.dataset.fontOption === activePreset) ??
        optionButtons[0];
      activeOptionButton?.focus();
    }
  });

  optionButtons.forEach((optionButton, optionIndex) => {
    optionButton.addEventListener('click', (clickEvent) => {
      clickEvent.stopPropagation();
      const selectedPreset = resolveProseFontPreset(optionButton.dataset.fontOption);
      applyProseFont(selectedPreset, rootElement);
      syncFontToggleElementState(containerElement, selectedPreset);
      setMenuOpenState(containerElement, false);
      triggerButton.focus();
    });

    optionButton.addEventListener('keydown', (keyboardEvent) => {
      if (keyboardEvent.key === 'ArrowDown' || keyboardEvent.key === 'ArrowRight') {
        keyboardEvent.preventDefault();
        const nextButton = optionButtons[(optionIndex + 1) % optionButtons.length];
        nextButton?.focus();
      } else if (keyboardEvent.key === 'ArrowUp' || keyboardEvent.key === 'ArrowLeft') {
        keyboardEvent.preventDefault();
        const previousButton =
          optionButtons[(optionIndex - 1 + optionButtons.length) % optionButtons.length];
        previousButton?.focus();
      }
    });
  });

  documentNode.addEventListener('click', (documentClickEvent) => {
    if (!containerElement.classList.contains('is-open')) return;
    const eventTarget = documentClickEvent.target as Node | null;
    if (eventTarget && !containerElement.contains(eventTarget)) {
      setMenuOpenState(containerElement, false);
    }
  });

  documentNode.addEventListener('keydown', (documentKeyEvent) => {
    if (documentKeyEvent.key === 'Escape' && containerElement.classList.contains('is-open')) {
      documentKeyEvent.preventDefault();
      setMenuOpenState(containerElement, false);
      triggerButton.focus();
    }
  });
}
