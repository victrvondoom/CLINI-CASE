/**
 * CardioTwin dashboard panels: safety banner, CAD card, vessel cards, "why this vessel" evidence panel,
 * model-trust panel, warnings, legend and the evidence-to-anatomy chain.
 *
 * Wording is deliberate: "estimated probability", "model evidence" — never "blockage found here".
 */
import clsx from "clsx";
import { AlertTriangle, CheckCircle2, Info, ShieldAlert } from "lucide-react";
import { useState } from "react";

import { BAND_LABEL, RAMP_STOPS, pct, probabilityColor } from "./vesselMapping";
import {
  TARGETS,
  VESSELS,
  VESSEL_NAMES,
  type FeatureContribution,
  type Prediction,
  type TargetId,
  type TargetPrediction,
  type VesselId,
  type Warning,
} from "./types";

export const CARD = "rounded-xl border border-surface-border bg-surface-raised";

export function SafetyBanner({ compact = false }: { compact?: boolean }) {
  return (
    <div
      role="note"
      aria-label="Clinical safety disclaimer"
      data-testid="cardiotwin-disclaimer"
      className={clsx(
        "flex items-start gap-2 rounded-lg border border-accent-amber/50 bg-accent-amber/10 text-ink-primary",
        compact ? "px-2.5 py-1.5 text-[11px]" : "px-3 py-2 text-[12.5px]",
      )}
    >
      <ShieldAlert size={compact ? 14 : 16} className="mt-0.5 shrink-0 text-accent-amber" aria-hidden />
      <p>
        <b>Decision support / educational use only.</b> These are statistical estimates from tabular clinical
        features — not a diagnosis and not a substitute for coronary angiography or other diagnostic imaging.
        {!compact && " The 3D view does not show where, or whether, a lesion exists."}
      </p>
    </div>
  );
}

export function Legend() {
  const grad = `linear-gradient(90deg, ${RAMP_STOPS.map((s) => `rgb(${s.rgb.join(",")}) ${s.p * 100}%`).join(", ")})`;
  return (
    <div className="text-[11px] text-ink-muted space-y-1.5" aria-label="Visual encoding legend">
      <div className="flex items-center gap-2">
        <span className="w-28 shrink-0">Estimated probability</span>
        <span className="h-2.5 flex-1 rounded-full" style={{ background: grad }} />
        <span className="tabular-nums">0 → 100%</span>
      </div>
      <div className="flex flex-wrap gap-x-4 gap-y-1">
        <span>
          <b className="text-ink-body">Outline</b> strength = model confidence
        </span>
        <span>
          <b className="text-ink-body">Halo</b> width = uncertainty (80% interval)
        </span>
        <span>Tube thickness is constant — colour is <i>not</i> a stenosis measurement.</span>
      </div>
    </div>
  );
}

const CONF_TEXT = { high: "High confidence", moderate: "Moderate confidence", low: "Low confidence" } as const;

function ProbBar({ p, lo, hi }: { p: number; lo: number; hi: number }) {
  return (
    <div className="relative h-2 rounded-full bg-surface-border/60" aria-hidden>
      <div
        className="absolute inset-y-0 rounded-full opacity-35"
        style={{ left: `${lo * 100}%`, width: `${Math.max(0.5, (hi - lo) * 100)}%`, background: probabilityColor(p) }}
      />
      <div
        className="absolute top-[-2px] h-3 w-1 rounded bg-ink-primary"
        style={{ left: `calc(${p * 100}% - 2px)`, background: probabilityColor(p), outline: "1px solid rgb(15 23 42 / .6)" }}
      />
    </div>
  );
}

export function CadCard({ t, selected, onSelect }: { t: TargetPrediction; selected: boolean; onSelect: () => void }) {
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      data-testid="cad-card"
      className={clsx(
        CARD,
        "w-full text-left p-4 space-y-2 focus:outline-none focus:ring-2 focus:ring-accent-brand",
        selected && "ring-2 ring-accent-brand",
      )}
    >
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-[11px] uppercase tracking-wide text-ink-muted">Predicted CAD probability</span>
        <span className="text-[10.5px] text-ink-muted">{CONF_TEXT[t.confidence]}</span>
      </div>
      <div className="flex items-baseline gap-3">
        <span className="text-4xl font-semibold tabular-nums text-ink-primary" data-testid="cad-probability">
          {pct(t.probability)}
        </span>
        <span className="text-[12px] text-ink-muted tabular-nums">
          80% interval {pct(t.interval_80[0])}–{pct(t.interval_80[1])}
        </span>
      </div>
      <ProbBar p={t.probability} lo={t.interval_80[0]} hi={t.interval_80[1]} />
      <div className="text-[11px] text-ink-muted flex flex-wrap gap-x-3 gap-y-0.5">
        <span>
          {t.calibrated ? "Calibrated" : "Uncalibrated"} · model output {pct(t.model_probability)}
        </span>
        <span>
          {t.above_operating_point ? "Above" : "Below"} model operating point ({pct(t.operating_point)})
        </span>
        <span>Held-out AUC {t.held_out_auc.toFixed(2)}</span>
      </div>
      {t.consistency_adjusted && (
        <div className="text-[11px] text-accent-amber">
          Raised from {pct(t.unadjusted_probability ?? 0)} so overall CAD is never below the largest vessel estimate.
        </div>
      )}
    </button>
  );
}

export function VesselCard({ t, selected, onSelect }: { t: TargetPrediction; selected: boolean; onSelect: () => void }) {
  const id = t.target as VesselId;
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      data-testid={`vessel-card-${id}`}
      className={clsx(
        CARD,
        "w-full text-left p-3 space-y-1.5 focus:outline-none focus:ring-2 focus:ring-accent-brand",
        selected && "ring-2 ring-accent-brand",
      )}
    >
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-[13px] font-semibold text-ink-primary">
          {id} <span className="font-normal text-ink-muted text-[11px]">· {VESSEL_NAMES[id]}</span>
        </span>
        <span className="text-[10.5px] text-ink-muted">{CONF_TEXT[t.confidence]}</span>
      </div>
      <div className="flex items-baseline gap-3">
        <span className="text-2xl font-semibold tabular-nums text-ink-primary" data-testid={`vessel-prob-${id}`}>
          {pct(t.probability)}
        </span>
        <span className="text-[11px] px-1.5 py-0.5 rounded" style={{ background: `${probabilityColor(t.probability)}33` }}>
          {BAND_LABEL[t.band]}
        </span>
        <span className="text-[11px] text-ink-muted tabular-nums ml-auto">
          {pct(t.interval_80[0])}–{pct(t.interval_80[1])}
        </span>
      </div>
      <ProbBar p={t.probability} lo={t.interval_80[0]} hi={t.interval_80[1]} />
    </button>
  );
}

// ---------------------------------------------------------------------------
// Evidence panel — "why is this vessel highlighted?"
// ---------------------------------------------------------------------------

function ContribRow({ c, max }: { c: FeatureContribution; max: number }) {
  const w = max > 0 ? (Math.abs(c.contribution) / max) * 100 : 0;
  const up = c.contribution > 0;
  const ref =
    c.reference_status === "above" ? "above reference" : c.reference_status === "below" ? "below reference" : null;
  return (
    <li className="grid grid-cols-[minmax(0,1.3fr)_minmax(0,0.9fr)_112px] items-center gap-2 py-1 text-[12px]" data-testid="contribution-row">
      <div className="min-w-0">
        <div className="truncate text-ink-primary">
          {c.label}
          {c.imputed && <span className="ml-1 text-[10px] text-ink-muted">(imputed)</span>}
        </div>
        <div className="text-[10.5px] text-ink-muted tabular-nums">
          {String(c.value)}
          {c.unit ? ` ${c.unit}` : ""}
          {c.cohort_percentile != null && ` · cohort ${Math.round(c.cohort_percentile)}th pct`}
          {ref && ` · ${ref}`}
        </div>
      </div>
      <div className="flex items-center h-3" aria-hidden>
        <div className="relative w-full h-2 bg-surface-border/40 rounded">
          <div className="absolute inset-y-0 left-1/2 w-px bg-surface-border-hi" />
          <div
            className={clsx("absolute inset-y-0 rounded", up ? "left-1/2 bg-accent-red/80" : "right-1/2 bg-accent-blue/80")}
            style={{ width: `${w / 2}%` }}
          />
        </div>
      </div>
      <div className="text-[11px] tabular-nums text-ink-body text-right">
        {up ? "▲ raises" : c.contribution < 0 ? "▼ lowers" : "neutral"}
        <div className="text-[10px] text-ink-muted">{c.contribution > 0 ? "+" : ""}{c.contribution.toFixed(2)} log-odds</div>
      </div>
    </li>
  );
}

export function EvidencePanel({ pred, target }: { pred: Prediction; target: TargetId }) {
  const [all, setAll] = useState(false);
  const t: TargetPrediction = target === "CAD" ? pred.cad : pred.vessels[target];
  const ex = pred.explanations[target];
  const provided = ex.features.filter((f) => !f.imputed);
  const rows = (all ? ex.features : provided.slice(0, 7)).filter((f) => Math.abs(f.contribution) > 1e-6 || all);
  const max = Math.max(...ex.features.map((f) => Math.abs(f.contribution)), 1e-9);
  const raises = provided.filter((f) => f.contribution > 0.05).slice(0, 3).map((f) => f.label);
  const lowers = provided.filter((f) => f.contribution < -0.05).slice(0, 3).map((f) => f.label);
  const isVessel = target !== "CAD";
  return (
    <section className={clsx(CARD, "p-4 space-y-3")} aria-label={`Why ${target} is highlighted`} data-testid="evidence-panel">
      <header>
        <h3 className="text-[13px] font-semibold text-ink-primary">
          {isVessel ? `Why ${target} is highlighted` : "Why the CAD estimate is what it is"}
        </h3>
        <p className="text-[12px] text-ink-body mt-1">
          The model's estimated {isVessel ? `${target}-level stenosis` : "CAD"} probability is{" "}
          <b className="tabular-nums">{pct(t.probability)}</b> ({CONF_TEXT[t.confidence].toLowerCase()}).
          {raises.length > 0 && (
            <>
              {" "}
              Higher with: <b>{raises.join(", ")}</b>.
            </>
          )}
          {lowers.length > 0 && (
            <>
              {" "}
              Lower with: <b>{lowers.join(", ")}</b>.
            </>
          )}
        </p>
      </header>
      <ul className="divide-y divide-surface-border/60" aria-label="Feature contributions">
        {rows.map((c) => (
          <ContribRow key={c.feature} c={c} max={max} />
        ))}
      </ul>
      <div className="flex items-center justify-between text-[11px] text-ink-muted">
        <span>
          Exact additive attribution (linear model): baseline {ex.baseline_logit.toFixed(2)} + Σ contributions ={" "}
          {ex.sum_check_logit.toFixed(2)} log-odds.
        </span>
        <button type="button" className="underline hover:text-ink-primary" onClick={() => setAll((v) => !v)}>
          {all ? "Top contributors" : "All features"}
        </button>
      </div>
      <p className="text-[11px] text-ink-muted flex gap-1.5">
        <Info size={13} className="mt-0.5 shrink-0" aria-hidden />
        <span>
          This shows which inputs drive the <i>model's estimate</i>. It is not a causal explanation and this view does
          not localise a physical lesion.
        </span>
      </p>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Warnings + model trust
// ---------------------------------------------------------------------------

export function WarningList({ warnings }: { warnings: Warning[] }) {
  if (!warnings.length) return null;
  return (
    <ul className="space-y-1.5" aria-label="Prediction warnings" data-testid="warnings">
      {warnings.map((w) => (
        <li
          key={w.code}
          data-testid={`warning-${w.code}`}
          className={clsx(
            "flex gap-2 rounded-lg border px-3 py-2 text-[12px]",
            w.severity === "high"
              ? "border-accent-red/50 bg-accent-red/10"
              : w.severity === "medium"
                ? "border-accent-amber/50 bg-accent-amber/10"
                : "border-surface-border bg-surface-raised",
          )}
        >
          <AlertTriangle size={14} className="mt-0.5 shrink-0" aria-hidden />
          <span>{w.message}</span>
        </li>
      ))}
    </ul>
  );
}

const short = (h: string) => `${h.slice(0, 8)}…${h.slice(-6)}`;

export function TrustPanel({ pred }: { pred: Prediction }) {
  const p = pred.provenance;
  const r = pred.representativeness;
  const rows: [string, React.ReactNode][] = [
    ["Model", `${p.model_id} v${p.version}`],
    [
      "Artifact integrity",
      <span key="i" className="inline-flex items-center gap-1">
        {p.integrity_verified ? <CheckCircle2 size={13} className="text-accent-green" aria-hidden /> : <AlertTriangle size={13} className="text-accent-red" aria-hidden />}
        SHA-256 {p.integrity_verified ? "verified" : "FAILED"} · <code>{short(p.artifact_sha256)}</code>
      </span>,
    ],
    ["Training data", `${p.trained_on} · sha ${p.dataset_sha256.slice(0, 10)}…`],
    ["Leakage audit", p.leakage_audit === "pass" ? "passed (Cath, LAD, LCX, RCA excluded from inputs)" : p.leakage_audit],
    ["Calibration", TARGETS.map((t) => `${t}: ${p.calibration[t]}`).join(" · ")],
    ["Feature completeness", `${pred.feature_completeness.provided}/${pred.feature_completeness.total} provided (${Math.round(pred.feature_completeness.fraction * 100)}%)`],
    [
      "Representativeness",
      `${r.status} · ${r.percentile_of_training.toFixed(0)}th percentile of training distance`,
    ],
    ["Confidence", `CAD ${pred.cad.confidence} · ${VESSELS.map((v) => `${v} ${pred.vessels[v].confidence}`).join(" · ")}`],
    ["Held-out AUC (95% CI)", TARGETS.map((t) => {
      const x = t === "CAD" ? pred.cad : pred.vessels[t];
      return `${t} ${x.held_out_auc.toFixed(2)} [${x.held_out_auc_ci95[0].toFixed(2)}–${x.held_out_auc_ci95[1].toFixed(2)}]`;
    }).join(" · ")],
    ["Prediction time", p.prediction_timestamp],
    ["Input hash", <code key="h">{short(p.input_sha256)}</code>],
  ];
  return (
    <section className={clsx(CARD, "p-4")} aria-label="Model trust" data-testid="trust-panel">
      <h3 className="text-[13px] font-semibold text-ink-primary mb-2">Model trust &amp; provenance</h3>
      <dl className="grid grid-cols-[130px_1fr] gap-x-3 gap-y-1.5 text-[12px]">
        {rows.map(([k, v]) => (
          <div key={k} className="contents">
            <dt className="text-ink-muted">{k}</dt>
            <dd className="text-ink-body break-words">{v}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Evidence → anatomy chain
// ---------------------------------------------------------------------------

export function EvidenceChain({ target }: { target: TargetId }) {
  const steps = [
    ["Patient physiology", "clinical · ECG · lab · echo"],
    ["Model reasoning", "calibrated logistic · exact attribution"],
    [`${target === "CAD" ? "Overall CAD" : target} estimate`, "probability + interval + confidence"],
    ["Anatomy view", "schematic — not a lesion location"],
  ];
  return (
    <ol className="flex flex-wrap items-stretch gap-1.5 text-[11px]" aria-label="Evidence to anatomy chain">
      {steps.map(([a, b], i) => (
        <li key={a} className="flex items-center gap-1.5">
          <div className="rounded-md border border-surface-border bg-surface-raised px-2 py-1">
            <div className="font-medium text-ink-primary">{a}</div>
            <div className="text-ink-muted">{b}</div>
          </div>
          {i < steps.length - 1 && <span aria-hidden className="text-ink-muted">→</span>}
        </li>
      ))}
    </ol>
  );
}
