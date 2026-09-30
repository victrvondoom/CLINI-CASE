/**
 * /cohorts — Cross-case analytics for THIS organisation, computed live from its cases and decisions
 * (GET /api/v1/cohorts). Nothing on this page is a fixture: with no cases it shows an empty state, and
 * insight cards only appear when there is enough evidence behind them.
 */
import { ArrowRight, BarChart3, Lightbulb, Loader2, RefreshCw } from "lucide-react";
import { Link } from "react-router-dom";
import { useState } from "react";

import { api } from "../lib/api";
import type { CohortInsight } from "../lib/types";
import { useLive } from "../lib/useLive";

const ACCENT_BG: Record<CohortInsight["accent"], string> = {
  amber:  "bg-accent-amber/5  border-accent-amber/30",
  blue:   "bg-accent-blue/5   border-accent-blue/30",
  violet: "bg-accent-violet/5 border-accent-violet/30",
  green:  "bg-accent-green/5  border-accent-green/30",
};

const ACCENT_ICON: Record<CohortInsight["accent"], string> = {
  amber:  "text-accent-amber",
  blue:   "text-accent-blue",
  violet: "text-accent-violet",
  green:  "text-accent-green",
};

const WINDOWS = [
  { days: 30, label: "30 days" },
  { days: 90, label: "90 days" },
  { days: 365, label: "1 year" },
];

const POLL_MS = 60_000;

export default function Cohorts() {
  const [days, setDays] = useState(90);
  const { data, error, loading, updatedAt, reload } = useLive(() => api.getCohorts(days), [days], POLL_MS);
  const empty = !!data && data.total_cases === 0;

  return (
    <div className="px-6 py-6" data-testid="cohorts-page">
      <header className="mb-6 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-ink-primary leading-tight flex items-center gap-2">
            <BarChart3 size={22} className="text-accent-brand" />
            Cohort insights
          </h1>
          <p className="text-sm text-ink-muted mt-1" data-testid="cohorts-summary">
            {data ? (
              <>
                Cross-case analytics across <span className="text-mono-tech text-ink-body">{data.total_cases}</span> cases
                in the last {data.window_days} days ·{" "}
                <span className="text-mono-tech text-ink-body">{data.decided_cases}</span> decided ·{" "}
                <span className="text-mono-tech text-ink-body">{data.pending_cases}</span> pending
              </>
            ) : (
              "Cross-case analytics for your organisation"
            )}
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <div role="group" aria-label="Time window" className="inline-flex rounded-md border border-surface-border overflow-hidden">
            {WINDOWS.map((w) => (
              <button
                key={w.days}
                type="button"
                aria-pressed={days === w.days}
                onClick={() => setDays(w.days)}
                className={`px-2.5 py-1 ${days === w.days ? "bg-accent-brand/15 text-ink-primary" : "text-ink-muted hover:text-ink-primary"}`}
              >
                {w.label}
              </button>
            ))}
          </div>
          <button
            type="button"
            onClick={reload}
            aria-label="Refresh cohort data"
            className="inline-flex items-center gap-1 px-2 py-1 rounded-md border border-surface-border text-ink-muted hover:text-ink-primary"
          >
            {loading ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />}
            {updatedAt ? updatedAt.toLocaleTimeString() : "Refresh"}
          </button>
        </div>
      </header>

      {error && (
        <div role="alert" data-testid="cohorts-error" className="mb-4 rounded-lg border border-accent-red/40 bg-accent-red/10 px-3 py-2 text-sm text-ink-body">
          Could not load cohort analytics: {error}{" "}
          <button type="button" onClick={reload} className="underline">Retry</button>
        </div>
      )}

      {!data && loading && <p className="text-sm text-ink-muted" role="status">Loading cohort analytics…</p>}

      {empty && (
        <div data-testid="cohorts-empty" className="rounded-2xl border border-surface-border bg-surface-raised p-8 text-center">
          <p className="text-sm text-ink-body">No cases in the last {data!.window_days} days.</p>
          <p className="text-xs text-ink-muted mt-1">
            Cohort insights are computed from your organisation's real cases and decisions —{" "}
            <Link to="/intake" className="text-accent-brand hover:underline">run a case</Link> and they will appear here.
          </p>
        </div>
      )}

      {data && !empty && (
        <>
          <section className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6" aria-label="Insights">
            {data.insights.length === 0 && (
              <p className="text-xs text-ink-muted md:col-span-2" data-testid="cohorts-no-insights">
                Not enough decided cases yet for comparative insights (each comparison needs at least {data.min_group_size} decided
                cases per group). Charts below show what is available.
              </p>
            )}
            {data.insights.map((it) => (
              <div key={it.id} data-testid={`insight-${it.id}`} className={`border-2 rounded-2xl p-5 ${ACCENT_BG[it.accent]} relative overflow-hidden`}>
                <Lightbulb size={16} className={`${ACCENT_ICON[it.accent]} mb-2`} />
                <div className="text-2xl font-bold text-ink-primary nums-tabular leading-none">{it.metric}</div>
                <div className="text-[11px] text-compact text-ink-muted mt-1">{it.metric_label}</div>
                <h3 className="text-sm font-semibold text-ink-primary mt-3 leading-snug">{it.title}</h3>
                <p className="text-xs text-ink-muted mt-2 leading-relaxed">{it.detail}</p>
                <Link to={it.link.to} className={`mt-3 text-xs font-medium ${ACCENT_ICON[it.accent]} hover:underline inline-flex items-center gap-1`}>
                  {it.link.label} <ArrowRight size={11} />
                </Link>
              </div>
            ))}
          </section>

          <section className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <ChartCard title="Approval rate by payer" subtitle={`last ${data.window_days}d · decided cases`}>
              {data.approval_by_payer.length ? (
                <BarsHorizontal
                  data={data.approval_by_payer.map((p) => ({ label: p.payer, value: p.rate ?? 0, suffix: "%", note: `n=${p.decided}` }))}
                  max={100}
                />
              ) : (
                <NoData />
              )}
            </ChartCard>

            <ChartCard
              title="Time-to-decision distribution"
              subtitle={data.time_to_decision.timed_cases ? `${data.time_to_decision.timed_cases} timed cases` : "no timed cases"}
            >
              {data.time_to_decision.timed_cases ? (
                <BarsVertical data={data.time_to_decision.buckets.map((b) => ({ label: b.bucket, value: b.count }))} />
              ) : (
                <NoData />
              )}
            </ChartCard>

            <ChartCard title="Verdict mix by treatment" subtitle={`last ${data.window_days}d`}>
              {data.verdict_by_treatment.length ? <StackedBars data={data.verdict_by_treatment} /> : <NoData />}
            </ChartCard>
          </section>
        </>
      )}
    </div>
  );
}

function NoData() {
  return <p className="text-xs text-ink-muted py-6 text-center">No decided cases in this window.</p>;
}

// =============================================================================
// Chart helpers (pure SVG / divs — no chart lib)
// =============================================================================

function ChartCard({ title, subtitle, children }: { title: string; subtitle: string; children: React.ReactNode }) {
  return (
    <div className="bg-surface-raised border border-surface-border rounded-2xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-ink-primary">{title}</h3>
        <span className="text-[10px] text-mono-tech text-ink-faint">{subtitle}</span>
      </div>
      {children}
    </div>
  );
}

function BarsHorizontal({ data, max }: { data: { label: string; value: number; suffix?: string; note?: string }[]; max: number }) {
  return (
    <div className="space-y-2.5">
      {data.map((d) => (
        <div key={d.label} className="flex items-center gap-3 text-xs">
          <span className="text-ink-muted w-16 shrink-0">{d.label}</span>
          <div className="flex-1 h-5 bg-surface-panel rounded overflow-hidden">
            <div
              className="h-full bg-accent-brand rounded transition-all"
              style={{ width: `${(d.value / max) * 100}%` }}
            />
          </div>
          <span className="text-ink-body text-mono-tech w-10 text-right nums-tabular">
            {d.value}{d.suffix ?? ""}
          </span>
          {d.note && <span className="text-[10px] text-ink-faint text-mono-tech w-10">{d.note}</span>}
        </div>
      ))}
    </div>
  );
}

function BarsVertical({ data }: { data: { label: string; value: number }[] }) {
  const max = Math.max(1, ...data.map((d) => d.value));
  return (
    <div className="mt-2">
      <div className="flex items-end gap-2 h-32">
        {data.map((d) => (
          <div
            key={d.label}
            className="flex-1 flex flex-col justify-end h-full"
            title={`${d.label}: ${d.value} cases`}
          >
            <div
              className="w-full bg-accent-cyan/80 rounded-t hover:bg-accent-cyan transition-colors"
              style={{ height: `${(d.value / max) * 100}%`, minHeight: 4 }}
            />
            <div className="text-center text-[9px] text-mono-tech text-ink-body mt-1 nums-tabular">
              {d.value}
            </div>
          </div>
        ))}
      </div>
      <div className="flex gap-2 mt-1">
        {data.map((d) => (
          <span key={d.label} className="flex-1 text-center text-[9px] text-mono-tech text-ink-faint">
            {d.label}
          </span>
        ))}
      </div>
    </div>
  );
}

function StackedBars({ data }: { data: { treatment: string; approve: number; deny: number; refer: number }[] }) {
  const max = Math.max(1, ...data.map((d) => d.approve + d.deny + d.refer));
  return (
    <div className="space-y-2 mt-1">
      {data.map((d) => {
        const total = d.approve + d.deny + d.refer;
        return (
          <div key={d.treatment} className="text-xs">
            <div className="flex items-center justify-between mb-1">
              <span className="text-ink-body truncate">{d.treatment}</span>
              <span className="text-ink-muted text-mono-tech nums-tabular">{total}</span>
            </div>
            <div className="flex h-4 rounded overflow-hidden bg-surface-panel" style={{ width: `${(total / max) * 100}%` }}>
              <div className="bg-accent-green" style={{ width: `${(d.approve / total) * 100}%` }} title={`${d.approve} approved`} />
              <div className="bg-accent-amber" style={{ width: `${(d.refer / total) * 100}%` }} title={`${d.refer} referred`} />
              <div className="bg-accent-red" style={{ width: `${(d.deny / total) * 100}%` }} title={`${d.deny} denied`} />
            </div>
          </div>
        );
      })}
      <div className="flex items-center gap-3 text-[10px] text-mono-tech text-ink-muted pt-2">
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-accent-green" />approved</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-accent-amber" />referred</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-accent-red" />denied</span>
      </div>
    </div>
  );
}
