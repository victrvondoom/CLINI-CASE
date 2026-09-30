/**
 * Per-case economics strip: cost, latency, tokens, vs. human-baseline savings.
 *
 * A re:Invent 2025 IND210 talk ("TriZetto AI Gateway on AWS
 * Bedrock") led with three numbers — claims/hour, hours saved, and dollars.
 * This strip translates ClinCase's per-case telemetry into that same payer
 * P&L language so a reviewer can read the value in two
 * seconds without scrolling.
 *
 * Pricing assumption: Bedrock Claude Sonnet 4.6 = $3 / 1M input, $15 / 1M output.
 * Human-baseline assumption: oncology PA coordinator at $32/hr fully-loaded;
 * average manual PA review = 11 minutes per case (AMA 2025 PA survey).
 */
import {
  Activity,
  Clock,
  Coins,
  Cpu,
  TrendingUp,
} from "lucide-react";
import { useEffect, useState } from "react";

import { api } from "../lib/api";
import type { CaseROI } from "../lib/api";
import type { AgentRun } from "../lib/types";

interface Props {
  caseId: string;
  refreshKey?: number;
}

type Pricing = Record<string, { in: number; out: number }>;

/** Price one run by its model family (haiku vs sonnet) using the backend's price table. */
export function runCostUsd(r: { model_id: string | null; input_tokens: number | null; output_tokens: number | null }, pricing: Pricing): number {
  const family = r.model_id && r.model_id.toLowerCase().includes("haiku") ? "haiku" : "sonnet";
  const p = pricing[family];
  if (!p) return 0;
  return ((r.input_tokens ?? 0) * p.in + (r.output_tokens ?? 0) * p.out) / 1e6;
}

export function CaseEconomicsStrip({ caseId, refreshKey = 0 }: Props) {
  const [runs, setRuns] = useState<AgentRun[] | null>(null);
  const [roi, setRoi] = useState<CaseROI | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getAudit(caseId)
      .then((d) => setRuns(d.agent_runs))
      .catch((e) => setError(String(e)));
    // the manual baseline + price table come from the backend so every page quotes the same numbers
    api.getCaseValue(caseId).then(setRoi).catch(() => setRoi(null));
  }, [caseId, refreshKey]);

  if (error || !runs || runs.length === 0) return null;
  const pricing = roi?.token_pricing_usd_per_m;

  const totalIn  = runs.reduce((s, r) => s + (r.input_tokens  ?? 0), 0);
  const totalOut = runs.reduce((s, r) => s + (r.output_tokens ?? 0), 0);
  const cost = pricing ? runs.reduce((s, r) => s + runCostUsd(r, pricing), 0) : null;
  const latencyMs = runs.reduce((s, r) => s + (r.latency_ms ?? 0), 0);
  const latencySec = latencyMs / 1000;

  // Savings vs the backend's manual-PA baseline (same numbers as the Dashboard and /roi)
  const manualCost = roi?.manual_cost_usd ?? null;
  const manualMinutes = roi?.manual_minutes ?? null;
  const dollarsSaved = manualCost != null && cost != null ? manualCost - cost : null;
  const minutesSaved = manualMinutes != null ? manualMinutes - latencySec / 60 : null;

  return (
    <div className="bg-surface-raised border border-surface-border rounded-2xl overflow-hidden">
      <div className="px-5 py-2.5 border-b border-surface-border flex items-center gap-2">
        <Activity size={14} className="text-accent-cyan" />
        <h3 className="text-sm font-semibold text-ink-primary">
          Case economics
        </h3>
        <span className="text-[10px] text-compact text-ink-muted">
          live agent_runs
        </span>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 divide-x divide-surface-border">
        <Cell
          icon={<Coins size={14} className="text-accent-cyan" />}
          label="LLM cost"
          value={cost != null ? `$${cost.toFixed(4)}` : "—"}
          sub={`${totalIn.toLocaleString()} in · ${totalOut.toLocaleString()} out`}
        />
        <Cell
          icon={<Clock size={14} className="text-accent-cyan" />}
          label="Wall-clock"
          value={
            latencySec < 60
              ? `${latencySec.toFixed(1)}s`
              : `${(latencySec / 60).toFixed(1)}m`
          }
          sub={`${runs.length} agent invocation${runs.length === 1 ? "" : "s"}`}
        />
        <Cell
          icon={<Cpu size={14} className="text-accent-cyan" />}
          label="Tokens"
          value={`${(totalIn + totalOut).toLocaleString()}`}
          sub={`${(((totalOut / Math.max(totalIn, 1)) * 100) | 0)}% out / in ratio`}
        />
        <Cell
          icon={<TrendingUp size={14} className="text-accent-green" />}
          label="vs human PA"
          value={dollarsSaved != null ? `$${dollarsSaved.toFixed(2)} saved` : "—"}
          sub={minutesSaved != null ? `${minutesSaved.toFixed(0)} min faster than the ${manualMinutes}-min manual baseline` : "baseline unavailable"}
          valueClass="text-accent-green"
        />
      </div>

      <div className="px-5 py-2 bg-surface-panel/40 border-t border-surface-border text-[10px] text-mono-tech text-ink-muted">
        unit-economics formula:{" "}
        <code>Σ per run (in_tokens × in-price + out_tokens × out-price) / 1M, by model family</code> &nbsp;·&nbsp;{" "}
        baseline: {manualCost != null ? `$${manualCost.toLocaleString()} / ${manualMinutes} min per manual PA` : "unavailable"}
      </div>
    </div>
  );
}

function Cell({
  icon,
  label,
  value,
  sub,
  valueClass = "text-ink-primary",
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  sub: string;
  valueClass?: string;
}) {
  return (
    <div className="px-4 py-3">
      <div className="flex items-center gap-1.5 text-[10px] text-compact text-ink-muted mb-1">
        {icon}
        {label}
      </div>
      <div className={`text-lg font-semibold nums-tabular ${valueClass}`}>
        {value}
      </div>
      <div className="text-[10px] text-ink-faint mt-0.5">{sub}</div>
    </div>
  );
}
