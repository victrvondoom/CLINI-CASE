// OAH-Bridge display helpers. Pure; no React.
import type { ComponentStatus, EpistemicStatus, WeatherResponse } from "./types";

export const EPISTEMIC_LABEL: Record<EpistemicStatus, string> = {
  observed: "Observed",
  inferred: "Inferred",
  confirmed: "Lab-confirmed",
};

/** What each epistemic status means, in the engine's own terms (scoring.py thresholds). */
export const EPISTEMIC_EXPLAINER: Record<EpistemicStatus, string> = {
  observed: "Direct observation with low corroboration (S below 0.40).",
  inferred: "Modelled inference from corroborating sources (S at least 0.40; strong at 0.70).",
  confirmed: "A simulated reference-laboratory assay was positive, which overrides the score.",
};

/** WebGL needs literal colours (CSS variables do not resolve inside three.js). */
export const EPISTEMIC_HEX: Record<EpistemicStatus, string> = {
  observed: "#94a3b8",
  inferred: "#f59e0b",
  confirmed: "#ef4444",
};

export const RISK_HEX: Record<string, string> = {
  negligible: "#22c55e",
  low: "#84cc16",
  moderate: "#f59e0b",
  high: "#ef4444",
  certain: "#b91c1c",
};

export function riskHex(risk: string): string {
  return RISK_HEX[risk] ?? "#94a3b8";
}

/** "recreational-water-contact" → "Recreational water contact". */
export function humanize(code: string): string {
  const text = code.replace(/[-_]+/g, " ").trim();
  return text ? text.charAt(0).toUpperCase() + text.slice(1) : text;
}

export function score2(value: number): string {
  return value.toFixed(2);
}

/** Engine timings are sub-millisecond; show them honestly rather than rounding to 0. */
export function formatMs(ms: number): string {
  if (!Number.isFinite(ms)) return "—";
  if (ms < 1) return `${Math.max(1, Math.round(ms * 1000))} µs`;
  return `${ms.toFixed(ms < 10 ? 2 : 1)} ms`;
}

export function formatAge(seconds: number | null | undefined): string {
  if (seconds == null || !Number.isFinite(seconds)) return "—";
  if (seconds < 45) return "just now";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  return `${hours} h ago`;
}

export function formatUptime(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  return h > 0 ? `${h}h ${m}m` : m > 0 ? `${m}m ${s}s` : `${s}s`;
}

const COMPASS = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"];

/** Meteorological degrees (direction the wind blows from) → 16-point compass label. */
export function compass(deg: number | null | undefined): string {
  if (deg == null || !Number.isFinite(deg)) return "—";
  return COMPASS[Math.round((((deg % 360) + 360) % 360) / 22.5) % 16];
}

export type FreshnessLabel = "LIVE" | "CACHED" | "STALE" | "UNAVAILABLE";

export function weatherFreshness(w: Pick<WeatherResponse, "mode" | "stale">): FreshnessLabel {
  if (w.mode === "unavailable") return "UNAVAILABLE";
  if (w.stale) return "STALE";
  return w.mode === "live" ? "LIVE" : "CACHED";
}

export const COMPONENT_STATUS_LABEL: Record<ComponentStatus, string> = {
  ok: "OK",
  idle: "Idle",
  degraded: "Degraded",
  error: "Error",
};

export const COMPONENT_STATUS_HEX: Record<ComponentStatus, string> = {
  ok: "#22c55e",
  idle: "#94a3b8",
  degraded: "#f59e0b",
  error: "#ef4444",
};

/** Format an instant in a named IANA zone; falls back to UTC text if the zone is unknown. */
export function formatInstant(iso: string | null | undefined, timeZone?: string): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "—";
  try {
    return new Intl.DateTimeFormat("en-GB", {
      timeZone,
      day: "2-digit",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
      timeZoneName: "short",
    }).format(date);
  } catch {
    return date.toISOString().replace("T", " ").slice(0, 16) + " UTC";
  }
}

/** "2026-10-04T18:00:00" (local, no offset) → "Sat 18:00". */
export function formatLocalHour(local: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(local);
  if (!match) return local;
  const [, y, mo, d, h, mi] = match;
  const day = new Date(Date.UTC(Number(y), Number(mo) - 1, Number(d))).toLocaleDateString("en-GB", {
    weekday: "short",
    timeZone: "UTC",
  });
  return `${day} ${h}:${mi}`;
}
