/**
 * Agent health panel — Datadog-APM-style row per agent. Shows 24h success rate,
 * p95 latency, and a green/red health dot. Currently running agents pulse softly.
 */
import clsx from "clsx";

interface AgentHealth {
  name: string;
  display: string;
  successRate: number;  // percent 0-100
  p95Ms: number;
  state: "healthy" | "running" | "error";
}

const AGENTS: AgentHealth[] = [
  { name: "clinical_extractor",  display: "Clinical Extractor",  successRate: 100.0, p95Ms: 14_100, state: "healthy" },
  { name: "policy_retriever",    display: "Policy Retriever",    successRate: 100.0, p95Ms: 60,     state: "healthy" },
  { name: "necessity_reasoner",  display: "Necessity Reasoner",  successRate:  99.4, p95Ms: 31_200, state: "running" },
  { name: "decision_composer",   display: "Decision Composer",   successRate: 100.0, p95Ms: 13_800, state: "healthy" },
  { name: "appeals_drafter",     display: "Appeals Drafter",     successRate:  98.7, p95Ms: 52_400, state: "healthy" },
];

const STATE_DOT: Record<AgentHealth["state"], string> = {
  healthy: "bg-accent-green",
  running: "bg-accent-brand animate-pulse-soft",
  error:   "bg-accent-red",
};

function formatMs(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

export function AgentHealthPanel() {
  return (
    <div className="bg-surface-raised border border-surface-border rounded-2xl overflow-hidden">
      <div className="flex items-center justify-between px-5 py-3 border-b border-surface-border">
        <h3 className="text-sm font-semibold text-ink-primary">Agent health</h3>
        <span className="text-[10px] text-mono-tech text-ink-muted">last 24h · sonnet-4-6</span>
      </div>

      <div className="divide-y divide-surface-border">
        {AGENTS.map((a, i) => (
          <div key={a.name} className="flex items-center gap-3 px-5 py-2.5">
            <span className="text-[10px] text-mono-tech text-ink-faint w-4">{String(i + 1).padStart(2, "0")}</span>
            <span className={clsx("w-1.5 h-1.5 rounded-full shrink-0", STATE_DOT[a.state])} />
            <span className="flex-1 text-sm text-ink-primary truncate">{a.display}</span>
            <span className="text-mono-tech text-xs text-ink-muted shrink-0 w-16 text-right">
              {a.successRate.toFixed(1)}%
            </span>
            <span className="text-mono-tech text-xs text-ink-muted shrink-0 w-14 text-right">
              {formatMs(a.p95Ms)}
            </span>
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
