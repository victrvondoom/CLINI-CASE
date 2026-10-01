/** Case Digital Twin: one identifier, one timeline and one evidence lineage for the whole case. */
import clsx from "clsx";
import { AlertTriangle, CheckCircle2, Loader2 } from "lucide-react";

import { api } from "../lib/api";
import { useLive } from "../lib/useLive";
import type { TwinStage } from "../lib/types";

const fmtMs = (ms: number | null) => (ms == null ? "—" : ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(1)} s`);
const DOT: Record<TwinStage["status"], string> = {
  ok: "bg-accent-green",
  error: "bg-accent-red",
  running: "bg-accent-amber",
  waiting: "bg-accent-amber animate-pulse",
};

export function CaseTwinPanel({ caseId }: { caseId: string }) {
  const { data: t, error, loading } = useLive(() => api.getCaseTwin(caseId), [caseId]);

  return (
    <section className="bg-surface-card border border-hairline rounded-lg p-5" data-testid="case-twin" aria-label="Case digital twin">
      <header className="flex items-center justify-between gap-3 mb-3">
        <h3 className="text-sm font-semibold text-ink-strong">Case digital twin</h3>
        {t && <code className="text-mono-tech text-[11px] text-ink-muted" data-testid="ciid">{t.case_intelligence_id}</code>}
      </header>
      {loading && !t && (
        <p className="text-sm text-ink-muted flex items-center gap-2" role="status"><Loader2 className="w-4 h-4 animate-spin" />Loading case twin…</p>
      )}
      {error && !t && <p className="text-sm text-accent-red" role="alert">Could not load the case twin: {error}</p>}
      {t && (
        <div className="space-y-4">
          {t.runs.length > 0 && (
            <div>
              <h4 className="text-[12px] uppercase tracking-wide text-ink-muted mb-1">Runs</h4>
              <ul className="space-y-1" aria-label="Case runs">
                {t.runs.map((r) => (
                  <li
                    key={r.run_id ?? "legacy"}
                    className={clsx("text-[12px]", r.run_id === t.headline_run_id ? "text-ink-strong" : "text-ink-body")}
                    data-testid="twin-run"
                  >
                    <span className="text-mono-tech">#{r.attempt_no}</span> · {r.trigger}
                    {r.status && <span> · {r.status}</span>}
                    {r.verdict && <span> · {r.verdict}</span>}
                    {r.job_attempts.length > 1 && <span className="text-accent-amber"> · {r.job_attempts.length} attempts</span>}
                    {r.run_id && <code className="text-mono-tech text-ink-muted"> · {r.run_id}</code>}
                    {r.run_id === t.headline_run_id && <span className="text-ink-muted"> · shown below</span>}
                  </li>
                ))}
              </ul>
            </div>
          )}
          <ol className="space-y-1" aria-label="Case trace">
            {t.trace.stages.map((s, i) => (
              <li key={`${s.stage}-${i}`} className="flex items-center gap-2 text-[13px]">
                <span className={clsx("w-2 h-2 rounded-full", DOT[s.status])} aria-hidden />
                <span className="text-ink-body w-48 truncate">{s.stage}</span>
                <span className="text-mono-tech text-ink-muted">{s.actor === "human" && s.status === "waiting" ? "waiting for reviewer" : fmtMs(s.duration_ms)}</span>
              </li>
            ))}
            {t.trace.stages.length === 0 && <li className="text-sm text-ink-muted">No agent has run on this case yet.</li>}
          </ol>
          <p className="text-[12px] text-ink-muted" data-testid="twin-totals">
            Agents {fmtMs(t.trace.totals.agent_ms)} · human wait {fmtMs(t.trace.totals.human_wait_ms)} ·{" "}
            {(t.trace.totals.input_tokens + t.trace.totals.output_tokens).toLocaleString()} tokens · est. ${t.trace.totals.estimated_cost_usd.toFixed(4)}
          </p>

          <div>
            <h4 className="text-[12px] uppercase tracking-wide text-ink-muted mb-1">Evidence lineage</h4>
            {t.integrity.all_clinical_citations_resolve ? (
              <p className="text-[12px] text-accent-green flex items-center gap-1"><CheckCircle2 className="w-3.5 h-3.5" />Every clinical citation resolves to a submitted FHIR resource ({t.integrity.citations_total} citations).</p>
            ) : (
              <p className="text-[12px] text-accent-red flex items-center gap-1" role="alert"><AlertTriangle className="w-3.5 h-3.5" />{t.integrity.dangling_citations.length} clinical citation(s) point to a FHIR resource that was not submitted.</p>
            )}
            <ul className="mt-2 space-y-1">
              {t.evidence.map((e) => (
                <li key={e.evidence_id} className="text-[12px] text-ink-body">
                  <code className="text-mono-tech text-ink-muted">{e.evidence_id}</code> · {e.kind} · {e.pointer}
                  {e.resolved === false && <span className="text-accent-red"> · unresolved</span>}
                  {e.fhir_resource_type && <span className="text-ink-muted"> · {e.fhir_resource_type}</span>}
                  {e.policy_version && <span className="text-ink-muted"> · v{e.policy_version}</span>}
                  {e.first_seen_agent && <span className="text-ink-muted"> · via {e.first_seen_agent}</span>}
                </li>
              ))}
              {t.evidence.length === 0 && <li className="text-[12px] text-ink-muted">No decision citations recorded yet.</li>}
            </ul>
          </div>

          {t.infrastructure_events.length > 0 && (
            <p className="text-[12px] text-ink-muted">Queue: {t.infrastructure_events.map((e) => e.event).join(" → ")}</p>
          )}
          <p className="text-[11px] text-ink-muted break-all">twin sha256 <code className="text-mono-tech">{t.twin_sha256}</code></p>
        </div>
      )}
    </section>
  );
}
