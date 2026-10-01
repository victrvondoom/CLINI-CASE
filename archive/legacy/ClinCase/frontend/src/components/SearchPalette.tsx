/**
 * Cmd+K search palette. Stub for now — opens a modal showing the demo
 * fixtures for quick navigation. Phase 11+ wires real fuzzy search across
 * cases, policies, agents.
 */
import clsx from "clsx";
import { ArrowRight, Search, X } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { api } from "../lib/api";
import type { DemoFixture } from "../lib/types";

const SECTIONS: { label: string; items: { label: string; href: string; mono?: boolean }[] }[] = [
  {
    label: "Workspace",
    items: [
      { label: "Dashboard",    href: "/dashboard" },
      { label: "All cases",    href: "/cases" },
      { label: "Bulk import",  href: "/cases/bulk-import" },
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

  useEffect(() => {
    if (!open) return;
    api.listFixtures().then(setFixtures).catch(() => setFixtures([]));
  }, [open]);

  // ESC closes
  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

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
    navigate(href);
    onClose();
    setQuery("");
  }

  async function loadFixture(name: string) {
    onClose();
    setQuery("");
    const { case_id } = await api.createFromFixture(name);
    navigate(`/cases/${case_id}`);
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-[12vh] px-4"
      onClick={onClose}
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-ink-primary/40 backdrop-blur-sm animate-slide-in-up" />

      {/* Panel */}
      <div
        className="relative w-full max-w-xl bg-surface-raised border border-surface-border rounded-2xl shadow-2xl overflow-hidden animate-slide-in-up"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-3 px-4 py-3 border-b border-surface-border">
          <Search size={16} className="text-ink-muted" />
          <input
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search cases, policies, agents..."
            className="flex-1 bg-transparent outline-none text-sm text-ink-primary placeholder:text-ink-faint"
          />
          <button
            type="button"
            onClick={onClose}
            className="text-ink-faint hover:text-ink-primary"
            aria-label="Close palette"
          >
            <X size={16} />
          </button>
        </div>

        <div className="max-h-[60vh] overflow-y-auto">
          {filteredSections.map((section) => (
            <div key={section.label} className="py-2">
              <div className="px-4 py-1 text-[10px] text-compact text-ink-faint">
                {section.label}
              </div>
              {section.items.map((item) => (
                <button
                  key={item.href}
                  type="button"
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
