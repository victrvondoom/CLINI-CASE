/** Compact workflow navigation with persistent scroll and preferences. */
import clsx from "clsx";
import {
  Droplets,
  FolderOpen,
  HeartPulse,
  Info,
  LayoutDashboard,
  Layers,
  Lock,
  LogOut,
  Microscope,
  Network,
  Server,
  Settings,
  ShieldCheck,
  Stethoscope,
  Upload,
  Workflow,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useEffect, useState, useRef, useLayoutEffect } from "react";
import { areaFor } from "../workflow/areas";
import { NavLink, useLocation } from "react-router-dom";

import { api } from "../lib/api";
import { EMPTY_SNAPSHOT, buildNavChips, fetchSnapshot } from "../lib/liveFeed";
import { useLive } from "../lib/useLive";
import { AboutModal } from "./AboutModal";
import { useAuth } from "./AuthContext";

interface NavItem {
  label: string;
  href: string;
  icon: LucideIcon;
  /** Static badge text. Ignored when `liveBadge` is set — see NavLiveCounts. */
  badge?: string;
  /** Key into NavLiveCounts — badge renders the live count (or nothing while
   * loading / on fetch failure, rather than a stale hardcoded number). */
  liveBadge?: keyof NavLiveCounts;
  chip?: string; // small inline chip (e.g. "CMS-0057-F")
  disabled?: boolean;
  end?: boolean; // active only on an exact match (not on child routes)
  adminOnly?: boolean;
  reviewerOrAdmin?: boolean;
}

interface NavSection {
  label: string;
  items: NavItem[];
}

interface NavLiveCounts {
  cases: number | null;
  awaitingReview: number | null;
}

// One platform as one flow: Dashboard, then each step of the evidence workflow in the order a
// reviewer works through it. Every pre-existing route is still listed here.
const SECTIONS: NavSection[] = [
  {
    label: "Main",
    items: [
      { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
      {
        label: "Cases",
        href: "/cases",
        icon: FolderOpen,
        liveBadge: "cases",
        end: true,
      },
      { label: "Journey", href: "/journey", icon: Workflow },
    ],
  },
  {
    label: "Workflow",
    items: [
      { label: "Intake", href: "/intake-tools", icon: Upload },
      { label: "Evidence", href: "/evidence", icon: Droplets },
      { label: "Interoperability", href: "/interop", icon: Network },
      { label: "Review & Safety", href: "/review", icon: ShieldCheck },
      {
        label: "Clinical Context",
        href: "/clinical-context",
        icon: Stethoscope,
      },
      { label: "Follow-up", href: "/follow-up", icon: HeartPulse },
    ],
  },
  {
    label: "Platform",
    items: [
      { label: "Research", href: "/research", icon: Microscope },
      { label: "Runtime", href: "/runtime", icon: Server },
      { label: "Architecture", href: "/architecture", icon: Layers },
      { label: "Settings", href: "/settings", icon: Settings, adminOnly: true },
    ],
  },
];

/** The workflow in reading order, for Previous / Next links under each page. */
export const FLOW = SECTIONS.flatMap((section) =>
  section.items
    .filter((item) => !item.adminOnly)
    .map((item) => ({
      label: item.label,
      href: item.href,
      group: section.label,
    })),
);

export function Sidenav() {
  const { user, logout } = useAuth();
  const [aboutOpen, setAboutOpen] = useState(false);
  const navRef = useRef<HTMLElement>(null);
  const [collapsed, setCollapsed] = useState(() => {
    try {
      return localStorage.getItem("clini-nav-collapsed") === "true";
    } catch {
      return false;
    }
  });
  const [closed, setClosed] = useState<string[]>(() => {
    try {
      const value = JSON.parse(
        localStorage.getItem("clini-nav-groups") ?? "[]",
      );
      return Array.isArray(value)
        ? value.filter((v): v is string => typeof v === "string")
        : [];
    } catch {
      return [];
    }
  });
  useLayoutEffect(() => {
    try {
      if (navRef.current)
        navRef.current.scrollTop = Number(
          sessionStorage.getItem("clini-nav-scroll") ?? 0,
        );
    } catch {
      /* storage unavailable */
    }
  }, []);
  function toggleGroup(label: string) {
    setClosed((previous) => {
      const next = previous.includes(label)
        ? previous.filter((v) => v !== label)
        : [...previous, label];
      try {
        localStorage.setItem("clini-nav-groups", JSON.stringify(next));
      } catch {
        /* storage unavailable */
      }
      return next;
    });
  }
  const role = user?.role ?? "coordinator";

  // Live nav badge counts — replaces the old hardcoded "47" / "8" placeholder
  // badges with real counts from the backend. null = not loaded yet (or the
  // fetch failed); the badge simply doesn't render rather than showing a lie.
  const [liveCounts, setLiveCounts] = useState<NavLiveCounts>({
    cases: null,
    awaitingReview: null,
  });

  useEffect(() => {
    let cancelled = false;
    async function refresh() {
      try {
        const [allCases, awaitingReview] = await Promise.all([
          api.listCases({ limit: 1 }),
          api.listCases({ status: "awaiting_review", limit: 1 }),
        ]);
        if (cancelled) return;
        setLiveCounts({
          cases: allCases.total,
          awaitingReview: awaitingReview.total,
        });
      } catch {
        // Backend unreachable / DB down — leave counts null so badges hide
        // rather than showing a stale or fabricated number.
      }
    }
    void refresh();
    // Refresh periodically so the badge doesn't go stale during a long session.
    const interval = window.setInterval(refresh, 60_000);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, []);

  // Metric-style chips (F1, projected savings, layer count) come from real endpoints; absent until loaded.
  const chips = buildNavChips(
    useLive(fetchSnapshot, [], 5 * 60_000).data ?? EMPTY_SNAPSHOT,
  );

  // Filter sections by role
  const visibleSections = SECTIONS.map((section) => ({
    ...section,
    items: section.items.filter((item) => {
      if (item.adminOnly && role !== "admin") return false;
      // Reviewer Queue is visible to all but RequireAuth blocks Coordinator
      // (we keep it visible so they understand the workflow exists).
      return true;
    }),
  })).filter((s) => s.items.length > 0);

  const initials =
    (user?.full_name ?? user?.email ?? "??")
      .split(/[@.\s]/)
      .filter(Boolean)
      .slice(0, 2)
      .map((s) => s[0]?.toUpperCase() ?? "")
      .join("") || "??";

  return (
    <>
      <aside
        className={clsx(
          collapsed ? "w-16" : "w-48",
          "shrink-0 border-r border-surface-border bg-surface-panel flex flex-col h-[calc(100vh-3.5rem)] sm:h-[calc(100vh-84px)] sticky top-14 sm:top-[84px]",
        )}
        aria-label="Primary navigation"
      >
        <button
          type="button"
          className="p-2 text-xs hover:bg-surface-raised"
          aria-label={collapsed ? "Expand navigation" : "Collapse navigation"}
          onClick={() =>
            setCollapsed((v) => {
              try {
                localStorage.setItem("clini-nav-collapsed", String(!v));
              } catch {
                /* storage unavailable */
              }
              return !v;
            })
          }
        >
          {collapsed ? (
            ">"
          ) : (
            <>
              <span aria-hidden="true">&lt;</span>
              <span className="hidden sm:inline"> Compact</span>
            </>
          )}
        </button>
        <nav
          ref={navRef}
          onScroll={(e) => {
            try {
              sessionStorage.setItem(
                "clini-nav-scroll",
                String(e.currentTarget.scrollTop),
              );
            } catch {
              /* storage unavailable */
            }
          }}
          className="flex-1 overflow-y-auto py-2 px-2 space-y-2"
          aria-label="Sections"
        >
          {visibleSections.map((section) => (
            <div
              key={section.label}
              role="group"
              aria-labelledby={`section-${section.label}`}
            >
              <button
                type="button"
                aria-label={section.label}
                aria-expanded={!closed.includes(section.label)}
                onClick={() => toggleGroup(section.label)}
                id={`section-${section.label}`}
                className="px-3 py-1 text-[10px] text-compact text-ink-faint"
              >
                <span className="hidden sm:inline">
                  {collapsed ? section.label.slice(0, 1) : section.label}
                </span>
                <span className="sm:hidden">{section.label.slice(0, 1)}</span>
              </button>
              {!closed.includes(section.label) && (
                <div className="mt-1 space-y-0.5">
                  {section.items.map((item) => (
                    <NavItemRow
                      key={item.href}
                      item={item}
                      liveCounts={liveCounts}
                      chips={chips}
                      collapsed={collapsed}
                    />
                  ))}
                </div>
              )}
            </div>
          ))}
        </nav>

        <div
          className={clsx("px-3 py-3 border-t border-surface-border space-y-2")}
        >
          {/* User identity card */}
          <div className="flex items-center gap-2 px-2 py-1.5 text-xs">
            <div
              className={clsx(
                collapsed && "hidden",
                "w-8 h-8 rounded-full bg-accent-brand/15 text-accent-brand flex items-center justify-center text-mono-tech font-semibold text-[11px] shrink-0",
              )}
              aria-hidden="true"
            >
              {initials}
            </div>
            <div className={clsx(collapsed && "hidden", "flex-1 min-w-0")}>
              <div className="text-ink-primary font-medium truncate">
                {user?.full_name || user?.email || "—"}
              </div>
              <div className="text-[10px] text-ink-muted truncate">
                <span className="uppercase text-mono-tech tracking-wider">
                  {role}
                </span>
                {user?.organization_name && (
                  <>
                    <span className="mx-1" aria-hidden="true">
                      ·
                    </span>
                    <span className="truncate">{user.organization_name}</span>
                  </>
                )}
              </div>
            </div>
            <button
              type="button"
              onClick={() => setAboutOpen(true)}
              className="p-1.5 rounded text-ink-muted hover:text-ink-primary hover:bg-surface-raised transition-all focus:outline-none focus:ring-2 focus:ring-accent-brand"
              aria-label="About CLINI-CASE (build version, deployment mode, feature flags)"
              title="About CLINI-CASE"
            >
              <Info size={14} aria-hidden="true" />
            </button>
          </div>

          {/* Always-visible Sign out */}
          <button
            type="button"
            onClick={logout}
            className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-md text-xs font-medium text-ink-body bg-surface-bg hover:bg-accent-red/10 hover:text-accent-red border border-surface-border hover:border-accent-red/40 transition-colors focus:outline-none focus:ring-2 focus:ring-accent-red/40"
            aria-label="Sign out of CLINI-CASE"
            title="Sign out"
          >
            <LogOut size={14} aria-hidden="true" />
            {!collapsed && <span>Sign out</span>}
          </button>
        </div>
      </aside>
      <AboutModal open={aboutOpen} onClose={() => setAboutOpen(false)} />
    </>
  );
}

function NavItemRow({
  item,
  liveCounts,
  chips,
  collapsed,
}: {
  collapsed?: boolean;
  item: NavItem;
  liveCounts: NavLiveCounts;
  chips: Record<string, string | null>;
}) {
  const { pathname } = useLocation();
  const contextualActive = areaFor(pathname)?.path === item.href;
  const chip = item.chip ?? chips[item.href] ?? null;
  const Icon = item.icon;
  const liveValue = item.liveBadge ? liveCounts[item.liveBadge] : null;
  const badgeText = item.liveBadge
    ? liveValue !== null
      ? String(liveValue)
      : null
    : (item.badge ?? null);

  if (item.disabled) {
    return (
      <div
        className="flex items-center gap-2.5 px-3 py-1.5 rounded-md text-sm text-ink-faint cursor-not-allowed"
        title="Coming soon"
      >
        <Icon size={15} />
        <span className="flex-1">{item.label}</span>
        <Lock size={11} className="opacity-60" />
      </div>
    );
  }

  return (
    <NavLink
      title={item.label}
      aria-label={item.label}
      aria-current={contextualActive ? "page" : undefined}
      to={item.href}
      end={item.end}
      className={({ isActive }) =>
        clsx(
          "flex items-center gap-2.5 px-3 py-1.5 rounded-md text-sm transition-colors duration-200 group relative",
          isActive || contextualActive
            ? "bg-accent-brand/10 text-accent-brand font-medium"
            : "text-ink-body hover:bg-surface-raised hover:text-ink-primary",
        )
      }
    >
      {({ isActive }) => (
        <>
          {(isActive || contextualActive) && (
            <span className="absolute left-0 top-1.5 bottom-1.5 w-[3px] rounded-r bg-accent-brand animate-fade-in" />
          )}
          <Icon
            size={15}
            className={clsx(
              isActive || contextualActive ? "text-accent-brand" : "",
              "transition-colors duration-200",
            )}
          />
          {!collapsed && <span className="flex-1 truncate">{item.label}</span>}
          {!collapsed && chip && (
            <span
              data-testid={`chip-${item.href}`}
              className="text-[9px] text-mono-tech px-1 py-0.5 rounded bg-accent-cyan/10 text-accent-cyan"
            >
              {chip}
            </span>
          )}
          {!collapsed && badgeText && (
            <span
              className={clsx(
                "text-[10px] text-mono-tech px-1.5 py-0.5 rounded transition-colors duration-200",
                isActive || contextualActive
                  ? "bg-accent-brand text-ink-invert"
                  : "bg-surface-border text-ink-muted group-hover:bg-surface-border-hi",
              )}
            >
              {badgeText}
            </span>
          )}
        </>
      )}
    </NavLink>
  );
}
