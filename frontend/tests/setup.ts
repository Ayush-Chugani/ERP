import '@testing-library/jest-dom/vitest';

// jsdom has no matchMedia: report a desktop-sized, light-preferring screen.
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: (query: string) => ({
    matches: /min-width/.test(query) && !/prefers-color-scheme: dark/.test(query),
    media: query, onchange: null,
    addEventListener: () => undefined, removeEventListener: () => undefined,
    addListener: () => undefined, removeListener: () => undefined, dispatchEvent: () => false,
  }),
});
