/**
 * OncoTwin 2.0 panels — Living Twin State, WHAT CHANGED, WHY NOW, change points, cross-signal
 * correlation, multi-horizon risk, trajectory dynamics, Twin Memory, conflicts/consistency,
 * uncertainty + readiness, Patient State Graph, Show-your-work, what-if builder, counterfactual
 * twin, clinical-loop intervention recorder, feature store, safety-gated explanation.
 *
 * Monochrome by design (same tokens as panels.tsx): severity is carried by marker shape and
 * weight, never by hue alone. Every number shown comes from the API — nothing is typed in.
 */
import clsx from "clsx";
import { ChevronDown, ChevronRight, CircleDot, Loader2, Play, ShieldCheck, ShieldX } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { ot } from "./api";
import { Legend, TimeChart } from "./charts";
import { pct } from "./panels";
import type { Tier } from "./types";
import type { Counterfactual, Dim, GEdge, GNode, Graph, Intel, Json, ScenarioParams, Severity, Transition, WhatIf } from "./types2";

const BTN = "inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md border border-surface-border bg-surface-raised text-[12px] text-ink-body hover:border-accent-brand/60 disabled:opacity-40 focus:outline-none focus:ring-2 focus:ring-accent-brand";
const TH = "text-left px-2 py-1 font-medium text-ink-muted text-[10.5px]";
const TD = "px-2 py-1 align-top";
const INPUT = "rounded border border-surface-border bg-surface-bg px-2 py-1";

export function SevMark({ s, size = 10 }: { s: Severity; size?: number }) {
  const label = { normal: "normal", attention: "needs attention", alert: "alert" }[s];
  return (
    <svg width={size} height={size} viewBox="0 0 10 10" role="img" aria-label={label} className="shrink-0 text-ink-primary">
      {s === "normal" && <circle cx="5" cy="5" r="3.6" fill="none" stroke="currentColor" strokeWidth="1.2" />}
      {s === "attention" && <><circle cx="5" cy="5" r="3.6" fill="none" stroke="currentColor" strokeWidth="1.2" /><path d="M5 1.4a3.6 3.6 0 0 1 0 7.2z" fill="currentColor" /></>}
      {s === "alert" && <rect x="1.8" y="1.8" width="6.4" height="6.4" fill="currentColor" transform="rotate(45 5 5)" />}
    </svg>
  );
}

export function Chip({ children, strong = false }: { children: React.ReactNode; strong?: boolean }) {
  return <span className={clsx("inline-flex items-center text-[10px] px-1.5 py-0.5 rounded border whitespace-nowrap",
    strong ? "border-ink-primary text-ink-primary font-semibold" : "border-surface-border text-ink-muted")}>{children}</span>;
}

export function Note({ children }: { children: React.ReactNode }) {
  return <p className="text-[10.5px] text-ink-muted mt-2 leading-snug">{children}</p>;
}

export function KV({ label, v }: { label: string; v: React.ReactNode }) {
  return (
    <div className="rounded-md border border-surface-border px-2.5 py-1.5">
      <div className="text-[9.5px] text-compact text-ink-faint">{label}</div>
      <div className="text-ink-body leading-snug">{v}</div>
    </div>
  );
}

function Collapsible({ title, children, defaultOpen = false }: { title: string; children: React.ReactNode; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="border border-surface-border rounded-lg">
      <button type="button" onClick={() => setOpen((o) => !o)} aria-expanded={open}
        className="w-full flex items-center gap-1.5 px-3 py-2 text-[12px] font-medium text-ink-primary">
        {open ? <ChevronDown size={13} aria-hidden /> : <ChevronRight size={13} aria-hidden />} {title}
      </button>
      {open && <div className="px-3 pb-3">{children}</div>}
    </div>
  );
}

const fmt = (v: unknown): string => {
  if (v == null) return "—";
  if (typeof v === "number") return Number.isInteger(v) ? String(v) : v.toFixed(Math.abs(v) < 1 ? 3 : 2);
  if (typeof v === "boolean") return v ? "yes" : "no";
  if (Array.isArray(v)) return v.map(fmt).join(", ");
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
};
const signed = (v: number, d = 2) => `${v > 0 ? "+" : ""}${v.toFixed(d)}`;

// =============================================================================
// Living Twin State (19 dimensions)
// =============================================================================

const GROUPS: [string, string[]][] = [
  ["Static clinical", ["demographic", "cancer", "pathology", "genomic"]],
  ["Clinical & treatment", ["clinical", "treatment", "medication", "laboratory", "adherence", "intervention"]],
  ["Dynamic (vs personal baseline)", ["physiological", "symptom", "activity", "sleep", "nutrition_recovery"]],
  ["Twin assessment", ["risk", "trajectory", "uncertainty", "data_quality"]],
];

export function StatePanel({ intel }: { intel: Intel }) {
  const [pick, setPick] = useState<string | null>(null);
  const dims = intel.state.dimensions;
  const d: Dim | null = pick ? dims[pick] ?? null : null;
  return (
    <div className="grid gap-3 lg:grid-cols-[1.6fr_1fr]">
      <div className="space-y-3">
        {GROUPS.map(([g, keys]) => (
          <div key={g}>
            <div className="text-[10px] text-compact text-ink-faint mb-1">{g}</div>
            <div className="grid gap-1.5 sm:grid-cols-2 xl:grid-cols-3">
              {keys.filter((k) => dims[k]).map((k) => {
                const x = dims[k];
                return (
                  <button type="button" key={k} onClick={() => setPick(k)} aria-pressed={pick === k}
                    className={clsx("text-left rounded-lg border px-2.5 py-2 bg-surface-bg hover:border-accent-brand/60 focus:outline-none focus:ring-2 focus:ring-accent-brand",
                      pick === k ? "border-accent-brand" : x.severity === "alert" ? "border-ink-primary" : "border-surface-border")}>
                    <div className="flex items-center gap-1.5">
                      <SevMark s={x.severity} />
                      <span className="text-[10px] text-compact text-ink-muted">{k.replace(/_/g, " ")}</span>
                      {x.basis.startsWith("model") && <Chip>model</Chip>}
                    </div>
                    <div className={clsx("text-[12px] leading-snug mt-0.5", x.severity !== "normal" ? "text-ink-primary font-semibold" : "text-ink-body")}>
                      {x.status}
                    </div>
                    {x.pending && <div className="text-[10px] text-ink-muted mt-0.5">today meets “{x.pending.status}” (held)</div>}
                  </button>
                );
              })}
            </div>
          </div>
        ))}
        <Note>State SHA-256 {intel.state.sha256.slice(0, 16)}… · as of {intel.state.as_of_time.slice(0, 10)} (Day {intel.state.day}).
          A status changes only on a real category change; milder changes are confirmed after 2 days and the day's raw value is kept as “held”.</Note>
      </div>
      <div className="rounded-lg border border-surface-border p-3 bg-surface-bg min-h-[220px]" aria-live="polite">
        {!d ? <div className="text-[12px] text-ink-muted">Select a dimension to inspect its evidence, basis, confidence and sources.</div> : (
          <div className="space-y-2 text-[12px]">
            <div className="flex items-center gap-2 flex-wrap"><SevMark s={d.severity} size={12} />
              <b className="text-ink-primary">{pick?.replace(/_/g, " ")}</b><Chip>{d.basis}</Chip></div>
            <div className="text-ink-primary">{d.status}</div>
            <div className="text-[11px] text-ink-muted">confidence {d.confidence == null ? "—" : pct(d.confidence)} · data quality:{" "}
              {Array.isArray(d.data_quality) ? d.data_quality.join("; ") : d.data_quality}</div>
            {d.pending && <div className="text-[11px] text-ink-muted">{d.pending.note}</div>}
            <table className="w-full text-[11px]"><tbody>
              {Object.entries(d.fields ?? {}).slice(0, 16).map(([k, v]) => (
                <tr key={k} className="border-t border-surface-border/60"><td className="py-0.5 pr-2 text-ink-muted align-top">{k.replace(/_/g, " ")}</td>
                  <td className="py-0.5 text-ink-body nums-tabular break-all">{fieldText(v)}</td></tr>
              ))}
            </tbody></table>
            <div>
              <div className="text-[10px] text-compact text-ink-faint">Sources</div>
              {d.sources.length === 0 ? <div className="text-[11px] text-ink-muted">derived (no direct resource)</div> :
                d.sources.map((s, i) => {
                  const ids = s.ids ?? (s.code ? [s.code] : []);
                  return <div key={i} className="text-[10.5px] text-mono-tech text-ink-body break-all">{s.type}: {ids.slice(0, 6).join(", ")}{ids.length > 6 ? ` +${ids.length - 6}` : ""}</div>;
                })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function fieldText(v: unknown): string {
  // Collapse the common nested shapes (lists of {label, …}, maps of {label, value}) into readable text.
  if (Array.isArray(v) && v.length && typeof v[0] === "object" && v[0] !== null) {
    return v.map((o: Json) => [o.label ?? o.display ?? o.signal ?? o.kind, o.z3 ?? o.value ?? o.day].filter((x) => x != null).join(" ")).join("; ");
  }
  if (v && typeof v === "object" && !Array.isArray(v)) {
    return Object.entries(v as Record<string, Json>).map(([k, o]) =>
      o && typeof o === "object" ? `${o.label ?? k}: ${fmt(o.value ?? o)}` : `${k.replace(/_/g, " ")} ${fmt(o)}`).join("; ");
  }
  return fmt(v);
}

export function WhatChangedPanel({ wc }: { wc: Json }) {
  return (
    <div>
      <div className="text-[13px] text-ink-primary font-semibold">{wc.headline}</div>
      <div className="text-[11px] text-ink-muted">Previous twin state Day {wc.from_day} (…{String(wc.from_sha256).slice(0, 8)}) → current Day {wc.to_day} (…{String(wc.to_sha256).slice(0, 8)})</div>
      <ul className="mt-2 space-y-1.5">
        {wc.changed.map((c: Json) => (
          <li key={c.dimension} className="flex gap-2 text-[12px]">
            <span className="mt-1"><SevMark s={c.severity} /></span>
            <div className="min-w-0">
              <div><b className="text-ink-primary">{c.label}</b>: <span className="text-ink-muted">{c.previous}</span> → <span className="text-ink-primary">{c.current}</span>
                <span className="text-[10.5px] text-ink-muted"> · {c.direction}</span></div>
              <div className="text-[11px] text-ink-muted">{c.reason}</div>
            </div>
          </li>
        ))}
      </ul>
      {wc.changed.length === 0 && <div className="text-[12px] text-ink-muted mt-1">The twin's state is unchanged over this window.</div>}
    </div>
  );
}

export function TransitionLedger({ rows }: { rows: Transition[] }) {
  if (!rows.length) return <div className="text-[12px] text-ink-muted">No state transitions recorded yet.</div>;
  return (
    <div className="max-h-80 overflow-auto border border-surface-border rounded-md">
      <table className="w-full text-[11px]">
        <thead className="sticky top-0 bg-surface-panel"><tr>
          <th className={TH}>Day</th><th className={TH}>Dimension</th><th className={TH}>Previous → new</th><th className={TH}>Reason for change</th>
          <th className={TH}>Conf.</th><th className={TH}>Sources</th></tr></thead>
        <tbody>
          {[...rows].reverse().map((t, i) => (
            <tr key={i} className="border-t border-surface-border/60">
              <td className={clsx(TD, "text-mono-tech")}>D{t.day}</td>
              <td className={TD}><span className="inline-flex items-center gap-1"><SevMark s={t.severity} size={9} />{t.label}</span></td>
              <td className={TD}><span className="text-ink-muted">{t.previous}</span> → <b className="text-ink-primary">{t.new}</b></td>
              <td className={clsx(TD, "text-ink-body")}>{t.reason}</td>
              <td className={clsx(TD, "nums-tabular")}>{t.confidence == null ? "—" : pct(t.confidence)}</td>
              <td className={clsx(TD, "text-mono-tech text-[10px] text-ink-muted")}>{t.sources.map((s) => `${s.type}×${s.ids?.length ?? 0}`).join(" ") || "computed"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// =============================================================================
// WHY NOW + Show your work
// =============================================================================

export function WhyNowPanel({ w, readiness }: { w: Json; readiness: Json }) {
  return (
    <div className="space-y-3">
      <div className="rounded-lg border border-ink-primary/60 p-3 bg-surface-bg">
        <div className="text-[10px] text-compact text-ink-muted">WHY NOW?</div>
        <ul className="text-[12.5px] text-ink-primary list-disc ml-4">{w.triggers.map((t: string) => <li key={t}>{t}</li>)}</ul>
      </div>
      <div>
        <div className="text-[11px] text-ink-muted mb-1">Compared with this patient's own baseline</div>
        {w.compared_with_baseline.length === 0 ? <div className="text-[12px] text-ink-muted">No signal beyond 1.5 SD of the personal baseline.</div> : (
          <div className="overflow-x-auto"><table className="w-full text-[12px]">
            <thead><tr><th className={TH}>Signal</th><th className={TH}>Change</th><th className={TH}>SD</th><th className={TH}>3-day mean</th>
              <th className={TH}>Baseline</th><th className={TH}>Persistence</th><th className={TH}>Model contribution</th></tr></thead>
            <tbody>{w.compared_with_baseline.map((v: Json) => (
              <tr key={v.signal} className="border-t border-surface-border/60">
                <td className={TD}>{v.label}</td><td className={clsx(TD, "font-semibold text-ink-primary nums-tabular whitespace-nowrap")}>{v.change}</td>
                <td className={clsx(TD, "nums-tabular")}>{v.z_sd?.toFixed(1)}</td>
                <td className={clsx(TD, "nums-tabular whitespace-nowrap")}>{fmt(v.recent_3d_mean)} {v.unit}</td>
                <td className={clsx(TD, "nums-tabular whitespace-nowrap")}>{fmt(v.baseline_median)} {v.unit}</td>
                <td className={clsx(TD, "nums-tabular whitespace-nowrap")}>{v.persistence_days} d{v.onset_day ? ` (since D${v.onset_day})` : ""}</td>
                <td className={clsx(TD, "nums-tabular whitespace-nowrap")}>{signed(v.model_contribution_logit)} log-odds</td>
              </tr>))}</tbody>
          </table></div>
        )}
      </div>
      <div className="grid gap-2 md:grid-cols-2 text-[12px]">
        <KV label="Temporal persistence" v={`${w.persistence.episode_days} day(s) since ${w.persistence.episode_basis} · ${w.persistence.trajectory_dynamics}`} />
        <KV label="Treatment context" v={w.treatment_context.text} />
        <KV label="Model" v={`${w.model.model_id} v${w.model.version} · ${w.model.outcome_id}, ${w.model.horizon_days}-day horizon · artifact ${String(w.model.artifact_sha256).slice(0, 10)}…${w.model.integrity_verified ? " (verified)" : " (UNVERIFIED)"}`} />
        <KV label="Confidence" v={`${pct(w.confidence.risk, 1)} (80% interval ${pct(w.confidence.p10, 1)}–${pct(w.confidence.p90, 1)}) · ${w.confidence.label}`} />
        <KV label="Data quality" v={`${w.data_quality.status} · 7-day completeness ${pct(w.data_quality.completeness_7d)}`} />
        <KV label="Twin readiness" v={`${pct(readiness.score)} (${readiness.label}); limited by ${String(readiness.limiting_factor).replace(/_/g, " ")}`} />
      </div>
      {w.persistence.change_point && <div className="text-[12px] text-ink-body border-l-2 border-ink-primary pl-2">{w.persistence.change_point.statement}</div>}
      {[...w.data_quality.flags, ...w.data_quality.uncertainty].map((s: string) => <div key={s} className="text-[11.5px] text-ink-body">⚠ {s}</div>)}
      <Note>{w.language_note}</Note>
    </div>
  );
}

export function ShowYourWork({ sw }: { sw: Json }) {
  return (
    <Collapsible title="Show your work: model version, inputs, assumptions, uncertainty">
      <div className="grid gap-2 md:grid-cols-2 text-[11.5px]">
        <KV label="Deterioration model" v={`${sw.model.model_id} v${sw.model.version} · sha256 ${String(sw.model.artifact_sha256).slice(0, 16)}…`} />
        <KV label="Horizon model" v={sw.horizon_model ? `${sw.horizon_model.model_id} v${sw.horizon_model.version} · sha256 ${String(sw.horizon_model.artifact_sha256).slice(0, 16)}…` : "not loaded"} />
        <KV label="Inputs" v={`${sw.n_inputs} observations/events, Days ${sw.feature_window_days[0]}–${sw.feature_window_days[1]} · SHA-256 ${String(sw.input_sha256).slice(0, 16)}…`} />
        <KV label="Uncertainty (80% widths)" v={Object.entries(sw.uncertainty).map(([k, v]) => `${k.replace(/_/g, " ")} ${pct(v as number, 1)}`).join(" · ")} />
      </div>
      <div className="mt-2 max-h-56 overflow-auto border border-surface-border rounded-md">
        <table className="w-full text-[11px]"><thead className="sticky top-0 bg-surface-panel"><tr><th className={TH}>Input signal</th><th className={TH}>Readings (day · value · observation id)</th></tr></thead>
          <tbody>{sw.input_signals.map((s: Json) => (
            <tr key={s.signal} className="border-t border-surface-border/60"><td className={TD}>{s.label}</td>
              <td className={clsx(TD, "text-mono-tech text-[10.5px]")}>{s.readings.map((r: Json) => `D${r.day} ${r.value ?? "missing"}${r.id ? ` · ${r.id}` : ""}`).join("  |  ")}</td></tr>))}</tbody></table>
      </div>
      <ul className="mt-2 text-[11px] text-ink-body list-disc ml-4">{sw.assumptions.map((a: string) => <li key={a}>{a}</li>)}</ul>
      <Note>Timeline evidence: Days {sw.timeline.from_day}–{sw.timeline.to_day} (multimodal timeline on the Digital Twin tab).</Note>
    </Collapsible>
  );
}

// =============================================================================
// Trajectory intelligence
// =============================================================================

export function TrajectoryNarrative({ tr }: { tr: Json }) {
  return (
    <div>
      <div className="flex flex-wrap items-baseline gap-2"><b className="text-[14px] text-ink-primary">{tr.dynamics}</b>
        <span className="text-[11.5px] text-ink-muted">{tr.explanation}</span></div>
      <ol className="mt-2 grid grid-cols-4 md:grid-cols-8 gap-1">
        {tr.narrative.map((n: Json) => (
          <li key={n.day} className={clsx("rounded-md border px-1.5 py-1", n.offset === "Today" ? "border-ink-primary" : "border-surface-border")}>
            <div className="text-[10px] text-mono-tech text-ink-muted">{n.offset}</div>
            <div className={clsx("text-[11px] leading-tight", n.label === "Stable" ? "text-ink-muted" : "text-ink-primary font-semibold")}>{n.label}</div>
            <div className="text-[10px] nums-tabular text-ink-muted">{pct(n.risk, 1)} · {n.tier}</div>
          </li>))}
      </ol>
      <Note>Slope {tr.slope_logit_per_day} log-odds/day, acceleration {tr.acceleration}. {tr.method}</Note>
    </div>
  );
}

export function ChangePointPanel({ cp }: { cp: Json }) {
  const marks = cp.change_points.filter((p: Json) => p.significance === "significant")
    .map((p: Json) => ({ x: p.day, label: `CP D${p.day}`, kind: "event" as const }));
  return (
    <div>
      <TimeChart ariaLabel="Posterior probability of a regime change within the last 3 days" height={150}
        xDomain={[cp.days[0] ?? 1, Math.max(2, cp.days.at(-1) ?? 2)]} yDomain={[0, 1]}
        lines={[{ key: "p", label: "P(change in last 3 d)", x: cp.days, y: cp.p_change_last_3d, weight: 1.6 }]} vmarks={marks}
        format={(v) => v.toFixed(2)} />
      <ul className="mt-2 space-y-2">
        {cp.change_points.slice().reverse().map((p: Json) => (
          <li key={p.day} className={clsx("text-[12px] border-l-2 pl-2", p.significance === "significant" ? "border-ink-primary" : "border-surface-border-hi")}>
            <div className="flex flex-wrap items-center gap-1.5"><b className="text-ink-primary">Day {p.day}</b><Chip strong={p.significance === "significant"}>{p.significance}</Chip>
              <Chip>{p.kind}</Chip>{p.expected_treatment_effect && <Chip>coincides with chemotherapy</Chip>}
              <span className="text-[10.5px] text-ink-muted">posterior {pct(p.posterior_mass)} · confirmed D{p.detected_on_day} · joint shift {p.joint_shift_sd} SD</span></div>
            <div className="text-ink-body">{p.statement}</div>
          </li>))}
        {cp.change_points.length === 0 && <li className="text-[12px] text-ink-muted">No regime change detected in this patient's signals.</li>}
      </ul>
      <Note>{cp.algorithm.reference} · hazard 1/{cp.algorithm.hazard_lambda_days} days · {cp.language_note}</Note>
    </div>
  );
}

export function HorizonPanel({ hz }: { hz: Json }) {
  if (!hz || hz.available === false || !hz.horizons) return <div className="text-[12px] text-ink-muted">{hz?.reason ?? "Horizon model unavailable."}</div>;
  return (
    <div>
      <div className="overflow-x-auto"><table className="w-full text-[12px]">
        <thead><tr><th className={TH}>Horizon</th><th className={TH}>Risk (80% interval)</th><th className={TH}>Supported?</th><th className={TH}>Held-out AUROC (95% CI)</th></tr></thead>
        {hz.horizons.map((h: Json) => (
          <tbody key={h.horizon} className="border-t border-surface-border/60">
            <tr>
              <td className={clsx(TD, "font-semibold whitespace-nowrap")}>{h.horizon}</td>
              <td className={clsx(TD, "nums-tabular whitespace-nowrap")}>{h.risk == null ? "—" : `${pct(h.risk, 1)} (${pct(h.p10, 1)}–${pct(h.p90, 1)})`}</td>
              <td className={clsx(TD, h.supported ? "" : "font-semibold")}>{h.supported ? "yes" : "no"}</td>
              <td className={clsx(TD, "nums-tabular whitespace-nowrap")}>{h.test_auroc == null ? "—" : `${h.test_auroc.toFixed(3)} (${h.test_auroc_95ci?.[0]?.toFixed(3)}–${h.test_auroc_95ci?.[1]?.toFixed(3)})`}</td>
            </tr>
            <tr><td colSpan={4} className="px-2 pb-1.5 text-[10.5px] text-ink-muted">{h.reason}</td></tr>
          </tbody>))}
      </table></div>
      {hz.agreement_with_primary && <Note>7-day agreement with the primary OT-ACUTE-7 model: {pct(hz.agreement_with_primary.primary_lr_7d, 1)} vs {pct(hz.agreement_with_primary.survival_7d, 1)}. {hz.agreement_with_primary.note}</Note>}
      <Note>{hz.method}. Metrics are from a held-out synthetic cohort.</Note>
    </div>
  );
}

export function CorrelationPanel({ co }: { co: Json }) {
  const rows = co.signals.filter((r: Json) => r.recent_3d_mean != null);
  const assoc = [...co.temporal_order, ...co.lead_lag, ...co.coupling] as Json[];
  return (
    <div>
      <div className={clsx("text-[13px]", co.n_deviating >= 3 ? "font-semibold text-ink-primary" : "text-ink-body")}>{co.headline}</div>
      <div className="text-[11.5px] text-ink-muted">{co.summary} Window Days {co.window.start_day}–{co.window.end_day} ({co.window.basis}).</div>
      <div className="mt-2 overflow-auto"><table className="w-full text-[11.5px]">
        <thead><tr><th className={TH}>Signal</th><th className={TH}>Direction</th><th className={TH}>Magnitude</th><th className={TH}>SD vs baseline</th>
          <th className={TH}>Baseline (range)</th><th className={TH}>Time window</th><th className={TH}>Model contribution</th></tr></thead>
        <tbody>{rows.map((r: Json) => (
          <tr key={r.signal} className={clsx("border-t border-surface-border/60", r.deviating_adversely && "font-semibold text-ink-primary")}>
            <td className={TD}>{r.label}</td>
            <td className={TD}>{r.direction}{r.deviating_adversely ? " (adverse)" : ""}</td>
            <td className={clsx(TD, "nums-tabular whitespace-nowrap")}>{r.pct_vs_baseline != null ? `${r.pct_vs_baseline > 0 ? "+" : ""}${r.pct_vs_baseline}%` : `${r.delta > 0 ? "+" : ""}${fmt(r.delta)} ${r.unit}`}</td>
            <td className={clsx(TD, "nums-tabular")}>{r.z_adverse_3d == null ? "—" : r.z_adverse_3d.toFixed(1)}</td>
            <td className={clsx(TD, "nums-tabular whitespace-nowrap")}>{r.baseline_median} ({r.baseline_range?.[0]}–{r.baseline_range?.[1]})</td>
            <td className={TD}>{r.time_window ?? "—"}</td>
            <td className={clsx(TD, "nums-tabular")}>{signed(r.model_contribution_logit)}</td>
          </tr>))}</tbody></table></div>
      {assoc.length > 0 && <ul className="mt-2 text-[11.5px] text-ink-body list-disc ml-4">{assoc.map((x) => <li key={x.text}>{x.text}</li>)}</ul>}
      <Note>{co.language_note}</Note>
    </div>
  );
}

const CYCLE_DASH = ["", "5 3", "2 3", "8 3 2 3"];

export function MemoryPanel({ mem }: { mem: Json }) {
  const cycles = mem.cycles as Json[];
  const maxLen = Math.max(2, ...cycles.map((c) => c.msdi.curve.length));
  return (
    <div className="space-y-3">
      {cycles.length > 0 ? (
        <>
          <TimeChart ariaLabel="Multi-signal deterioration index by day of cycle, one line per cycle" height={160} xDomain={[1, maxLen]}
            lines={cycles.map((c, i) => ({ key: `c${c.cycle}`, label: `Cycle ${c.cycle}${c.complete ? "" : " (current)"}`,
              x: c.msdi.curve.map((_: unknown, j: number) => j + 1), y: c.msdi.curve, dash: CYCLE_DASH[i % CYCLE_DASH.length],
              weight: c.complete ? 1.5 : 2.4, directLabel: true }))} format={(v) => v.toFixed(1)} />
          <div className="text-[10.5px] text-ink-muted -mt-1">x = day of cycle (“D” labels), y = multi-signal deterioration index.</div>
          <div className="overflow-x-auto"><table className="w-full text-[11.5px]">
            <thead><tr><th className={TH}>Cycle</th><th className={TH}>Days</th><th className={TH}>Index peak (day of cycle)</th><th className={TH}>Recovery</th>
              <th className={TH}>Recovery velocity</th><th className={TH}>ANC nadir (lab)</th><th className={TH}>G-CSF</th></tr></thead>
            <tbody>{cycles.map((c) => (
              <tr key={c.cycle} className="border-t border-surface-border/60">
                <td className={TD}>{c.cycle}{c.complete ? "" : " (current)"}</td><td className={clsx(TD, "whitespace-nowrap")}>D{c.start_day}–{c.end_day}</td>
                <td className={clsx(TD, "nums-tabular")}>{fmt(c.msdi.peak)} (day {c.msdi.peak_day_of_cycle ?? "—"})</td>
                <td className={TD}>{c.msdi.status}{c.msdi.half_recovery_days != null ? ` · half-recovery ${c.msdi.half_recovery_days} d` : ""}</td>
                <td className={clsx(TD, "nums-tabular")}>{c.msdi.velocity_sd_per_day == null ? "—" : `${c.msdi.velocity_sd_per_day} SD/day`}</td>
                <td className={clsx(TD, "nums-tabular")}>{c.anc_nadir_lab ? `${c.anc_nadir_lab.value} (day ${c.anc_nadir_lab.day_of_cycle})` : "—"}</td>
                <td className={TD}>{c.gcsf_in_cycle ? "yes" : "no"}</td>
              </tr>))}</tbody>
          </table></div>
        </>) : <div className="text-[12px] text-ink-muted">No chemotherapy cycle has started yet: nothing to remember.</div>}
      {mem.similarity.map((s: Json) => <div key={s.compared_with_cycle} className="text-[12px]"><b className="text-ink-primary">{s.text}</b> <span className="text-ink-muted">{s.previous_course}</span></div>)}
      {mem.episodes.length > 0 && (
        <div className="text-[11.5px]"><div className="text-ink-muted">Remembered deterioration episodes</div>
          <ul className="list-disc ml-4">{mem.episodes.map((e: Json) => (
            <li key={e.start_day}>Day {e.start_day}–{e.end_day ?? "now"}: peak {e.peak_tier} ({pct(e.peak_risk, 0)}) on Day {e.peak_day}; {e.resolution}
              {e.interventions.length ? ` · interventions: ${e.interventions.map((i: Json) => `${i.display} (D${i.day})`).join("; ")}` : ""}</li>))}</ul></div>)}
      <Note>{mem.notes.join(" ")}</Note>
    </div>
  );
}

export function ConflictsPanel({ conflicts, consistency }: { conflicts: Json[]; consistency: Json }) {
  const warn = conflicts.some((c) => c.detected && c.severity === "warning");
  return (
    <div className="grid gap-3 md:grid-cols-2">
      <div>
        <div className="text-[12px] font-semibold text-ink-primary">{warn ? "Trajectory conflict detected: review the underlying data." : "No trajectory conflict."}</div>
        <ul className="mt-1 space-y-1 text-[11.5px]">{conflicts.map((c) => (
          <li key={c.id} className="flex gap-1.5"><span className="mt-0.5"><SevMark s={c.detected ? (c.severity === "warning" ? "alert" : "attention") : "normal"} /></span>
            <span><b>{c.title}</b>{c.detected ? <>: <span className="text-ink-body">{c.text}</span></> : <span className="text-ink-muted"> (consistent)</span>}</span></li>))}</ul>
      </div>
      <div>
        <div className="text-[12px] font-semibold text-ink-primary">{consistency.summary}</div>
        <ul className="mt-1 space-y-1 text-[11.5px]">{consistency.checks.map((c: Json) => (
          <li key={c.id} className="flex gap-1.5"><span className="mt-0.5"><SevMark s={c.status === "fail" ? "alert" : c.status === "warn" ? "attention" : "normal"} /></span>
            <span><b>{c.title}</b> <span className={c.status === "pass" ? "text-ink-muted" : "text-ink-body"}>: {c.text}</span></span></li>))}</ul>
      </div>
    </div>
  );
}

export function UncertaintyPanel({ u, rd }: { u: Json; rd: Json }) {
  const comps = Object.entries(u.components) as [string, Json][];
  const maxW = Math.max(0.001, ...comps.map(([, c]) => c.width_80));
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <div>
        <div className="text-[11px] text-ink-muted mb-1">Uncertainty decomposition (80% width of the {u.horizon_days}-day risk {pct(u.risk, 1)})</div>
        {comps.map(([k, c]) => (
          <div key={k} className="mb-1.5">
            <div className="flex justify-between text-[11.5px] gap-2"><span className={k === u.dominant_source ? "font-semibold text-ink-primary" : ""}>{k.replace(/_/g, " ")}{k === u.dominant_source ? " (dominant)" : ""}</span>
              <span className="nums-tabular">{pct(c.width_80, 1)} · {pct(c.range[0], 1)}–{pct(c.range[1], 1)}</span></div>
            <div className="h-1.5 bg-surface-panel rounded" aria-hidden><div className="h-1.5 bg-ink-primary rounded" style={{ width: `${(100 * c.width_80) / maxW}%` }} /></div>
            <div className="text-[10px] text-ink-muted">{c.method}</div>
          </div>))}
        <div className="text-[11.5px] mt-1">Distribution shift: <b>{u.distribution_shift.ood ? "outside the training range" : "within the training range"}</b> (RMS z {u.distribution_shift.ood_score})</div>
        {u.statements.map((s: string) => <div key={s} className="text-[11.5px] text-ink-primary mt-1">⚠ {s}</div>)}
      </div>
      <div>
        <div className="text-[11px] text-ink-muted mb-1">{rd.name}: <b className="text-ink-primary">{pct(rd.score)}</b> ({rd.label}), limited by {String(rd.limiting_factor).replace(/_/g, " ")}</div>
        {Object.entries(rd.components as Record<string, Json>).map(([k, c]) => (
          <div key={k} className="mb-1.5">
            <div className="flex justify-between text-[11.5px]"><span>{k.replace(/_/g, " ")}</span><span className="nums-tabular">{pct(c.value)}</span></div>
            <div className="h-1.5 bg-surface-panel rounded" aria-hidden><div className="h-1.5 bg-ink-primary rounded" style={{ width: `${100 * c.value}%` }} /></div>
            <div className="text-[10px] text-ink-muted">{c.measure}</div>
          </div>))}
        <Note>{rd.note}</Note>
      </div>
    </div>
  );
}

// =============================================================================
// Patient State Graph
// =============================================================================

const COLS: string[][] = [["clinical"], ["treatment", "intervention"], ["wearable", "home", "symptom", "lab"], ["physiology", "changepoint"], ["risk", "outcome"]];
const EDGE_STYLE: Record<GEdge["kind"], { dash?: string; width: number; opacity: number }> = {
  clinical: { width: 1.4, opacity: 0.8 }, temporal: { dash: "1.5 3", width: 1.3, opacity: 0.7 },
  data: { width: 0.7, opacity: 0.35 }, model: { dash: "6 3", width: 1.3, opacity: 0.75 },
};
const NODE_W = 150;

export function StateGraph({ graph }: { graph: Graph }) {
  const [sel, setSel] = useState<string | null>(null);
  const [kinds, setKinds] = useState<Record<string, boolean>>({ clinical: true, temporal: true, data: false, model: true });
  const W = 980;
  const pos = useMemo(() => {
    const p: Record<string, { x: number; y: number }> = {};
    COLS.forEach((groups, ci) => {
      graph.nodes.filter((n) => groups.includes(n.group))
        .forEach((n, i) => { p[n.id] = { x: 12 + ci * ((W - NODE_W - 24) / (COLS.length - 1)), y: 14 + i * 42 }; });
    });
    return p;
  }, [graph]);
  const H = Math.max(240, ...Object.values(pos).map((v) => v.y + 44));
  const node: GNode | undefined = graph.nodes.find((n) => n.id === sel);
  const related = new Set(sel ? graph.edges.filter((e) => e.source === sel || e.target === sel).flatMap((e) => [e.source, e.target]) : []);
  const labelOf = (id: string) => graph.nodes.find((x) => x.id === id)?.label ?? id;
  return (
    <div className="grid gap-3 xl:grid-cols-[1fr_300px]">
      <div className="min-w-0">
        <div className="flex flex-wrap gap-3 mb-2 text-[11px]">
          {(Object.keys(EDGE_STYLE) as GEdge["kind"][]).map((k) => (
            <label key={k} className="inline-flex items-center gap-1.5 cursor-pointer">
              <input type="checkbox" checked={kinds[k]} onChange={(e) => setKinds((s) => ({ ...s, [k]: e.target.checked }))} />
              <svg width="26" height="8" aria-hidden className="text-ink-primary"><line x1="0" x2="26" y1="4" y2="4" stroke="currentColor" strokeWidth={EDGE_STYLE[k].width + 0.4} strokeDasharray={EDGE_STYLE[k].dash} /></svg>
              {k} ({graph.counts[k] ?? 0}): <span className="text-ink-muted">{graph.edge_kinds[k]}</span>
            </label>))}
        </div>
        <div className="overflow-x-auto border border-surface-border rounded-lg bg-surface-bg">
          <svg width={W} height={H} role="img" aria-label="Patient state graph: facts, measurements, model estimates and their relationships" className="text-ink-primary block">
            {graph.edges.filter((e) => kinds[e.kind] && pos[e.source] && pos[e.target]).map((e, i) => {
              const a = pos[e.source], b = pos[e.target];
              const st = EDGE_STYLE[e.kind];
              const x1 = a.x + NODE_W, y1 = a.y + 15, x2 = b.x, y2 = b.y + 15;
              const d = x2 <= x1
                ? `M${a.x + NODE_W / 2},${a.y + 30} C${a.x + NODE_W / 2},${a.y + 58} ${b.x + NODE_W / 2},${b.y + 58} ${b.x + NODE_W / 2},${b.y + 30}`
                : `M${x1},${y1} C${(x1 + x2) / 2},${y1} ${(x1 + x2) / 2},${y2} ${x2},${y2}`;
              const hi = sel != null && (e.source === sel || e.target === sel);
              return <path key={i} d={d} fill="none" stroke="currentColor" strokeWidth={hi ? st.width + 1 : st.width} strokeDasharray={st.dash}
                opacity={sel ? (hi ? 0.95 : 0.07) : st.opacity}><title>{`${e.kind}: ${labelOf(e.source)} → ${labelOf(e.target)} (${e.label})`}</title></path>;
            })}
            {graph.nodes.filter((n) => pos[n.id]).map((n) => {
              const p = pos[n.id];
              const dim = sel != null && sel !== n.id && !related.has(n.id);
              return (
                <g key={n.id} transform={`translate(${p.x},${p.y})`} onClick={() => setSel(n.id === sel ? null : n.id)}
                  onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setSel(n.id === sel ? null : n.id); } }}
                  tabIndex={0} role="button" aria-pressed={sel === n.id} aria-label={`${n.label}: ${n.status}`}
                  className="cursor-pointer focus:outline-none" opacity={dim ? 0.3 : 1}>
                  <rect width={NODE_W} height="30" rx="6" fill="rgb(var(--surface-raised))" stroke="currentColor"
                    strokeWidth={sel === n.id ? 2.5 : n.severity === "alert" ? 2 : 1} strokeDasharray={n.basis === "model" ? "4 2" : undefined} />
                  <text x="8" y="12.5" fontSize="9.5" className="fill-ink-primary" fontWeight={n.severity !== "normal" ? 700 : 500}>{n.label.slice(0, 26)}</text>
                  <text x="8" y="24" fontSize="8.5" className="fill-ink-muted">{n.status.slice(0, 32)}</text>
                </g>);
            })}
          </svg>
        </div>
        <Note>{graph.note} A dashed node border marks a model-derived estimate; a solid border marks a recorded fact or measurement.</Note>
      </div>
      <div className="rounded-lg border border-surface-border p-3 text-[11.5px] bg-surface-bg" aria-live="polite">
        {!node ? <div className="text-ink-muted">Select a node to inspect its evidence and relationships.</div> : (
          <div className="space-y-1.5">
            <div className="flex items-center gap-1.5 flex-wrap"><SevMark s={node.severity} /><b className="text-ink-primary">{node.label}</b><Chip>{node.basis}</Chip></div>
            <div>{node.status}</div>
            <div className="text-[10px] text-compact text-ink-faint mt-1">Relationships</div>
            <ul className="space-y-0.5">{graph.edges.filter((e) => e.source === node.id || e.target === node.id).slice(0, 16).map((e, i) => (
              <li key={i}><Chip>{e.kind}</Chip> {e.source === node.id ? "→" : "←"} {labelOf(e.source === node.id ? e.target : e.source)}: <span className="text-ink-muted">{e.label}</span></li>))}</ul>
            <div className="text-[10px] text-compact text-ink-faint mt-1">Evidence</div>
            {node.evidence.length === 0 ? <div className="text-ink-muted">computed / model output</div> :
              node.evidence.map((ev: Json, i: number) => (
                <div key={i} className="text-mono-tech text-[10px] break-all">{ev.type}: {(ev.ids ?? (ev.features ? ev.features : [ev.code ?? ""])).slice(0, 6).join(", ")}</div>))}
          </div>)}
      </div>
    </div>
  );
}

// =============================================================================
// What-if builder, counterfactual twin, intervention recorder
// =============================================================================

const SCEN_DASH = ["", "6 3", "2 3", "10 3 2 3", "4 4", "1 2"];
export const SIM_LABEL = "Simulation — not a clinical prediction or treatment recommendation.";

export function ScenarioBuilder({ pid, asOf }: { pid: string; asOf?: number }) {
  const [p, setP] = useState<ScenarioParams>({ label: "Custom scenario", antibiotics_days: 7, next_dose_scale: 1, delay_next_dose_days: 0 });
  const [useCustom, setUseCustom] = useState(true);
  const [res, setRes] = useState<WhatIf | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { setRes(null); }, [pid, asOf]);
  const run = async () => {
    setBusy(true); setErr(null);
    try { setRes(await ot.whatif(pid, { as_of_day: asOf, custom: useCustom ? p : undefined })); }
    catch (e) { setErr((e as Error).message); }
    finally { setBusy(false); }
  };
  const sc = res ? Object.values(res.simulation.scenarios as Record<string, Json>) : [];
  const obs = res?.observed ?? [];
  const xLo = obs.length ? obs[0].day : (asOf ?? 1);
  const xHi = sc.length ? (sc[0].days.at(-1) as number) : xLo + 10;
  const num = (k: keyof ScenarioParams, v: string) => setP((s) => ({ ...s, [k]: v === "" ? undefined : Number(v) }));
  return (
    <div className="space-y-3">
      <div className="text-[11px] px-3 py-1.5 rounded-md border border-dashed border-surface-border-hi">{SIM_LABEL}</div>
      <fieldset className="grid gap-2 md:grid-cols-3 text-[12px] border border-surface-border rounded-lg p-3">
        <legend className="px-1 text-[11px] text-ink-muted">
          <label className="inline-flex gap-1.5 items-center"><input type="checkbox" checked={useCustom} onChange={(e) => setUseCustom(e.target.checked)} /> Custom scenario (compared with the five predefined scenarios)</label>
        </legend>
        <label className="flex flex-col gap-0.5">Label<input className={INPUT} maxLength={80} value={p.label ?? ""} onChange={(e) => setP({ ...p, label: e.target.value })} /></label>
        <label className="flex flex-col gap-0.5">Supportive-medication adherence (0–1; blank = observed)<input type="number" min={0} max={1} step={0.05} className={INPUT} value={p.adherence ?? ""} onChange={(e) => num("adherence", e.target.value)} /></label>
        <label className="flex flex-col gap-0.5">Antibiotics start (days from now; blank = none)<input type="number" min={1} max={10} className={INPUT} value={p.antibiotics_start_day_offset ?? ""} onChange={(e) => num("antibiotics_start_day_offset", e.target.value)} /></label>
        <label className="flex flex-col gap-0.5">Antibiotic course (days)<input type="number" min={1} max={14} className={INPUT} value={p.antibiotics_days ?? ""} onChange={(e) => num("antibiotics_days", e.target.value)} /></label>
        <label className="flex flex-col gap-0.5">IV hydration on days (e.g. 1,2)<input className={INPUT} value={(p.iv_hydration_day_offsets ?? []).join(",")}
          onChange={(e) => setP({ ...p, iv_hydration_day_offsets: e.target.value.split(",").map((x) => Number(x.trim())).filter((x) => Number.isInteger(x) && x >= 1 && x <= 10).slice(0, 5) })} /></label>
        <label className="flex flex-col gap-0.5">Next-dose scale (0.5–1)<input type="number" min={0.5} max={1} step={0.05} className={INPUT} value={p.next_dose_scale ?? ""} onChange={(e) => num("next_dose_scale", e.target.value)} /></label>
        <label className="flex flex-col gap-0.5">Delay next dose (days)<input type="number" min={0} max={7} className={INPUT} value={p.delay_next_dose_days ?? ""} onChange={(e) => num("delay_next_dose_days", e.target.value)} /></label>
        <div className="flex flex-wrap gap-3 items-center md:col-span-2">
          {([["gcsf_tomorrow", "G-CSF tomorrow"], ["gcsf_with_next_cycle", "G-CSF with next cycle"], ["oral_hydration_coaching", "Oral hydration coaching"],
            ["activity_program", "Activity programme"], ["new_infection", "Stress test: new infection"]] as const).map(([k, l]) => (
            <label key={k} className="inline-flex items-center gap-1.5"><input type="checkbox" checked={Boolean(p[k])} onChange={(e) => setP({ ...p, [k]: e.target.checked })} /> {l}</label>))}
        </div>
        <div className="md:col-span-3">
          <button type="button" onClick={run} disabled={busy} className={BTN}>
            {busy ? <Loader2 size={13} className="animate-spin" aria-hidden /> : <Play size={13} aria-hidden />} Run simulation (Monte Carlo, all scenarios)
          </button>
        </div>
      </fieldset>
      {err && <div className="text-[12px] text-accent-red" role="alert">{err}</div>}
      {res && (
        <>
          <TimeChart ariaLabel="Observed risk and simulated risk trajectories per scenario" height={240} xDomain={[xLo, xHi]} yDomain={[0, 1]} shadeAfter={res.as_of_day}
            lines={[{ key: "obs", label: "Observed (as-of)", x: obs.map((o) => o.day), y: obs.map((o) => o.risk), weight: 2.6 },
              ...sc.map((s: Json, i: number) => ({ key: s.key, label: s.label, x: s.days, y: s.risk.median, dash: SCEN_DASH[i % SCEN_DASH.length],
                weight: s.key === "custom" ? 2.4 : 1.3 }))]}
            bands={sc.filter((s: Json) => s.key === "current" || s.key === "custom").map((s: Json) => ({
              key: `b${s.key}`, label: `${s.label} 80% band`, x: s.days, lo: s.risk.p10, hi: s.risk.p90, opacity: s.key === "custom" ? 0.14 : 0.08 }))}
            vmarks={[{ x: res.as_of_day, label: "now", kind: "now" }]} format={(v) => `${(v * 100).toFixed(0)}%`} />
          {/* Scenario lines converge, so they are identified by a legend (dash pattern), not direct labels. */}
          <Legend items={[{ label: "Observed (as-of)" }, ...sc.map((s: Json, i: number) => ({ label: `${s.label} (median)`, dash: SCEN_DASH[i % SCEN_DASH.length] })),
            { label: "80% band (current / custom)", kind: "band" as const }]} />
          <div className="overflow-x-auto"><table className="w-full text-[11.5px]">
            <thead><tr><th className={TH}>Scenario</th><th className={TH}>P(acute care ≤ 7 d)</th><th className={TH}>Δ vs current</th><th className={TH}>Day-7 risk (median)</th><th className={TH}>Assumptions</th></tr></thead>
            <tbody>{sc.map((s: Json) => (
              <tr key={s.key} className={clsx("border-t border-surface-border/60", s.key === "custom" && "font-semibold text-ink-primary")}>
                <td className={TD}>{s.label}</td><td className={clsx(TD, "nums-tabular")}>{pct(s.event_probability_7d)}</td>
                <td className={clsx(TD, "nums-tabular whitespace-nowrap")}>{s.delta_vs_current && s.key !== "current" ? `${signed(s.delta_vs_current.event_probability_7d * 100, 0)} pts` : "—"}</td>
                <td className={clsx(TD, "nums-tabular")}>{pct(s.risk_day7_median, 1)}</td>
                <td className={clsx(TD, "text-ink-muted")}>{(s.assumptions ?? []).join("; ")}</td></tr>))}</tbody>
          </table></div>
          <Note>Data used: as of Day {res.data_used.as_of_day}, {res.data_used.n_inputs} inputs (SHA-256 {String(res.data_used.input_sha256).slice(0, 12)}…); model {res.data_used.model.model_id} v{res.data_used.model.version}. {res.simulation.method} {res.simulation.disclaimer}</Note>
        </>)}
    </div>
  );
}

export function CounterfactualPanel({ pid, live }: { pid: string; live: number }) {
  const [anchor, setAnchor] = useState<number | undefined>(undefined);
  const [cf, setCf] = useState<Counterfactual | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const load = async (a?: number) => {
    setBusy(true); setErr(null);
    try { setCf(await ot.counterfactual(pid, a)); } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { setAnchor(undefined); void load(undefined); }, [pid, live]);
  const days = cf?.days ?? [];
  const truth = cf?.synthetic_truth;
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-end gap-2 text-[12px]">
        <label className="flex flex-col gap-0.5">Anchor day (default: first alert)
          <input type="number" min={2} max={Math.max(2, live - 1)} className={clsx(INPUT, "w-40")}
            value={anchor ?? cf?.anchor_day ?? ""} onChange={(e) => setAnchor(e.target.value ? Number(e.target.value) : undefined)} /></label>
        <button type="button" className={BTN} onClick={() => load(anchor)} disabled={busy}>
          {busy ? <Loader2 size={13} className="animate-spin" aria-hidden /> : <Play size={13} aria-hidden />} Compare twins</button>
      </div>
      {err && <div className="text-[12px] text-accent-red" role="alert">{err}</div>}
      {cf && (
        <>
          <div className="text-[11px] px-3 py-1.5 rounded-md border border-dashed border-surface-border-hi">{cf.disclaimer}</div>
          <TimeChart ariaLabel="Observed twin versus counterfactual twin risk" height={230}
            xDomain={[cf.anchor_day, Math.max(cf.anchor_day + 1, days.at(-1)?.day ?? cf.anchor_day + 1)]} yDomain={[0, 1]}
            lines={[{ key: "obs", label: "Observed twin", x: days.map((d) => d.day), y: days.map((d) => d.observed_risk), weight: 2.6, points: true, directLabel: true },
              { key: "cf", label: "Counterfactual", x: days.map((d) => d.day), y: days.map((d) => d.simulated_median), dash: "6 3", directLabel: true },
              { key: "ev", label: "Counterfactual cumulative P(acute care)", x: days.map((d) => d.day), y: days.map((d) => d.simulated_event_probability_cumulative), dash: "2 3", weight: 1.2 }]}
            bands={[{ key: "band", label: "Counterfactual 80% band", x: days.map((d) => d.day), lo: days.map((d) => d.simulated_p10), hi: days.map((d) => d.simulated_p90) }]}
            vmarks={[...cf.observed_interventions.map((i) => ({ x: i.day, label: "intervention", kind: "event" as const })),
              ...cf.observed_outcomes.map((o) => ({ x: o.day, label: "acute care", kind: "alert" as const }))]}
            format={(v) => `${(v * 100).toFixed(0)}%`} />
          <Legend items={[{ label: "Observed twin", kind: "point" }, { label: `Counterfactual twin: ${cf.scenario.label} (median)`, dash: "6 3" },
            { label: "Counterfactual 80% band", kind: "band" }, { label: "Counterfactual cumulative P(acute care)", dash: "2 3" }]} />
          <div className="text-[12.5px] text-ink-body">{cf.summary}</div>
          <div className="grid gap-2 md:grid-cols-3 text-[12px]">
            <KV label="Observed days inside the counterfactual 80% band" v={cf.band_coverage == null ? "—" : pct(cf.band_coverage)} />
            <KV label="First divergence" v={cf.first_divergence ? `Day ${cf.first_divergence.day}: observed ${pct(cf.first_divergence.observed_risk, 1)} vs counterfactual ${pct(cf.first_divergence.simulated_median, 1)}` : "none"} />
            <KV label="Data used" v={`inputs until Day ${cf.data_used.as_of_day}: risk ${pct(cf.data_used.risk_at_anchor, 1)} (${cf.data_used.tier_at_anchor})`} />
          </div>
          {cf.observed_interventions.length > 0 && <div className="text-[11.5px] text-ink-body">Observed interventions: {cf.observed_interventions.map((i) => `${i.display} (Day ${i.day})`).join("; ")}</div>}
          {truth?.available && (
            <div className="rounded-lg border border-ink-primary/50 p-3 text-[12px]">
              <div className="text-[10px] text-compact text-ink-muted">Synthetic ground-truth check (possible only because this patient is simulated)</div>
              {truth.removed_interventions.length > 0 ? (
                <div>Generator re-run <b>without</b> {truth.removed_interventions.map((r: Json) => `${String(r.kind).replace(/_/g, " ")} (Day ${r.day})`).join(", ")}:{" "}
                  <b className="text-ink-primary">{eventText(truth.counterfactual_first_event_after_anchor)}</b>
                  {" "}· as it actually happened: <b className="text-ink-primary">{eventText(truth.factual_first_event_after_anchor)}</b>
                  {" "}· peak infection load {truth.counterfactual_peak_infection_load} without vs {truth.factual_peak_infection_load} with.</div>
              ) : (
                <div>No intervention was recorded after Day {cf.anchor_day}, so the counterfactual world is the observed world:{" "}
                  <b className="text-ink-primary">{eventText(truth.factual_first_event_after_anchor)}</b> in the generator's ground truth.</div>
              )}
              <Note>{truth.note} Where the twin's projection and this ground truth disagree, that is a measured limitation of the twin; it is shown here rather than hidden.</Note>
            </div>)}
        </>)}
    </div>
  );
}

function eventText(e: Json | null | undefined): string {
  return e ? `acute care (${String(e.condition).replace(/_/g, " ")}) on Day ${e.day}` : "no acute care";
}

export function InterventionRecorder({ pid, alerts, canAct, onDone }: {
  pid: string; alerts: { id: string; tier: Tier; as_of_day: number }[]; canAct: boolean; onDone: () => void;
}) {
  const [cat, setCat] = useState<{ kind: string; label: string }[]>([]);
  const [kind, setKind] = useState("urgent_eval_abx");
  const [note, setNote] = useState("");
  const [alertId, setAlertId] = useState<string>("");
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { ot.interventionCatalog().then((c) => setCat(c.interventions)).catch(() => undefined); }, []);
  const go = async () => {
    setBusy(true); setMsg(null);
    try {
      const r = await ot.recordIntervention(pid, kind, note, alertId || null);
      setMsg(`Recorded: ${r.intervention.label}. Effective from Day ${r.intervention.effective_from_day}; past data unchanged: ${r.intervention.past_data_unchanged ? "yes" : "NO"}. Advance the twin clock to see how the twin responds.`);
      setNote("");
      onDone();
    } catch (e) { setMsg((e as Error).message); } finally { setBusy(false); }
  };
  if (!canAct) return <div className="text-[12px] text-ink-muted">Recording a clinical intervention requires the reviewer or admin role; coordinators can view.</div>;
  return (
    <div className="grid gap-2 md:grid-cols-[1.3fr_1fr_1fr_auto] items-end text-[12px]">
      <label className="flex flex-col gap-0.5">Intervention<select className={INPUT} value={kind} onChange={(e) => setKind(e.target.value)}>
        {cat.map((c) => <option key={c.kind} value={c.kind}>{c.label}</option>)}</select></label>
      <label className="flex flex-col gap-0.5">Linked alert<select className={INPUT} value={alertId} onChange={(e) => setAlertId(e.target.value)}>
        <option value="">none</option>{alerts.map((a) => <option key={a.id} value={a.id}>{a.tier} · Day {a.as_of_day}</option>)}</select></label>
      <label className="flex flex-col gap-0.5">Note<input maxLength={2000} className={INPUT} value={note} onChange={(e) => setNote(e.target.value)} /></label>
      <button type="button" onClick={go} disabled={busy} className={BTN}>{busy ? <Loader2 size={13} className="animate-spin" aria-hidden /> : <CircleDot size={13} aria-hidden />} Record</button>
      {msg && <div className="md:col-span-4 text-[12px] text-ink-body" role="status">{msg}</div>}
    </div>
  );
}

// =============================================================================
// Safety-gated explanation + feature store
// =============================================================================

export function ExplanationPanel({ pid, asOf }: { pid: string; asOf?: number }) {
  const [ex, setEx] = useState<Json | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    let live = true;
    setEx(null); setErr(null);
    ot.explain(pid, asOf).then((r) => live && setEx(r)).catch((e) => live && setErr((e as Error).message));
    return () => { live = false; };
  }, [pid, asOf]);
  if (err) return <div className="text-[12px] text-accent-red" role="alert">{err}</div>;
  if (!ex) return <div className="text-[12px] text-ink-muted flex items-center gap-2"><Loader2 size={13} className="animate-spin" aria-hidden /> Building the explanation…</div>;
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 text-[11px] text-ink-muted flex-wrap">
        {ex.safety_gates.passed ? <ShieldCheck size={14} className="text-ink-primary" aria-hidden /> : <ShieldX size={14} className="text-ink-primary" aria-hidden />}
        {ex.safety_gates.passed ? "Passed every safety gate" : "Blocked by the safety gates: fallback shown"} · source: {ex.source}
        {ex.llm.enabled ? (ex.llm.used ? " · LLM synthesis accepted" : " · LLM synthesis rejected or unavailable, deterministic text shown") : " · LLM off (deterministic)"}
      </div>
      <p className="text-[12.5px] text-ink-primary leading-relaxed">{ex.summary}</p>
      <ul className="text-[12px] list-disc ml-4 space-y-0.5">{ex.key_points.map((k: Json, i: number) => (
        <li key={i}>{k.text} {k.evidence_ids.length > 0 && <span className="text-mono-tech text-[10px] text-ink-muted">[{k.evidence_ids.slice(0, 3).join(", ")}{k.evidence_ids.length > 3 ? " …" : ""}]</span>}</li>))}</ul>
      <div className="flex flex-wrap gap-1.5">{ex.safety_gates.gates.map((g: Json) => <Chip key={g.gate} strong={!g.passed}>{g.passed ? "✓" : "✗"} {g.gate}</Chip>)}</div>
      {ex.caveats.map((c: string) => <Note key={c}>{c}</Note>)}
      {!ex.llm.enabled && ex.llm.reason && <Note>{ex.llm.reason}</Note>}
      {ex.llm.trace && <Note>LLM trace: model {ex.llm.trace.model ?? "—"}, prompt {ex.llm.trace.prompt_version}, {ex.llm.trace.latency_ms} ms, tokens {ex.llm.trace.input_tokens ?? "—"}/{ex.llm.trace.output_tokens ?? "—"}; the output is stored only as a SHA-256 hash.</Note>}
    </div>
  );
}

export function FeatureTable({ pid, asOf }: { pid: string; asOf?: number }) {
  const [f, setF] = useState<Json | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  useEffect(() => {
    let live = true;
    setF(null); setErr(null);
    ot.features(pid, asOf).then((r) => live && setF(r)).catch((e) => live && setErr((e as Error).message));
    return () => { live = false; };
  }, [pid, asOf]);
  if (err) return <div className="text-[12px] text-accent-red" role="alert">{err}</div>;
  if (!f) return <div className="text-[12px] text-ink-muted flex items-center gap-2"><Loader2 size={13} className="animate-spin" aria-hidden /> Materialising features…</div>;
  return (
    <div>
      <div className="text-[11px] text-ink-muted">Registry {f.registry_version} · feature code {f.feature_code_version} · content SHA-256 {String(f.content_sha256).slice(0, 16)}… ·
        model features equal the deployed model's input row: <b className="text-ink-primary">{f.model_input_consistency.equal_to_model_input_row ? "yes" : "NO"}</b></div>
      <div className="mt-2 max-h-80 overflow-auto border border-surface-border rounded-md">
        <table className="w-full text-[11px]"><thead className="sticky top-0 bg-surface-panel"><tr><th className={TH}>Feature</th><th className={TH}>Value</th><th className={TH}>Unit</th><th className={TH}>Kind</th><th className={TH}>Window</th><th className={TH}>Lineage</th></tr></thead>
          <tbody>{f.rows.map((r: Json) => {
            const ids = [...r.lineage.observation_ids, ...r.lineage.event_or_lab_ids];
            return (
              <tr key={r.feature} className="border-t border-surface-border/60">
                <td className={clsx(TD, "text-mono-tech")}>{r.feature}</td><td className={clsx(TD, "nums-tabular")}>{fmt(r.value)}</td><td className={TD}>{r.unit}</td>
                <td className={TD}>{r.in_model ? "model input" : "analytic"}</td><td className={clsx(TD, "whitespace-nowrap")}>D{r.window[0]}–{r.window[1]}</td>
                <td className={TD}><button type="button" className="underline decoration-dotted" aria-expanded={open === r.feature} onClick={() => setOpen(open === r.feature ? null : r.feature)}>
                  {ids.length} source(s)</button>
                  {open === r.feature && <div className="text-mono-tech text-[10px] break-all text-ink-muted">{ids.join(", ") || "profile / care plan"}</div>}</td>
              </tr>);
          })}</tbody></table>
      </div>
    </div>
  );
}
