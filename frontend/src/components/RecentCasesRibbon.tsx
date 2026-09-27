/**
 * Recent cases ribbon — compact rows showing the latest PA cases.
 * Status pill | Patient | Treatment | Payer | Submitted (time-ago) → click row to open.
 *
 * Backed by GET /api/v1/cases?limit=6 (real backend) — no synthetic fallback.
 * An org with no cases yet sees an honest empty state instead of fake rows.
 */
import clsx from "clsx";
import { ArrowRight, Loader2 } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api, type CaseListItem } from "../lib/api";

type Status = "approved" | "denied" | "referred" | "appealed" | "running" | "pending" | "awaiting_review" | "overturned";

const STATUS_TINT: Record<string, string> = {
  approved:         "bg-accent-green/10 text-accent-green",
  denied:           "bg-accent-red/10   text-accent-red",
  referred:         "bg-accent-amber/10 text-accent-amber",
  appealed:         "bg-accent-violet/10 text-accent-violet",
  running:          "bg-accent-brand/10 text-accent-brand",
  pending:          "bg-surface-border text-ink-muted",
  awaiting_review:  "bg-accent-amber/10 text-accent-amber",
  overturned:       "bg-accent-violet/10 text-accent-violet",
};

function timeAgo(iso: string | null): string {
  if (!iso) return "—";
  const ms = Date.now() - new Date(iso).getTime();
  if (ms < 60_000) return "just now";
  if (ms < 3_600_000) return `${Math.round(ms / 60_000)}m ago`;
  if (ms < 86_400_000) return `${Math.round(ms / 3_600_000)}h ago`;
  return `${Math.round(ms / 86_400_000)}d ago`;
}

export function RecentCasesRibbon() {
  const [cases, setCases] = useState<CaseListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const d = await api.listCases({ limit: 6 });
        if (cancelled) return;
        setCases(d.cases || []);
        setTotal(d.total ?? d.cases?.length ?? 0);
        setError(null);
      } catch (e) {
        if (cancelled) return;
        setError(e instanceof Error ? e.message : "Failed to load cases");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="bg-surface-raised border border-surface-border rounded-2xl overflow-hidden">
      <div className="flex items-center justify-between px-5 py-3 border-b border-surface-border">
        <h3 className="text-sm font-semibold text-ink-primary flex items-center gap-2">
          Recent cases
          {loading && <Loader2 size={11} className="animate-spin text-ink-faint" />}
        </h3>
        <Link to="/cases" className="text-xs text-accent-brand hover:underline flex items-center gap-1">
          View all {total} →
        </Link>
      </div>

      {error && (
        <div className="px-5 py-2 text-xs text-accent-red bg-accent-red/5 border-b border-accent-red/20">
          {error}
        </div>
      )}

      {!loading && cases.length === 0 && !error && (
        <div className="px-5 py-8 text-center text-sm text-ink-muted">
          No cases yet.{" "}
          <Link to="/intake" className="text-accent-brand hover:underline">
            Create the first one →
          </Link>
        </div>
      )}

      <div className="divide-y divide-surface-border">
        {cases.map((c) => (
          <Link
            key={c.case_id}
            to={`/cases/${c.case_id}`}
            className="flex items-center gap-3 px-5 py-2.5 hover:bg-surface-raised-hi transition-colors group"
          >
            <span
              className={clsx(
                "text-[10px] text-mono-tech uppercase px-2 py-0.5 rounded tracking-wide",
                STATUS_TINT[c.status as Status] ?? "bg-surface-border text-ink-muted",
              )}
            >
              {c.status}
            </span>
            <span className="text-mono-tech text-xs text-ink-muted shrink-0 w-12">{c.patient_initials}</span>
            <div className="flex-1 min-w-0 text-sm text-ink-body truncate">
              <span className="font-medium text-ink-primary">{c.treatment}</span>
              {c.j_code && (
                <span className="ml-1.5 text-[10px] text-mono-tech text-ink-faint">
                  {c.j_code}
                </span>
              )}
            </div>
            <span className="text-[11px] text-mono-tech text-ink-muted shrink-0">{c.payer_id?.toUpperCase()}</span>
            <span className="text-[11px] text-ink-faint shrink-0 w-16 text-right">{timeAgo(c.created_at)}</span>
            <ArrowRight size={14} className="text-ink-faint group-hover:text-accent-brand transition-colors shrink-0" />
          </Link>
        ))}
      </div>
    </div>
  );
}
