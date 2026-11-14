import { describe, expect, it } from 'vitest';
import { bindSearchInputInteractions } from '../search-page';

type FakeEventListener = (event: unknown) => void;

class FakeSearchInputElement {
  value = '';
  focusCount = 0;
  keydownOptions: AddEventListenerOptions | boolean | undefined;
  private listeners = new Map<string, FakeEventListener[]>();

  addEventListener(
    eventType: string,
    listener: FakeEventListener,
    options?: AddEventListenerOptions | boolean,
  ) {
    if (eventType === 'keydown') {
      this.keydownOptions = options;
    }
    const existingListeners = this.listeners.get(eventType) ?? [];
    existingListeners.push(listener);
    this.listeners.set(eventType, existingListeners);
  }

  dispatchKeydown(key: string) {
    let defaultPrevented = false;
    let propagationStopped = false;
    let immediatePropagationStopped = false;
    const keyboardEvent = {
      key,
      preventDefault: () => {
        defaultPrevented = true;
      },
      stopPropagation: () => {
        propagationStopped = true;
      },
      stopImmediatePropagation: () => {
        immediatePropagationStopped = true;
      },
    };

    for (const listener of this.listeners.get('keydown') ?? []) {
      listener(keyboardEvent);
    }

    return { defaultPrevented, propagationStopped, immediatePropagationStopped };
  }

  focus() {
    this.focusCount += 1;
  }
}

class FakeSearchClearButtonElement {
  attributes = new Map<string, string>();
  clickCount = 0;
  private listeners = new Map<string, FakeEventListener[]>();

  setAttribute(name: string, value: string) {
    this.attributes.set(name, value);
  }

  addEventListener(eventType: string, listener: FakeEventListener) {
    const existingListeners = this.listeners.get(eventType) ?? [];
    existingListeners.push(listener);
    this.listeners.set(eventType, existingListeners);
  }

  click() {
    this.clickCount += 1;
    for (const listener of this.listeners.get('click') ?? []) {
      listener({});
    }
  }
}

class FakeSearchRoot {
  constructor(
    private readonly searchInputElement: FakeSearchInputElement | null,
    private readonly clearButtonElement: FakeSearchClearButtonElement | null,
  ) {}

  querySelector(selector: string) {
    if (selector === '.pagefind-ui__search-input') {
      return this.searchInputElement;
    }
    if (selector === '.pagefind-ui__search-clear') {
      return this.clearButtonElement;
    }
    return null;
  }
}

describe('bindSearchInputInteractions', () => {
  it('assigns an accessible aria-label to the clear button', () => {
    const searchInputElement = new FakeSearchInputElement();
    const clearButtonElement = new FakeSearchClearButtonElement();
    const searchRootElement = new FakeSearchRoot(searchInputElement, clearButtonElement);

    bindSearchInputInteractions(searchRootElement as unknown as ParentNode);

    expect(clearButtonElement.attributes.get('aria-label')).toBe('Clear search');
  });

  it('clears a non-empty input and keeps focus on Escape', () => {
    const searchInputElement = new FakeSearchInputElement();
    searchInputElement.value = 'distributed systems';
    const clearButtonElement = new FakeSearchClearButtonElement();
    const searchRootElement = new FakeSearchRoot(searchInputElement, clearButtonElement);

    bindSearchInputInteractions(searchRootElement as unknown as ParentNode);
    const keydownResult = searchInputElement.dispatchKeydown('Escape');

    expect(searchInputElement.keydownOptions).toEqual({ capture: true });
    expect(keydownResult.defaultPrevented).toBe(true);
    expect(keydownResult.propagationStopped).toBe(true);
    expect(keydownResult.immediatePropagationStopped).toBe(true);
    expect(clearButtonElement.clickCount).toBe(1);
    expect(searchInputElement.value).toBe('');
    expect(searchInputElement.focusCount).toBeGreaterThanOrEqual(1);
  });

  it('ignores Escape when the search input is already empty', () => {
    const searchInputElement = new FakeSearchInputElement();
    const clearButtonElement = new FakeSearchClearButtonElement();
    const searchRootElement = new FakeSearchRoot(searchInputElement, clearButtonElement);

    bindSearchInputInteractions(searchRootElement as unknown as ParentNode);
    const keydownResult = searchInputElement.dispatchKeydown('Escape');

    expect(keydownResult.defaultPrevented).toBe(false);
    expect(keydownResult.propagationStopped).toBe(false);
    expect(keydownResult.immediatePropagationStopped).toBe(false);
    expect(clearButtonElement.clickCount).toBe(0);
    expect(searchInputElement.focusCount).toBe(0);
  });

  it('refocuses the search input when the clear button is clicked', () => {
    const searchInputElement = new FakeSearchInputElement();
    searchInputElement.value = 'consensus';
    const clearButtonElement = new FakeSearchClearButtonElement();
    const searchRootElement = new FakeSearchRoot(searchInputElement, clearButtonElement);

    bindSearchInputInteractions(searchRootElement as unknown as ParentNode);
    clearButtonElement.click();

    expect(clearButtonElement.clickCount).toBe(1);
    expect(searchInputElement.value).toBe('');
    expect(searchInputElement.focusCount).toBe(1);
  });
});
