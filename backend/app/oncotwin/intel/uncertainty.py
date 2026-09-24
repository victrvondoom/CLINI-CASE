"""Uncertainty Engine + Twin Readiness.

Every prediction is shown with a DECOMPOSED uncertainty, each part measured by
pushing perturbed inputs through the SAME deployed model and features:

  model          epistemic: 80 % interval across the bootstrap refits (existing)
  measurement    aleatoric: the last 3 days of each model signal re-drawn with
                 device measurement noise (assumed = ½ of the patient's own
                 baseline day-to-day spread — stated in the payload)
  missing data   each model-signal reading missing in the last 3 days is imputed
                 from the patient's recent observed distribution, 64 draws
  distribution   today's feature vector against the training distribution
  shift          (per-feature z vs training mean/std; RMS "OOD score")

Twin Readiness (a.k.a. Twin Data Quality) is an ENGINEERING metric composed of
measured components — data completeness, temporal coverage, signal
reliability, personalisation quality, prediction confidence, model validity.
It is not a health score and carries no clinical meaning.
"""
from __future__ import annotations

from typing import Any

import numpy as np

from app.oncotwin.engine.features import FEATURE_NAMES, feature_tensor, signal_matrix
from app.oncotwin.engine.series import PatientSeries
from app.oncotwin.signals import MODEL_SIGNALS, SIGNALS

N_DRAWS = 64
WINDOW = 3
MEASUREMENT_FRACTION = 0.5
OOD_FEATURE_Z = 4.0
OOD_SCORE_WARN = 2.5


def _risk_draws(model, values: np.ndarray, baseline, ctx: dict[str, Any]) -> np.ndarray:
    F = feature_tensor(values, baseline, **ctx)
    return model.predict(F[:, -1, :])


def _band(r: np.ndarray) -> tuple[float, list[float]]:
    lo, hi = float(np.percentile(r, 10)), float(np.percentile(r, 90))
    return round(hi - lo, 4), [round(lo, 4), round(hi, 4)]


def decompose(series: PatientSeries, baseline, ctx: dict[str, Any], model, prediction: dict[str, Any],
              *, population_drift: dict[str, Any] | None = None, seed: int = 0) -> dict[str, Any]:
    t = series.as_of_day
    rng = np.random.default_rng([seed, t, 41])
    V = signal_matrix(series)                                  # (1, T, S) transformed
    spread = np.array([baseline.signals[k].spread_t for k in MODEL_SIGNALS])
    lo = max(0, t - WINDOW)
    p = prediction["risk"]

    Vm = np.repeat(V, N_DRAWS, axis=0)
    noise = rng.normal(size=(N_DRAWS, t - lo, len(MODEL_SIGNALS))) * spread * MEASUREMENT_FRACTION
    Vm[:, lo:, :] = np.where(np.isnan(Vm[:, lo:, :]), Vm[:, lo:, :], Vm[:, lo:, :] + noise)
    meas_width, meas_range = _band(_risk_draws(model, Vm, baseline, ctx))

    miss = np.isnan(V[0, lo:, :])
    missing = [{"signal": MODEL_SIGNALS[j], "label": SIGNALS[MODEL_SIGNALS[j]].label, "day": lo + i + 1}
               for i, j in zip(*np.nonzero(miss), strict=True)]
    if missing:
        Vi = np.repeat(V, N_DRAWS, axis=0)
        for j, k in enumerate(MODEL_SIGNALS):
            recent = V[0, max(0, t - 7): t, j]
            recent = recent[~np.isnan(recent)]
            center = float(np.mean(recent)) if recent.size else baseline.signals[k].median_t
            if np.isnan(center):
                continue
            draws = center + rng.normal(size=(N_DRAWS, t - lo)) * spread[j]
            Vi[:, lo:, j] = np.where(np.isnan(Vi[:, lo:, j]), draws, Vi[:, lo:, j])
        miss_width, miss_range = _band(_risk_draws(model, Vi, baseline, ctx))
    else:
        miss_width, miss_range = 0.0, [p, p]

    x = np.array([prediction["features"][f] for f in FEATURE_NAMES])
    zt = (x - model.lr.mean) / model.lr.std
    ood_feats = sorted(({"feature": f, "z_vs_training": round(float(zt[i]), 2), "value": round(float(x[i]), 3)}
                        for i, f in enumerate(FEATURE_NAMES) if abs(zt[i]) > OOD_FEATURE_Z),
                       key=lambda d: -abs(d["z_vs_training"]))
    ood_score = float(np.sqrt(np.mean(zt ** 2)))
    ood = bool(ood_feats) or ood_score > OOD_SCORE_WARN

    parts = {
        "model": {"width_80": round(prediction["risk_p90"] - prediction["risk_p10"], 4),
                  "range": [prediction["risk_p10"], prediction["risk_p90"]],
                  "method": f"{len(model.boot_intercepts)} bootstrap refits of the model (patient-level resampling)"},
        "measurement": {"width_80": meas_width, "range": meas_range,
                        "method": (f"{N_DRAWS} draws re-measuring the last {WINDOW} days with noise = "
                                   f"{MEASUREMENT_FRACTION} × personal baseline spread (assumed device error)")},
        "missing_data": {"width_80": round(miss_width, 4), "range": miss_range, "n_missing_readings": len(missing),
                         "missing": missing[:12],
                         "method": (f"{N_DRAWS} imputations of readings missing in the last {WINDOW} days from the "
                                    "patient's recent observed distribution") if missing else
                                   f"no model-signal reading missing in the last {WINDOW} days"},
    }
    dominant = max(parts, key=lambda k: parts[k]["width_80"])
    completeness = float(np.mean([series.quality[k].completeness_7d for k in MODEL_SIGNALS]))
    statements = []
    if ood:
        top = ood_feats[0]["feature"] if ood_feats else "several features"
        statements.append(f"Distribution-shift warning: today's inputs lie outside the range seen in training ({top}); "
                          "treat the model output with caution.")
    if population_drift and population_drift.get("status") == "drift":
        statements.append("Model reliability warning: the live population's feature distribution has drifted from training.")
    if missing and (dominant == "missing_data" or completeness < 0.8):
        statements.append("Prediction reliability reduced because recent physiological data are incomplete "
                          f"({len(missing)} reading(s) missing in the last {WINDOW} days; 7-day completeness {completeness:.0%}).")
    if dominant == "model" and parts["model"]["width_80"] > max(0.02, 0.5 * p):
        statements.append("Model uncertainty dominates: the bootstrap models disagree about this patient-day.")
    if not statements:
        statements.append("Uncertainty is small relative to the risk level; inputs are complete and in-distribution.")
    return {
        "as_of_day": t, "risk": p, "horizon_days": prediction["horizon_days"],
        "components": parts, "dominant_source": dominant,
        "distribution_shift": {"ood": ood, "ood_score": round(ood_score, 2), "features_out_of_range": ood_feats[:8],
                               "rule": f"any feature |z| > {OOD_FEATURE_Z} vs training mean/std, or RMS z > {OOD_SCORE_WARN}",
                               "population_drift": population_drift},
        "data_completeness_7d": round(completeness, 3),
        "statements": statements,
        "model_version": prediction["model"],
    }


def readiness(facts: dict[str, Any], series: PatientSeries, prediction: dict[str, Any], model,
              uncertainty: dict[str, Any] | None = None) -> dict[str, Any]:
    t = series.as_of_day
    q = facts["quality"]
    lo = max(1, t - 27)
    dense = sum(1 for d in range(lo, t + 1)
                if sum(not np.isnan(series.values[k][d - 1]) for k in MODEL_SIGNALS) >= 5) / (t - lo + 1)
    depth = min(1.0, t / 21.0)
    flagged = {f["signal"] for f in q["flags"] if f["kind"] in ("stuck", "implausible", "conflict", "stale")}
    reliability = 1.0 - len(flagged & set(MODEL_SIGNALS)) / len(MODEL_SIGNALS)
    b = facts["baseline"]
    personal = b["adequacy"] * (1.0 if b["kind"] == "pre-treatment" else 0.6)
    ds = (uncertainty or {}).get("distribution_shift", {})
    ood = bool(ds.get("ood"))
    drift = (ds.get("population_drift") or {}).get("status") == "drift"
    validity = 0.0 if not model.integrity_verified else (0.5 if (ood or drift) else 1.0)
    comps = {
        "data_completeness": {"value": q["completeness"], "measure": "mean 7-day completeness of the model signals"},
        "temporal_coverage": {"value": round(depth * dense, 3),
                              "measure": f"history depth min(1, {t}/21 days) × share of the last 28 days with ≥ 5 of 9 signals"},
        "signal_reliability": {"value": round(reliability, 3),
                               "measure": "1 − share of model signals with an active stuck/implausible/conflict/stale flag"},
        "personalization_quality": {"value": round(personal, 3),
                                    "measure": "baseline adequacy × (1.0 for a pre-treatment baseline, 0.6 otherwise)"},
        "prediction_confidence": {"value": prediction["confidence"]["score"], "measure": "composite prediction confidence"},
        "model_validity": {"value": validity,
                           "measure": "artifact integrity verified × in-distribution inputs × no population drift"},
    }
    vals = [c["value"] for c in comps.values()]
    score = float(np.mean(vals))
    limiting = min(comps, key=lambda k: comps[k]["value"])
    label = "high" if score >= 0.8 and min(vals) >= 0.5 else "moderate" if score >= 0.6 else "low"
    return {"name": "Twin Readiness (Twin Data Quality)", "score": round(score, 3), "label": label,
            "components": comps, "limiting_factor": limiting,
            "note": "Engineering readiness of the twin's inputs and model — not a health score; no clinical meaning."}
