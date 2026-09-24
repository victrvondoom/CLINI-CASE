"""Twin state estimation: latent physiology, neutrophil projection, confidence.

Latent loads are estimated each day by inverting the observation model:
    y_s(t) − baseline_s ≈ Σ_k L_sk · θ_k(t),   θ ≥ 0
solved by weighted non-negative least squares (weights = 1 / personal
spread²), then exponentially smoothed (causal). The fit's weighted R²
is reported so a clinician can see when deviations are NOT explained by
the twin's physiology (e.g. an isolated bad night's sleep).
"""
from __future__ import annotations

import itertools
from typing import Any

import numpy as np

from app.oncotwin.engine.baseline import Baseline
from app.oncotwin.engine.neutrophil import NeutrophilFit
from app.oncotwin.engine.series import PatientSeries
from app.oncotwin.signals import MODEL_SIGNALS, SIGNALS
from app.oncotwin.simulator import physiology as P

LATENT_LABELS = {
    "infection": "Infection / inflammation load",
    "dehydration": "Dehydration / GI-toxicity load",
    "fatigue": "Treatment-related fatigue load",
}
EWMA_ALPHA = 0.6
_SUBSETS = [s for r in range(1, 4) for s in itertools.combinations(range(3), r)]


def _nnls3(y: np.ndarray, L: np.ndarray, w: np.ndarray) -> tuple[np.ndarray, float]:
    """Exact NNLS for 3 unknowns by enumerating active sets. Returns (θ, weighted R²)."""
    m = ~np.isnan(y)
    if m.sum() < 3:
        return np.zeros(3), float("nan")
    ym, Lm, wm = y[m], L[m], w[m]
    sw = np.sqrt(wm)
    best, best_err = np.zeros(3), float(np.sum(wm * ym**2))
    for sub in _SUBSETS:
        A = Lm[:, sub] * sw[:, None]
        coef, *_ = np.linalg.lstsq(A, ym * sw, rcond=None)
        if np.any(coef < 0):
            continue
        theta = np.zeros(3)
        theta[list(sub)] = coef
        err = float(np.sum(wm * (ym - Lm @ theta) ** 2))
        if err < best_err:
            best, best_err = theta, err
    total = float(np.sum(wm * ym**2))
    r2 = 1.0 - best_err / total if total > 1e-9 else float("nan")
    return best, r2


def estimate_latent(series: PatientSeries, baseline: Baseline) -> dict[str, Any]:
    keys = [k for k in MODEL_SIGNALS if baseline.signals[k].n_days]
    L = np.array([P.LOADINGS[k] for k in keys])
    w = np.array([1.0 / baseline.signals[k].spread_t ** 2 for k in keys])
    med = np.array([baseline.signals[k].median_t for k in keys])
    n = series.n
    raw = np.zeros((n, 3))
    r2 = np.full(n, np.nan)
    for t in range(n):
        vals = np.array([series.transformed(k)[t] for k in keys])
        if t > 0:
            prev = np.array([series.transformed(k)[t - 1] for k in keys])
            vals = np.where(np.isnan(vals), prev, vals)
        theta, fit = _nnls3(vals - med, L, w)
        raw[t], r2[t] = theta, fit
    smooth = np.zeros_like(raw)
    for t in range(n):
        smooth[t] = raw[t] if t == 0 else EWMA_ALPHA * raw[t] + (1 - EWMA_ALPHA) * smooth[t - 1]
    return {"series": smooth, "raw": raw, "r2": r2, "names": P.LATENT}


def neutrophil_projection(series: PatientSeries, fit: NeutrophilFit, horizon: int = 7,
                          n_samples: int = 200, seed: int = 0) -> dict[str, Any]:
    """Forward-simulate ANC over the next `horizon` days (observed + planned doses)."""
    t = series.as_of_day
    if not fit.labs_used:
        return {"available": False, "reason": "no ANC result on file yet"}
    rng = np.random.default_rng([seed, t, 11])
    slopes = fit.sample_slopes(rng, n_samples)
    doses = dict(series.dose_days)
    for d in series.planned_dose_days:
        if t < d <= t + horizon and not any(abs(d - g) <= 3 for g in series.dose_days):
            doses[d] = 1.0
    anc, _ = P.simulate_anc(np.full(n_samples, fit.circ0), slopes, t + horizon, doses, series.gcsf_days)
    future = anc[:, t:]                       # days t+1 .. t+horizon
    today = anc[:, t - 1]
    nadir = future.min(axis=1)
    nadir_day = t + 1 + future.argmin(axis=1)
    within48 = anc[:, t - 1:t + 2].min(axis=1)
    return {
        "available": True,
        "today_median": round(float(np.median(today)), 2),
        "nadir_median": round(float(np.median(nadir)), 2),
        "nadir_p10": round(float(np.percentile(nadir, 10)), 2),
        "nadir_p90": round(float(np.percentile(nadir, 90)), 2),
        "nadir_day_median": int(np.median(nadir_day)),
        "p_below_0_5_within_48h": round(float(np.mean(within48 < 0.5)), 3),
        "p_below_1_0_within_7d": round(float(np.mean(nadir < 1.0)), 3),
        "trajectory_median": [round(float(x), 2) for x in np.median(anc, axis=0)[max(0, t - 14):]],
        "trajectory_p10": [round(float(x), 2) for x in np.percentile(anc, 10, axis=0)[max(0, t - 14):]],
        "trajectory_p90": [round(float(x), 2) for x in np.percentile(anc, 90, axis=0)[max(0, t - 14):]],
        "trajectory_start_day": max(1, t - 13),
        "planned_doses_in_horizon": sorted(d for d in doses if d > t),
        "method": "Friberg model, patient-fitted drug sensitivity (grid posterior), 200 posterior draws",
    }


def confidence(series: PatientSeries, baseline: Baseline, p: float, p_lo: float, p_hi: float) -> dict[str, Any]:
    """Composite prediction confidence — every component is measured, none is assumed."""
    comp = float(np.mean([series.quality[k].completeness_7d for k in MODEL_SIGNALS]))
    fresh = float(np.mean([series.quality[k].freshness for k in MODEL_SIGNALS]))
    width = max(0.0, p_hi - p_lo)
    certainty = float(np.clip(1.0 - width / max(0.2, 2.5 * p), 0.0, 1.0))
    sufficiency = 0.4 * comp + 0.35 * fresh + 0.25 * baseline.adequacy
    score = sufficiency * (0.5 + 0.5 * certainty)
    label = "high" if score >= 0.75 else "moderate" if score >= 0.5 else "low"
    stale = [SIGNALS[k].label for k in MODEL_SIGNALS if not series.quality[k].fresh]
    return {
        "score": round(score, 3), "label": label,
        "components": {
            "input_completeness_7d": round(comp, 3),
            "input_freshness": round(fresh, 3),
            "baseline_adequacy": round(baseline.adequacy, 3),
            "model_agreement": round(certainty, 3),
            "bootstrap_interval_width": round(width, 4),
        },
        "stale_signals": stale,
        "formula": ("score = (0.40·completeness + 0.35·freshness + 0.25·baseline adequacy) × "
                    "(0.5 + 0.5·model agreement); model agreement = 1 − bootstrap 80% interval width / max(0.2, 2.5·p)"),
    }
