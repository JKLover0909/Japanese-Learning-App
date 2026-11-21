import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ThemeModeProvider, ThemeToggle } from './ThemeMode';

let systemDark = false;
const changeListeners = new Set<(event: MediaQueryListEvent) => void>();

function matchMedia(query: string): MediaQueryList {
  return {
    matches: query === '(prefers-color-scheme: dark)' && systemDark,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: (_type: string, listener: EventListenerOrEventListenerObject | null) => {
      if (typeof listener === 'function') changeListeners.add(listener as (event: MediaQueryListEvent) => void);
    },
    removeEventListener: (_type: string, listener: EventListenerOrEventListenerObject | null) => {
      if (typeof listener === 'function') changeListeners.delete(listener as (event: MediaQueryListEvent) => void);
    },
    dispatchEvent: vi.fn(),
  };
}

function renderTheme() {
  return render(<ThemeModeProvider><ThemeToggle /></ThemeModeProvider>);
}

beforeEach(() => {
  localStorage.clear();
  document.documentElement.removeAttribute('data-theme');
  document.documentElement.style.removeProperty('color-scheme');
  systemDark = false;
  changeListeners.clear();
  vi.stubGlobal('matchMedia', matchMedia);
});

describe('ThemeMode', () => {
  it('uses light mode by default regardless of the system preference', () => {
    systemDark = true;
    renderTheme();

    expect(document.documentElement).toHaveAttribute('data-theme', 'light');
    expect(document.documentElement.style.colorScheme).toBe('light');
    expect(screen.getByRole('button', { name: 'Chuyển sang giao diện tối' })).toHaveAttribute('aria-pressed', 'false');
  });

  it('restores an explicit dark preference', () => {
    localStorage.setItem('kana-theme', 'dark');
    renderTheme();

    expect(screen.getByRole('button', { name: 'Chuyển sang giao diện sáng' })).toHaveAttribute('aria-pressed', 'true');
    expect(document.documentElement).toHaveAttribute('data-theme', 'dark');
  });

  it('toggles the selected mode and persists it', () => {
    renderTheme();
    fireEvent.click(screen.getByRole('button', { name: 'Chuyển sang giao diện tối' }));

    expect(document.documentElement).toHaveAttribute('data-theme', 'dark');
    expect(localStorage.getItem('kana-theme')).toBe('dark');
    fireEvent.click(screen.getByRole('button', { name: 'Chuyển sang giao diện sáng' }));
    expect(document.documentElement).toHaveAttribute('data-theme', 'light');
  });
});
