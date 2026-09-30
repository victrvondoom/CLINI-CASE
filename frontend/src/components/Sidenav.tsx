/**
 * Left sidenav. Sections: Workspace / Knowledge / Analytics / Admin.
 * Active route gets accent-brand left border + tinted bg + brand-tinted text.
 *
 * Width 240px expanded; can be collapsed to 64px (icons only) on a future
 * iteration. For now, expanded by default per spec.
 */
import clsx from "clsx";
import {
  BarChart3,
  Beaker,
  BookOpen,
  Calculator,
  Cpu,
  Droplets,
  Fish,
  FlaskConical,
  FolderOpen,
  Gauge,
  HeartPulse,
  Info,
  LayoutDashboard,
  Layers,
  Lock,
  LogOut,
  Map,
  Microscope,
  Network,
  PlayCircle,
  Sprout,
  ScanLine,
  Settings,
  ShieldCheck,
  Stethoscope,
  TrendingUp,
  Upload,
  UserCheck,
  Users,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useEffect, useState } from "react";
import { NavLink } from "react-router-dom";

import { api } from "../lib/api";
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
  chip?: string;        // small inline chip (e.g. "CMS-0057-F")
  disabled?: boolean;
  end?: boolean;        // active only on an exact match (not on child routes)
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

const SECTIONS: NavSection[] = [
  {
    label: "Workspace",
    items: [
      { label: "Dashboard",    href: "/dashboard",         icon: LayoutDashboard },
      { label: "Cases",        href: "/cases",             icon: FolderOpen, liveBadge: "cases" },
      { label: "Drop a scan",  href: "/intake",            icon: ScanLine, chip: "INTAKE" },
      { label: "Bulk import",  href: "/cases/bulk-import", icon: Upload, chip: "§ IV.A" },
      { label: "Sandbox",      href: "/sandbox",           icon: Beaker, chip: "SIM" },
    ],
  },
  {
    label: "Digital twin",
    items: [
      { label: "Command center", href: "/twin",      icon: HeartPulse,   chip: "TWIN", end: true },
      { label: "Guided demo",    href: "/twin/demo", icon: PlayCircle,   chip: "OT-005" },
      { label: "Research lab",   href: "/twin/lab",  icon: FlaskConical, chip: "BENCH" },
      { label: "Observability",  href: "/twin/ops",  icon: Gauge,        chip: "MLOPS" },
    ],
  },
  {
    label: "Cardio twin",
    items: [
      { label: "Vessel risk",  href: "/cardiotwin",            icon: HeartPulse,   chip: "CAD", end: true },
      { label: "Evaluation",   href: "/cardiotwin/evaluation", icon: FlaskConical, chip: "METHODS" },
    ],
  },
  {
    label: "AquaHealth",
    items: [
      { label: "Overview",        href: "/aquahealth",                  icon: Droplets,   chip: "AQUA", end: true },
      { label: "New observation", href: "/aquahealth/observations/new", icon: Sprout },
      { label: "Observations",    href: "/aquahealth/observations",     icon: FolderOpen, end: true },
      { label: "Map",             href: "/aquahealth/map",              icon: Map },
      { label: "Trends",          href: "/aquahealth/trends",           icon: TrendingUp },
      { label: "One Health",      href: "/aquahealth/one-health",       icon: Fish },
      { label: "Review queue",    href: "/aquahealth/review",           icon: UserCheck, reviewerOrAdmin: true },
      { label: "Community",       href: "/aquahealth/community",        icon: Users },
    ],
  },
  {
    label: "Knowledge",
    items: [
      { label: "Policies",  href: "/policies", icon: BookOpen },
      { label: "Agents",    href: "/agents",   icon: Cpu },
      { label: "Oncology",  href: "/onco",     icon: Stethoscope, chip: "10 USPs" },
    ],
  },
  {
    label: "Analytics",
    items: [
      { label: "Cohorts",         href: "/cohorts",     icon: BarChart3 },
      { label: "Reviewer queue",  href: "/reviewer",    icon: UserCheck, liveBadge: "awaitingReview", reviewerOrAdmin: true },
      { label: "Eval harness",    href: "/eval",        icon: Microscope, chip: "F1 .90" },
    ],
  },
  {
    label: "Business value",
    items: [
      { label: "ROI",             href: "/roi",            icon: Calculator,  chip: "$1.26B" },
      { label: "Compliance",      href: "/compliance",     icon: ShieldCheck, chip: "LIVE" },
      { label: "Industrialize",   href: "/industrialize",  icon: Layers,      chip: "FOUNDRY" },
      { label: "Architecture",    href: "/architecture",   icon: Network,     chip: "5-LAYER" },
    ],
  },
  {
    label: "Admin",
    items: [
      { label: "Settings", href: "/settings", icon: Settings, adminOnly: true },
    ],
  },
];

export function Sidenav() {
  const { user, logout } = useAuth();
  const [aboutOpen, setAboutOpen] = useState(false);
  const role = user?.role ?? "coordinator";

  // Live nav badge counts — replaces the old hardcoded "47" / "8" placeholder
  // badges with real counts from the backend. null = not loaded yet (or the
  // fetch failed); the badge simply doesn't render rather than showing a lie.
  const [liveCounts, setLiveCounts] = useState<NavLiveCounts>({ cases: null, awaitingReview: null });

  useEffect(() => {
    let cancelled = false;
    async function refresh() {
      try {
        const [allCases, awaitingReview] = await Promise.all([
          api.listCases({ limit: 1 }),
          api.listCases({ status: "awaiting_review", limit: 1 }),
        ]);
        if (cancelled) return;
        setLiveCounts({ cases: allCases.total, awaitingReview: awaitingReview.total });
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

  const initials = (user?.full_name ?? user?.email ?? "??")
    .split(/[@.\s]/)
    .filter(Boolean)
    .slice(0, 2)
    .map((s) => s[0]?.toUpperCase() ?? "")
    .join("") || "??";

  return (
    <>
      <aside
        className="w-60 shrink-0 border-r border-surface-border bg-surface-panel flex flex-col h-[calc(100vh-3.5rem)] sm:h-[calc(100vh-84px)] sticky top-14 sm:top-[84px]"
        aria-label="Primary navigation"
      >
        <nav className="flex-1 overflow-y-auto py-4 px-3 space-y-5" aria-label="Sections">
          {visibleSections.map((section) => (
            <div key={section.label} role="group" aria-labelledby={`section-${section.label}`}>
              <div
                id={`section-${section.label}`}
                className="px-3 py-1 text-[10px] text-compact text-ink-faint"
              >
                {section.label}
              </div>
              <div className="mt-1 space-y-0.5">
                {section.items.map((item) => (
                  <NavItemRow key={item.href} item={item} liveCounts={liveCounts} />
                ))}
              </div>
            </div>
          ))}
        </nav>

        <div className="px-3 py-3 border-t border-surface-border space-y-2">
          {/* User identity card */}
          <div className="flex items-center gap-2 px-2 py-1.5 text-xs">
            <div
              className="w-8 h-8 rounded-full bg-accent-brand/15 text-accent-brand flex items-center justify-center text-mono-tech font-semibold text-[11px] shrink-0"
              aria-hidden="true"
            >
              {initials}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-ink-primary font-medium truncate">
                {user?.full_name || user?.email || "—"}
              </div>
              <div className="text-[10px] text-ink-muted truncate">
                <span className="uppercase text-mono-tech tracking-wider">{role}</span>
                {user?.organization_name && (
                  <>
                    <span className="mx-1" aria-hidden="true">·</span>
                    <span className="truncate">{user.organization_name}</span>
                  </>
                )}
              </div>
            </div>
            <button
              type="button"
              onClick={() => setAboutOpen(true)}
              className="p-1.5 rounded text-ink-muted hover:text-ink-primary hover:bg-surface-raised transition-all focus:outline-none focus:ring-2 focus:ring-accent-brand"
              aria-label="About ClinCase (build version, deployment mode, feature flags)"
              title="About ClinCase"
            >
              <Info size={14} aria-hidden="true" />
            </button>
          </div>

          {/* Always-visible Sign out */}
          <button
            type="button"
            onClick={logout}
            className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-md text-xs font-medium text-ink-body bg-surface-bg hover:bg-accent-red/10 hover:text-accent-red border border-surface-border hover:border-accent-red/40 transition-colors focus:outline-none focus:ring-2 focus:ring-accent-red/40"
            aria-label="Sign out of ClinCase"
            title="Sign out"
          >
            <LogOut size={14} aria-hidden="true" />
            <span>Sign out</span>
          </button>
        </div>
      </aside>
      <AboutModal open={aboutOpen} onClose={() => setAboutOpen(false)} />
    </>
  );
}

function NavItemRow({ item, liveCounts }: { item: NavItem; liveCounts: NavLiveCounts }) {
  const Icon = item.icon;
  const liveValue = item.liveBadge ? liveCounts[item.liveBadge] : null;
  const badgeText = item.liveBadge ? (liveValue !== null ? String(liveValue) : null) : item.badge ?? null;

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
      to={item.href}
      end={item.end}
      className={({ isActive }) =>
        clsx(
          "flex items-center gap-2.5 px-3 py-1.5 rounded-md text-sm transition-colors duration-200 group relative",
          isActive
            ? "bg-accent-brand/10 text-accent-brand font-medium"
            : "text-ink-body hover:bg-surface-raised hover:text-ink-primary",
        )
      }
    >
      {({ isActive }) => (
        <>
          {isActive && (
            <span className="absolute left-0 top-1.5 bottom-1.5 w-[3px] rounded-r bg-accent-brand animate-fade-in" />
          )}
          <Icon size={15} className={clsx(isActive ? "text-accent-brand" : "", "transition-colors duration-200")} />
          <span className="flex-1 truncate">{item.label}</span>
          {item.chip && (
            <span className="text-[9px] text-mono-tech px-1 py-0.5 rounded bg-accent-cyan/10 text-accent-cyan">
              {item.chip}
            </span>
          )}
          {badgeText && (
            <span
              className={clsx(
                "text-[10px] text-mono-tech px-1.5 py-0.5 rounded transition-colors duration-200",
                isActive
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
