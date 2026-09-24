"""Personalized Baseline Engine.

For each patient and each daily signal it estimates a ROBUST personal normal
range from the pre-treatment window (median ± 2 × MAD-derived spread, with a
per-signal floor so a very steady baseline cannot make noise look alarming),
then characterises every later day relative to that personal range:

  deviation     — adverse-oriented z-score (positive = worse, whatever the
                  signal's clinical direction)
  rate          — least-squares slope of the z-score over 3 and 7 days
  persistence   — consecutive days beyond the deviation threshold
  sudden change — day-over-day jump in z, and a one-sided CUSUM for drift
  concordance   — how many signals deviate adversely on the same day
  anomaly       — Mahalanobis distance of the day's deviation vector under
                  the (shrunk) baseline correlation structure

All deviation functions accept a leading batch axis so the what-if simulator
can run them on Monte Carlo futures with exactly the same code.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from app.oncotwin.engine.series import PatientSeries
from app.oncotwin.signals import DAILY_SIGNALS, MODEL_SIGNALS, SIGNALS, adverse_sign

DEVIATION_Z = 1.5            # adverse deviation threshold used for persistence / concordance
SUDDEN_JUMP_Z = 2.5
CUSUM_K = 0.5
CUSUM_H = 4.0
MIN_BASELINE_DAYS = 5

# Typical adult reference ranges — shown ONLY for contrast with the personal
# range ("population thresholds would not fire yet"). Not used for scoring.
POPULATION_REFERENCE: dict[str, dict[str, Any]] = {
    "resting_hr": {"low": 60, "high": 100, "note": "adult resting HR 60–100 bpm"},
    "temperature": {"low": 36.1, "high": 37.9, "note": "fever threshold ≥ 38.0 °C"},
    "spo2": {"low": 95, "high": 100, "note": "SpO₂ ≥ 95 %"},
    "sbp": {"low": 90, "high": 140, "note": "hypotension < 90 mmHg"},
    "sleep_hours": {"low": 7, "high": 9, "note": "adult sleep 7–9 h"},
    "glucose_cgm": {"low": 70, "high": 180, "note": "CGM time-in-range 70–180 mg/dL"},
}


@dataclass
class SignalBaseline:
    signal: str
    median_t: float
    spread_t: float
    n_days: int
    established: bool

    def display(self) -> dict[str, Any]:
        spec = SIGNALS[self.signal]
        if spec.transform == "log":
            med = float(np.exp(self.median_t))
            lo, hi = float(np.exp(self.median_t - 2 * self.spread_t)), float(np.exp(self.median_t + 2 * self.spread_t))
        else:
            med = self.median_t
            lo, hi = self.median_t - 2 * self.spread_t, self.median_t + 2 * self.spread_t
        d = spec.decimals
        return {
            "signal": self.signal, "label": spec.label, "unit": spec.unit_display,
            "median": round(med, d), "low": round(lo, d), "high": round(hi, d),
            "spread": round(self.spread_t, 4), "transform": spec.transform,
            "n_days": self.n_days, "established": self.established,
            "adverse_direction": spec.adverse,
            "population_reference": POPULATION_REFERENCE.get(self.signal),
        }


@dataclass
class Baseline:
    signals: dict[str, SignalBaseline]
    window: tuple[int, int]
    kind: str
    adequacy: float
    corr_inv: np.ndarray        # inverse shrunk correlation over MODEL_SIGNALS

    @property
    def median_vec(self) -> np.ndarray:
        return np.array([self.signals[k].median_t for k in MODEL_SIGNALS])

    @property
    def spread_vec(self) -> np.ndarray:
        return np.array([self.signals[k].spread_t for k in MODEL_SIGNALS])

    def to_dict(self) -> dict[str, Any]:
        return {
            "window": {"start_day": self.window[0], "end_day": self.window[1]},
            "kind": self.kind,
            "adequacy": round(self.adequacy, 3),
            "method": "median ± 2×(1.4826·MAD), per-signal spread floor; pre-treatment window",
            "signals": {k: b.display() for k, b in self.signals.items()},
        }


def compute_baseline(series: PatientSeries) -> Baseline:
    end = min(series.baseline_end_day, series.as_of_day)
    start = 1
    kind = "pre-treatment" if series.as_of_day >= series.baseline_end_day else "pre-treatment (still accruing)"
    avail = [np.sum(~np.isnan(series.values[k][start - 1:end])) for k in MODEL_SIGNALS]
    if end < 3 or np.median(avail) < 3:
        # No usable pre-treatment window (monitoring began on treatment).
        end = min(series.as_of_day, 10)
        kind = "on-treatment (no pre-treatment data)"

    signals: dict[str, SignalBaseline] = {}
    zmat = []
    for key in DAILY_SIGNALS:
        spec = SIGNALS[key]
        x = series.transformed(key)[start - 1:end]
        x = x[~np.isnan(x)]
        if x.size == 0:
            continue
        med = float(np.median(x))
        mad = float(np.median(np.abs(x - med))) * 1.4826 if x.size >= 3 else 0.0
        spread = max(spec.spread_floor, mad)
        signals[key] = SignalBaseline(key, med, spread, int(x.size), x.size >= MIN_BASELINE_DAYS)
    # Fill any model signal never observed so vectors stay aligned (flagged as not established).
    for key in MODEL_SIGNALS:
        if key not in signals:
            signals[key] = SignalBaseline(key, float("nan"), SIGNALS[key].spread_floor, 0, False)

    for key in MODEL_SIGNALS:
        b = signals[key]
        x = series.transformed(key)[start - 1:end]
        zmat.append((x - b.median_t) / b.spread_t if b.n_days else np.full(end - start + 1, np.nan))
    Z = np.array(zmat).T                               # (days, S)
    corr = _shrunk_corr(Z)
    adequacy = float(np.mean([min(1.0, signals[k].n_days / 10.0) for k in MODEL_SIGNALS]))
    return Baseline(signals, (start, end), kind, adequacy, np.linalg.inv(corr))


def _shrunk_corr(Z: np.ndarray) -> np.ndarray:
    S = Z.shape[1]
    R = np.eye(S)
    n_eff = 0
    for i in range(S):
        for j in range(i + 1, S):
            m = ~np.isnan(Z[:, i]) & ~np.isnan(Z[:, j])
            if m.sum() >= 4:
                a, b = Z[m, i], Z[m, j]
                if a.std() > 0 and b.std() > 0:
                    R[i, j] = R[j, i] = float(np.corrcoef(a, b)[0, 1])
                    n_eff = max(n_eff, int(m.sum()))
    lam = float(np.clip(4.0 / max(n_eff, 1), 0.3, 1.0))
    return (1 - lam) * R + lam * np.eye(S)


# =============================================================================
# Deviation analytics (batched: arrays are (B, T, S))
# =============================================================================


def adverse_z(values_t: np.ndarray, baseline: Baseline, keys: tuple[str, ...] = MODEL_SIGNALS) -> np.ndarray:
    med = np.array([baseline.signals[k].median_t for k in keys])
    spread = np.array([baseline.signals[k].spread_t for k in keys])
    signs = np.array([adverse_sign(k) for k in keys])
    return signs * (values_t - med) / spread


def carry_forward(z: np.ndarray, max_gap: int = 1) -> np.ndarray:
    """Fill a missing day with the previous day's value (at most `max_gap` days)."""
    out = z.copy()
    for lag in range(1, max_gap + 1):
        prev = np.concatenate([np.full_like(z[:, :lag], np.nan), z[:, :-lag]], axis=1)
        out = np.where(np.isnan(out), prev, out)
    return out


def rolling_slope(z: np.ndarray, window: int) -> np.ndarray:
    """OLS slope (per day) over the trailing `window` days, NaN-aware; needs ≥2 points."""
    B, T, S = z.shape
    stack = np.full((window, B, T, S), np.nan)
    for k in range(window):
        stack[k, :, k:, :] = z[:, : T - k, :]
    x = -np.arange(window, dtype=float).reshape(window, 1, 1, 1) * np.ones_like(stack)
    m = ~np.isnan(stack)
    n = m.sum(axis=0)
    xs = np.where(m, x, 0.0)
    ys = np.where(m, stack, 0.0)
    sx, sy = xs.sum(0), ys.sum(0)
    sxx, sxy = (xs * xs).sum(0), (xs * ys).sum(0)
    den = n * sxx - sx * sx
    with np.errstate(invalid="ignore", divide="ignore"):
        slope = (n * sxy - sx * sy) / den
    return np.where((n >= 2) & (den > 0), slope, np.nan)


def persistence(z: np.ndarray, thr: float = DEVIATION_Z) -> np.ndarray:
    """Consecutive days ending at t with z ≥ thr (missing days neither count nor break)."""
    B, T, S = z.shape
    out = np.zeros((B, T, S))
    run = np.zeros((B, S))
    for t in range(T):
        zt = z[:, t, :]
        run = np.where(np.isnan(zt), run, np.where(zt >= thr, run + 1, 0))
        out[:, t, :] = run
    return out


def cusum(z: np.ndarray, k: float = CUSUM_K) -> np.ndarray:
    B, T, S = z.shape
    out = np.zeros((B, T, S))
    s = np.zeros((B, S))
    for t in range(T):
        zt = np.nan_to_num(z[:, t, :], nan=0.0)
        s = np.maximum(0.0, s + zt - k)
        out[:, t, :] = s
    return out


def jumps(z: np.ndarray) -> np.ndarray:
    prev = np.concatenate([np.full_like(z[:, :1], np.nan), z[:, :-1]], axis=1)
    return z - prev


def anomaly_score(z_signed: np.ndarray, corr_inv: np.ndarray) -> np.ndarray:
    """RMS-normalised Mahalanobis distance of the daily deviation vector."""
    zz = np.nan_to_num(z_signed, nan=0.0)
    d2 = np.einsum("bts,sr,btr->bt", zz, corr_inv, zz)
    return np.sqrt(np.maximum(d2, 0.0) / z_signed.shape[-1])
