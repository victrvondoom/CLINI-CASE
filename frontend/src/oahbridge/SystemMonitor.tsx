/**
 * Live system monitor for the OAH-Bridge backend: component health (engine self-test, validator,
 * conformance pack, CDS Hooks, Open-Meteo upstream), run counters and recent runs.
 * Polls every 10 s while the tab is visible and keeps the last good snapshot on a failed poll.
 */
import { Activity } from "lucide-react";

import { useLive } from "../lib/useLive";
import { oahBridge } from "./api";
import { COMPONENT_STATUS_HEX, COMPONENT_STATUS_LABEL, formatInstant, formatMs, formatUptime } from "./format";

export default function SystemMonitor({ refreshKey = 0 }: { refreshKey?: number }) {
  const live = useLive(() => oahBridge.monitor(), [refreshKey], 10_000);
  const m = live.data;

  return (
    <div className="space-y-3" data-testid="system-monitor">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2 text-sm text-ink-primary">
          <span className="relative flex h-2.5 w-2.5">
            {m?.status === "operational" && (
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-60" />
            )}
            <span
              className="relative inline-flex h-2.5 w-2.5 rounded-full"
              style={{ background: m ? (m.status === "operational" ? "#22c55e" : "#f59e0b") : "#94a3b8" }}
            />
          </span>
          <Activity size={14} aria-hidden="true" /> System monitor
          {m && <span className="text-[11px] text-ink-muted">· {m.status === "operational" ? "Operational" : "Degraded"}</span>}
        </div>
        <span className="text-[10px] text-ink-faint">
          {live.updatedAt ? `updated ${live.updatedAt.toLocaleTimeString("en-GB")}` : live.loading ? "connecting…" : ""}
          {" "}· polls every 10 s
        </span>
      </div>

      {live.error && !m && <p role="alert" className="text-xs text-red-300">Monitor unavailable: {live.error}</p>}
      {live.error && m && <p className="text-[11px] text-amber-300">Last poll failed ({live.error}); showing the last good snapshot.</p>}

      {m && (
        <>
          <ul className="space-y-1.5">
            {m.components.map((c) => (
              <li key={c.id} className="flex items-start justify-between gap-3 text-[11px]">
                <span className="flex items-center gap-2 text-ink-body">
                  <span className="inline-block h-2 w-2 shrink-0 rounded-full" style={{ background: COMPONENT_STATUS_HEX[c.status] }} />
                  {c.label}
                </span>
                <span className="text-right text-ink-muted">
                  <span className="text-ink-body">{COMPONENT_STATUS_LABEL[c.status]}</span> · {c.detail}
                </span>
              </li>
            ))}
          </ul>

          <div className="grid grid-cols-2 gap-2 text-[11px] sm:grid-cols-4">
            <Stat label="Pipeline runs" value={String(m.counters.pipeline_runs)} hint={`${m.counters.pipeline_runs_passed} passed · ${m.counters.pipeline_runs_failed} failed`} />
            <Stat label="CDS evaluations" value={String(m.counters.cds_evaluations)} hint={`${m.counters.cds_cards_issued} cards issued`} />
            <Stat label="Weather upstream" value={String(m.weather.upstream_calls)} hint={`${m.weather.cache_hits} cache hits · ${m.weather.upstream_failures} failures`} />
            <Stat label="Uptime" value={formatUptime(m.uptime_seconds)} hint={`since ${formatInstant(m.started_at)}`} />
          </div>

          <div className="text-[11px]">
            <div className="text-ink-faint">
              Engine self-test · {m.self_test.passed ? "passed" : "FAILED"} in {formatMs(m.self_test.duration_ms)}
            </div>
            <div className="mt-1 flex flex-wrap gap-1.5">
              {m.self_test.results.map((r) => (
                <span key={r.scenario} className="rounded border border-surface-border px-1.5 py-0.5 text-ink-body">
                  <span style={{ color: r.passed ? "#22c55e" : "#ef4444" }}>{r.passed ? "✓" : "✗"}</span> {r.scenario} · {r.checks}
                </span>
              ))}
            </div>
          </div>

          {m.recent_runs.length > 0 && (
            <div className="text-[11px]">
              <div className="text-ink-faint">Recent runs</div>
              <ul className="mt-1 space-y-0.5">
                {m.recent_runs.slice(0, 5).map((r) => (
                  <li key={r.id} className="flex justify-between gap-2 text-ink-muted">
                    <span className="truncate">
                      <span style={{ color: r.passed ? "#22c55e" : "#ef4444" }}>●</span> {r.scenario}
                    </span>
                    <span className="shrink-0 text-ink-body">
                      {formatMs(r.total_ms)} · {r.checks} · {new Date(r.ran_at).toLocaleTimeString("en-GB")}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          <p className="text-[10px] text-ink-faint">{m.scope_note}</p>
        </>
      )}
    </div>
  );
}

function Stat({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <div className="rounded-lg border border-surface-border bg-surface-bg p-2">
      <div className="text-ink-faint">{label}</div>
      <div className="text-sm text-ink-primary">{value}</div>
      <div className="truncate text-ink-muted" title={hint}>{hint}</div>
    </div>
  );
}
