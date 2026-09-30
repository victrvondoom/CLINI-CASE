/**
 * Model sensitivity simulation ("counterfactual feature perturbation").
 * Re-evaluates the trained model with one input changed. It exposes the model's response surface — it is NOT a
 * treatment recommendation and NOT a causal claim.
 */
import clsx from "clsx";
import { useEffect, useMemo, useRef, useState } from "react";

import { cardio } from "./api";
import { CARD } from "./panels";
import { pct, probabilityColor, signedPct } from "./vesselMapping";
import {
  TARGETS,
  type CounterfactualResult,
  type FeatureCatalog,
  type FeatureSpec,
  type PatientValues,
  type TargetId,
} from "./types";

interface Props {
  catalog: FeatureCatalog;
  patient: PatientValues;
  active: boolean;
  onActive: (v: boolean) => void;
  /** preset from a scenario (feature → value) */
  preset?: Record<string, number | string> | null;
  view: "baseline" | "perturbed";
  onView: (v: "baseline" | "perturbed") => void;
  onResult: (r: CounterfactualResult | null) => void;
  selectedTarget: TargetId;
}

function numericBounds(spec: FeatureSpec, current: number): [number, number] {
  const lo = spec.min ?? current * 0.5;
  const hi = spec.max ?? current * 1.5;
  // cover the current value AND both reference bounds, with headroom, clamped to the valid range
  const cands = [current, spec.ref_low, spec.ref_high].filter((v): v is number => typeof v === "number");
  const cmin = Math.min(...cands);
  const cmax = Math.max(...cands);
  const pad = Math.max((cmax - cmin) * 0.25, Math.abs(current) * 0.1, 1e-6);
  const a = Math.max(lo, cmin - pad);
  const b = Math.min(hi, cmax + pad);
  return a < b ? [a, b] : [lo, hi];
}

function Curve({ pts, target, current }: { pts: { x: number; y: number }[]; target: TargetId; current: number }) {
  if (pts.length < 2) return null;
  const xs = pts.map((p) => p.x);
  const x0 = Math.min(...xs);
  const x1 = Math.max(...xs);
  const sx = (x: number) => 6 + ((x - x0) / (x1 - x0 || 1)) * 188;
  const sy = (y: number) => 54 - y * 48;
  const d = pts.map((p, i) => `${i ? "L" : "M"}${sx(p.x).toFixed(1)},${sy(p.y).toFixed(1)}`).join(" ");
  return (
    <svg viewBox="0 0 200 60" className="w-full h-16" role="img" aria-label={`Model response curve for ${target}`}>
      <line x1="6" x2="194" y1={sy(0.5)} y2={sy(0.5)} stroke="currentColor" strokeOpacity=".15" strokeDasharray="3 3" />
      <path d={d} fill="none" stroke="rgb(var(--accent-brand))" strokeWidth="1.8" />
      {Number.isFinite(current) && <line x1={sx(current)} x2={sx(current)} y1="4" y2="56" stroke="currentColor" strokeOpacity=".4" />}
    </svg>
  );
}

export function SensitivityPanel({ catalog, patient, active, onActive, preset, view, onView, onResult, selectedTarget }: Props) {
  const specs = useMemo(
    () => catalog.features.filter((f) => f.kind !== "categorical" || f.options.length > 1),
    [catalog],
  );
  const [feature, setFeature] = useState<string>("LDL");
  const [value, setValue] = useState<number | string>("");
  const [res, setRes] = useState<CounterfactualResult | null>(null);
  const [curve, setCurve] = useState<{ x: number; y: number }[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const seq = useRef(0);
  const spec = specs.find((s) => s.name === feature) ?? specs[0];

  // adopt a scenario preset
  useEffect(() => {
    if (preset && Object.keys(preset).length) {
      const [k, v] = Object.entries(preset)[0];
      setFeature(k);
      setValue(v);
      onActive(true);
    }
  }, [preset]); // eslint-disable-line react-hooks/exhaustive-deps

  const current = patient[spec.name];
  const curNum = typeof current === "number" ? current : Number(current);

  useEffect(() => {
    if (!active) {
      setRes(null);
      onResult(null);
      return;
    }
    if (value === "" || value === null) return;
    const id = ++seq.current;
    const h = setTimeout(async () => {
      try {
        const r = await cardio.counterfactual(patient, { [spec.name]: value });
        if (id !== seq.current) return;
        setRes(r);
        onResult(r);
        setErr(null);
      } catch (e) {
        if (id === seq.current) setErr((e as Error).message);
      }
    }, 220);
    return () => clearTimeout(h);
  }, [active, value, spec.name, patient]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!active || spec.kind !== "numeric") {
      setCurve([]);
      return;
    }
    let live = true;
    cardio
      .sensitivity(patient, spec.name, 15)
      .then((r) => {
        if (!live) return;
        setCurve(
          r.curve.map((c) => ({
            x: Number(c.value),
            y: Number(c[selectedTarget]),
          })),
        );
      })
      .catch(() => live && setCurve([]));
    return () => {
      live = false;
    };
  }, [active, spec.name, spec.kind, patient, selectedTarget]);

  const [lo, hi] = spec.kind === "numeric" && Number.isFinite(curNum) ? numericBounds(spec, curNum) : [0, 1];
  return (
    <section className={clsx(CARD, "p-4 space-y-3")} aria-label="Model sensitivity simulation" data-testid="sensitivity-panel">
      <header className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-[13px] font-semibold text-ink-primary">Model sensitivity simulation</h3>
          <p className="text-[11.5px] text-ink-muted mt-0.5">
            Change one input and re-run the model. Shows how the <i>model</i> responds — not a treatment recommendation.
          </p>
        </div>
        <label className="inline-flex items-center gap-1.5 text-[12px] shrink-0">
          <input
            type="checkbox"
            checked={active}
            onChange={(e) => onActive(e.target.checked)}
            data-testid="sensitivity-toggle"
          />
          Enable
        </label>
      </header>

      {active && (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            <label className="text-[11.5px] text-ink-muted">
              Input to change
              <select
                className="mt-1 w-full rounded-md border border-surface-border bg-surface-bg px-2 py-1 text-[12.5px] text-ink-body"
                value={spec.name}
                data-testid="sensitivity-feature"
                onChange={(e) => {
                  setFeature(e.target.value);
                  setValue("");
                  setRes(null);
                  onResult(null);
                }}
              >
                {specs.map((s) => (
                  <option key={s.name} value={s.name}>
                    {s.label}
                    {s.unit ? ` (${s.unit})` : ""}
                  </option>
                ))}
              </select>
            </label>
            <div className="text-[11.5px] text-ink-muted">
              New value
              {spec.kind === "numeric" ? (
                <div className="mt-1 flex items-center gap-2">
                  <input
                    type="range"
                    min={lo}
                    max={hi}
                    step={(hi - lo) / 200}
                    value={value === "" ? (Number.isFinite(curNum) ? curNum : lo) : Number(value)}
                    onChange={(e) => setValue(Number(e.target.value))}
                    className="flex-1"
                    aria-label={`New value for ${spec.label}`}
                    data-testid="sensitivity-slider"
                  />
                  <input
                    type="number"
                    value={value === "" ? "" : Number(Number(value).toFixed(2))}
                    onChange={(e) => setValue(e.target.value === "" ? "" : Number(e.target.value))}
                    className="w-20 rounded-md border border-surface-border bg-surface-bg px-1.5 py-1 text-[12.5px] text-ink-body tabular-nums"
                    aria-label={`Numeric value for ${spec.label}`}
                    data-testid="sensitivity-number"
                  />
                </div>
              ) : (
                <select
                  className="mt-1 w-full rounded-md border border-surface-border bg-surface-bg px-2 py-1 text-[12.5px] text-ink-body"
                  value={String(value)}
                  onChange={(e) => setValue(e.target.value)}
                  data-testid="sensitivity-choice"
                >
                  <option value="">—</option>
                  {(spec.kind === "binary" ? ["0", "1"] : spec.options).map((o) => (
                    <option key={o} value={o}>
                      {spec.kind === "binary" ? (o === "1" ? "Yes" : "No") : o}
                    </option>
                  ))}
                </select>
              )}
              <div className="mt-1 flex gap-1.5 flex-wrap">
                {spec.kind === "numeric" && spec.ref_low != null && (
                  <button type="button" className="px-1.5 py-0.5 rounded border border-surface-border text-[11px]" onClick={() => setValue(spec.ref_low as number)}>
                    to ref. low {spec.ref_low}
                  </button>
                )}
                {spec.kind === "numeric" && spec.ref_high != null && (
                  <button type="button" className="px-1.5 py-0.5 rounded border border-surface-border text-[11px]" onClick={() => setValue(spec.ref_high as number)}>
                    to ref. high {spec.ref_high}
                  </button>
                )}
              </div>
            </div>
          </div>

          {err && <p role="alert" className="text-[12px] text-accent-red">{err}</p>}

          {res && (
            <div data-testid="sensitivity-result" className="space-y-2">
              <div className="text-[12px] text-ink-body">
                {res.changes.map((c) => (
                  <span key={c.feature}>
                    <b>{c.label}</b>: {String(c.before)}
                    {c.unit ? ` ${c.unit}` : ""}
                    {c.was_imputed ? " (imputed)" : ""} → <b>{String(c.after)}{c.unit ? ` ${c.unit}` : ""}</b>
                  </span>
                ))}
              </div>
              <table className="w-full text-[12px] tabular-nums">
                <thead>
                  <tr className="text-ink-muted text-[11px]">
                    <th className="text-left font-medium">Target</th>
                    <th className="text-right font-medium">Before</th>
                    <th className="text-right font-medium">After</th>
                    <th className="text-right font-medium">Δ</th>
                  </tr>
                </thead>
                <tbody>
                  {TARGETS.map((t) => {
                    const r = res.targets[t];
                    return (
                      <tr key={t} className="border-t border-surface-border/60" data-testid={`delta-${t}`}>
                        <td className="py-1 text-ink-primary">{t}</td>
                        <td className="text-right">{pct(r.before)}</td>
                        <td className="text-right" style={{ color: probabilityColor(r.after) }}>{pct(r.after)}</td>
                        <td className="text-right">
                          {signedPct(r.delta)}
                          {r.within_model_uncertainty && (
                            <span className="ml-1 text-[10px] text-ink-muted" title="Smaller than the model's own ensemble spread">
                              (within model noise)
                            </span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              <div className="flex items-center gap-2 text-[11.5px]" role="group" aria-label="3D view shows">
                <span className="text-ink-muted">3D view shows:</span>
                {(["baseline", "perturbed"] as const).map((v) => (
                  <button
                    key={v}
                    type="button"
                    aria-pressed={view === v}
                    onClick={() => onView(v)}
                    data-testid={`view-${v}`}
                    className={clsx(
                      "px-2 py-0.5 rounded-md border text-[11.5px]",
                      view === v ? "border-accent-brand bg-accent-brand/10 text-ink-primary" : "border-surface-border text-ink-body",
                    )}
                  >
                    {v === "baseline" ? "Baseline" : "Perturbed"}
                  </button>
                ))}
              </div>
              <p className="text-[11px] text-ink-muted">{res.label}</p>
            </div>
          )}
          {curve.length > 1 && (
            <div>
              <div className="text-[11px] text-ink-muted">
                Response of {selectedTarget} to {spec.label} (other inputs fixed)
              </div>
              <Curve pts={curve} target={selectedTarget} current={curNum} />
            </div>
          )}
        </>
      )}
    </section>
  );
}
