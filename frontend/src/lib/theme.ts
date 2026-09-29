/**
 * Theme management with localStorage persistence.
 * Default: light. Dark applied via `.dark` class on <html>.
 *
 * The provider reads localStorage BEFORE first paint via a tiny inline
 * script in index.html (see frontend/index.html) to avoid a flash of
 * wrong theme. The hook here only handles runtime toggling.
 *
 * Multiple components on the same page (e.g. Landing.tsx + its Nav) each
 * call this hook independently. They must not drift out of sync: a toggle
 * fired from one instance's button needs every other mounted instance to
 * re-render too, or only the component that owns the click updates while
 * everything else (the actual page background, in Landing's case) stays on
 * the old theme. A module-level subscriber set makes every instance's
 * `set()` notify every other mounted instance in this tab.
 */
import { useCallback, useEffect, useState } from "react";

export type Theme = "light" | "dark";
const STORAGE_KEY = "clincase-theme";

const listeners = new Set<(t: Theme) => void>();

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

  // Pick up theme changes made through a different useTheme() instance on
  // the same page (e.g. a nav's toggle button vs. the page component that
  // reads theme for its own background/data-theme attribute).
  useEffect(() => {
    listeners.add(setThemeState);
    return () => {
      listeners.delete(setThemeState);
    };
  }, []);

  const set = useCallback((t: Theme) => {
    window.localStorage.setItem(STORAGE_KEY, t);
    applyThemeToDom(t);
    listeners.forEach((notify) => notify(t));
  }, []);

  const toggle = useCallback(() => {
    set(readStoredTheme() === "dark" ? "light" : "dark");
  }, [set]);

  return { theme, toggle, set };
}
