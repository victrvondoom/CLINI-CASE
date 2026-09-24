/**
 * OncoTwin dashboard panels. Monochrome by design (see styles/index.css):
 * tiers are distinguished by icon + label + weight/fill, never by hue alone.
 */
import clsx from "clsx";
import {
  AlertOctagon,
  AlertTriangle,
  BedDouble,
  CheckCircle2,
  ExternalLink,
  Eye,
  Hash,
  Loader2,
  Pause,
  Play,
  Radio,
  Send,
  ShieldCheck,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { type AlertActionKind, ot } from "./api";
import { Legend, TimeChart } from "./charts";
import type {
  AlertSummary,
  AncPanel,
  Dashboard,
  KeyMoment,
  LedgerEntry,
  Simulation,
  SignalPanel,
  Tier,
  TimelineItem,
  WhyResponse,
} from "./types";

export const pct = (v: number | null | undefined, d = 0) => (v == null ? "—" : `${(v * 100).toFixed(d)}%`);

const TIER_STYLE: Record<Tier, { Icon: LucideIcon; cls: string; hint: string }> = {
  NORMAL: { Icon: CheckCircle2, cls: "border-surface-border text-ink-body", hint: "within personal range" },
  WATCH: { Icon: Eye, cls: "border-dashed border-ink-muted text-ink-primary", hint: "subtle deviation — keep watching" },
  "EARLY WARNING": { Icon: AlertTriangle, cls: "border-accent-brand bg-accent-brand/10 text-ink-primary font-semibold", hint: "review within 24 h" },
  "HIGH PRIORITY": { Icon: AlertOctagon, cls: "border-accent-brand bg-accent-brand text-ink-invert font-semibold", hint: "clinician review now" },
  "IN ACUTE CARE": { Icon: BedDouble, cls: "border-surface-border-hi bg-surface-panel text-ink-body", hint: "patient in acute care — alerts paused" },
};

export function TierBadge({ tier, size = "md" }: { tier: Tier; size?: "sm" | "md" | "lg" }) {
  const s = TIER_STYLE[tier] ?? TIER_STYLE.NORMAL;
  return (
    <span className={clsx("inline-flex items-center gap-1.5 rounded-md border whitespace-nowrap", s.cls,
      size === "sm" && "px-1.5 py-0.5 text-[10px]", size === "md" && "px-2 py-1 text-[11px]", size === "lg" && "px-3 py-1.5 text-sm")}
      title={s.hint}>
      <s.Icon size={size === "lg" ? 16 : 12} aria-hidden />
      <span className="text-compact tracking-wide">{tier}</span>
    </span>
  );
}

export function Section({ id, eyebrow, title, right, children, className }: {
  id?: string; eyebrow?: string; title: string; right?: React.ReactNode; children: React.ReactNode; className?: string;
}) {
  return (
    <section id={id} className={clsx("bg-surface-raised border border-surface-border rounded-2xl p-4 scroll-mt-24", className)}>
      <header className="flex items-start justify-between gap-3 mb-3">
        <div>
          {eyebrow && <div className="text-[10px] text-compact text-ink-muted">{eyebrow}</div>}
          <h2 className="text-[15px] font-semibold text-ink-primary leading-tight">{title}</h2>
        </div>
        {right}
      </header>
      {children}
    </section>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="min-w-0">
      <div className="text-[9.5px] text-compact text-ink-faint">{label}</div>
      <div className="text-[12.5px] text-ink-primary leading-snug">{children}</div>
    </div>
  );
}

// =============================================================================
// Patient Digital Twin Card
// =============================================================================

export function TwinCardView({ d }: { d: Dashboard }) {
  const c = d.card;
  const tx = c.treatment;
  return (
    <div className="grid gap-3 md:grid-cols-[1.1fr_1fr_1fr_1fr]">
      <div className="md:row-span-2 rounded-xl border border-surface-border p-3 bg-surface-bg">
        <Field label="Patient">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-semibold text-base">{c.patient.label}</span>
            <span className="text-[10px] px-1.5 py-0.5 rounded border border-surface-border text-mono-tech">SYNTHETIC</span>
          </div>
          <div className="text-ink-body">{c.patient.age}{c.patient.sex === "female" ? "F" : "M"} · {c.patient.cancer}</div>
          <div className="text-ink-muted text-[11.5px]">
            Stage {c.patient.stage} · {Object.entries(c.patient.biomarkers).map(([k, v]) => `${k} ${v}`).join(" · ")}
          </div>
        </Field>
        <div className="mt-3"><TierBadge tier={c.current_state.tier} size="lg" /></div>
        <div className="mt-3 text-data-numeric text-4xl text-ink-primary nums-tabular">{pct(c.risk.probability, 1)}</div>
        <div className="text-[11px] text-ink-muted">
          probability of unplanned acute care within {c.risk.horizon_days} days ({c.risk.outcome_id}) · 80% interval{" "}
          {pct(c.risk.p10, 1)}–{pct(c.risk.p90, 1)} · confidence <b className="text-ink-body">{c.risk.confidence}</b>
        </div>
      </div>
      <Field label="Current state">
        {c.current_state.care_setting}; dominant load: {c.current_state.dominant_latent_load.toLowerCase()} ({c.current_state.dominant_latent_value.toFixed(2)})
      </Field>
      <Field label="Personal baseline">
        Day {c.baseline.window.start_day}–{c.baseline.window.end_day} · {c.baseline.kind} · adequacy {pct(c.baseline.adequacy)}
      </Field>
      <Field label="Trajectory">
        {c.trajectory.pattern}
        {c.trajectory.signals_adverse.length > 0 && (
          <div className="text-[11px] text-ink-muted">adverse: {c.trajectory.signals_adverse.join(", ").replace(/_/g, " ")}</div>
        )}
      </Field>
      <Field label="Treatment">
        {tx.regimen} · cycle {tx.cycle}{tx.day_of_cycle ? ` day ${tx.day_of_cycle}` : ""}{tx.next_dose_day ? ` · next dose D${tx.next_dose_day}` : ""}
        <div className="text-[11px] text-ink-muted">
          {tx.nadir_window ? "in expected nadir window · " : ""}G-CSF this cycle: {tx.gcsf_this_cycle ? "yes" : "no"} · twin ANC{" "}
          {tx.anc_estimate.mean.toFixed(2)} ×10³/µL
        </div>
      </Field>
      <Field label="Symptoms">
        {c.symptoms.symptom_score ?? "—"}/10 (baseline {c.symptoms.symptom_baseline})
        {c.symptoms.symptom_change_3d != null && (
          <span className="text-ink-muted"> · {c.symptoms.symptom_change_3d >= 0 ? "+" : ""}{c.symptoms.symptom_change_3d} over 3 d</span>
        )}
      </Field>
      <Field label="Wearables">
        {c.wearables.model_signals_fresh}/{c.wearables.model_signals_total} signals fresh · completeness {pct(c.wearables.completeness_7d)}
        {c.wearables.active_quality_flags > 0 && (
          <div className="text-[11px] text-ink-muted">{c.wearables.active_quality_flags} data-quality flag(s)</div>
        )}
      </Field>
      <Field label="Predicted changes (current trajectory)">
        {c.predicted_changes ? (
          <>
            risk at +7 d {pct(c.predicted_changes.risk_day7_median, 1)} · simulated event probability{" "}
            {pct(c.predicted_changes.event_probability_7d)}
            {c.predicted_changes.anc_nadir_projection != null && <> · ANC nadir ≈ {c.predicted_changes.anc_nadir_projection}</>}
          </>
        ) : "—"}
      </Field>
      <div className="md:col-span-3">
        <Field label="Recommended review (considerations, not orders)">
          <ul className="list-disc pl-4 space-y-0.5 text-[12px]">
            {c.recommended_review.length ? c.recommended_review.map((r) => <li key={r}>{r}</li>) : <li>No specific review items.</li>}
          </ul>
        </Field>
      </div>
    </div>
  );
}

// =============================================================================
// What changed / Why
// =============================================================================

export function ExplainPanel({ d }: { d: Dashboard }) {
  const ev = d.evidence;
  const maxLogit = Math.max(0.01, ...ev.contributors.map((c) => Math.abs(c.logit)));
  const lc = d.prediction.logit_check;
  return (
    <div className="space-y-3 text-[12.5px]">
      <p className="text-ink-primary font-medium">{ev.headline}</p>
      <div>
        <div className="text-[10px] text-compact text-ink-faint mb-1">What changed</div>
        {ev.what_changed.length ? (
          <ul className="space-y-1">{ev.what_changed.map((w) => <li key={w.signal} className="text-ink-body">{w.text}</li>)}</ul>
        ) : <div className="text-ink-muted">No signal beyond 1.5 SD of the personal baseline.</div>}
      </div>
      <div><div className="text-[10px] text-compact text-ink-faint mb-1">Why</div><p className="text-ink-body">{ev.why}</p></div>
      <div className="grid sm:grid-cols-2 gap-3">
        <div><div className="text-[10px] text-compact text-ink-faint mb-1">Compared with</div><p className="text-ink-body">{ev.compared_with}</p></div>
        <div><div className="text-[10px] text-compact text-ink-faint mb-1">Over what period</div><p className="text-ink-body">{ev.period.text}</p></div>
      </div>
      <div>
        <div className="text-[10px] text-compact text-ink-faint mb-1">Which signals contributed (exact log-odds contributions)</div>
        <ul className="space-y-1">
          {ev.contributors.map((c) => (
            <li key={c.group} className="grid grid-cols-[1fr_120px_52px] items-center gap-2">
              <span className="truncate text-ink-body">{c.label}</span>
              <span className="h-2 bg-surface-panel rounded-sm overflow-hidden relative" aria-hidden>
                <span className={clsx("absolute top-0 h-full", c.logit >= 0 ? "left-1/2 bg-accent-brand" : "right-1/2 bg-ink-faint")}
                  style={{ width: `${(Math.abs(c.logit) / maxLogit) * 50}%` }} />
              </span>
              <span className="text-mono-tech text-[11px] text-right">{c.logit >= 0 ? "+" : ""}{c.logit.toFixed(2)}</span>
            </li>
          ))}
        </ul>
        <div className="text-[10.5px] text-ink-muted mt-1">
          intercept {lc.intercept.toFixed(2)} + contributions {lc.sum_contributions.toFixed(2)} = logit {lc.logit.toFixed(2)} →{" "}
          {pct(lc.probability_from_logit, 1)}
        </div>
      </div>
      {ev.rules_fired.length > 0 && (
        <div>
          <div className="text-[10px] text-compact text-ink-faint mb-1">Clinical rules fired</div>
          <ul className="space-y-1">{ev.rules_fired.map((r) => <li key={r.rule}>{r.text} <span className="text-ink-muted">— {r.basis}</span></li>)}</ul>
        </div>
      )}
      <div>
        <div className="text-[10px] text-compact text-ink-faint mb-1">What to review</div>
        <ul className="list-disc pl-4 space-y-0.5">{ev.review.map((r) => <li key={r}>{r}</li>)}</ul>
      </div>
      <details className="text-[11.5px]">
        <summary className="cursor-pointer text-ink-muted">
          Supporting observations ({ev.evidence.length}) & references ({ev.references.length})
        </summary>
        <ul className="mt-1 space-y-0.5 text-mono-tech text-[10.5px]">
          {ev.evidence.map((e) => <li key={e.observation_id}>{e.observation_id} · D{e.day} · {e.value} {e.unit}</li>)}
        </ul>
        <ul className="mt-2 space-y-1">
          {ev.references.map((r) => <li key={r.id}><b>{r.id}</b> — {r.text} <span className="text-ink-muted">({r.source})</span></li>)}
        </ul>
      </details>
      <p className="text-[10.5px] text-ink-muted border-t border-surface-border pt-2">{ev.decision_support_notice}</p>
    </div>
  );
}

// =============================================================================
// Confidence, freshness, data quality
// =============================================================================

export function ConfidencePanel({ d }: { d: Dashboard }) {
  const c = d.prediction.confidence;
  const comps: [string, number][] = [
    ["Input completeness (7 d)", c.components.input_completeness_7d],
    ["Input freshness", c.components.input_freshness],
    ["Baseline adequacy", c.components.baseline_adequacy],
    ["Model agreement (bootstrap)", c.components.model_agreement],
  ];
  const q = d.state.data_quality;
  return (
    <div className="space-y-3 text-[12px]">
      <div className="flex items-baseline gap-2">
        <span className="text-data-numeric text-2xl">{pct(c.score)}</span>
        <span className="text-ink-muted">confidence · {c.label}</span>
      </div>
      <ul className="space-y-1.5">
        {comps.map(([label, v]) => (
          <li key={label}>
            <div className="flex justify-between text-[11px]"><span className="text-ink-body">{label}</span><span className="text-mono-tech">{pct(v)}</span></div>
            <div className="h-1.5 bg-surface-panel rounded-full overflow-hidden"><div className="h-full bg-accent-brand" style={{ width: `${v * 100}%` }} /></div>
          </li>
        ))}
      </ul>
      <p className="text-[10.5px] text-ink-muted">{c.formula}</p>
      <div>
        <div className="text-[10px] text-compact text-ink-faint mb-1">Data freshness (twin clock)</div>
        <div className="grid grid-cols-2 gap-x-3 gap-y-0.5 text-[11px]">
          {Object.entries(q.signals).map(([k, s]) => (
            <div key={k} className="flex justify-between gap-2">
              <span className="truncate text-ink-body">{k.replace(/_/g, " ")}</span>
              <span className={clsx("text-mono-tech", !s.fresh && "font-semibold underline decoration-dotted")}>
                {s.hours_since_last == null ? "no data" : `${s.hours_since_last.toFixed(0)} h`}{!s.fresh && s.hours_since_last != null ? " stale" : ""}
              </span>
            </div>
          ))}
        </div>
      </div>
      <div>
        <div className="text-[10px] text-compact text-ink-faint mb-1">Data-quality flags ({q.flags.length})</div>
        {q.flags.length ? (
          <ul className="space-y-1 max-h-40 overflow-auto pr-1">
            {q.flags.map((f, i) => (
              <li key={i} className="text-[11px] text-ink-body">
                <span className="text-mono-tech uppercase text-[9.5px] mr-1 px-1 border border-surface-border rounded">{f.kind}</span>{f.message}
              </li>
            ))}
          </ul>
        ) : <div className="text-ink-muted">None active.</div>}
      </div>
    </div>
  );
}

// =============================================================================
// Charts: risk, signals, ANC, latent state
// =============================================================================

export function RiskChart({ d, alerts }: { d: Dashboard; alerts: AlertSummary[] }) {
  const t = d.prediction.thresholds;
  const hist = d.risk_timeline;
  const fc = d.risk_forecast;
  const maxY = Math.min(1, Math.max(t.high_priority * 1.3, ...hist.map((h) => h.risk_p90), ...(fc?.p90 ?? [0])) * 1.05);
  const moments = d.key_moments.filter((m) => ["treatment", "intervention", "acute_care"].includes(m.kind));
  return (
    <div>
      <TimeChart
        ariaLabel="Seven-day risk timeline: history as computed each day, current day and current-trajectory forecast"
        height={230}
        xDomain={[1, fc?.days.at(-1) ?? d.as_of_day]}
        yDomain={[0, maxY]}
        format={(v) => `${(v * 100).toFixed(v < 0.1 ? 1 : 0)}%`}
        shadeAfter={d.as_of_day}
        hbands={[
          { from: t.watch, to: t.early_warning, label: "WATCH", opacity: 0.04 },
          { from: t.early_warning, to: t.high_priority, label: "EARLY WARNING", opacity: 0.08 },
          { from: t.high_priority, to: maxY, label: "HIGH PRIORITY", opacity: 0.13 },
        ]}
        bands={[
          { key: "hi", label: "80% interval", x: hist.map((h) => h.day), lo: hist.map((h) => h.risk_p10), hi: hist.map((h) => h.risk_p90) },
          ...(fc ? [{ key: "fci", label: "forecast 10–90%", x: fc.days, lo: fc.p10, hi: fc.p90, opacity: 0.08 }] : []),
        ]}
        lines={[
          { key: "risk", label: "7-day risk", x: hist.map((h) => h.day), y: hist.map((h) => h.risk), weight: 2.25 },
          ...(fc ? [{ key: "fc", label: "current trajectory (sim.)", x: [d.as_of_day, ...fc.days], y: [hist.at(-1)?.risk ?? null, ...fc.median], dash: "5 4" }] : []),
        ]}
        vmarks={[
          { x: d.as_of_day, kind: "now" as const, label: d.is_replay ? `replay D${d.as_of_day}` : "now" },
          ...moments.map((m) => ({ x: m.day, kind: "moment" as const })),
          ...alerts.filter((a) => a.as_of_day <= d.as_of_day).map((a) => ({ x: a.as_of_day, kind: "alert" as const })),
        ]}
      />
      <Legend items={[
        { label: "7-day risk (recomputed as-of each day)" }, { label: "80% bootstrap interval", kind: "band" },
        { label: "current-trajectory simulation", dash: "5 4" }, { label: "tier thresholds (validation-derived)", kind: "band" },
      ]} />
    </div>
  );
}

function isSignal(p: SignalPanel | AncPanel): p is SignalPanel {
  return (p as SignalPanel).values !== undefined;
}

export function SignalGrid({ d }: { d: Dashboard }) {
  const entries = Object.entries(d.signals).filter(([k, p]) => k !== "dbp" && isSignal(p)) as [string, SignalPanel][];
  const xmax = Math.max(d.as_of_day, ...entries.map(([, p]) => p.forecast?.days.at(-1) ?? 0));
  const adverse = new Set(d.trajectory.signals_adverse);
  return (
    <div>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {entries.map(([k, p]) => {
          const b = p.baseline;
          const decimals = k === "temperature" ? 2 : ["steps", "resting_hr", "hrv_sdnn", "sbp", "glucose_cgm"].includes(k) ? 0 : 1;
          const z = d.trajectory.signals[k];
          return (
            <div key={k} className={clsx("rounded-xl border p-2.5", adverse.has(k) ? "border-accent-brand" : "border-surface-border")}>
              <div className="flex items-start justify-between gap-2 mb-1">
                <div className="min-w-0">
                  <div className="text-[12px] font-medium text-ink-primary truncate">{p.label}</div>
                  <div className="text-[10px] text-ink-muted truncate">
                    {p.device} · {p.code_system.includes("loinc") ? `LOINC ${p.code}` : "local code"}
                  </div>
                </div>
                <div className="text-right shrink-0">
                  <div className="text-mono-tech text-[12px]">{p.values[d.as_of_day - 1] ?? "—"} <span className="text-ink-muted">{p.unit}</span></div>
                  {z && (
                    <div className="text-[10px] text-ink-muted">
                      {z.status}{z.z_adverse != null ? ` · ${z.z_adverse >= 0 ? "+" : ""}${z.z_adverse} SD` : ""}
                    </div>
                  )}
                </div>
              </div>
              <TimeChart compact height={96} ariaLabel={`${p.label}: history, personal baseline range and forecast`}
                xDomain={[1, xmax]} format={(v) => v.toFixed(decimals)} shadeAfter={d.as_of_day}
                hbands={b ? [{ from: b.low, to: b.high, opacity: 0.1 }] : []}
                hlines={k === "temperature" ? [{ y: 38.0, label: "38 °C" }] : []}
                bands={p.forecast ? [{ key: "f", label: "forecast 10–90%", x: p.forecast.days, lo: p.forecast.p10, hi: p.forecast.p90, opacity: 0.1 }] : []}
                lines={[
                  { key: "v", label: p.label, x: p.days, y: p.values, weight: 1.75 },
                  ...(p.forecast ? [{ key: "fm", label: "forecast", x: p.forecast.days, y: p.forecast.median, dash: "4 3", weight: 1.5 }] : []),
                ]}
                vmarks={[{ x: d.as_of_day, kind: "now" as const }]}
              />
              {b && (
                <div className="text-[10px] text-ink-muted">
                  personal range {b.low}–{b.high} {p.unit}{b.population_reference ? ` · population ${b.population_reference.note}` : ""}
                </div>
              )}
            </div>
          );
        })}
      </div>
      <div className="mt-2">
        <Legend items={[{ label: "observed" }, { label: "personal baseline range", kind: "band" }, { label: "forecast (median, 10–90%)", dash: "4 3" }]} />
      </div>
    </div>
  );
}

export function AncChart({ d }: { d: Dashboard }) {
  const a = d.signals.anc as AncPanel;
  const proj = a.projection;
  const start = proj.trajectory_start_day ?? 1;
  const future = (proj.available && proj.trajectory_median ? proj.trajectory_median : [])
    .map((v, i) => ({ x: start + i, m: v, lo: proj.trajectory_p10?.[i] ?? v, hi: proj.trajectory_p90?.[i] ?? v }))
    .filter((p) => p.x > d.as_of_day);
  const nt = d.state.cancer_treatment_state.neutrophil;
  return (
    <div>
      <TimeChart ariaLabel="Neutrophil count: lab results, patient-fitted twin estimate and projection" height={200}
        xDomain={[1, Math.max(d.as_of_day, future.at(-1)?.x ?? d.as_of_day)]}
        yDomain={[0, Math.max(6, ...a.labs.map((l) => l.value))]} format={(v) => v.toFixed(1)} shadeAfter={d.as_of_day}
        hbands={[{ from: 0, to: 0.5, label: "ANC < 0.5", opacity: 0.12 }, { from: 0.5, to: 1.0, label: "ANC < 1.0", opacity: 0.06 }]}
        bands={[
          { key: "te", label: "twin 80% interval", x: a.twin_estimate.map((t) => t.day), lo: a.twin_estimate.map((t) => t.p10), hi: a.twin_estimate.map((t) => t.p90) },
          ...(future.length ? [{ key: "pj", label: "projection 10–90%", x: future.map((f) => f.x), lo: future.map((f) => f.lo), hi: future.map((f) => f.hi), opacity: 0.08 }] : []),
        ]}
        lines={[
          { key: "tw", label: "twin estimate", x: a.twin_estimate.map((t) => t.day), y: a.twin_estimate.map((t) => t.mean), weight: 1.75 },
          ...(future.length ? [{ key: "pm", label: "projection", x: future.map((f) => f.x), y: future.map((f) => f.m), dash: "5 4" }] : []),
          { key: "lab", label: "lab ANC", x: a.labs.map((l) => l.day), y: a.labs.map((l) => l.value), points: true, weight: 0 },
        ]}
        vmarks={[{ x: d.as_of_day, kind: "now" as const }]}
      />
      <Legend items={[{ label: "lab ANC (EHR)", kind: "point" }, { label: "Friberg twin estimate" }, { label: "projection (planned doses)", dash: "5 4" }]} />
      <p className="text-[11px] text-ink-muted mt-1">
        Baseline ANC {nt.baseline_anc.value} ({nt.baseline_anc.source})
        {nt.fitted_sensitivity && (
          <> · fitted drug sensitivity ×{nt.fitted_sensitivity.relative_sensitivity_mean.toFixed(2)} (80%:{" "}
            {nt.fitted_sensitivity.relative_sensitivity_p10.toFixed(2)}–{nt.fitted_sensitivity.relative_sensitivity_p90.toFixed(2)})</>
        )}
        {proj.available && <> · projected nadir {proj.nadir_median} (D{proj.nadir_day_median}) · P(ANC&lt;0.5 within 48 h) {pct(proj.p_below_0_5_within_48h)}</>}
      </p>
    </div>
  );
}

const LATENT_KEYS = [
  { k: "infection", label: "infection / inflammation", dash: undefined },
  { k: "dehydration", label: "dehydration / GI", dash: "6 3" },
  { k: "fatigue", label: "fatigue", dash: "1.5 3" },
] as const;

export function LatentChart({ d }: { d: Dashboard }) {
  const lt = d.latent_timeline;
  const lf = d.latent_forecast;
  return (
    <div>
      <TimeChart ariaLabel="Latent physiological loads estimated by the twin" height={200}
        xDomain={[1, lf?.days.at(-1) ?? d.as_of_day]} yDomain={[0, 2.2]} format={(v) => v.toFixed(1)} shadeAfter={d.as_of_day}
        hlines={[{ y: 1.5, label: "admission level" }]}
        lines={[
          ...LATENT_KEYS.map(({ k, label, dash }) => ({ key: k, label, x: lt.map((p) => p.day), y: lt.map((p) => p[k]), dash, directLabel: !lf })),
          ...(lf ? LATENT_KEYS.map(({ k, label, dash }) => ({ key: `${k}f`, label: `${label} (sim.)`, x: lf.days, y: lf[k], dash, opacity: 0.5, directLabel: true })) : []),
        ]}
        vmarks={[{ x: d.as_of_day, kind: "now" as const }]}
      />
      <Legend items={LATENT_KEYS.map(({ label, dash }) => ({ label, dash }))} />
      <p className="text-[11px] text-ink-muted mt-1">
        {d.state.physiological_state.method}; observation-model fit R² today {d.state.physiological_state.observation_model_fit_r2 ?? "—"}.
      </p>
    </div>
  );
}

// =============================================================================
// What-if simulator
// =============================================================================

const SCEN_DASH: Record<string, string | undefined> = {
  current: undefined, early_intervention: "6 3", improved_recovery: "2 3", reduced_adherence: "10 3 2 3", regimen_change: "1 5",
};

export function ScenarioPanel({ pid, asOf, autoRun }: { pid: string; asOf: number; autoRun?: number }) {
  const [sim, setSim] = useState<Simulation | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { setSim(null); }, [pid, asOf]);
  const run = async () => {
    setBusy(true); setErr(null);
    try { setSim((await ot.simulate(pid, asOf)).simulation); }
    catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  };
  useEffect(() => { if (autoRun) void run(); }, [autoRun]); // eslint-disable-line react-hooks/exhaustive-deps
  const scen = sim ? Object.values(sim.scenarios) : [];
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 flex-wrap">
        <button type="button" onClick={run} disabled={busy}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-accent-brand text-ink-invert text-[12px] font-medium disabled:opacity-60">
          {busy ? <Loader2 size={13} className="animate-spin" /> : <Play size={13} />} Run 5 scenarios from Day {asOf}
        </button>
        <span className="text-[11px] text-ink-muted">Monte Carlo on the personalised twin · common random numbers across scenarios</span>
      </div>
      {err && <div className="text-[12px] text-accent-red">{err}</div>}
      {sim && (
        <>
          <TimeChart ariaLabel="Projected 7-day risk under each what-if scenario" height={220}
            xDomain={[sim.as_of_day + 1, sim.as_of_day + sim.horizon_days]}
            yDomain={[0, Math.min(1, Math.max(0.05, ...scen.flatMap((s) => s.risk.p90)) * 1.1)]}
            format={(v) => `${(v * 100).toFixed(v < 0.1 ? 1 : 0)}%`}
            bands={sim.scenarios.current ? [{ key: "cb", label: "current 10–90%", x: sim.scenarios.current.days, lo: sim.scenarios.current.risk.p10, hi: sim.scenarios.current.risk.p90, opacity: 0.08 }] : []}
            lines={scen.map((s) => ({ key: s.key, label: s.label, x: s.days, y: s.risk.median, dash: SCEN_DASH[s.key], weight: s.key === "current" ? 2.5 : 1.75 }))}
          />
          <Legend items={scen.map((s) => ({ label: s.label, dash: SCEN_DASH[s.key] }))} />
          <table className="w-full text-[12px]">
            <thead>
              <tr className="text-left text-ink-muted text-[10.5px]">
                <th className="py-1 font-medium">Scenario</th>
                <th className="font-medium text-right">Simulated event prob. (7 d)</th>
                <th className="font-medium text-right">Δ vs current</th>
                <th className="font-medium text-right">Model risk at +7 d</th>
              </tr>
            </thead>
            <tbody>
              {scen.map((s) => (
                <tr key={s.key} className="border-t border-surface-border align-top">
                  <td className="py-1.5 pr-2">
                    <div className="font-medium text-ink-primary">{s.label}</div>
                    <div className="text-[10.5px] text-ink-muted">{s.description}</div>
                  </td>
                  <td className="text-right text-mono-tech">{pct(s.event_probability_7d)}</td>
                  <td className="text-right text-mono-tech">
                    {s.key === "current" ? "—" : `${s.delta_vs_current.event_probability_7d >= 0 ? "+" : ""}${(s.delta_vs_current.event_probability_7d * 100).toFixed(0)} pts`}
                  </td>
                  <td className="text-right text-mono-tech">{pct(s.risk_day7_median, 1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <details className="text-[11px] text-ink-muted">
            <summary className="cursor-pointer">Assumptions & method</summary>
            <p className="mt-1">
              {sim.method} · {sim.n_runs} runs · start state {Object.entries(sim.initial_state).map(([k, v]) => `${k} ${v}`).join(", ")}
            </p>
            <ul className="list-disc pl-4 mt-1">
              {scen.flatMap((s) => s.assumptions.map((a) => <li key={s.key + a}><b>{s.label}:</b> {a}</li>))}
            </ul>
          </details>
          <p className="text-[11px] font-medium text-ink-body border-l-2 border-accent-brand pl-2">{sim.disclaimer}</p>
        </>
      )}
    </div>
  );
}

// =============================================================================
// Multimodal timeline
// =============================================================================

export function TimelinePanel({ pid, asOf, refreshKey }: { pid: string; asOf: number; refreshKey: number }) {
  const [items, setItems] = useState<TimelineItem[]>([]);
  const [lanes, setLanes] = useState<string[]>([]);
  const [off, setOff] = useState<Set<string>>(new Set(["adherence"]));
  useEffect(() => {
    let live = true;
    ot.timeline(pid, asOf).then((r) => { if (live) { setItems(r.items); setLanes(r.lanes); } }).catch(() => undefined);
    return () => { live = false; };
  }, [pid, asOf, refreshKey]);
  const shown = useMemo(() => items.filter((i) => !off.has(i.lane)).slice().reverse(), [items, off]);
  const toggle = (l: string) => setOff((s) => { const n = new Set(s); if (n.has(l)) n.delete(l); else n.add(l); return n; });
  return (
    <div>
      <div className="flex flex-wrap gap-1.5 mb-2" role="group" aria-label="Filter timeline lanes">
        {lanes.map((l) => (
          <button key={l} type="button" aria-pressed={!off.has(l)} onClick={() => toggle(l)}
            className={clsx("text-[10.5px] px-2 py-0.5 rounded border",
              off.has(l) ? "border-surface-border text-ink-faint" : "border-ink-muted text-ink-primary bg-surface-panel")}>
            {l}
          </button>
        ))}
      </div>
      <ol className="max-h-[440px] overflow-auto pr-1 space-y-1">
        {shown.map((i, n) => (
          <li key={n} className={clsx("grid grid-cols-[44px_84px_1fr] gap-2 text-[11.5px] py-1 border-b border-surface-border/60",
            i.severity === "high" && "font-semibold")}>
            <span className="text-mono-tech text-ink-muted">D{i.day}</span>
            <span className="text-[10px] text-compact text-ink-muted pt-0.5">{i.lane}</span>
            <span className="text-ink-body">
              {i.severity !== "info" && <span aria-label={i.severity} className="mr-1">{i.severity === "high" ? "▲" : "△"}</span>}
              {i.title}
              {i.detail && typeof i.detail.top_drivers === "string" && (
                <span className="block text-[10.5px] text-ink-muted font-normal">
                  drivers: {i.detail.top_drivers}{i.detail.rules ? ` · ${String(i.detail.rules)}` : ""}
                </span>
              )}
              {i.fhir && <span className="block text-[10px] text-mono-tech text-ink-faint font-normal">{i.fhir.resourceType}/{i.fhir.id} · {i.source}</span>}
            </span>
          </li>
        ))}
      </ol>
    </div>
  );
}

// =============================================================================
// Alerts + HITL + ClinCase handoff
// =============================================================================

export function AlertPanel({ alerts, canAct, onChanged, selected, onSelect }: {
  alerts: AlertSummary[]; canAct: boolean; onChanged: () => void; selected: string | null; onSelect: (id: string) => void;
}) {
  const [why, setWhy] = useState<WhyResponse | null>(null);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const id = selected ?? alerts[0]?.id ?? null;
  const load = () => { if (id) ot.why(id).then(setWhy).catch((e) => setErr((e as Error).message)); };
  useEffect(load, [id, alerts.length]); // eslint-disable-line react-hooks/exhaustive-deps

  const act = async (a: AlertActionKind) => {
    if (!id) return;
    setBusy(a); setErr(null);
    try { await ot.act(id, a, note); setNote(""); load(); onChanged(); } catch (e) { setErr((e as Error).message); } finally { setBusy(null); }
  };
  const handoff = async () => {
    if (!id) return;
    setBusy("handoff"); setErr(null);
    try { await ot.handoff(id); load(); onChanged(); } catch (e) { setErr((e as Error).message); } finally { setBusy(null); }
  };

  if (!alerts.length) {
    return <p className="text-[12px] text-ink-muted">No alerts yet. Alerts are raised when the twin escalates to EARLY WARNING or HIGH PRIORITY while its clock advances.</p>;
  }
  const a = why?.alert;
  return (
    <div className="grid gap-3 lg:grid-cols-[220px_1fr]">
      <ul className="space-y-1.5">
        {alerts.map((al) => (
          <li key={al.id}>
            <button type="button" onClick={() => onSelect(al.id)}
              className={clsx("w-full text-left rounded-lg border p-2", al.id === id ? "border-accent-brand bg-accent-brand/5" : "border-surface-border")}>
              <div className="flex items-center justify-between gap-1"><TierBadge tier={al.tier} size="sm" /><span className="text-mono-tech text-[10px]">D{al.as_of_day}</span></div>
              <div className="text-[11px] mt-1">{pct(al.risk, 1)} · <span className="uppercase text-[10px] text-compact">{al.status}</span></div>
            </button>
          </li>
        ))}
      </ul>
      {a && why && (
        <div className="space-y-3 text-[12px]">
          <div>
            <div className="text-[10px] text-compact text-ink-faint">Why did the twin raise this alert at this exact time?</div>
            <p className="text-ink-body mt-0.5">{why.answer}</p>
            <div className="mt-1 text-[10.5px] text-ink-muted inline-flex items-center gap-1">
              <ShieldCheck size={12} aria-hidden /> ledger chain {why.chain_verification.valid ? "verified" : "BROKEN"} over{" "}
              {why.chain_verification.entries} entries · alert entry {why.ledger_entries.find((e) => e.kind === "alert")?.hash.slice(0, 12)}…
            </div>
          </div>
          <div className="rounded-lg border border-surface-border p-2.5">
            <div className="text-[10px] text-compact text-ink-faint mb-1">Clinician review — status: <b>{a.status}</b></div>
            {a.actions.map((x) => (
              <div key={x.ledger_entry_id} className="text-[11px]">
                {x.at.slice(0, 16).replace("T", " ")} · {x.user_email} ({x.role}) → <b>{x.action}</b>{x.note ? ` — “${x.note}”` : ""}
              </div>
            ))}
            {canAct ? (
              a.status !== "dismissed" && (
                <div className="mt-2 space-y-2">
                  <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={2} maxLength={2000}
                    placeholder="Clinical note (recorded in the audit trail)" aria-label="Clinical note"
                    className="w-full text-[12px] rounded-md border border-surface-border bg-surface-bg p-2 focus:outline-none focus:ring-2 focus:ring-accent-brand" />
                  <div className="flex flex-wrap gap-2">
                    {(["accept", "investigate", "dismiss"] as AlertActionKind[]).map((k) => (
                      <button key={k} type="button" disabled={busy !== null} onClick={() => act(k)}
                        className={clsx("px-3 py-1.5 rounded-md text-[12px] border capitalize disabled:opacity-50",
                          k === "accept" ? "bg-accent-brand text-ink-invert border-accent-brand" : "border-surface-border-hi")}>
                        {busy === k ? <Loader2 size={12} className="animate-spin inline" /> : k}
                      </button>
                    ))}
                  </div>
                </div>
              )
            ) : <p className="text-[11px] text-ink-muted mt-1">Sign in as a reviewer or admin to accept, dismiss or investigate.</p>}
          </div>
          <div className="rounded-lg border border-surface-border p-2.5">
            <div className="text-[10px] text-compact text-ink-faint mb-1">Connect to ClinCase (prior-authorisation workflow)</div>
            {a.handoff ? (
              <div className="space-y-1.5">
                <div>
                  Case{" "}
                  <Link to={`/cases/${a.handoff.case_id}`} className="underline font-semibold inline-flex items-center gap-1">
                    {a.handoff.case_id} <ExternalLink size={11} aria-hidden />
                  </Link>{" "}
                  created for <b>{a.handoff.requested_treatment.name}</b>
                  {a.handoff.requested_treatment.hcpcs_code ? ` (${a.handoff.requested_treatment.hcpcs_code})` : ""}.
                </div>
                <div className="text-[11px] text-ink-muted">{a.handoff.requested_treatment_rationale}</div>
                <div className="text-[11px]">{a.handoff.policy_preview_note}</div>
                <ul className="text-[11px] list-disc pl-4">
                  {a.handoff.policy_preview.map((p) => <li key={p.section_heading}><b>{p.policy_id}</b> · {p.section_heading}</li>)}
                </ul>
                <details className="text-[11px]">
                  <summary className="cursor-pointer text-ink-muted">
                    Draft physician note ({a.handoff.bundle_resource_count} FHIR resources, package {a.handoff.package_sha256.slice(0, 12)}…)
                  </summary>
                  <pre className="whitespace-pre-wrap text-[11px] mt-1 p-2 bg-surface-bg rounded border border-surface-border">{a.handoff.physician_note_draft}</pre>
                </details>
                <div className="text-[11px] font-medium">{a.handoff.next_step}</div>
              </div>
            ) : (
              <div className="flex items-center gap-2 flex-wrap">
                <button type="button" onClick={handoff}
                  disabled={!canAct || busy !== null || !["accepted", "investigating"].includes(a.status)}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-accent-brand text-[12px] font-medium disabled:opacity-40">
                  {busy === "handoff" ? <Loader2 size={12} className="animate-spin" /> : <Send size={12} aria-hidden />} Hand off to ClinCase
                </button>
                <span className="text-[11px] text-ink-muted">
                  Requires a clinician to accept or investigate first. Creates a ClinCase case; the 7-agent pipeline runs from the case page.
                </span>
              </div>
            )}
          </div>
          {err && <div className="text-[12px] text-accent-red">{err}</div>}
        </div>
      )}
    </div>
  );
}

// =============================================================================
// Audit trail
// =============================================================================

export function AuditPanel({ pid, refreshKey }: { pid: string; refreshKey: number }) {
  const [rows, setRows] = useState<LedgerEntry[]>([]);
  const [ver, setVer] = useState<{ valid: boolean; entries: number } | null>(null);
  useEffect(() => {
    ot.audit(pid).then((r) => { setRows(r.entries); setVer(r.verification); }).catch(() => undefined);
  }, [pid, refreshKey]);
  return (
    <div>
      {ver && (
        <div className="text-[11.5px] mb-2 inline-flex items-center gap-1.5">
          <ShieldCheck size={13} aria-hidden /> Hash chain {ver.valid ? "verified" : "BROKEN"} · {ver.entries} entries in this
          organisation's ledger (SHA-256; each entry includes the previous entry's hash)
        </div>
      )}
      <ol className="max-h-80 overflow-auto space-y-1 pr-1">
        {rows.map((e) => (
          <li key={e.id} className="text-[11px] border-b border-surface-border/60 pb-1">
            <div className="flex flex-wrap gap-x-2">
              <span className="text-mono-tech text-ink-muted">#{e.seq}</span>
              <b className="uppercase text-[10px] text-compact">{e.kind.replace(/_/g, " ")}</b>
              <span className="text-ink-muted">{e.created_at.slice(0, 19).replace("T", " ")}Z · {e.actor}</span>
            </div>
            <div className="text-ink-body">{summarise(e)}</div>
            <div className="text-mono-tech text-[9.5px] text-ink-faint inline-flex items-center gap-1">
              <Hash size={9} aria-hidden />{e.hash.slice(0, 20)}… ← {e.prev_hash.slice(0, 12)}…
              {e.persisted === false ? " · in-process only (no DB)" : e.persisted ? " · persisted" : ""}
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}

function summarise(e: LedgerEntry): string {
  const p = e.payload as Record<string, unknown>;
  switch (e.kind) {
    case "evaluation":
      return `Day ${p.as_of_day}: ${p.tier} (risk ${pct(p.risk as number, 1)}) · model ${(p.model as { version: string }).version} · inputs ${String(p.input_sha256).slice(0, 10)}… · ${p.trigger}`;
    case "alert": return `ALERT ${p.alert_id}: ${p.previous_tier} → ${p.tier} (${pct(p.risk as number, 1)})`;
    case "alert_action": return `${p.action} on ${p.alert_id}${p.note ? ` — “${p.note}”` : ""}`;
    case "handoff": return `ClinCase case ${p.case_id} for ${p.requested_treatment} (${p.policy_sections_matched} policy sections matched)`;
    case "demo_injection": return `DEMO CONTROL: ${p.label} (from Day ${p.effective_from_day}; past data unchanged: ${p.past_data_unchanged})`;
    case "ingest": return `Ingested ${p.accepted} observation(s), rejected ${p.rejected}`;
    default: return String(p.notice ?? e.kind);
  }
}

// =============================================================================
// Replay bar
// =============================================================================

export function ReplayBar({ asOf, live, moments, playing, onSeek, onPlay, onLive }: {
  asOf: number; live: number; moments: KeyMoment[]; playing: boolean;
  onSeek: (d: number) => void; onPlay: () => void; onLive: () => void;
}) {
  return (
    <div className="rounded-xl border border-surface-border bg-surface-raised p-3">
      <div className="flex items-center gap-3 flex-wrap">
        <button type="button" onClick={onPlay} aria-label={playing ? "Pause replay" : "Play replay"}
          className="w-8 h-8 rounded-full bg-accent-brand text-ink-invert inline-flex items-center justify-center">
          {playing ? <Pause size={14} aria-hidden /> : <Play size={14} aria-hidden />}
        </button>
        <div className="text-[12px]">
          <span className="text-compact text-[10px] text-ink-muted">TIME TRAVEL</span>
          <div className="text-mono-tech">Day {asOf} / {live}</div>
        </div>
        <input type="range" min={1} max={live} value={asOf} onChange={(e) => onSeek(Number(e.target.value))}
          className="flex-1 min-w-[160px]" aria-label="Replay day" />
        <button type="button" onClick={onLive} disabled={asOf === live}
          className="text-[11px] px-2 py-1 rounded border border-surface-border inline-flex items-center gap-1 disabled:opacity-40">
          <Radio size={11} aria-hidden /> Live
        </button>
      </div>
      <div className="mt-2 flex flex-wrap gap-1.5">
        {moments.filter((m) => m.day <= live).map((m, i) => (
          <button key={i} type="button" onClick={() => onSeek(m.day)} title={m.text}
            className={clsx("text-[10.5px] px-2 py-0.5 rounded border",
              m.day === asOf ? "border-accent-brand bg-accent-brand/10" : "border-surface-border text-ink-body")}>
            D{m.day} · {m.text.length > 42 ? `${m.text.slice(0, 40)}…` : m.text}
          </button>
        ))}
      </div>
    </div>
  );
}

export function RiskSpark({ series }: { series: { day: number; risk: number }[] }) {
  const xs = series.map((s) => s.day);
  return (
    <TimeChart compact height={54} ariaLabel="21-day risk history" xDomain={[xs[0] ?? 1, xs.at(-1) ?? 1]}
      yDomain={[0, Math.max(0.1, ...series.map((s) => s.risk)) * 1.1]} format={(v) => `${Math.round(v * 100)}%`}
      lines={[{ key: "r", label: "risk", x: xs, y: series.map((s) => s.risk), weight: 1.75 }]} />
  );
}
