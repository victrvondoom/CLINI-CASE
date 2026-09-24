"""Clinical Time-Series Feature Store.

  registry        every feature's definition: meaning, unit, group, window, the
                  signals / labs / events it reads, and whether the deployed
                  model consumes it. The registry version is a SHA-256 over the
                  definitions + the feature-code version.
  materialise     values for one patient AS OF a day, each with lineage — the
                  exact observation / event ids inside its window — and a
                  content SHA-256 over (values, lineage) for reproducibility.
  consistency     the materialised MODEL features must equal the deployed
                  model's input row for that day (checked and reported).

Model features are the 30 inputs of OT-ACUTE-7. Analytic features (sleep debt,
HRV trend, weight velocity, symptom acceleration, lab velocity, treatment
proximity, the multi-signal deterioration index, recovery velocity …) serve the
twin's analytics and explanations; they are not model inputs. No clinical score
is hard-coded anywhere.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from functools import lru_cache
from typing import Any

import numpy as np

from app.oncotwin.engine.baseline import adverse_z, carry_forward
from app.oncotwin.engine.features import FEATURE_NAMES, IDX, signal_matrix
from app.oncotwin.intel.memory import msdi
from app.oncotwin.mlops.versions import feature_version
from app.oncotwin.records import day_to_iso
from app.oncotwin.signals import LAB_SIGNALS, MODEL_SIGNALS, SIGNALS


@dataclass(frozen=True)
class FeatureDef:
    name: str
    description: str
    group: str
    unit: str
    window_days: int
    sources: tuple[str, ...]
    in_model: bool
    kind: str                          # model | analytic


def _model_defs() -> list[FeatureDef]:
    out = [FeatureDef(f"z_{k}", f"Adverse-oriented deviation of {SIGNALS[k].label.lower()} from the personal baseline "
                      "(yesterday carried forward one day if today is missing)", k, "SD", 2, (k,), True, "model")
           for k in MODEL_SIGNALS]
    out += [FeatureDef(f"slope3_{k}", f"3-day least-squares slope of the {SIGNALS[k].label.lower()} deviation",
                       k, "SD/day", 3, (k,), True, "model") for k in MODEL_SIGNALS]
    ctx = {
        "n_concordant": ("Signals simultaneously ≥ 1.5 SD adverse", "multi_signal", "count", 1, MODEL_SIGNALS),
        "anomaly": ("Mahalanobis distance of the day's deviation vector (shrunk baseline correlation)", "multi_signal",
                    "RMS SD", 1, MODEL_SIGNALS),
        "persist_max": ("Longest current run of adverse deviation across signals", "multi_signal", "days", 7, MODEL_SIGNALS),
        "nadir_risk": ("Expected-nadir timing × regimen myelotoxicity, discounted after G-CSF", "neutrophil", "index", 21,
                       ("chemo_dose", "gcsf_dose")),
        "anc_twin_log": ("log ANC estimated today by the personalised neutrophil twin", "neutrophil", "log 10³/µL", 56,
                         ("anc", "chemo_dose", "gcsf_dose")),
        "anc_twin_low": ("Twin probability that ANC < 1.0 ×10³/µL today", "neutrophil", "probability", 56,
                         ("anc", "chemo_dose", "gcsf_dose")),
        "anc_lab_low": ("A measured ANC < 1.0 in the last 7 days", "neutrophil", "flag", 7, ("anc",)),
        "adherence_7d": ("Supportive-medication adherence over 7 days", "adherence", "fraction", 7, ("supportive_dose",)),
        "adherence_gap": ("(1 − adherence) while doses are scheduled", "adherence", "fraction", 7, ("supportive_dose",)),
        "age65": ("Age ≥ 65", "context", "flag", 0, ("Patient",)),
        "on_treatment": ("Chemotherapy has started", "context", "flag", 56, ("chemo_dose",)),
        "myelotox": ("Regimen myelotoxicity (simulation parameter)", "context", "index", 0, ("careplan",)),
    }
    out += [FeatureDef(n, d, g, u, w, tuple(s), True, "model") for n, (d, g, u, w, s) in ctx.items()]
    assert tuple(f.name for f in out) == FEATURE_NAMES
    return out


ANALYTIC_DEFS = [
    FeatureDef("hrv_trend_7d_pct_per_day", "7-day HRV trend as % of the personal baseline per day", "hrv_sdnn", "%/day", 7,
               ("hrv_sdnn",), False, "analytic"),
    FeatureDef("resting_hr_trend_3d", "3-day resting-heart-rate trend", "resting_hr", "bpm/day", 3, ("resting_hr",), False,
               "analytic"),
    FeatureDef("sleep_debt_7d", "Σ max(0, personal baseline − sleep) over 7 days", "sleep_hours", "h", 7, ("sleep_hours",),
               False, "analytic"),
    FeatureDef("activity_deviation_pct", "3-day mean steps vs personal baseline", "steps", "%", 3, ("steps",), False, "analytic"),
    FeatureDef("weight_velocity_7d", "Least-squares weight change over 7 days", "weight", "kg/day", 7, ("weight",), False,
               "analytic"),
    FeatureDef("temperature_deviation", "3-day mean daily-max temperature minus the personal baseline", "temperature", "°C",
               3, ("temperature",), False, "analytic"),
    FeatureDef("symptom_acceleration", "3-day symptom slope now minus 3 days earlier", "symptom_score", "points/day²", 6,
               ("symptom_score",), False, "analytic"),
    FeatureDef("anc_velocity", "log-ANC change per day between the last two results", "neutrophil", "log/day", 21, ("anc",),
               False, "analytic"),
    FeatureDef("days_since_dose", "Days since the last chemotherapy administration (treatment proximity)", "context", "days",
               56, ("chemo_dose",), False, "analytic"),
    FeatureDef("days_to_next_planned_dose", "Days until the next planned dose on the CarePlan", "context", "days", 56,
               ("careplan",), False, "analytic"),
    FeatureDef("multi_signal_deterioration_index", "Σ adverse deviation beyond 1 SD across model signals (trailing 3 days)",
               "multi_signal", "SD", 3, MODEL_SIGNALS, False, "analytic"),
    FeatureDef("recovery_velocity", "Decline rate of the multi-signal index after its current-cycle peak", "multi_signal",
               "SD/day", 21, MODEL_SIGNALS, False, "analytic"),
]


@lru_cache(maxsize=1)
def registry() -> dict[str, Any]:
    defs = _model_defs() + ANALYTIC_DEFS
    body = json.dumps([asdict(d) for d in defs], sort_keys=True)
    return {"registry_version": hashlib.sha256((body + feature_version()).encode()).hexdigest()[:16],
            "feature_code_version": feature_version(), "n_features": len(defs),
            "n_model_features": sum(d.in_model for d in defs), "features": [asdict(d) for d in defs],
            "entity": "patient-day (as-of: only data dated ≤ that day)"}


def _slope(y: np.ndarray) -> float | None:
    m = ~np.isnan(y)
    return None if m.sum() < 3 else round(float(np.polyfit(np.arange(len(y))[m], y[m], 1)[0]), 5)


def _ids(series, keys, lo: int, hi: int) -> list[str]:
    return [i for k in keys if k in series.obs_ids for i in series.obs_ids[k][max(0, lo - 1): hi] if i]


def _mean(a: np.ndarray) -> float | None:
    return float(np.nanmean(a)) if np.any(~np.isnan(a)) else None


def materialize(comp) -> dict[str, Any]:
    """Feature rows for one patient-day from a TwinComputation (state + trajectory stages already run)."""
    s, b, t = comp.series, comp.baseline, comp.as_of_day
    x = comp.F[t - 1]
    reg = registry()
    lab_ids = {k: [oid for d, _, oid in s.labs.get(k, []) if d <= t] for k in LAB_SIGNALS}
    ev_ids = {kind: [e.id for e in s.events if e.kind == kind and e.day <= t]
              for kind in ("chemo_dose", "gcsf_dose", "supportive_dose", "careplan")}
    rows = []
    for d in reg["features"]:
        if not d["in_model"]:
            continue
        w = max(d["window_days"], 1)
        obs = _ids(s, [k for k in d["sources"] if k in MODEL_SIGNALS], t - w + 1, t)
        other = [i for src in d["sources"] for i in (ev_ids[src][-6:] if src in ev_ids else lab_ids.get(src, [])[-4:])]
        rows.append({"feature": d["name"], "value": round(float(x[IDX[d["name"]]]), 6), "unit": d["unit"],
                     "group": d["group"], "kind": "model", "in_model": True, "window": [max(1, t - w + 1), t],
                     "lineage": {"observation_ids": obs, "event_or_lab_ids": other}})

    base = comp.state["baseline_state"]["signals"]

    def med(k: str):
        return (base.get(k) or {}).get("median")

    M = msdi(carry_forward(adverse_z(signal_matrix(s), b), 1)[0])
    hrv_sl = _slope(s.values["hrv_sdnn"][max(0, t - 7): t])
    sym = s.values["symptom_score"]
    s_now, s_prev = _slope(sym[max(0, t - 3): t]), _slope(sym[max(0, t - 6): max(0, t - 3)])
    anc = [(d, v) for d, v, _ in s.labs.get("anc", []) if d <= t]
    dsd = s.days_since_dose()[t - 1]
    nxt = comp.state["cancer_treatment_state"]["next_planned_dose_day"]
    sleep7 = s.values["sleep_hours"][max(0, t - 7): t]
    steps3, temp3 = _mean(s.values["steps"][max(0, t - 3): t]), _mean(s.values["temperature"][max(0, t - 3): t])
    rec_vel = None
    if s.dose_days:
        seg = M[max(s.dose_days) - 1: t]
        seg = seg[~np.isnan(seg)]
        if seg.size >= 3 and seg.max() >= 3.0:
            ip = int(np.argmax(seg))
            if ip < len(seg) - 1:
                rec_vel = float((seg[ip] - seg[-1]) / (len(seg) - 1 - ip))
    analytic = {
        "hrv_trend_7d_pct_per_day": None if hrv_sl is None or not med("hrv_sdnn") else 100 * hrv_sl / med("hrv_sdnn"),
        "resting_hr_trend_3d": _slope(s.values["resting_hr"][max(0, t - 3): t]),
        "sleep_debt_7d": (float(np.nansum(np.maximum(0.0, med("sleep_hours") - sleep7)))
                          if med("sleep_hours") is not None and np.any(~np.isnan(sleep7)) else None),
        "activity_deviation_pct": None if steps3 is None or not med("steps") else 100 * (steps3 - med("steps")) / med("steps"),
        "weight_velocity_7d": _slope(s.values["weight"][max(0, t - 7): t]),
        "temperature_deviation": None if temp3 is None or med("temperature") is None else temp3 - med("temperature"),
        "symptom_acceleration": None if s_now is None or s_prev is None else s_now - s_prev,
        "anc_velocity": ((np.log(anc[-1][1]) - np.log(anc[-2][1])) / max(1, anc[-1][0] - anc[-2][0])
                         if len(anc) >= 2 else None),
        "days_since_dose": None if np.isnan(dsd) else int(dsd),
        "days_to_next_planned_dose": None if nxt is None else int(nxt - t),
        "multi_signal_deterioration_index": _mean(M[max(0, t - 3): t]),
        "recovery_velocity": rec_vel,
    }
    for d in reg["features"]:
        if d["in_model"]:
            continue
        v = analytic[d["name"]]
        w = d["window_days"]
        other = (lab_ids["anc"][-2:] if d["name"] == "anc_velocity" else
                 ev_ids["chemo_dose"][-1:] if d["name"] == "days_since_dose" else [])
        rows.append({"feature": d["name"], "value": None if v is None else round(float(v), 6), "unit": d["unit"],
                     "group": d["group"], "kind": "analytic", "in_model": False, "window": [max(1, t - w + 1), t],
                     "lineage": {"observation_ids": _ids(s, [k for k in d["sources"] if k in MODEL_SIGNALS], t - w + 1, t),
                                 "event_or_lab_ids": other}})
    body = json.dumps([{k: r[k] for k in ("feature", "value", "lineage")} for r in rows], sort_keys=True)
    model_row = np.array([r["value"] for r in rows if r["in_model"]], dtype=float)
    return {
        "patient_id": comp.record.profile.patient_id, "as_of_day": t, "twin_time": day_to_iso(t, 23, 59),
        "registry_version": reg["registry_version"], "feature_code_version": reg["feature_code_version"],
        "content_sha256": hashlib.sha256(body.encode()).hexdigest(), "rows": rows,
        "model_input_consistency": {
            "equal_to_model_input_row": bool(np.allclose(model_row, np.round(x, 6), atol=1e-6)),
            "model": comp.model.version_info()["model_id"],
            "note": "The feature store's model features are the deployed model's exact input row for this day."},
    }
