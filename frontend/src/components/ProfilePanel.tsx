/**
 * Profile button + panel — click the user chip in the TopBar to see who
 * you're signed in as (per logged-in user, not shared) and your own recent
 * activity (cases opened, reviewer actions taken, last login), pulled from
 * GET /api/v1/auth/me/activity. Same dropdown-panel pattern as the
 * NotificationsBell in TopBar.tsx.
 */
import { AlertOctagon, CheckCircle2, Clock, LogIn, LogOut, StickyNote } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { useAuth } from "./AuthContext";
import { type ActivityEvent, fetchMyActivity } from "../lib/auth";

const KIND_ICON: Record<string, LucideIcon> = {
  case_opened: StickyNote,
  reviewer_action: CheckCircle2,
  login: LogIn,
};

function timeAgo(iso: string | null): string {
  if (!iso) return "";
  const ms = Date.now() - new Date(iso).getTime();
  if (!Number.isFinite(ms) || ms < 0) return "";
  const min = Math.floor(ms / 60_000);
  if (min < 1) return "just now";
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;
  return `${Math.floor(hr / 24)}d ago`;
}

interface ProfilePanelProps {
  trigger: (props: { onClick: () => void; open: boolean }) => React.ReactNode;
}

export function ProfilePanel({ trigger }: ProfilePanelProps) {
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const [events, setEvents] = useState<ActivityEvent[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [open]);

  useEffect(() => {
    if (!open || events !== null) return;
    fetchMyActivity(12)
      .then((r) => setEvents(r.events))
      .catch((e) => setErr((e as Error).message));
  }, [open, events]);

  const displayName = user?.full_name ?? user?.email?.split("@")[0] ?? "ClinCase user";
  const role = (user?.role ?? "admin").toLowerCase();

  return (
    <div ref={ref} className="relative">
      {trigger({ onClick: () => setOpen((o) => !o), open })}
      {open && (
        <div
          className="absolute right-0 mt-2 w-[340px] rounded-xl border border-surface-border bg-surface-raised overflow-hidden card-pop animate-slide-in-down origin-top-right"
          style={{ boxShadow: "var(--shadow-pop)" }}
          role="dialog"
          aria-label="Profile"
        >
          <div className="px-3.5 py-3 border-b border-surface-border">
            <div className="text-[13px] font-semibold text-ink-primary truncate">{displayName}</div>
            <div className="text-[11px] text-ink-muted truncate">{user?.email}</div>
            <div className="mt-1.5 flex items-center gap-1.5">
              <span className="text-[9px] text-mono-tech px-1.5 py-0.5 rounded bg-accent-brand/10 text-accent-brand border border-accent-brand/30 uppercase tracking-wider">
                {role}
              </span>
              {user?.organization_name && (
                <span className="text-[10px] text-ink-muted truncate">{user.organization_name}</span>
              )}
            </div>
          </div>

          <div className="px-3.5 py-2 border-b border-surface-border flex items-center justify-between">
            <span className="text-[11px] font-semibold text-ink-primary flex items-center gap-1.5">
              <Clock size={12} aria-hidden /> Your recent activity
            </span>
          </div>

          <div className="max-h-[280px] overflow-auto">
            {err && <div className="px-3.5 py-3 text-[11.5px] text-accent-red" role="alert">{err}</div>}
            {!err && events === null && (
              <div className="px-3.5 py-4 text-[11.5px] text-ink-muted">Loading…</div>
            )}
            {!err && events !== null && events.length === 0 && (
              <div className="px-3.5 py-4 text-[11.5px] text-ink-muted">No activity yet.</div>
            )}
            {!err && events !== null && events.length > 0 && (
              <ul className="divide-y divide-surface-border">
                {events.map((e) => {
                  const Icon = KIND_ICON[e.kind] ?? AlertOctagon;
                  return (
                    <li key={e.id} className="px-3.5 py-2.5 flex items-start gap-2.5">
                      <span className="shrink-0 w-6 h-6 rounded-md grid place-items-center border border-surface-border text-ink-muted">
                        <Icon size={12} aria-hidden />
                      </span>
                      <div className="flex-1 min-w-0">
                        <div className="text-[11.5px] text-ink-body leading-snug">{e.summary}</div>
                      </div>
                      <span className="text-[10px] text-mono-tech text-ink-faint shrink-0 mt-0.5">{timeAgo(e.at)}</span>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>

          <div className="px-3.5 py-2 border-t border-surface-border bg-surface-raised-hi/40">
            <button
              type="button"
              onClick={logout}
              className="w-full inline-flex items-center justify-center gap-1.5 h-8 rounded-md border border-surface-border text-[11.5px] text-ink-body hover:border-accent-red/60 hover:text-accent-red transition-colors"
            >
              <LogOut size={12} aria-hidden /> Sign out
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
