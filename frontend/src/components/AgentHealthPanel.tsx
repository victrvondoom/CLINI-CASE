/**
 * Agent health panel — one row per pipeline agent from REAL data: the agent list and order come from the live manifest
 * (compiled LangGraph), success rate / p95 / state from the last 24 h of this organisation's agent_runs.
 * Agents with no runs are shown as idle with dashes — never a made-up "100 % healthy".
 */
import clsx from "clsx";
import { useMemo } from "react";

import { buildAgents, type AgentState } from "../lib/agentsModel";
import { fetchManifest, fetchMetrics } from "../lib/agentsApi";
import { useLive } from "../lib/useLive";

const STATE_DOT: Record<AgentState, string> = {
  healthy: "bg-accent-green",
  running: "bg-accent-brand animate-pulse-soft",
  error: "bg-accent-red",
  idle: "bg-ink-faint",
};

export function formatMs(ms: number | null): string {
  if (ms == null) return "—";
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

export function AgentHealthPanel() {
  const manifest = useLive(fetchManifest, [], 0);
  const metrics = useLive(() => fetchMetrics(24), [], 30_000);
  const agents = useMemo(() => (manifest.data ? buildAgents(manifest.data, metrics.data) : []), [manifest.data, metrics.data]);
  const error = manifest.error ?? null;

  return (
    <div className="bg-surface-raised border border-surface-border rounded-2xl overflow-hidden" data-testid="agent-health">
      <div className="flex items-center justify-between px-5 py-3 border-b border-surface-border">
        <h3 className="text-sm font-semibold text-ink-primary">Agent health</h3>
        <span className="text-[10px] text-mono-tech text-ink-muted">
          last 24h{metrics.data ? ` · ${metrics.data.totals.invocations.toLocaleString()} runs` : ""}
        </span>
      </div>

      {error && (
        <p role="alert" className="px-5 py-3 text-xs text-accent-red">Could not load agents: {error}</p>
      )}
      {!manifest.data && manifest.loading && <p className="px-5 py-3 text-xs text-ink-muted" role="status">Loading agents…</p>}
      {metrics.error && manifest.data && (
        <p data-testid="agent-health-metrics-error" className="px-5 py-2 text-[11px] text-accent-amber">Live metrics unavailable: {metrics.error}</p>
      )}

      <div className="divide-y divide-surface-border">
        {agents.map((a) => (
          <div key={a.id} data-testid={`agent-health-${a.id}`} className="flex items-center gap-3 px-5 py-2.5">
            <span className="text-[10px] text-mono-tech text-ink-faint w-4">{String(a.index).padStart(2, "0")}</span>
            <span className={clsx("w-1.5 h-1.5 rounded-full shrink-0", STATE_DOT[a.state])} title={a.state} />
            <span className="flex-1 text-sm text-ink-primary truncate">{a.display}</span>
            <span className="text-mono-tech text-xs text-ink-muted shrink-0 w-16 text-right">
              {a.metrics?.success_pct != null ? `${a.metrics.success_pct.toFixed(1)}%` : "—"}
            </span>
            <span className="text-mono-tech text-xs text-ink-muted shrink-0 w-14 text-right">{formatMs(a.metrics?.p95_ms ?? null)}</span>
          </div>
        ))}
      </div>

      <div className="px-5 py-2 border-t border-surface-border text-[10px] text-mono-tech text-ink-faint flex justify-between">
        <span>name</span>
        <span className="flex gap-3">
          <span className="w-16 text-right">success</span>
          <span className="w-14 text-right">p95</span>
        </span>
      </div>
    </div>
  );
}
