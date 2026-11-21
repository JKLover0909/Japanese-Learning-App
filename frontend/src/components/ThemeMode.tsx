import { createContext, useContext, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';

export type Theme = 'light' | 'dark';

const STORAGE_KEY = 'kana-theme';
const ThemeContext = createContext<{ theme: Theme; toggleTheme: () => void } | null>(null);

function readStoredTheme(): Theme | null {
  try {
    const value = window.localStorage.getItem(STORAGE_KEY);
    return value === 'light' || value === 'dark' ? value : null;
  } catch {
    return null;
  }
}

export function ThemeModeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>(readStoredTheme() ?? 'light');

  useEffect(() => {
    const root = document.documentElement;
    root.dataset.theme = theme;
    root.style.colorScheme = theme;
  }, [theme]);

  const value = useMemo(() => ({
    theme,
    toggleTheme: () => {
      const nextTheme = theme === 'dark' ? 'light' : 'dark';
      setTheme(nextTheme);
      try {
        window.localStorage.setItem(STORAGE_KEY, nextTheme);
      } catch {
        // The in-memory choice still works when browser storage is unavailable.
      }
    },
  }), [theme]);

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function ThemeToggle() {
  const context = useContext(ThemeContext);
  if (!context) throw new Error('ThemeToggle must be used within ThemeModeProvider');
  const isDark = context.theme === 'dark';
  return (
    <button
      className="theme-toggle"
      type="button"
      aria-label={`Chuyển sang giao diện ${isDark ? 'sáng' : 'tối'}`}
      aria-pressed={isDark}
      onClick={context.toggleTheme}
      title={`Giao diện ${isDark ? 'tối' : 'sáng'}`}
    >
      <span aria-hidden="true">{isDark ? '☀' : '☾'}</span>
      <span className="theme-toggle-label">{isDark ? 'Sáng' : 'Tối'}</span>
    </button>
  );
}
