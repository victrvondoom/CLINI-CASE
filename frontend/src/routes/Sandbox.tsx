/**
 * /sandbox — PA Decision Sandbox.
 *
 * Construct a hypothetical prior-authorization scenario from scratch (no
 * real case required) and see how it would be decided — reusing the exact
 * same multi-payer arbitration engine as /cases/:id/compare (see
 * lib/sandboxSimulation.ts). Save scenarios, duplicate them, tweak one
 * field, and compare the result against a baseline — all in memory /
 * localStorage. Nothing here reads, writes, or counts toward real case data.
 *
 * Additive feature: new route, new nav entry, zero changes to existing
 * case/decision/backend code paths.
 */
import clsx from "clsx";
import {
  AlertTriangle, ArrowRight, Beaker, Copy, FlaskConical, Play,
  RotateCcw, Save, Trash2, TrendingDown, TrendingUp,
} from "lucide-react";
import { useMemo, useState } from "react";

import { api } from "../lib/api";
import type { PolicyCatalog } from "../lib/types";
import { useLive } from "../lib/useLive";
import { PAYERS as FALLBACK_PAYERS } from "../lib/syntheticCases";
import {
  defaultScenarioParams, HER2_STATUS_LABELS, meanConfidence, runScenario, tallyVerdicts,
  type Her2Status, type ScenarioParams, type ScenarioRunResult,
} from "../lib/sandboxSimulation";
import {
  clearAllScenarios, deleteScenario, loadScenarios, saveScenario, type SavedScenario,
} from "../lib/sandboxStorage";
import type { PayerId, PayerVerdict } from "../lib/compareSimulation";
import type { Verdict } from "../lib/types";

// Reference J-codes (billing-code data, not case data). Treatment / payer OPTIONS come from the live policy catalog.
const TREATMENT_JCODES: Record<string, string> = {
  "trastuzumab": "J9355",
  "osimertinib": "J9335",
  "pembrolizumab": "J9271",
  "olaparib": "J9305",
  "T-DXd (trastuzumab deruxtecan)": "J9358",
  "nivolumab": "J9299",
  "bevacizumab": "J9035",
  "enzalutamide": "J9180",
  "brentuximab vedotin": "J9042",
};
const FALLBACK_TREATMENTS = Object.keys(TREATMENT_JCODES);
const PAYER_LABELS: Record<string, string> = Object.fromEntries(FALLBACK_PAYERS.map((p) => [p.id, p.label]));

/** J-code for a treatment name, matched on drug name (case-insensitive); "—" when we have no code for it. */
function jCodeFor(treatment: string): string {
  const t = treatment.toLowerCase();
  const hit = Object.entries(TREATMENT_JCODES).find(([k]) => t.includes(k.toLowerCase().split(" ")[0]));
  return hit ? hit[1] : "—";
}

/** The catalog policy governing (payer, treatment) — same whole-keyword rule the backend uses. */
export function policyOnFile(catalog: PolicyCatalog | null, payer: string, treatment: string) {
  if (!catalog) return null;
  const t = treatment.toLowerCase();
  return catalog.policies.find((p) => p.payer_id === payer && p.treatment_keywords.some((k) => t.includes(k.toLowerCase()))) ?? null;
}
const HER2_OPTIONS: Her2Status[] = ["positive", "negative", "equivocal", "unknown"];
const STAGE_OPTIONS = ["I", "II", "IIIA", "IIIB", "IV"];

const VERDICT_TEXT: Record<Verdict, string> = { APPROVE: "text-accent-green", DENY: "text-accent-red", REFER: "text-accent-amber" };
const VERDICT_BG: Record<Verdict, string> = {
  APPROVE: "border-accent-green/40 bg-accent-green/5",
  DENY: "border-accent-red/40 bg-accent-red/5",
  REFER: "border-accent-amber/40 bg-accent-amber/5",
};

export default function Sandbox() {
  const [params, setParams] = useState<ScenarioParams>(defaultScenarioParams());
  const [run, setRun] = useState<ScenarioRunResult | null>(null);
  const [baseline, setBaseline] = useState<ScenarioRunResult | null>(null);
  const [history, setHistory] = useState<SavedScenario[]>(() => loadScenarios());
  const [saved, setSaved] = useState(false);
  const catalogLive = useLive(() => api.getPolicyCatalog(), []);
  const catalog = catalogLive.data;
  const treatmentOptions = useMemo(
    () => (catalog ? [...new Set(catalog.policies.map((p) => p.treatment_keywords[0]))].sort() : FALLBACK_TREATMENTS),
    [catalog],
  );
  const payerOptions = useMemo(
    () => (catalog ? catalog.payers.map((id) => ({ id, label: PAYER_LABELS[id] ?? id.toUpperCase() })) : FALLBACK_PAYERS),
    [catalog],
  );

  const set = <K extends keyof ScenarioParams>(key: K, value: ScenarioParams[K]) => {
    setParams((p) => ({ ...p, [key]: value }));
    setSaved(false);
  };

  const handleRun = () => {
    setRun(runScenario(params));
    setSaved(false);
  };

  const handleSave = () => {
    if (!run) return;
    const s = saveScenario(run);
    setHistory((h) => [s, ...h]);
    setSaved(true);
  };

  const handleReset = () => {
    setParams(defaultScenarioParams());
    setRun(null);
    setBaseline(null);
    setSaved(false);
  };

  const handleLoad = (s: SavedScenario) => {
    setParams(s.params);
    setRun(s);
    setSaved(true);
  };

  const handleDuplicate = (s: SavedScenario) => {
    setParams({ ...s.params, label: `${s.params.label} (copy)` });
    setRun(null);
    setSaved(false);
  };

  const handleSetBaseline = () => {
    if (run) setBaseline(run);
  };

  const handleDelete = (id: string) => {
    deleteScenario(id);
    setHistory((h) => h.filter((s) => s.id !== id));
  };

  const handleClearHistory = () => {
    if (!confirm("Clear all saved sandbox scenarios? This only affects your local scenario history — no real case data is touched.")) return;
    clearAllScenarios();
    setHistory([]);
  };

  const tally = run ? tallyVerdicts(run.result) : null;
  const baselineTally = baseline ? tallyVerdicts(baseline.result) : null;
  const confDelta = useMemo(() => {
    if (!run || !baseline) return null;
    return meanConfidence(run.result) - meanConfidence(baseline.result);
  }, [run, baseline]);

  return (
    <div className="px-6 py-6 max-w-7xl mx-auto">
      {/* Header */}
      <header className="mb-5">
        <div className="flex items-center gap-2 text-[10px] text-compact text-accent-brand mb-2">
          <FlaskConical size={12} />
          SANDBOX / SIMULATION MODE
          <span className="text-ink-faint">·</span>
          <span className="text-ink-muted">no real data is read, written, or submitted</span>
        </div>
        <h1 className="text-2xl font-semibold text-ink-primary leading-tight flex items-center gap-2">
          <Beaker size={22} className="text-accent-brand" />
          PA Decision Sandbox
        </h1>
        <p className="text-sm text-ink-muted mt-1 max-w-2xl leading-relaxed">
          Build a hypothetical case from scratch and see how each payer would decide — powered by
          the same multi-payer arbitration engine as <span className="text-ink-body">Compare</span>,
          run entirely in your browser. Nothing here creates a real case, calls the backend, or
          appears in case counts, audit logs, or reviewer queues.
        </p>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_280px] gap-5">
        <div className="space-y-5 min-w-0">
          {/* Scenario builder */}
          <div className="bg-surface-raised border border-surface-border rounded-2xl p-5">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-semibold text-ink-primary">Scenario</h2>
              <button
                type="button"
                onClick={handleReset}
                className="text-[11px] font-medium text-ink-muted hover:text-ink-primary flex items-center gap-1 transition-colors"
              >
                <RotateCcw size={11} /> Reset sandbox
              </button>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <label className="flex flex-col gap-1 sm:col-span-2">
                <span className="text-xs font-medium text-ink-body">Scenario name</span>
                <input
                  value={params.label}
                  onChange={(e) => set("label", e.target.value)}
                  className="px-3 py-1.5 rounded-lg border border-surface-border bg-surface-bg text-sm text-ink-primary focus:outline-none focus:ring-2 focus:ring-accent-brand/40"
                />
              </label>

              <label className="flex flex-col gap-1">
                <span className="text-xs font-medium text-ink-body">Treatment</span>
                <select
                  value={params.treatment}
                  onChange={(e) => set("treatment", e.target.value)}
                  className="px-3 py-1.5 rounded-lg border border-surface-border bg-surface-bg text-sm text-ink-primary focus:outline-none focus:ring-2 focus:ring-accent-brand/40"
                >
                  {(treatmentOptions.includes(params.treatment) ? treatmentOptions : [params.treatment, ...treatmentOptions]).map((t) => <option key={t} value={t}>{t}</option>)}
                </select>
              </label>

              <label className="flex flex-col gap-1">
                <span className="text-xs font-medium text-ink-body">J-code (auto)</span>
                <div className="px-3 py-1.5 rounded-lg border border-surface-border bg-surface-panel text-sm text-mono-tech text-accent-amber">
                  {jCodeFor(params.treatment)}
                </div>
              </label>

              <label className="flex flex-col gap-1">
                <span className="text-xs font-medium text-ink-body">Diagnosis</span>
                <input
                  value={params.diagnosis}
                  onChange={(e) => set("diagnosis", e.target.value)}
                  className="px-3 py-1.5 rounded-lg border border-surface-border bg-surface-bg text-sm text-ink-primary focus:outline-none focus:ring-2 focus:ring-accent-brand/40"
                />
              </label>

              <label className="flex flex-col gap-1">
                <span className="text-xs font-medium text-ink-body">Stage</span>
                <select
                  value={params.stage}
                  onChange={(e) => set("stage", e.target.value)}
                  className="px-3 py-1.5 rounded-lg border border-surface-border bg-surface-bg text-sm text-ink-primary focus:outline-none focus:ring-2 focus:ring-accent-brand/40"
                >
                  {STAGE_OPTIONS.map((s) => <option key={s} value={s}>Stage {s}</option>)}
                </select>
              </label>

              <label className="flex flex-col gap-1">
                <span className="text-xs font-medium text-ink-body">Payer (submission target)</span>
                <select
                  value={params.livePayer}
                  onChange={(e) => set("livePayer", e.target.value as PayerId)}
                  className="px-3 py-1.5 rounded-lg border border-surface-border bg-surface-bg text-sm text-ink-primary focus:outline-none focus:ring-2 focus:ring-accent-brand/40"
                >
                  {payerOptions.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}
                </select>
              </label>

              <label className="flex flex-col gap-1">
                <span className="text-xs font-medium text-ink-body">HER2 status</span>
                <select
                  value={params.her2Status}
                  onChange={(e) => set("her2Status", e.target.value as Her2Status)}
                  className="px-3 py-1.5 rounded-lg border border-surface-border bg-surface-bg text-sm text-ink-primary focus:outline-none focus:ring-2 focus:ring-accent-brand/40"
                >
                  {HER2_OPTIONS.map((h) => <option key={h} value={h}>{HER2_STATUS_LABELS[h]}</option>)}
                </select>
              </label>
            </div>

            {/* Documentation completeness — the axis most sandbox exploration lives on */}
            <div className="mt-4 pt-4 border-t border-surface-border">
              <div className="text-xs font-medium text-ink-body mb-2">Documentation completeness</div>
              <div className="flex flex-wrap gap-4">
                {([
                  ["lvefDocumented", "Baseline LVEF documented"],
                  ["comboRegimenDocumented", "Combination regimen documented"],
                  ["ecogDocumented", "ECOG performance status documented"],
                ] as const).map(([key, label]) => (
                  <label key={key} className="inline-flex items-center gap-2 text-sm text-ink-body">
                    <input
                      type="checkbox"
                      checked={params[key]}
                      onChange={(e) => set(key, e.target.checked)}
                      className="rounded border-surface-border"
                    />
                    {label}
                  </label>
                ))}
              </div>
            </div>

            <div className="mt-4 pt-4 border-t border-surface-border flex items-center gap-2">
              <button
                type="button"
                onClick={handleRun}
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-accent-brand text-ink-invert text-sm font-medium hover:opacity-90 transition-opacity"
              >
                <Play size={13} /> Run simulation
              </button>
              {run && (
                <>
                  <button
                    type="button"
                    onClick={handleSave}
                    disabled={saved}
                    className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg border border-surface-border text-ink-body text-sm font-medium hover:bg-surface-raised-hi disabled:opacity-50 transition-colors"
                  >
                    <Save size={13} /> {saved ? "Saved" : "Save scenario"}
                  </button>
                  <button
                    type="button"
                    onClick={handleSetBaseline}
                    className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg border border-surface-border text-ink-body text-sm font-medium hover:bg-surface-raised-hi transition-colors"
                    title="Pin this result as the baseline to compare future runs against"
                  >
                    Set as baseline
                  </button>
                </>
              )}
            </div>
          </div>

          {/* Results */}
          {run && (
            <div className="bg-surface-raised border border-surface-border rounded-2xl p-5">
              <div className="flex items-center justify-between mb-1">
                <h2 className="text-sm font-semibold text-ink-primary">Results — {run.params.label}</h2>
                <span
                  className="text-[10px] text-compact px-1.5 py-0.5 rounded bg-accent-brand/10 text-accent-brand"
                  title="Verdicts come from a documentation heuristic, not the ClinCase agent pipeline. Use Compare on a real case for recorded outcomes."
                >
                  SIMULATED · heuristic
                </span>
              </div>
              {tally && (
                <p className="text-xs text-ink-muted mb-4">
                  <span className="text-accent-green">{tally.approve} approve</span>
                  {" · "}
                  <span className="text-accent-amber">{tally.refer} refer</span>
                  {" · "}
                  <span className="text-accent-red">{tally.deny} deny</span>
                  {" · "}
                  {Math.round(meanConfidence(run.result) * 100)}% mean confidence
                </p>
              )}

              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
                {run.result.payers.map((p) => (
                  <div key={p.payer_id} className="flex flex-col gap-1">
                    <SandboxVerdictTile verdict={p} isPrimary={p.payer_id === run.result.recommendation.primary} />
                    <PolicyChip catalog={catalog} payer={p.payer_id} treatment={run.params.treatment} />
                  </div>
                ))}
              </div>

              <div className="rounded-xl border border-surface-border bg-surface-panel/40 p-3 text-xs text-ink-body leading-relaxed">
                {run.result.recommendation.summary}
              </div>

              {/* Baseline comparison */}
              {baseline && (
                <div className="mt-4 pt-4 border-t border-surface-border">
                  <div className="text-xs font-medium text-ink-body mb-2">
                    Baseline comparison — vs. "{baseline.params.label}"
                  </div>
                  <table className="w-full text-xs">
                    <thead className="text-[10px] text-compact text-ink-muted">
                      <tr>
                        <th className="text-left py-1">Metric</th>
                        <th className="text-right py-1">Baseline</th>
                        <th className="text-right py-1">This scenario</th>
                        <th className="text-right py-1">Difference</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-surface-border">
                      <tr>
                        <td className="py-1.5 text-ink-body">Mean confidence</td>
                        <td className="py-1.5 text-right text-mono-tech">{Math.round(meanConfidence(baseline.result) * 100)}%</td>
                        <td className="py-1.5 text-right text-mono-tech">{Math.round(meanConfidence(run.result) * 100)}%</td>
                        <td className={clsx("py-1.5 text-right text-mono-tech font-medium flex items-center justify-end gap-1",
                          confDelta !== null && confDelta > 0 ? "text-accent-green" : confDelta !== null && confDelta < 0 ? "text-accent-red" : "text-ink-muted")}>
                          {confDelta !== null && confDelta > 0 && <TrendingUp size={11} />}
                          {confDelta !== null && confDelta < 0 && <TrendingDown size={11} />}
                          {confDelta !== null ? `${confDelta > 0 ? "+" : ""}${Math.round(confDelta * 100)} pts` : "—"}
                        </td>
                      </tr>
                      {baselineTally && tally && (
                        <>
                          <TallyRow label="Approvals" a={baselineTally.approve} b={tally.approve} />
                          <TallyRow label="Refers" a={baselineTally.refer} b={tally.refer} />
                          <TallyRow label="Denials" a={baselineTally.deny} b={tally.deny} />
                        </>
                      )}
                    </tbody>
                  </table>
                </div>
              )}

              <details className="mt-3 text-[11px] text-ink-faint">
                <summary className="cursor-pointer hover:text-ink-muted">Synthetic clinical note used for this run</summary>
                <p className="mt-1.5 text-mono-tech leading-relaxed">{run.synthetic_note}</p>
              </details>
            </div>
          )}

          {!run && (
            <div className="bg-surface-raised border-2 border-dashed border-surface-border rounded-2xl p-10 text-center text-ink-muted text-sm">
              Configure a scenario above and click "Run simulation" to see how each payer would decide.
            </div>
          )}
        </div>

        {/* History sidebar */}
        <aside className="space-y-3">
          <div className="bg-surface-raised border border-surface-border rounded-2xl p-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-xs font-semibold text-ink-primary">Saved scenarios ({history.length})</h3>
              {history.length > 0 && (
                <button type="button" onClick={handleClearHistory} className="text-[10px] text-ink-faint hover:text-accent-red transition-colors">
                  clear all
                </button>
              )}
            </div>
            {history.length === 0 ? (
              <p className="text-[11px] text-ink-muted">
                No saved scenarios yet. Run and save one to build a comparison history — stored only in this browser.
              </p>
            ) : (
              <ul className="space-y-1.5">
                {history.map((s) => (
                  <li key={s.id} className="border border-surface-border rounded-lg p-2.5 bg-surface-bg">
                    <div className="flex items-start justify-between gap-1.5">
                      <button
                        type="button"
                        onClick={() => handleLoad(s)}
                        className="text-left text-xs font-medium text-ink-primary hover:text-accent-brand transition-colors truncate flex-1"
                      >
                        {s.params.label}
                      </button>
                      <span className={clsx("text-[9px] text-compact px-1 py-0.5 rounded shrink-0", VERDICT_TEXT[s.result.payers.find((p) => p.payer_id === s.params.livePayer)?.verdict ?? "REFER"])}>
                        {s.result.payers.find((p) => p.payer_id === s.params.livePayer)?.verdict ?? "—"}
                      </span>
                    </div>
                    <div className="text-[10px] text-ink-faint mt-0.5">{s.params.treatment} · {s.params.livePayer.toUpperCase()}</div>
                    <div className="flex items-center gap-1 mt-1.5">
                      <button type="button" onClick={() => handleDuplicate(s)} className="p-1 rounded text-ink-faint hover:text-ink-body hover:bg-surface-raised-hi transition-colors" title="Duplicate">
                        <Copy size={11} />
                      </button>
                      <button type="button" onClick={() => setBaseline(s)} className="p-1 rounded text-ink-faint hover:text-accent-brand hover:bg-surface-raised-hi transition-colors" title="Compare as baseline">
                        <ArrowRight size={11} />
                      </button>
                      <button type="button" onClick={() => handleDelete(s.id)} className="p-1 rounded text-ink-faint hover:text-accent-red hover:bg-surface-raised-hi transition-colors ml-auto" title="Delete">
                        <Trash2 size={11} />
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="rounded-xl border border-dashed border-surface-border-hi px-3 py-2.5 text-[10px] text-ink-faint leading-relaxed flex items-start gap-1.5">
            <AlertTriangle size={12} className="shrink-0 mt-0.5" />
            Simulated / hypothetical only. Verdicts here never touch real cases, the review queue,
            or audit trail, and this page never calls the backend.
          </div>
        </aside>
      </div>
    </div>
  );
}

function TallyRow({ label, a, b }: { label: string; a: number; b: number }) {
  const d = b - a;
  return (
    <tr>
      <td className="py-1.5 text-ink-body">{label}</td>
      <td className="py-1.5 text-right text-mono-tech">{a}</td>
      <td className="py-1.5 text-right text-mono-tech">{b}</td>
      <td className={clsx("py-1.5 text-right text-mono-tech font-medium", d > 0 ? "text-accent-green" : d < 0 ? "text-accent-red" : "text-ink-muted")}>
        {d > 0 ? `+${d}` : d}
      </td>
    </tr>
  );
}

// Sandbox-local verdict tile. Deliberately NOT reusing PayerVerdictCard: that
// component's CTA reads "Submit to {payer} →" for approvals, which would
// misleadingly imply a sandbox scenario can submit a real PA request. This
// tile mirrors its visual language (verdict color, confidence bar, criteria)
// without any submission-shaped affordance.
function SandboxVerdictTile({ verdict, isPrimary }: { verdict: PayerVerdict; isPrimary: boolean }) {
  return (
    <div className={clsx("border rounded-xl p-3 flex flex-col gap-2", VERDICT_BG[verdict.verdict], isPrimary && "ring-1 ring-accent-brand")}>
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-ink-primary">{verdict.payer_name}</span>
        {isPrimary && <span className="text-[9px] text-compact px-1 py-0.5 rounded bg-accent-brand text-ink-invert">best</span>}
      </div>
      <div className={clsx("text-sm font-bold uppercase tracking-wide", VERDICT_TEXT[verdict.verdict])}>
        {verdict.verdict}
      </div>
      <div className="h-1 rounded-full bg-surface-border overflow-hidden">
        <div
          className={clsx("h-full rounded-full", verdict.verdict === "APPROVE" ? "bg-accent-green" : verdict.verdict === "DENY" ? "bg-accent-red" : "bg-accent-amber")}
          style={{ width: `${Math.round(verdict.confidence * 100)}%` }}
        />
      </div>
      <div className="text-[10px] text-mono-tech text-ink-muted">{Math.round(verdict.confidence * 100)}% confidence</div>
      <p className="text-[11px] text-ink-body leading-snug line-clamp-2">{verdict.reasoning_summary}</p>
    </div>
  );
}

function PolicyChip({ catalog, payer, treatment }: { catalog: PolicyCatalog | null; payer: string; treatment: string }) {
  if (!catalog) return null;
  const pol = policyOnFile(catalog, payer, treatment);
  return pol ? (
    <a href={`/policies/${pol.policy_id}/diff`} data-testid={`sandbox-policy-${payer}`} className="text-[10px] text-mono-tech text-accent-brand hover:underline px-1">
      real policy on file: {pol.policy_id}
    </a>
  ) : (
    <span data-testid={`sandbox-policy-${payer}`} className="text-[10px] text-mono-tech text-ink-faint px-1">no policy on file for this drug</span>
  );
}
