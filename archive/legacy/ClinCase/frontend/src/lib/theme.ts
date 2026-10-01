/**
 * Theme management with localStorage persistence.
 * Default: light. Dark applied via `.dark` class on <html>.
 *
 * The provider reads localStorage BEFORE first paint via a tiny inline
 * script in index.html (see frontend/index.html) to avoid a flash of
 * wrong theme. The hook here only handles runtime toggling.
 */
import { useCallback, useEffect, useState } from "react";

export type Theme = "light" | "dark";
const STORAGE_KEY = "clincase-theme";

function readStoredTheme(): Theme {
  if (typeof window === "undefined") return "dark";
  const stored = window.localStorage.getItem(STORAGE_KEY);
  // Default to dark — matches the deployed clinical-healthcare showcase.
  // Users who toggle to light have it persisted.
  return stored === "light" ? "light" : "dark";
}

function applyThemeToDom(theme: Theme): void {
  const root = document.documentElement;
  if (theme === "dark") {
    root.classList.add("dark");
  } else {
    root.classList.remove("dark");
  }
}

export function useTheme(): {
  theme: Theme;
  toggle: () => void;
  set: (t: Theme) => void;
} {
  const [theme, setThemeState] = useState<Theme>(readStoredTheme);

  // Sync class on mount (covers the case where index.html script didn't run yet)
  useEffect(() => {
    applyThemeToDom(theme);
  }, [theme]);

  const set = useCallback((t: Theme) => {
    window.localStorage.setItem(STORAGE_KEY, t);
    applyThemeToDom(t);
    setThemeState(t);
  }, []);

  const toggle = useCallback(() => {
    set(readStoredTheme() === "dark" ? "light" : "dark");
  }, [set]);

  return { theme, toggle, set };
}
