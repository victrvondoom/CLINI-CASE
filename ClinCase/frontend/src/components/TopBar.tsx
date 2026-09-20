/**
 * Top app bar (h-14) — sits below the ActivityTicker (sm:top-7) so the
 * 28px live ticker peeks above it. Ported 1:1 from the deployed
 * clinical-healthcare showcase (components.jsx TopBar, lines 379-450).
 *
 * Layout (left → right):
 *   - Logo + brand lockup ("ClinCase." with cyan dot · "Clinical AI Platform")
 *   - Cmd+K search (md+ block, mobile icon-only)
 *   - StatusPill ("All systems operational")
 *   - NotificationsBell (with unread count)
 *   - Theme toggle
 *   - UserChip (initials + role + Verified badge)
 */
import { useEffect, useRef, useState } from "react";
import {
  Activity,
  AlertCircle,
  Bell,
  BookOpen,
  CheckCircle,
  Moon,
  Search,
  Sun,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { Link } from "react-router-dom";

import { useAuth } from "./AuthContext";
import { useTheme } from "../lib/theme";

interface Props {
  onOpenSearch: () => void;
}

export function TopBar({ onOpenSearch }: Props) {
  const { theme, toggle } = useTheme();
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header
      className={`fixed top-0 sm:top-7 inset-x-0 z-30 transition-colors duration-200 border-b ${
        scrolled
          ? "backdrop-blur-xl bg-surface-bg/90 border-surface-border"
          : "bg-surface-bg/70 backdrop-blur-md border-surface-border/60"
      }`}
    >
      <div className="h-14 flex items-center justify-between px-3 sm:px-4 lg:px-5 gap-2 sm:gap-3">
        <Link
          to="/dashboard"
          className="flex items-center gap-2 sm:gap-3 group focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-brand rounded-md min-w-0 lg:w-[228px] lg:shrink-0"
          aria-label="ClinCase home"
        >
          <img
            src="/clincase-mark.svg"
            alt=""
            aria-hidden="true"
            className="w-8 h-8 object-contain shrink-0"
            width={32}
            height={32}
          />
          <div className="leading-tight min-w-0">
            <div className="text-ui-primary tracking-[0.01em] text-ink-primary text-[15px] truncate">
              ClinCase<span className="text-accent-cyan">.</span>
            </div>
            <div className="text-compact hidden sm:block text-[9px] text-ink-muted">
              Clinical AI Platform
            </div>
          </div>
        </Link>

        {/* Desktop search */}
        <div className="flex-1 max-w-xl hidden md:block">
          <button
            type="button"
            onClick={onOpenSearch}
            className="w-full h-9 px-3 flex items-center gap-2.5 rounded-md border border-surface-border bg-surface-raised hover:border-surface-border-hi text-left text-[13px] text-ink-muted transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-brand"
          >
            <Search size={14} className="text-ink-faint" />
            <span className="text-ui-secondary flex-1">Search cases, policies, agents…</span>
            <span className="text-mono-tech text-[10px] text-ink-faint">⌘K</span>
          </button>
        </div>

        {/* Mobile-only search icon */}
        <button
          type="button"
          onClick={onOpenSearch}
          className="md:hidden inline-grid place-items-center w-9 h-9 rounded-md border border-surface-border bg-surface-raised text-ink-muted hover:text-ink-primary transition-colors shrink-0"
          aria-label="Search"
        >
          <Search size={14} />
        </button>

        <div className="flex items-center gap-1 sm:gap-1.5 shrink-0">
          <StatusPill />
          <NotificationsBell />
          <button
            type="button"
            onClick={toggle}
            className="inline-grid place-items-center w-8 h-8 rounded-md border border-surface-border bg-surface-raised text-ink-muted hover:text-ink-primary hover:border-surface-border-hi transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-brand"
            aria-label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
            title={theme === "dark" ? "Switch to light" : "Switch to dark"}
          >
            {theme === "dark" ? <Sun size={14} /> : <Moon size={14} />}
          </button>
          <UserChip />
        </div>
      </div>
    </header>
  );
}

// ---------- Status pill ("All systems operational") ----------
function StatusPill() {
  return (
    <Link
      to="/compliance"
      className="hidden lg:inline-flex items-center gap-2 h-8 px-2.5 rounded-md border border-accent-green/30 bg-accent-green/[0.06] text-[11px] text-mono-tech text-accent-green hover:bg-accent-green/10 transition-colors"
      title="99.98% uptime, 30d"
    >
      <span className="relative flex h-1.5 w-1.5">
        <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-accent-green status-dot-live" />
      </span>
      <span className="tracking-tight">All systems operational</span>
    </Link>
  );
}

// ---------- Notifications bell ----------
type Tone = "emerald" | "amber" | "cyan" | "brand";
interface Notif {
  tone: Tone;
  Icon: LucideIcon;
  title: string;
  body: string;
  time: string;
}

const NOTIFS: Notif[] = [
  { tone: "emerald", Icon: CheckCircle, title: "AUTH-2918 approved",        body: "Trastuzumab · Anthem MCG-2026.04 · 4m 12s",                 time: "just now" },
  { tone: "amber",   Icon: AlertCircle, title: "AUTH-2914 needs review",    body: "LVEF missing — escalated to nurse reviewer",                time: "6m" },
  { tone: "brand",   Icon: BookOpen,    title: "Policy update synced",      body: "UnitedHealth UHCO-2026-04 · 12 references re-indexed",      time: "24m" },
  { tone: "cyan",    Icon: Activity,    title: "Daily digest ready",        body: "34 cases decided · 92.4% within SLA",                       time: "2h" },
];

function NotificationsBell() {
  const [open, setOpen] = useState(false);
  const [unread, setUnread] = useState(3);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [open]);

  const toneCls = (t: Tone) =>
    t === "emerald" ? "text-accent-green   bg-accent-green/10  border-accent-green/30"
    : t === "amber" ? "text-accent-amber   bg-accent-amber/10  border-accent-amber/30"
    : t === "cyan"  ? "text-accent-cyan    bg-accent-cyan/10   border-accent-cyan/30"
    :                 "text-accent-brand-glow bg-accent-brand/10 border-accent-brand/30";

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => {
          setOpen((o) => !o);
          if (unread) setUnread(0);
        }}
        className="relative inline-grid place-items-center w-8 h-8 rounded-md border border-surface-border bg-surface-raised text-ink-muted hover:text-ink-primary hover:border-surface-border-hi transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-brand"
        aria-label="Notifications"
      >
        <Bell size={14} />
        {unread > 0 && (
          <span className="absolute -top-1 -right-1 min-w-[16px] h-4 px-1 rounded-full bg-accent-red text-white text-[9px] text-mono-tech font-semibold grid place-items-center border-2 border-surface-bg">
            {unread}
          </span>
        )}
      </button>
      {open && (
        <div
          className="absolute right-0 mt-2 w-[360px] rounded-xl border border-surface-border bg-surface-raised overflow-hidden card-pop"
          style={{ boxShadow: "var(--shadow-pop)" }}
        >
          <div className="px-3.5 py-2.5 border-b border-surface-border flex items-center justify-between">
            <span className="text-[12px] font-semibold text-ink-primary">Notifications</span>
            <span className="text-[10px] text-mono-tech text-ink-muted">live · 4 new</span>
          </div>
          <ul className="max-h-[360px] overflow-auto divide-y divide-surface-border">
            {NOTIFS.map((n, i) => (
              <li key={i} className="px-3.5 py-2.5 hover:bg-surface-raised-hi flex items-start gap-2.5">
                <span className={`shrink-0 w-7 h-7 rounded-md grid place-items-center border ${toneCls(n.tone)}`}>
                  <n.Icon size={13} />
                </span>
                <div className="flex-1 min-w-0">
                  <div className="text-[12.5px] font-medium text-ink-primary truncate">{n.title}</div>
                  <div className="text-[11px] text-ink-muted truncate">{n.body}</div>
                </div>
                <span className="text-[10px] text-mono-tech text-ink-faint shrink-0 mt-0.5">{n.time}</span>
              </li>
            ))}
          </ul>
          <div className="px-3.5 py-2 border-t border-surface-border bg-surface-raised-hi/40 flex items-center justify-between">
            <button
              type="button"
              onClick={() => setUnread(0)}
              className="text-[11px] text-mono-tech text-ink-muted hover:text-ink-body"
            >
              Mark all read
            </button>
            <Link to="/cases" onClick={() => setOpen(false)} className="text-[11px] text-mono-tech text-accent-brand-glow hover:underline">
              View all →
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}

// ---------- User chip with role ----------
function UserChip() {
  const { user } = useAuth();
  const role = (user?.role ?? "admin").toLowerCase();
  const isAdmin = role === "admin";

  // Use email/team initials when name isn't available, falling back to "AF" (AeroFyta)
  const initials =
    (user?.full_name ?? user?.email ?? "AeroFyta")
      .split(/[@.\s]/)
      .filter(Boolean)
      .slice(0, 2)
      .map((s) => s[0]?.toUpperCase() ?? "")
      .join("") || "AF";

  const displayName = (user?.full_name ?? user?.email?.split("@")[0] ?? "aerofyta").toLowerCase();

  return (
    <div className="hidden md:flex items-center gap-2 h-8 pl-1 pr-2.5 rounded-md border border-surface-border bg-surface-raised hover:border-surface-border-hi transition-colors">
      <div
        className="w-6 h-6 rounded-full grid place-items-center text-[10px] text-mono-tech font-semibold text-white"
        style={{ background: "linear-gradient(135deg, #121212 0%, #737373 100%)" }}
      >
        {initials}
      </div>
      <div className="leading-tight hidden lg:block">
        <div className="text-[11px] font-medium text-ink-primary truncate max-w-[110px]">{displayName}</div>
        <div className="text-[9px] text-mono-tech text-ink-muted uppercase tracking-wider">
          {isAdmin ? "Admin" : role}
        </div>
      </div>
      <span className="hidden xl:inline-flex items-center text-[9px] text-mono-tech px-1.5 py-0.5 rounded bg-accent-green/10 text-accent-green border border-accent-green/30 uppercase tracking-wider">
        Verified
      </span>
    </div>
  );
}
