/**
 * Full app layout, ported from the deployed clinical-healthcare showcase.
 *
 * Stack (top → bottom):
 *   - ActivityTicker: fixed top-0, h-7 (28px), only on sm+
 *   - TopBar:         fixed top-0 sm:top-7, h-14
 *   - Sidenav:        sticky top-14 sm:top-[84px], full-height column
 *   - Main outlet:    inside same flex as Sidenav, padding-top compensates
 *                     for the fixed ticker + topbar
 *   - FAB:            fixed bottom-6 right-6, "New case" pill
 *   - SearchPalette:  Cmd+K modal overlay
 */
import { useCallback, useEffect, useState } from "react";
import { Outlet, useLocation } from "react-router-dom";

import { ActivityTicker } from "./ActivityTicker";
import { FAB } from "./FAB";
import { SearchPalette } from "./SearchPalette";
import { Sidenav } from "./Sidenav";
import { TopBar } from "./TopBar";

// Routes that already have their own primary CTA at the bottom-right where
// the FAB would otherwise overlap content. The FAB is suppressed here.
const _SUPPRESS_FAB_ROUTES = new Set([
  "/intake",
]);

export function AppShell() {
  const location = useLocation();
  const [paletteOpen, setPaletteOpen] = useState(false);
  const showFab = !_SUPPRESS_FAB_ROUTES.has(location.pathname);

  const openPalette = useCallback(() => setPaletteOpen(true), []);
  const closePalette = useCallback(() => setPaletteOpen(false), []);

  // Global keyboard shortcuts:
  //  - Cmd+K / Ctrl+K → toggle command palette
  //  - N (when no input focused, no modifier) → new case (intake)
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const target = e.target as HTMLElement | null;
      const isInput =
        !!target &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.isContentEditable);

      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen((prev) => !prev);
        return;
      }
      if (!isInput && !e.metaKey && !e.ctrlKey && !e.altKey && e.key.toLowerCase() === "n") {
        e.preventDefault();
        window.location.assign("/intake");
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <div className="min-h-screen bg-surface-bg text-ink-body">
      <ActivityTicker />
      <TopBar onOpenSearch={openPalette} />

      {/* Compensate for fixed ticker (28px on sm+) + topbar (56px) = 84px */}
      <div className="pt-14 sm:pt-[84px] flex">
        <Sidenav />
        <main className="flex-1 min-w-0">
          <Outlet />
        </main>
      </div>

      {showFab && <FAB />}
      <SearchPalette open={paletteOpen} onClose={closePalette} />
    </div>
  );
}
