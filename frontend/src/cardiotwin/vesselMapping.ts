/**
 * Model output → visual state. The ONLY place that decides how an estimated probability, a confidence label
 * and an uncertainty width become colour / outline / halo. The 3D scene, the legend and the tests all use it.
 *
 * Deliberate design rules (clinical honesty):
 *  - colour encodes ESTIMATED PROBABILITY (neutral → amber → red); it never means "diagnosed stenosis";
 *  - vessel THICKNESS is never modulated — narrowing of the drawn tube would imply anatomical stenosis geometry;
 *  - uncertainty is drawn as a translucent halo whose radius grows with the 80 % ensemble interval width;
 *  - confidence is drawn as outline strength;
 *  - colour is never the only channel: numeric labels + band text always accompany the 3D view.
 */
import type { Band, Confidence, VesselViz } from "./types";

export const RAMP_STOPS: { p: number; rgb: [number, number, number] }[] = [
  { p: 0.0, rgb: [138, 161, 181] }, // neutral slate
  { p: 0.5, rgb: [242, 169, 0] }, // amber
  { p: 1.0, rgb: [200, 16, 46] }, // red
];

export const BAND_LABEL: Record<Band, string> = {
  low: "Low",
  intermediate: "Intermediate",
  elevated: "Elevated",
};

export function clamp01(x: number): number {
  return Number.isFinite(x) ? Math.min(1, Math.max(0, x)) : 0;
}

export function probabilityRgb(p: number): [number, number, number] {
  const x = clamp01(p);
  for (let i = 1; i < RAMP_STOPS.length; i++) {
    const a = RAMP_STOPS[i - 1];
    const b = RAMP_STOPS[i];
    if (x <= b.p) {
      const t = (x - a.p) / (b.p - a.p);
      return [0, 1, 2].map((k) => Math.round(a.rgb[k] + (b.rgb[k] - a.rgb[k]) * t)) as [number, number, number];
    }
  }
  return RAMP_STOPS[RAMP_STOPS.length - 1].rgb;
}

export function probabilityColor(p: number): string {
  const [r, g, b] = probabilityRgb(p);
  return `#${[r, g, b].map((v) => v.toString(16).padStart(2, "0")).join("")}`;
}

/** Display bands (visual only — NOT clinical thresholds). Must match backend `BANDS`. */
export function bandFor(p: number): Band {
  const x = clamp01(p);
  if (x < 0.33) return "low";
  if (x < 0.66) return "intermediate";
  return "elevated";
}

const OUTLINE: Record<Confidence, number> = { high: 0.95, moderate: 0.6, low: 0.28 };

export interface VesselRenderState {
  id: VesselViz["id"];
  color: string;
  emissive: number;
  /** multiplier on the tube radius for the uncertainty halo (>= 1.3 so it is always visible) */
  haloScale: number;
  haloOpacity: number;
  outlineOpacity: number;
  /** text alternative for assistive tech and the legend */
  label: string;
}

export function vesselRenderState(v: VesselViz): VesselRenderState {
  const p = clamp01(v.probability);
  const halo = clamp01(v.halo);
  return {
    id: v.id,
    color: probabilityColor(p),
    emissive: 0.08 + 0.32 * p,
    haloScale: 1.35 + 2.2 * halo,
    haloOpacity: 0.1 + 0.32 * halo,
    outlineOpacity: OUTLINE[v.confidence],
    label: `${v.id}: estimated stenosis probability ${(p * 100).toFixed(0)}% (${BAND_LABEL[bandFor(p)]}), ${v.confidence} confidence`,
  };
}

export const pct = (p: number, digits = 0): string => `${(clamp01(p) * 100).toFixed(digits)}%`;

export function signedPct(delta: number): string {
  const v = delta * 100;
  return `${v > 0 ? "+" : ""}${v.toFixed(1)} pp`;
}
