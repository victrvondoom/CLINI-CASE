/**
 * /twin/ops — OncoTwin observability & MLOps: health checks, population drift (PSI with ICC-adjusted
 * effective n, case-mix separated from signal drift), the prediction log with delayed ground truth,
 * the twin event stream, latency / agent / LLM traces, model + feature registries, the red-team
 * "Twin Stress Test", and the architecture inventory (implemented vs designed vs deliberately unused).
 */
import clsx from "clsx";
import { ArrowLeft, Gauge, Loader2, Play, RefreshCw, ShieldAlert } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { useAuth } from "../components/AuthContext";
import { ot } from "../oncotwin/api";
import { Chip, KV, Note, SevMark } from "../oncotwin/intel";
import { Section, pct } from "../oncotwin/panels";
import type { Json } from "../oncotwin/types2";

const BTN = "inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md border border-surface-border bg-surface-raised text-[12px] text-ink-body hover:border-accent-brand/60 disabled:opacity-40 focus:outline-none focus:ring-2 focus:ring-accent-brand";
const TH = "text-left px-2 py-1 font-medium text-ink-muted text-[10.5px] whitespace-nowrap";
const TD = "px-2 py-1 align-top";
const labels = (l: Record<string, string>) => Object.entries(l).map(([k, v]) => `${k}=${v}`).join(" ");
// Registry metrics nest (e.g. per-horizon {auroc, ci95, positives}); render them as readable text, not JSON.
const metricText = (v: unknown): string => {
  if (v == null) return "—";
  if (Array.isArray(v)) return v.map(metricText).join("–");
  if (typeof v === "object") return Object.entries(v as Record<string, unknown>).map(([k, x]) => `${k.replace(/_/g, " ")} ${metricText(x)}`).join(", ");
  return String(v);
};

export default function TwinOps() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [obs, setObs] = useState<Json | null>(null);
  const [health, setHealth] = useState<Json | null>(null);
  const [preds, setPreds] = useState<Json | null>(null);
  const [events, setEvents] = useState<Json | null>(null);
  const [reg, setReg] = useState<Json | null>(null);
  const [feat, setFeat] = useState<Json | null>(null);
  const [arch, setArch] = useState<Json[] | null>(null);
  const [stress, setStress] = useState<Json | null>(null);
  const [drift, setDrift] = useState<Json | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(async () => {
    setErr(null);
    try {
      const [o, h, p, e, r, f, a, s] = await Promise.all([ot.observability(), ot.health(), ot.predictions(), ot.events({ limit: 40 }),
        ot.modelRegistry(), ot.featureRegistry(), ot.architecture(), ot.stressLatest()]);
      setObs(o); setHealth(h); setPreds(p); setEvents(e); setReg(r); setFeat(f); setArch(a.components); setStress(s); setDrift(o.drift);
    } catch (e) { setErr((e as Error).message); }
  }, []);
  useEffect(() => { void load(); }, [load]);

  const refreshDrift = async () => {
    setBusy("drift");
    try { setDrift(await ot.drift(true)); } catch (e) { setErr((e as Error).message); } finally { setBusy(null); }
  };
  const runStress = async () => {
    setBusy("stress");
    try { setStress(await ot.stressTest()); } catch (e) { setErr((e as Error).message); } finally { setBusy(null); }
  };

  return (
    <div className="px-4 sm:px-6 py-6 space-y-4">
      <header className="flex items-start justify-between gap-3 flex-wrap">
        <div className="max-w-3xl">
          <Link to="/twin" className="text-[11px] text-ink-muted hover:text-ink-primary inline-flex items-center gap-1"><ArrowLeft size={12} aria-hidden /> Command Center</Link>
          <h1 className="text-2xl font-semibold text-ink-primary flex items-center gap-2"><Gauge size={22} aria-hidden /> OncoTwin Observability & MLOps</h1>
          <p className="text-[12.5px] text-ink-body mt-1">Is the twin healthy, is the population still the one it was trained on, and would we know if it failed?</p>
        </div>
        <button type="button" onClick={load} className={BTN}><RefreshCw size={13} aria-hidden /> Refresh</button>
      </header>
      {err && <div className="text-[12px] text-accent-red" role="alert">{err}</div>}
      {!obs && !err && <div className="text-[12px] text-ink-muted flex items-center gap-2"><Loader2 size={14} className="animate-spin" aria-hidden /> Loading…</div>}

      {obs && health && (
        <>
          <div className="grid gap-2 md:grid-cols-5 text-[12px]">
            {Object.entries(health.checks as Record<string, Json>).map(([k, c]) => (
              <div key={k} className="rounded-lg border border-surface-border px-3 py-2 bg-surface-raised flex items-start gap-2">
                <span className="mt-0.5"><SevMark s={c.ok ? "normal" : "alert"} /></span>
                <div><div className="font-medium">{k.replace(/_/g, " ")}</div><div className="text-[10.5px] text-ink-muted">{c.ok ? "ok" : "FAILING"}{c.sha256 ? ` · ${c.sha256}` : ""}</div></div>
              </div>))}
            <div className="rounded-lg border border-surface-border px-3 py-2 bg-surface-raised flex items-start gap-2">
              <span className="mt-0.5"><SevMark s={obs.ledger.valid ? "normal" : "alert"} /></span>
              <div><div className="font-medium">audit ledger</div><div className="text-[10.5px] text-ink-muted">{obs.ledger.valid ? "chain valid" : "INVALID"} · {obs.ledger.entries} entries</div></div>
            </div>
          </div>
          <Note>OncoTwin {obs.oncotwin_version} · uptime {Math.round(obs.metrics.uptime_seconds)} s · {obs.logging} · Prometheus text format at GET /api/v1/oncotwin/metrics (authenticated).</Note>

          {drift && (
            <Section eyebrow="Drift monitor" title={`Population drift: ${drift.status ?? "unavailable"}`}
              right={<button type="button" className={BTN} onClick={refreshDrift} disabled={busy !== null}>
                {busy === "drift" ? <Loader2 size={13} className="animate-spin" aria-hidden /> : <RefreshCw size={13} aria-hidden />} Recompute</button>}>
              <div className="text-[12.5px] text-ink-body">{drift.message}</div>
              {drift.features && (
                <>
                  <div className="grid gap-2 md:grid-cols-4 text-[12px] mt-2">
                    <KV label="Live window" v={`${drift.n_patient_days} patient-days · ${drift.n_patients} patients · last ${drift.window_days} days`} />
                    <KV label="Reference" v={`${drift.reference.n_rows} training rows · dataset ${drift.reference.dataset_version}`} />
                    <KV label="Prediction drift" v={`PSI ${drift.prediction.psi} (threshold ${drift.prediction.threshold}, n_eff ${drift.prediction.n_eff})${drift.prediction.drifted ? " · DRIFTED" : ""}`} />
                    <KV label="Effective n" v={drift.n_eff_method} />
                  </div>
                  <div className="grid gap-3 xl:grid-cols-[1.5fr_1fr] mt-3">
                    <div className="max-h-72 overflow-auto border border-surface-border rounded-md">
                      <table className="w-full text-[11px]"><thead className="sticky top-0 bg-surface-panel"><tr><th className={TH}>Feature</th><th className={TH}>Category</th><th className={TH}>PSI</th><th className={TH}>Threshold</th><th className={TH}>n_eff</th><th className={TH}>Live / ref mean</th></tr></thead>
                        <tbody>{[...drift.features].sort((a: Json, b: Json) => b.psi / b.threshold - a.psi / a.threshold).map((f: Json) => (
                          <tr key={f.feature} className={clsx("border-t border-surface-border/60", f.drifted && "font-semibold text-ink-primary")}>
                            <td className={clsx(TD, "text-mono-tech")}>{f.feature}{f.drifted ? " ◆" : ""}</td><td className={TD}>{f.category}</td>
                            <td className={clsx(TD, "nums-tabular")}>{f.psi}</td><td className={clsx(TD, "nums-tabular")}>{f.threshold}</td>
                            <td className={clsx(TD, "nums-tabular")}>{f.n_eff}</td><td className={clsx(TD, "nums-tabular")}>{f.live_mean} / {f.reference_mean}</td></tr>))}</tbody></table>
                    </div>
                    <div className="max-h-72 overflow-auto border border-surface-border rounded-md">
                      <table className="w-full text-[11px]"><thead className="sticky top-0 bg-surface-panel"><tr><th className={TH}>Signal missingness</th><th className={TH}>Live</th><th className={TH}>Reference</th><th className={TH}>z</th></tr></thead>
                        <tbody>{(drift.missingness ?? []).map((m: Json) => (
                          <tr key={m.signal} className={clsx("border-t border-surface-border/60", m.drifted && "font-semibold text-ink-primary")}>
                            <td className={TD}>{m.signal}{m.drifted ? " ◆" : ""}</td><td className={clsx(TD, "nums-tabular")}>{pct(m.live_rate, 1)}</td>
                            <td className={clsx(TD, "nums-tabular")}>{pct(m.reference_rate, 1)}</td><td className={clsx(TD, "nums-tabular")}>{m.z}</td></tr>))}</tbody></table>
                    </div>
                  </div>
                  <Note>◆ = drifted. Case-mix / treatment-phase features are reported separately from signal drift, because live patients who share a cycle phase legitimately differ from the training population.</Note>
                </>)}
            </Section>)}

          {preds && (
            <Section eyebrow="Prediction log" title="Every prediction, versioned, with ground truth resolved when the horizon passes">
              <div className="grid gap-2 md:grid-cols-4 text-[12px] mb-2">
                <KV label="Predictions" v={preds.metrics.n_predictions} />
                <KV label="Resolved / pending" v={`${preds.metrics.n_resolved} / ${preds.metrics.n_pending}`} />
                <KV label="Positive outcomes" v={preds.metrics.n_positive} />
                <KV label="Live AUROC" v={preds.metrics.auroc != null ? preds.metrics.auroc : "not yet computable (needs ≥ 3 resolved events and non-events)"} />
              </div>
              <div className="max-h-72 overflow-auto border border-surface-border rounded-md">
                <table className="w-full text-[11px]"><thead className="sticky top-0 bg-surface-panel"><tr><th className={TH}>Patient</th><th className={TH}>Day</th><th className={TH}>Risk</th><th className={TH}>Tier</th>
                  <th className={TH}>Model</th><th className={TH}>Feature ver.</th><th className={TH}>Dataset ver.</th><th className={TH}>Ground truth</th></tr></thead>
                  <tbody>{[...preds.predictions].reverse().map((p: Json) => (
                    <tr key={p.prediction_id} className="border-t border-surface-border/60">
                      <td className={TD}>{p.patient_id}</td><td className={TD}>D{p.as_of_day}</td><td className={clsx(TD, "nums-tabular")}>{pct(p.risk, 1)}</td><td className={TD}>{p.tier}</td>
                      <td className={clsx(TD, "text-mono-tech")}>{p.model_version} · {String(p.artifact_sha256).slice(0, 8)}</td>
                      <td className={clsx(TD, "text-mono-tech")}>{String(p.feature_version).slice(0, 8)}</td><td className={clsx(TD, "text-mono-tech")}>{String(p.dataset_version).slice(0, 8)}</td>
                      <td className={TD}>{p.label_status}{p.label != null ? ` · ${p.label ? "event" : "no event"}` : ""}{p.label_evidence?.day ? ` (D${p.label_evidence.day})` : ""}</td></tr>))}</tbody></table>
                {preds.predictions.length === 0 && <div className="text-[12px] text-ink-muted p-2">No predictions yet: advance a twin clock.</div>}
              </div>
              <Note>{preds.metrics.note}</Note>
            </Section>)}

          <div className="grid gap-4 xl:grid-cols-2">
            {events && (
              <Section eyebrow="Event-driven infrastructure" title="Twin event stream (CloudEvents, bridged to the ClinCase outbox)">
                <div className="flex flex-wrap gap-1.5 mb-2">{Object.entries(events.stats.by_type as Record<string, number>).map(([k, v]) => <Chip key={k}>{k} × {v}</Chip>)}</div>
                <div className="text-[11px] text-ink-muted mb-1">{events.stats.events_in_log} events · bridged {events.stats.bridged_to_outbox} · not bridged {events.stats.not_bridged} · pending {events.stats.pending_bridge} · subscribers: {events.stats.subscribers.join(", ")}</div>
                <div className="max-h-64 overflow-auto border border-surface-border rounded-md">
                  <table className="w-full text-[11px]"><thead className="sticky top-0 bg-surface-panel"><tr><th className={TH}>#</th><th className={TH}>Type</th><th className={TH}>Patient · day</th><th className={TH}>Handled by</th></tr></thead>
                    <tbody>{events.events.map((e: Json) => (
                      <tr key={e.id} className="border-t border-surface-border/60"><td className={clsx(TD, "nums-tabular")}>{e.seq}</td>
                        <td className={TD}><div>{e.type}</div><div className="text-[10px] text-mono-tech text-ink-muted">{e.cloudevent_type}</div></td>
                        <td className={TD}>{e.patient_id ?? "—"} · D{e.twin_day ?? "—"}</td><td className={TD}>{(e.handled_by ?? []).join(", ") || "—"}</td></tr>))}</tbody></table>
                  {events.events.length === 0 && <div className="text-[12px] text-ink-muted p-2">No events yet: advance a twin clock or ingest data.</div>}
                </div>
              </Section>)}
            <Section eyebrow="Latency" title="Per-stage and per-agent latency (rolling window)">
              <div className="max-h-80 overflow-auto border border-surface-border rounded-md">
                <table className="w-full text-[11px]"><thead className="sticky top-0 bg-surface-panel"><tr><th className={TH}>Metric</th><th className={TH}>n</th><th className={TH}>p50</th><th className={TH}>p95</th><th className={TH}>p99</th></tr></thead>
                  <tbody>{obs.metrics.latencies.map((l: Json, i: number) => (
                    <tr key={i} className="border-t border-surface-border/60"><td className={TD}><span className="text-mono-tech">{l.name}</span> <span className="text-ink-muted">{labels(l.labels)}</span></td>
                      <td className={clsx(TD, "nums-tabular")}>{l.count}</td><td className={clsx(TD, "nums-tabular")}>{l.p50_ms} ms</td><td className={clsx(TD, "nums-tabular")}>{l.p95_ms} ms</td><td className={clsx(TD, "nums-tabular")}>{l.p99_ms} ms</td></tr>))}</tbody></table>
              </div>
              <details className="mt-2 text-[11px]"><summary className="cursor-pointer text-ink-muted">Counters ({obs.metrics.counters.length})</summary>
                <ul className="mt-1 space-y-0.5">{obs.metrics.counters.map((c: Json, i: number) => <li key={i}><span className="text-mono-tech">{c.name}</span> {labels(c.labels)}: <b>{c.value}</b></li>)}</ul></details>
            </Section>
          </div>

          <div className="grid gap-4 xl:grid-cols-2">
            <Section eyebrow="Agent orchestration" title="Latest twin-graph runs">
              {obs.agent_runs.length === 0 ? <div className="text-[12px] text-ink-muted">No run yet: advance a twin clock.</div> : (
                <ul className="space-y-2 text-[11.5px]">{[...obs.agent_runs].reverse().slice(0, 5).map((r: Json) => (
                  <li key={r.run_id} className="border-l-2 border-surface-border-hi pl-2">
                    <div><b>{r.patient_id}</b> · Day {r.as_of_day} · {r.topology} <span className="text-ink-muted">· {r.trigger}</span></div>
                    <div className="flex flex-wrap gap-1 mt-0.5">{r.agent_trace.map((a: Json) => (
                      <Chip key={a.agent} strong={a.status !== "ok"}>{a.agent.replace(/_agent$/, "").replace(/_/g, " ")} {a.status === "ok" ? `${a.latency_ms} ms` : a.status}</Chip>))}</div>
                  </li>))}</ul>)}
            </Section>
            <Section eyebrow="LLM observability" title="Explanation-agent LLM calls">
              {obs.llm_traces.length === 0 ? <div className="text-[12px] text-ink-muted">No LLM call recorded. Explanations are deterministic unless ONCOTWIN_LLM_EXPLANATIONS=1 and an LLM provider is configured; LLM output must still pass every safety gate.</div> : (
                <table className="w-full text-[11px]"><thead><tr><th className={TH}>At</th><th className={TH}>Model</th><th className={TH}>Prompt</th><th className={TH}>Latency</th><th className={TH}>Tokens</th><th className={TH}>Gates</th></tr></thead>
                  <tbody>{obs.llm_traces.map((t: Json, i: number) => (
                    <tr key={i} className="border-t border-surface-border/60"><td className={TD}>{String(t.at).slice(11, 19)}</td><td className={TD}>{t.model ?? "—"}</td><td className={TD}>{t.prompt_version}</td>
                      <td className={clsx(TD, "nums-tabular")}>{t.latency_ms} ms</td><td className={clsx(TD, "nums-tabular")}>{t.input_tokens ?? "—"}/{t.output_tokens ?? "—"}</td>
                      <td className={TD}>{t.validation?.passed ? "passed" : `failed: ${(t.validation?.failed_gates ?? []).join(", ")}`}{t.error ? ` · ${t.error}` : ""}</td></tr>))}</tbody></table>)}
              <Note>Traces store hashes and metadata only (the patient reference is hashed and the output stored as SHA-256); no prompt text or patient data is logged.</Note>
            </Section>
          </div>

          <Section eyebrow="Red team" title="Twin Stress Test: does the twin fail safe?"
            right={isAdmin ? <button type="button" className={BTN} onClick={runStress} disabled={busy !== null}>
              {busy === "stress" ? <Loader2 size={13} className="animate-spin" aria-hidden /> : <Play size={13} aria-hidden />} Run stress test</button> : undefined}>
            {!stress || !stress.results ? (
              <div className="text-[12px] text-ink-muted">Not run in this session.{isAdmin ? " Running it perturbs synthetic copies of the patients; the live demo state is never modified." : " An admin can run it."}</div>
            ) : (
              <>
                <div className="flex items-center gap-2 text-[13px] font-semibold text-ink-primary"><ShieldAlert size={15} aria-hidden /> {stress.passed}/{stress.total} scenarios failed safe
                  <span className="text-[11px] font-normal text-ink-muted">· {stress.duration_seconds} s{stress.at ? ` · ${String(stress.at).slice(0, 19).replace("T", " ")}` : ""}</span></div>
                <div className="overflow-x-auto mt-2"><table className="w-full text-[11px] min-w-[720px]"><thead><tr><th className={TH}>Scenario</th><th className={TH}>Perturbation</th><th className={TH}>Expected safe behaviour</th><th className={TH}>Observed</th><th className={TH}>Result</th></tr></thead>
                  <tbody>{stress.results.map((s: Json) => (
                    <tr key={s.id} className="border-t border-surface-border/60"><td className={clsx(TD, "font-medium")}>{s.title}</td><td className={TD}>{s.perturbation ?? "—"}</td>
                      <td className={TD}>{s.expectation ?? "—"}</td><td className={clsx(TD, "text-ink-muted")}>{typeof s.observed === "string" ? s.observed : JSON.stringify(s.observed ?? s.error)}</td>
                      <td className={TD}><Chip strong={!s.passed}>{s.passed ? "pass" : "FAIL"}</Chip></td></tr>))}</tbody></table></div>
                <Note>{stress.note}</Note>
              </>)}
          </Section>

          {reg && (
            <Section eyebrow="Model registry" title="Every model has a purpose and a metric">
              <div className="overflow-x-auto"><table className="w-full text-[11px] min-w-[760px]"><thead><tr><th className={TH}>Model</th><th className={TH}>Status</th><th className={TH}>Purpose</th><th className={TH}>Metrics</th><th className={TH}>Metric definition</th></tr></thead>
                <tbody>{reg.models.map((m: Json) => (
                  <tr key={m.id} className="border-t border-surface-border/60"><td className={TD}><div className="font-medium text-mono-tech">{m.id}</div><div className="text-ink-muted">v{m.version} · {m.task}</div></td>
                    <td className={TD}>{m.status}</td><td className={TD}>{m.purpose}</td>
                    <td className={clsx(TD, "text-[10.5px]")}>{m.metrics ? Object.entries(m.metrics as Record<string, unknown>).map(([k, v]) => (
                      <div key={k}><span className="text-ink-muted">{k.replace(/_/g, " ")}</span> {metricText(v)}</div>)) : "—"}</td>
                    <td className={clsx(TD, "text-ink-muted")}>{m.metric_definition}</td></tr>))}</tbody></table></div>
              <div className="mt-2 text-[11.5px]"><div className="text-[11px] text-ink-muted">Deliberately not added</div>
                <ul className="list-disc ml-4">{reg.not_added_by_design.map((n: Json) => <li key={n.family}><b>{n.family}</b>: {n.reason}</li>)}</ul></div>
              <Note>Adapter contract: {reg.adapter_contract.join(", ")}. Promotion policy: {reg.promotion_policy}</Note>
            </Section>)}

          {feat && (
            <Section eyebrow="Feature store" title={`${feat.n_features} registered features (${feat.n_model_features} model inputs)`}>
              <div className="text-[11px] text-ink-muted mb-1">Registry {feat.registry_version} · feature code {feat.feature_code_version} · entity: {feat.entity}</div>
              <div className="max-h-72 overflow-auto border border-surface-border rounded-md">
                <table className="w-full text-[11px]"><thead className="sticky top-0 bg-surface-panel"><tr><th className={TH}>Feature</th><th className={TH}>Group</th><th className={TH}>Kind</th><th className={TH}>Window</th><th className={TH}>Sources</th><th className={TH}>Description</th></tr></thead>
                  <tbody>{feat.features.map((f: Json) => (
                    <tr key={f.name} className="border-t border-surface-border/60"><td className={clsx(TD, "text-mono-tech")}>{f.name}</td><td className={TD}>{f.group}</td>
                      <td className={TD}>{f.in_model ? "model input" : "analytic"}</td><td className={TD}>{f.window_days} d</td><td className={clsx(TD, "text-ink-muted")}>{(f.sources ?? []).join(", ")}</td>
                      <td className={clsx(TD, "text-ink-muted")}>{f.description}</td></tr>))}</tbody></table>
              </div>
            </Section>)}

          {arch && (
            <Section eyebrow="Architecture" title="What is implemented, what is designed, and what is deliberately not used">
              <div className="overflow-x-auto"><table className="w-full text-[11px] min-w-[760px]"><thead><tr><th className={TH}>Component</th><th className={TH}>Status</th><th className={TH}>Why</th><th className={TH}>Data</th><th className={TH}>If it fails</th></tr></thead>
                <tbody>{arch.map((c) => (
                  <tr key={c.component} className="border-t border-surface-border/60"><td className={clsx(TD, "font-medium")}>{c.component}</td>
                    <td className={TD}><Chip strong={c.status === "implemented"}>{c.status}</Chip></td><td className={TD}>{c.why}</td>
                    <td className={clsx(TD, "text-ink-muted")}>{c.data}</td><td className={clsx(TD, "text-ink-muted")}>{c.if_it_fails}</td></tr>))}</tbody></table></div>
            </Section>)}
        </>
      )}
    </div>
  );
}
