import { describe, expect, it, vi } from 'vitest';
import {
  PROSE_FONT_OPTIONS,
  PROSE_FONT_PRESETS,
  PROSE_FONT_STORAGE_KEY,
  applyProseFont,
  isValidProseFont,
  mountFontToggle,
  resolveProseFontPreset,
  syncFontToggleElementState,
} from '../font-toggle';

function createFakeFontToggleDom(initialFontAttribute: string | null = 'sans') {
  const rootAttributes = new Map<string, string>();
  if (initialFontAttribute !== null) {
    rootAttributes.set('data-prose-font', initialFontAttribute);
  }

  const fakeRootElement = {
    getAttribute: vi.fn((attributeName: string) => rootAttributes.get(attributeName) ?? null),
    setAttribute: vi.fn((attributeName: string, attributeValue: string) =>
      rootAttributes.set(attributeName, attributeValue)
    ),
    hasAttribute: vi.fn((attributeName: string) => rootAttributes.has(attributeName)),
  } as unknown as HTMLElement;

  const triggerAttributes = new Map<string, string>([['aria-expanded', 'false']]);
  let triggerClickHandler: ((event: { stopPropagation: () => void }) => void) | null = null;
  let triggerKeydownHandler:
    | ((event: { key: string; preventDefault: () => void }) => void)
    | null = null;
  const fakeTriggerButton = {
    dataset: {} as Record<string, string>,
    setAttribute: vi.fn((attributeName: string, attributeValue: string) =>
      triggerAttributes.set(attributeName, attributeValue)
    ),
    getAttribute: vi.fn((attributeName: string) => triggerAttributes.get(attributeName) ?? null),
    addEventListener: vi.fn((eventName: string, callback: (...args: never[]) => void) => {
      if (eventName === 'click') triggerClickHandler = callback;
      if (eventName === 'keydown') triggerKeydownHandler = callback;
    }),
    focus: vi.fn(),
    click: () => triggerClickHandler?.({ stopPropagation: vi.fn() }),
    keydown: (key: string) => triggerKeydownHandler?.({ key, preventDefault: vi.fn() }),
  };

  const fakePopoverMenu = {
    hidden: true,
  };

  const fakeOptionButtons = PROSE_FONT_OPTIONS.map((fontOption) => {
    const optionClasses = new Set<string>();
    const optionAttributes = new Map<string, string>();
    let optionClickHandler: ((event: { stopPropagation: () => void }) => void) | null = null;
    let optionKeydownHandler:
      | ((event: { key: string; preventDefault: () => void }) => void)
      | null = null;

    return {
      dataset: { fontOption: fontOption.id },
      setAttribute: vi.fn((attributeName: string, attributeValue: string) =>
        optionAttributes.set(attributeName, attributeValue)
      ),
      getAttribute: vi.fn((attributeName: string) => optionAttributes.get(attributeName) ?? null),
      classList: {
        toggle: vi.fn((className: string, forceState?: boolean) => {
          if (forceState) optionClasses.add(className);
          else optionClasses.delete(className);
        }),
        contains: (className: string) => optionClasses.has(className),
      },
      addEventListener: vi.fn((eventName: string, callback: (...args: never[]) => void) => {
        if (eventName === 'click') optionClickHandler = callback;
        if (eventName === 'keydown') optionKeydownHandler = callback;
      }),
      focus: vi.fn(),
      click: () => optionClickHandler?.({ stopPropagation: vi.fn() }),
      keydown: (key: string) => optionKeydownHandler?.({ key, preventDefault: vi.fn() }),
    };
  });

  const containerClasses = new Set<string>();
  const fakeContainerElement = {
    dataset: {} as Record<string, string>,
    classList: {
      toggle: vi.fn((className: string, forceState?: boolean) => {
        if (forceState) containerClasses.add(className);
        else containerClasses.delete(className);
      }),
      contains: vi.fn((className: string) => containerClasses.has(className)),
    },
    querySelector: vi.fn((selector: string) => {
      if (selector === '[data-font-toggle-btn]') return fakeTriggerButton;
      if (selector === '[data-font-toggle-menu]') return fakePopoverMenu;
      return null;
    }),
    querySelectorAll: vi.fn((selector: string) => {
      if (selector === '[data-font-option]') return fakeOptionButtons;
      return [];
    }),
    contains: vi.fn((targetNode: unknown) => targetNode === fakeContainerElement),
  } as unknown as HTMLElement;

  let documentClickHandler: ((event: { target: unknown }) => void) | null = null;
  let documentKeydownHandler:
    | ((event: { key: string; preventDefault: () => void }) => void)
    | null = null;

  const fakeDocument = {
    getElementById: vi.fn((elementId: string) =>
      elementId === 'font-toggle-container' ? fakeContainerElement : null
    ),
    addEventListener: vi.fn((eventName: string, callback: (...args: never[]) => void) => {
      if (eventName === 'click') documentClickHandler = callback;
      if (eventName === 'keydown') documentKeydownHandler = callback;
    }),
    dispatchOutsideClick: (target: unknown) => documentClickHandler?.({ target }),
    dispatchEscape: () =>
      documentKeydownHandler?.({ key: 'Escape', preventDefault: vi.fn() }),
  };

  return {
    fakeRootElement,
    fakeContainerElement,
    fakeTriggerButton,
    fakePopoverMenu,
    fakeOptionButtons,
    fakeDocument: fakeDocument as unknown as Document & {
      dispatchOutsideClick: (target: unknown) => void;
      dispatchEscape: () => void;
    },
  };
}

describe('font-toggle controller', () => {
  it('validates all supported prose font presets and rejects unknown values', () => {
    for (const preset of PROSE_FONT_PRESETS) {
      expect(isValidProseFont(preset)).toBe(true);
      expect(resolveProseFontPreset(preset)).toBe(preset);
    }

    expect(isValidProseFont('comic-sans')).toBe(false);
    expect(isValidProseFont(null)).toBe(false);
    expect(resolveProseFontPreset('unknown')).toBe('sans');
    expect(resolveProseFontPreset(undefined)).toBe('sans');
  });

  it('applies data-prose-font on the root element and persists to storage', () => {
    const { fakeRootElement } = createFakeFontToggleDom();
    const fakeStorage = { setItem: vi.fn() };

    const appliedPreset = applyProseFont('serif', fakeRootElement, fakeStorage);

    expect(appliedPreset).toBe('serif');
    expect(fakeRootElement.getAttribute('data-prose-font')).toBe('serif');
    expect(fakeStorage.setItem).toHaveBeenCalledWith(PROSE_FONT_STORAGE_KEY, 'serif');
  });

  it('continues updating root attribute when storage throws an error', () => {
    const { fakeRootElement } = createFakeFontToggleDom();
    const throwingStorage = {
      setItem: vi.fn(() => {
        throw new Error('QuotaExceededError');
      }),
    };

    expect(() => applyProseFont('book', fakeRootElement, throwingStorage)).not.toThrow();
    expect(fakeRootElement.getAttribute('data-prose-font')).toBe('book');
  });

  it('synchronizes trigger button metadata and option aria-checked states', () => {
    const { fakeContainerElement, fakeTriggerButton, fakeOptionButtons } =
      createFakeFontToggleDom();

    syncFontToggleElementState(fakeContainerElement, 'book');

    expect(fakeTriggerButton.dataset.activeFont).toBe('book');
    expect(fakeTriggerButton.dataset.fontCategory).toBe('serif');
    expect(fakeTriggerButton.getAttribute('title')).toBe('Article font: Literata');

    const literataOption = fakeOptionButtons.find((item) => item.dataset.fontOption === 'book');
    const pretendardOption = fakeOptionButtons.find((item) => item.dataset.fontOption === 'sans');
    expect(literataOption?.getAttribute('aria-checked')).toBe('true');
    expect(literataOption?.classList.contains('is-active')).toBe(true);
    expect(pretendardOption?.getAttribute('aria-checked')).toBe('false');
    expect(pretendardOption?.classList.contains('is-active')).toBe(false);
  });

  it('opens the popover on trigger click, selects a font option, and closes on Escape or outside click', () => {
    const {
      fakeRootElement,
      fakeTriggerButton,
      fakePopoverMenu,
      fakeOptionButtons,
      fakeDocument,
    } = createFakeFontToggleDom('sans');

    mountFontToggle(fakeRootElement, fakeDocument);

    expect(fakePopoverMenu.hidden).toBe(true);
    fakeTriggerButton.click();
    expect(fakePopoverMenu.hidden).toBe(false);
    expect(fakeTriggerButton.getAttribute('aria-expanded')).toBe('true');

    const interOption = fakeOptionButtons.find((item) => item.dataset.fontOption === 'inter');
    interOption?.click();

    expect(fakeRootElement.getAttribute('data-prose-font')).toBe('inter');
    expect(fakePopoverMenu.hidden).toBe(true);
    expect(fakeTriggerButton.focus).toHaveBeenCalled();

    fakeTriggerButton.click();
    expect(fakePopoverMenu.hidden).toBe(false);
    fakeDocument.dispatchEscape();
    expect(fakePopoverMenu.hidden).toBe(true);

    fakeTriggerButton.click();
    expect(fakePopoverMenu.hidden).toBe(false);
    fakeDocument.dispatchOutsideClick({});
    expect(fakePopoverMenu.hidden).toBe(true);
  });

  it('cycles focus between font options with arrow keys and opens menu on trigger ArrowDown', () => {
    const {
      fakeRootElement,
      fakeTriggerButton,
      fakePopoverMenu,
      fakeOptionButtons,
      fakeDocument,
    } = createFakeFontToggleDom('book');
    mountFontToggle(fakeRootElement, fakeDocument);

    expect(fakePopoverMenu.hidden).toBe(true);
    fakeTriggerButton.keydown('ArrowDown');
    expect(fakePopoverMenu.hidden).toBe(false);
    const literataOption = fakeOptionButtons.find((item) => item.dataset.fontOption === 'book');
    expect(literataOption?.focus).toHaveBeenCalledOnce();

    fakeOptionButtons[0].keydown('ArrowDown');
    expect(fakeOptionButtons[1].focus).toHaveBeenCalledOnce();

    fakeOptionButtons[0].keydown('ArrowUp');
    expect(fakeOptionButtons[fakeOptionButtons.length - 1].focus).toHaveBeenCalledOnce();
  });
});
