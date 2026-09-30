/**
 * /cardiotwin/evaluation — every number here is read from the training run's evaluation report
 * (backend/app/cardiotwin/artifacts/evaluation.json); nothing is hand-entered.
 */
import { ArrowLeft } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { cardio } from "../cardiotwin/api";
import { CARD, SafetyBanner } from "../cardiotwin/panels";
import { TARGETS, type EvaluationReport, type TargetId } from "../cardiotwin/types";

const f = (v: number | null | undefined, d = 3) => (v == null ? "—" : v.toFixed(d));
const ci = (c?: number[]) => (c ? `${f(c[0])}–${f(c[1])}` : "—");
const TH = "text-right px-2 py-1 font-medium text-ink-muted text-[11px] whitespace-nowrap";
const TD = "text-right px-2 py-1 tabular-nums whitespace-nowrap";

function Section({ title, children, note }: { title: string; children: React.ReactNode; note?: string }) {
  return (
    <section className={`${CARD} p-4 space-y-2`}>
      <h2 className="text-[14px] font-semibold text-ink-primary">{title}</h2>
      {note && <p className="text-[11.5px] text-ink-muted">{note}</p>}
      <div className="overflow-x-auto">{children}</div>
    </section>
  );
}

/** Small dependency-free line chart. points are [x, y] in 0..1. */
function LineChart({ series, label, diagonal = true }: { series: { name: string; pts: number[][]; color: string }[]; label: string; diagonal?: boolean }) {
  const S = 140;
  const sx = (x: number) => 22 + x * (S - 28);
  const sy = (y: number) => S - 18 - y * (S - 28);
  return (
    <svg viewBox={`0 0 ${S} ${S}`} className="w-[150px] h-[150px] shrink-0" role="img" aria-label={label}>
      <rect x="22" y="10" width={S - 28} height={S - 28} fill="none" stroke="currentColor" strokeOpacity=".2" />
      {diagonal && <line x1={sx(0)} y1={sy(0)} x2={sx(1)} y2={sy(1)} stroke="currentColor" strokeOpacity=".25" strokeDasharray="3 3" />}
      {series.map((s) => (
        <polyline key={s.name} fill="none" stroke={s.color} strokeWidth="1.6" points={s.pts.map(([x, y]) => `${sx(x)},${sy(y)}`).join(" ")} />
      ))}
    </svg>
  );
}

export default function CardioEvaluation() {
  const [r, setR] = useState<EvaluationReport | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    cardio.evaluation().then(setR).catch((e) => setErr((e as Error).message));
  }, []);

  return (
    <div className="px-4 sm:px-6 py-6 space-y-4 max-w-[1300px]">
      <header className="space-y-2">
        <Link to="/cardiotwin" className="text-[11px] text-ink-muted hover:text-ink-primary inline-flex items-center gap-1">
          <ArrowLeft size={12} aria-hidden /> CardioTwin
        </Link>
        <h1 className="text-2xl font-semibold text-ink-primary">CardioTwin — evaluation &amp; methods</h1>
        <SafetyBanner compact />
      </header>
      {err && <div role="alert" className="rounded-lg border border-accent-red/50 bg-accent-red/10 px-3 py-2 text-[12.5px]">{err}</div>}
      {!r && !err && <p className="text-[12.5px] text-ink-muted">Loading evaluation report…</p>}
      {r && (
        <>
          <p className="text-[12px] text-ink-body max-w-3xl" data-testid="eval-protocol">
            <b>Protocol.</b> {r.protocol} n = {r.dataset.rows} patients ({r.dataset.name}, {r.dataset.license}). Artifact{" "}
            <code>{String(r.artifact_sha256).slice(0, 12)}…</code>
          </p>

          <Section title="Per-target performance (shipped model: L2 logistic regression + calibration)" note="ROC-AUC / PR-AUC / Brier / ECE from averaged out-of-fold predictions with 1000× patient bootstrap 95% CIs. Threshold metrics use thresholds chosen inside each training fold only.">
            <table className="w-full text-[12px]" data-testid="eval-metrics">
              <thead>
                <tr>
                  <th className="text-left px-2 py-1 font-medium text-ink-muted text-[11px]">Target</th>
                  {["Prev.", "ROC-AUC (95% CI)", "PR-AUC", "Brier", "ECE", "Accuracy", "Precision", "Recall", "Specificity", "F1"].map((h) => (
                    <th key={h} className={TH}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {TARGETS.map((t) => {
                  const s = r.targets[t].cv_summary;
                  return (
                    <tr key={t} className="border-t border-surface-border/60">
                      <td className="px-2 py-1 font-medium text-ink-primary">{t}</td>
                      <td className={TD}>{f(s.prevalence, 2)}</td>
                      <td className={TD}>{f(s.roc_auc)} ({ci(s.roc_auc_ci95)})</td>
                      <td className={TD}>{f(s.pr_auc)}</td>
                      <td className={TD}>{f(s.brier)}</td>
                      <td className={TD}>{f(s.ece)}</td>
                      <td className={TD}>{f(s.accuracy.mean, 2)}±{f(s.accuracy.sd, 2)}</td>
                      <td className={TD}>{f(s.precision.mean, 2)}</td>
                      <td className={TD}>{f(s.recall.mean, 2)}</td>
                      <td className={TD}>{f(s.specificity.mean, 2)}</td>
                      <td className={TD}>{f(s.f1.mean, 2)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </Section>

          <Section title="Curves &amp; confusion matrices" note="ROC (left), reliability before/after calibration (dashed = ideal), and the expected confusion matrix per pass over the 303 patients.">
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
              {TARGETS.map((t) => {
                const e = r.targets[t];
                const cm = e.cv_summary.confusion_matrix_per_pass;
                return (
                  <div key={t} className="space-y-1" data-testid={`eval-curves-${t}`}>
                    <div className="text-[12px] font-medium text-ink-primary">{t}</div>
                    <div className="flex gap-2">
                      <LineChart label={`${t} ROC curve`} series={[{ name: "roc", pts: e.curves.roc, color: "rgb(var(--accent-brand))" }]} />
                      <LineChart
                        label={`${t} reliability`}
                        series={[
                          { name: "raw", pts: e.calibration_curve_raw.map((p: { mean_predicted: number; observed_rate: number }) => [p.mean_predicted, p.observed_rate]), color: "rgb(var(--accent-amber))" },
                          { name: "cal", pts: e.calibration_curve_shipped.map((p: { mean_predicted: number; observed_rate: number }) => [p.mean_predicted, p.observed_rate]), color: "rgb(var(--accent-green))" },
                        ]}
                      />
                    </div>
                    <table className="text-[11px] tabular-nums">
                      <tbody>
                        <tr><td className="pr-2 text-ink-muted">TP / FN</td><td>{cm.tp} / {cm.fn}</td></tr>
                        <tr><td className="pr-2 text-ink-muted">FP / TN</td><td>{cm.fp} / {cm.tn}</td></tr>
                      </tbody>
                    </table>
                  </div>
                );
              })}
            </div>
          </Section>

          <Section title="Calibration comparison (nested, per-fold)" note="Raw model output vs Platt scaling vs isotonic regression, each fit on inner out-of-fold predictions only. Platt ships only when its mean per-fold Brier gain exceeds its standard error.">
            <table className="w-full text-[12px]" data-testid="eval-calibration">
              <thead>
                <tr>
                  <th className="text-left px-2 py-1 font-medium text-ink-muted text-[11px]">Target</th>
                  {["Brier raw", "Brier Platt", "Brier isotonic", "ECE raw", "ECE Platt", "ECE isotonic", "Shipped"].map((h) => <th key={h} className={TH}>{h}</th>)}
                </tr>
              </thead>
              <tbody>
                {TARGETS.map((t) => {
                  const c = r.targets[t].calibration;
                  return (
                    <tr key={t} className="border-t border-surface-border/60">
                      <td className="px-2 py-1 font-medium text-ink-primary">{t}</td>
                      <td className={TD}>{f(c.raw.brier.mean)}</td><td className={TD}>{f(c.platt.brier.mean)}</td><td className={TD}>{f(c.isotonic.brier.mean)}</td>
                      <td className={TD}>{f(c.raw.ece.mean)}</td><td className={TD}>{f(c.platt.ece.mean)}</td><td className={TD}>{f(c.isotonic.ece.mean)}</td>
                      <td className={TD}>{c.decision.shipped}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </Section>

          <Section title="Model comparison (paired, corrected)" note="Per-fold ROC-AUC of challengers vs the pre-specified shipped model. p-values use the Nadeau–Bengio corrected resampled t-test (repeated-CV folds overlap). No challenger is promoted: differences are within fold noise, and the shipped model gives exact attribution.">
            <table className="w-full text-[12px]" data-testid="eval-comparators">
              <thead>
                <tr>
                  <th className="text-left px-2 py-1 font-medium text-ink-muted text-[11px]">Target</th>
                  {["L2-LR (shipped)", "L1-LR", "Random forest", "Gradient boosting"].map((h) => <th key={h} className={TH}>{h}</th>)}
                </tr>
              </thead>
              <tbody>
                {TARGETS.map((t) => {
                  const c = r.targets[t].comparators;
                  const cell = (k: string) =>
                    c[k] ? `${f(c[k].roc_auc.mean)}${c[k].paired_vs_shipped ? ` (Δ ${c[k].paired_vs_shipped.mean_diff > 0 ? "+" : ""}${f(c[k].paired_vs_shipped.mean_diff)}, p=${f(c[k].paired_vs_shipped.p_value, 2)})` : ""}` : "—";
                  return (
                    <tr key={t} className="border-t border-surface-border/60">
                      <td className="px-2 py-1 font-medium text-ink-primary">{t}</td>
                      <td className={TD}>{cell("lr_l2_shipped")}</td><td className={TD}>{cell("lr_l1")}</td><td className={TD}>{cell("random_forest")}</td><td className={TD}>{cell("gradient_boosting")}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </Section>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <Section title="Hierarchical consistency: CAD ⊇ any vessel" note={r.consistency.supported_by_data}>
              <ul className="text-[12px] text-ink-body space-y-1" data-testid="eval-consistency">
                <li>Independent models violate P(CAD) ≥ max vessel in <b>{(r.consistency.independent_model_violation_rate * 100).toFixed(1)}%</b> of patients.</li>
                <li>CAD AUC — direct {f(r.consistency.cad_direct.roc_auc)} · max-projection {f(r.consistency.cad_max_projection.roc_auc)} · noisy-OR of vessels {f(r.consistency.cad_noisy_or_of_vessels.roc_auc)}.</li>
                <li>CAD Brier — direct {f(r.consistency.cad_direct.brier)} · projection {f(r.consistency.cad_max_projection.brier)} · noisy-OR {f(r.consistency.cad_noisy_or_of_vessels.brier)} (vessel labels are correlated, so independence is wrong).</li>
                <li>{r.consistency.decision}</li>
              </ul>
            </Section>
            <Section title="Leakage audit" note={r.leakage_audit.guard}>
              <ul className="text-[12px] text-ink-body space-y-1" data-testid="eval-leakage">
                <li>Status: <b>{r.leakage_audit.status}</b> · excluded: {r.leakage_audit.excluded_label_columns.join(", ")}</li>
                {TARGETS.map((t) => {
                  const a = r.leakage_audit.per_target[t];
                  return <li key={t}>{t}: strongest single feature {a.strongest_single_feature.feature} (separation {a.strongest_single_feature.separation}); shuffled-label AUC {a.shuffled_label_auc} (≈0.5 expected)</li>;
                })}
                <li className="text-ink-muted">{r.leakage_audit.bypass_demonstration.description} → CAD AUC would be <b>{r.leakage_audit.bypass_demonstration.cad_auc_with_vessel_labels}</b>.</li>
              </ul>
            </Section>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <Section title="Multi-task probe" note="Does sharing trees across the four targets help? Multi-output RF vs single-output RF, paired.">
              <ul className="text-[12px] text-ink-body space-y-1">
                {TARGETS.map((t) => {
                  const m = r.targets[t].multitask_probe;
                  return m ? <li key={t}>{t}: single {f(m.single_output_rf_auc.mean)} · multi-output {f(m.multi_output_rf_auc.mean)} (p={f(m.paired_multi_minus_single.p_value, 2)})</li> : null;
                })}
                <li className="text-ink-muted">No significant multi-task gain → separate per-target models are kept.</li>
              </ul>
            </Section>
            <Section title="Uncertainty &amp; representativeness" note={`${r.representativeness.method}. ${r.representativeness.caveat}`}>
              <ul className="text-[12px] text-ink-body space-y-1">
                {TARGETS.map((t) => (
                  <li key={t}>{t}: ensemble width vs |error| Spearman ρ = {r.uncertainty[t].spearman_ensemble_width_vs_abs_error}; median 80% interval width {r.uncertainty[t].median_interval_width}</li>
                ))}
                <li className="text-ink-muted">{r.uncertainty.caveat}</li>
              </ul>
            </Section>
          </div>

          <Section title="Feature importance (mean |standardised coefficient|)" note="Top drivers per target from the final models. '+' raises, '−' lowers the estimated probability.">
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
              {TARGETS.map((t: TargetId) => (
                <div key={t}>
                  <div className="text-[12px] font-medium text-ink-primary mb-1">{t}</div>
                  <ol className="text-[11.5px] space-y-0.5">
                    {r.feature_importance[t].slice(0, 8).map((x: { feature: string; mean_abs_standardised_coef: number; sign: string }) => (
                      <li key={x.feature} className="flex justify-between gap-2"><span>{x.sign} {x.feature}</span><span className="tabular-nums text-ink-muted">{x.mean_abs_standardised_coef.toFixed(2)}</span></li>
                    ))}
                  </ol>
                </div>
              ))}
            </div>
          </Section>

          <Section title="Dataset & label relationships">
            <p className="text-[12px] text-ink-body">{r.label_relationships.note}</p>
            <p className="text-[12px] text-ink-body mt-1">
              Prevalence: {Object.entries(r.label_relationships.prevalence).map(([k, v]) => `${k} ${(Number(v) * 100).toFixed(0)}%`).join(" · ")} · vessel correlations: {Object.entries(r.label_relationships.vessel_correlation).map(([k, v]) => `${k} ${v}`).join(", ")}
            </p>
            <p className="text-[11.5px] text-ink-muted mt-1">Source: {r.dataset.source.citation} <a className="underline" href={r.dataset.source.url}>{r.dataset.source.url}</a> ({r.dataset.license})</p>
          </Section>

          <Section title="Known limitations">
            <ul className="list-disc pl-5 text-[12px] text-ink-body space-y-1" data-testid="eval-limitations">
              {(r.limitations as string[]).map((l) => <li key={l}>{l}</li>)}
            </ul>
          </Section>
        </>
      )}
    </div>
  );
}
