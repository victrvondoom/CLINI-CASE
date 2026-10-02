/**
 * Cmd+K search palette. Stub for now — opens a modal showing the demo
 * fixtures for quick navigation. Phase 11+ wires real fuzzy search across
 * cases, policies, agents.
 */
import clsx from "clsx";
import { ArrowRight, Search, X } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { api } from "../lib/api";
import type { DemoFixture } from "../lib/types";

const SECTIONS: { label: string; items: { label: string; href: string; mono?: boolean }[] }[] = [
  {
    label: "CLINI-CASE",
    items: [
      { label: "Evidence journey", href: "/journey" },
      { label: "Runtime topology", href: "/runtime" },
    ],
  },
  {
    label: "Workspace",
    items: [
      { label: "Dashboard",    href: "/dashboard" },
      { label: "All cases",    href: "/cases" },
      { label: "Bulk import",  href: "/cases/bulk-import" },
      { label: "Sandbox — PA decision simulator", href: "/sandbox" },
    ],
  },
  {
    label: "Knowledge",
    items: [
      { label: "Policy library", href: "/policies" },
      { label: "Agents",         href: "/agents" },
    ],
  },
  {
    label: "Analytics",
    items: [
      { label: "Cohort insights", href: "/cohorts" },
      { label: "Reviewer queue",  href: "/reviewer" },
      { label: "Compliance",      href: "/compliance" },
    ],
  },
];

interface Props {
  open: boolean;
  onClose: () => void;
}

export function SearchPalette({ open, onClose }: Props) {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [fixtures, setFixtures] = useState<DemoFixture[]>([]);
  const [fixturesLoading, setFixturesLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const creatingRef = useRef(false);
  const operationRef = useRef(0);
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    let active = true;
    operationRef.current += 1;
    creatingRef.current = false;
    setCreating(false);
    setFixturesLoading(true);
    setError(null);
    api.listFixtures()
      .then((items) => { if (active) setFixtures(items); })
      .catch(() => {
        if (active) { setFixtures([]); setError("Demo cases could not be loaded. Close and reopen search to retry."); }
      })
      .finally(() => { if (active) setFixturesLoading(false); });
    return () => {
      active = false;
      operationRef.current += 1;
      creatingRef.current = false;
    };
  }, [open]);

  const closePalette = useCallback(() => {
    operationRef.current += 1;
    creatingRef.current = false;
    onClose();
  }, [onClose]);

  // Trap keyboard focus and return it to the invoking control when closing.
  useEffect(() => {
    if (!open) return;
    const previous = document.activeElement as HTMLElement | null;
    panelRef.current?.querySelector("input")?.focus();
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") closePalette();
      if (e.key === "Tab") {
        const controls = Array.from(panelRef.current?.querySelectorAll<HTMLElement>("input, button:not(:disabled)") ?? []);
        const first = controls[0];
        const last = controls[controls.length - 1];
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last?.focus(); }
        if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first?.focus(); }
      }
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        const controls = Array.from(panelRef.current?.querySelectorAll<HTMLElement>("input, button:not(:disabled)") ?? []);
        if (!controls.length) return;
        const current = controls.indexOf(document.activeElement as HTMLElement);
        const delta = e.key === "ArrowDown" ? 1 : -1;
        const next = (current + delta + controls.length) % controls.length;
        e.preventDefault();
        controls[next]?.focus();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => { window.removeEventListener("keydown", onKey); previous?.focus(); };
  }, [closePalette, open]);

  if (!open) return null;

  const q = query.toLowerCase().trim();
  const filteredSections = SECTIONS.map((section) => ({
    ...section,
    items: section.items.filter((item) =>
      q === "" ? true : item.label.toLowerCase().includes(q),
    ),
  })).filter((s) => s.items.length > 0);

  const filteredFixtures = q
    ? fixtures.filter(
        (f) =>
          f.label.toLowerCase().includes(q) ||
          f.requested_treatment.name.toLowerCase().includes(q) ||
          f.payer_id.toLowerCase().includes(q),
      )
    : fixtures.slice(0, 3);

  function go(href: string) {
    operationRef.current += 1;
    creatingRef.current = false;
    navigate(href);
    onClose();
    setQuery("");
  }

  async function loadFixture(name: string) {
    if (creatingRef.current) return;
    creatingRef.current = true;
    const operation = ++operationRef.current;
    setCreating(true);
    setError(null);
    try {
      const { case_id } = await api.createFromFixture(name);
      if (operation !== operationRef.current) return;
      navigate(`/cases/${case_id}`);
      onClose();
      setQuery("");
    } catch {
      if (operation !== operationRef.current) return;
      setError("The demo case could not be created. Check your connection and try again.");
    } finally {
      if (operation === operationRef.current) {
        creatingRef.current = false;
        setCreating(false);
      }
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-[12vh] px-4"
      onClick={closePalette}
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-ink-primary/40 backdrop-blur-sm animate-slide-in-up" />

      {/* Panel */}
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label="Search workspace and demo cases"
        aria-busy={creating || fixturesLoading}
        className="relative w-full max-w-xl bg-surface-raised border border-surface-border rounded-2xl shadow-2xl overflow-hidden animate-slide-in-up"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-3 px-4 py-3 border-b border-surface-border">
          <Search size={16} className="text-ink-muted" />
          <input
            aria-label="Search workspace and demo cases"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search cases, policies, agents..."
            className="flex-1 bg-transparent outline-none text-sm text-ink-primary placeholder:text-ink-faint"
          />
          <button
            type="button"
            onClick={closePalette}
            className="text-ink-faint hover:text-ink-primary transition-colors duration-150"
            aria-label="Close palette"
          >
            <X size={16} />
          </button>
        </div>

        <div className="max-h-[60vh] overflow-y-auto">
          {error && <p role="alert" className="px-4 py-3 text-sm text-accent-red">{error}</p>}
          {fixturesLoading && <p role="status" className="px-4 py-3 text-sm text-ink-muted">Loading demo cases…</p>}
          {creating && <p role="status" className="px-4 py-3 text-sm">Creating demo case…</p>}
          {!fixturesLoading && !filteredSections.length && !filteredFixtures.length && !error && <p role="status" className="px-4 py-3 text-sm text-ink-muted">No matching pages or demo cases.</p>}
          {filteredSections.map((section) => (
            <div key={section.label} className="py-2">
              <div className="px-4 py-1 text-[10px] text-compact text-ink-faint">
                {section.label}
              </div>
              {section.items.map((item) => (
                <button
                  key={item.href}
                  type="button"
                  disabled={creating}
                  onClick={() => go(item.href)}
                  className="w-full flex items-center justify-between px-4 py-2 text-sm text-ink-body hover:bg-surface-raised-hi transition-colors"
                >
                  <span>{item.label}</span>
                  <ArrowRight size={12} className="text-ink-faint" />
                </button>
              ))}
            </div>
          ))}

          {filteredFixtures.length > 0 && (
            <div className="py-2 border-t border-surface-border">
              <div className="px-4 py-1 text-[10px] text-compact text-ink-faint">
                Demo cases
              </div>
              {filteredFixtures.map((f) => (
                <button
                  key={f.name}
                  type="button"
                  disabled={creating}
                  onClick={() => loadFixture(f.name)}
                  className="w-full flex items-center justify-between px-4 py-2 text-sm text-ink-body hover:bg-surface-raised-hi transition-colors"
                >
                  <div className="flex flex-col items-start">
                    <span className="text-ink-primary">{f.label}</span>
                    <span className="text-[11px] text-ink-faint text-mono-tech">
                      {f.payer_id.toUpperCase()} · {f.requested_treatment.name}
                    </span>
                  </div>
                  <span
                    className={clsx(
                      "text-[10px] text-mono-tech px-1.5 py-0.5 rounded",
                      f.expected_verdict === "APPROVE" && "bg-accent-green/10 text-accent-green",
                      f.expected_verdict === "DENY"    && "bg-accent-red/10   text-accent-red",
                      f.expected_verdict === "REFER"   && "bg-accent-amber/10 text-accent-amber",
                    )}
                  >
                    {f.expected_verdict}
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="px-4 py-2 border-t border-surface-border flex items-center justify-between text-[11px] text-ink-faint">
          <span className="text-mono-tech">↑↓ navigate · ↵ select · esc close</span>
          <span className="text-mono-tech">⌘K to reopen</span>
        </div>
      </div>
    </div>
  );
}
