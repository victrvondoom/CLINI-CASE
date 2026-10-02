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
import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from "react";
import {
  Outlet,
  useLocation,
  useNavigate,
  useNavigationType,
} from "react-router-dom";

import { WorkflowNavigation } from "../workflow/WorkflowNavigation";
import { ActivityTicker } from "./ActivityTicker";
import { FAB } from "./FAB";
import { SearchPalette } from "./SearchPalette";
import { Sidenav } from "./Sidenav";
import { TopBar } from "./TopBar";
import { RouteBoundary } from "./RouteBoundary";

// Routes that already have their own primary CTA at the bottom-right where
// the FAB would otherwise overlap content. The FAB is suppressed here.
const _SUPPRESS_FAB_ROUTES = new Set(["/intake"]);

export function AppShell() {
  const location = useLocation();
  const navigate = useNavigate();
  const navigationType = useNavigationType();
  const contentRef = useRef<HTMLDivElement>(null);
  const pageScroll = useRef(new Map<string, number>());
  useLayoutEffect(() => {
    const key = location.key;
    if (!window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      contentRef.current?.animate?.(
        [
          { opacity: 0.65, transform: "translateY(4px)" },
          { opacity: 1, transform: "translateY(0)" },
        ],
        { duration: 160, easing: "ease-out" },
      );
    }
    window.scrollTo({
      top: navigationType === "POP" ? (pageScroll.current.get(key) ?? 0) : 0,
      behavior: "instant",
    });
    const remember = () => pageScroll.current.set(key, window.scrollY);
    window.addEventListener("scroll", remember, { passive: true });
    return () => window.removeEventListener("scroll", remember);
  }, [location.key, navigationType]);
  useEffect(() => {
    if (location.pathname.startsWith("/journey/")) {
      try {
        sessionStorage.setItem("clini-current-journey", location.pathname);
      } catch {
        /* storage unavailable */
      }
    }
  }, [location.pathname]);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const oneHealth =
    location.pathname === "/onehealth" ||
    location.pathname === "/interop" ||
    location.pathname.startsWith("/journey") ||
    location.pathname.startsWith("/aquahealth");
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
          target.tagName === "SELECT" ||
          target.isContentEditable);

      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen((prev) => !prev);
        return;
      }
      if (
        !paletteOpen &&
        !isInput &&
        !e.metaKey &&
        !e.ctrlKey &&
        !e.altKey &&
        e.key.toLowerCase() === "n"
      ) {
        e.preventDefault();
        navigate("/intake");
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [navigate, paletteOpen]);

  return (
    <div className="min-h-screen bg-surface-bg text-ink-body">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:z-[100] focus:top-2 focus:left-2 focus:bg-surface-raised focus:p-3"
      >
        Skip to content
      </a>
      <ActivityTicker oneHealth={oneHealth} />
      <TopBar onOpenSearch={openPalette} oneHealth={oneHealth} />

      {/* Compensate for fixed ticker (28px on sm+) + topbar (56px) = 84px */}
      <div className="pt-14 sm:pt-[84px] flex">
        <Sidenav />
        <main id="main-content" tabIndex={-1} className="flex-1 min-w-0 pb-24">
          <WorkflowNavigation />
          <div ref={contentRef}>
            <RouteBoundary>
              {/* Dashboard and Cases own their intro; every other page gets the same reveal and heading style. */}
              {location.pathname === "/dashboard" || location.pathname === "/cases" ? (
                <Outlet />
              ) : (
                <div
                  key={location.pathname}
                  className="page-typography reveal-go [&_h1]:text-2xl [&_h1]:font-semibold [&_h1]:leading-tight [&_h1]:text-ink-primary"
                >
                  <Outlet />
                </div>
              )}
            </RouteBoundary>
          </div>
        </main>
      </div>

      {showFab && <FAB />}
      <SearchPalette open={paletteOpen} onClose={closePalette} />
    </div>
  );
}
