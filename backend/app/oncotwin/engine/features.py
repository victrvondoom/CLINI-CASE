"""Feature engineering for the deterioration model.

Every feature on day t is a function of data dated ≤ t only. Features are
deliberately few and human-readable so each model coefficient maps to a
statement a clinician can check ("temperature is 2.4 SD above HER baseline").

Personal-baseline features (per model signal):
  z_<signal>       adverse-oriented deviation from the personal baseline
                   (yesterday's value carried forward one day if today is missing)
  slope3_<signal>  3-day trend of that deviation (SD/day)
Cross-signal:
  n_concordant     signals simultaneously ≥ 1.5 SD in the adverse direction
  anomaly          Mahalanobis distance of the deviation vector
  persist_max      longest current run of adverse deviation across signals
Clinical / twin context:
  nadir_risk       expected-nadir timing × regimen myelotoxicity, discounted
                   when G-CSF was given this cycle
  anc_twin_log     log ANC estimated TODAY by the personalised neutrophil twin
  anc_twin_low     twin probability that ANC < 1.0 ×10³/µL today
  anc_lab_low      a measured ANC < 1.0 in the last 7 days
  adherence_7d     supportive-medication adherence over the last 7 days
  adherence_gap    (1 − adherence) while doses are actually scheduled
  age65, on_treatment, myelotox

Design note: we A/B-tested dropping `nadir_risk` in favour of the twin's ANC
features alone. Pooled over three independent synthetic cohorts, keeping it
detected more events earlier (EARLY WARNING sensitivity 90 % vs 85 %, median
lead 4.0 vs 3.5 days) at the cost of more false alerts (1.67 vs 1.26 per
100 patient-days), so it stays (see docs/ONCOTWIN.md, "Design decisions").
"""
from __future__ import annotations

import numpy as np

from app.oncotwin.engine.baseline import (
    DEVIATION_Z,
    Baseline,
    adverse_z,
    anomaly_score,
    carry_forward,
    persistence,
    rolling_slope,
)
from app.oncotwin.engine.neutrophil import NeutrophilTwin
from app.oncotwin.engine.series import PatientSeries
from app.oncotwin.signals import MODEL_SIGNALS, adverse_sign

CONTEXT_FEATURES = (
    "n_concordant", "anomaly", "persist_max", "nadir_risk", "anc_twin_log", "anc_twin_low",
    "anc_lab_low", "adherence_7d", "adherence_gap", "age65", "on_treatment", "myelotox",
)
FEATURE_NAMES: tuple[str, ...] = (
    tuple(f"z_{s}" for s in MODEL_SIGNALS)
    + tuple(f"slope3_{s}" for s in MODEL_SIGNALS)
    + CONTEXT_FEATURES
)
N_SIG = len(MODEL_SIGNALS)
IDX = {name: i for i, name in enumerate(FEATURE_NAMES)}

NADIR_CENTER_DAYS = 10.0
NADIR_WIDTH_DAYS = 3.5


def signal_matrix(series: PatientSeries) -> np.ndarray:
    """(1, T, S) transformed model-signal values."""
    return np.stack([series.transformed(k) for k in MODEL_SIGNALS], axis=-1)[None, :, :]


def nadir_risk(days_since_dose: np.ndarray, myelotox: float, gcsf_cycle: np.ndarray) -> np.ndarray:
    w = np.exp(-(((days_since_dose - NADIR_CENTER_DAYS) / NADIR_WIDTH_DAYS) ** 2))
    w = np.where(np.isnan(days_since_dose), 0.0, w)
    return w * myelotox * (1.0 - 0.6 * gcsf_cycle)


def feature_tensor(
    values_t: np.ndarray,          # (B, T, S) transformed, NaN missing
    baseline: Baseline,
    *,
    nadir: np.ndarray,              # (B, T) or (T,)
    anc_twin_log: np.ndarray,       # (B, T) or (T,)
    anc_twin_low: np.ndarray,
    anc_lab_low: np.ndarray,
    adherence_7d: np.ndarray,
    adherence_sched: np.ndarray,
    age65: float,
    on_treatment: np.ndarray,
    myelotox: float,
) -> np.ndarray:
    B, T, S = values_t.shape
    z = adverse_z(values_t, baseline)
    z_cf = carry_forward(z, 1)
    slope3 = rolling_slope(z, 3)
    pers = persistence(z_cf, DEVIATION_Z)
    signs = np.array([adverse_sign(k) for k in MODEL_SIGNALS])
    anomaly = anomaly_score(z_cf * signs, baseline.corr_inv)

    F = np.zeros((B, T, len(FEATURE_NAMES)))
    F[:, :, :N_SIG] = np.clip(np.nan_to_num(z_cf, nan=0.0), -3.0, 8.0)
    F[:, :, N_SIG:2 * N_SIG] = np.clip(np.nan_to_num(slope3, nan=0.0), -4.0, 4.0)

    def put(name: str, arr) -> None:
        F[:, :, IDX[name]] = np.broadcast_to(np.asarray(arr, dtype=float), (B, T))

    put("n_concordant", np.nansum(z_cf >= DEVIATION_Z, axis=-1))
    put("anomaly", np.clip(anomaly, 0.0, 10.0))
    put("persist_max", np.clip(pers.max(axis=-1), 0.0, 7.0))
    put("nadir_risk", nadir)
    put("anc_twin_log", anc_twin_log)
    put("anc_twin_low", anc_twin_low)
    put("anc_lab_low", anc_lab_low)
    put("adherence_7d", adherence_7d)
    put("adherence_gap", (1.0 - np.asarray(adherence_7d)) * (np.asarray(adherence_sched) > 0))
    put("age65", age65)
    put("on_treatment", on_treatment)
    put("myelotox", myelotox)
    return F


def series_context(
    series: PatientSeries,
    neutro: NeutrophilTwin | None = None,
    anc_arrays: tuple[np.ndarray, np.ndarray] | None = None,
) -> dict[str, np.ndarray | float]:
    """Per-day clinical/twin context arrays for the actual history.

    `anc_arrays` lets a caller pass the (causal) twin ANC features computed on
    a longer as-of view; they are truncated to this series' length.
    """
    n = series.n
    dsd = series.days_since_dose()
    gcsf = series.gcsf_since_last_dose()
    myelo = series.regimen.myelotox
    if anc_arrays is not None:
        anc_log, anc_low = anc_arrays[0][:n], anc_arrays[1][:n]
    else:
        anc_log, anc_low = (neutro or NeutrophilTwin(series)).daily_features()
    lab_low = np.zeros(n)
    for d, v, _ in series.labs.get("anc", []):
        if v < 1.0:
            lab_low[d - 1: min(n, d + 6)] = 1.0
    adh, sched = series.adherence_7d()
    return {
        "nadir": nadir_risk(dsd, myelo, gcsf),
        "anc_twin_log": anc_log, "anc_twin_low": anc_low, "anc_lab_low": lab_low,
        "adherence_7d": adh, "adherence_sched": sched,
        "age65": 1.0 if series.profile.age >= 65 else 0.0,
        "on_treatment": (~np.isnan(dsd)).astype(float),
        "myelotox": myelo,
    }


def series_features(
    series: PatientSeries, baseline: Baseline, neutro: NeutrophilTwin | None = None,
    anc_arrays: tuple[np.ndarray, np.ndarray] | None = None,
) -> np.ndarray:
    """(T, F) feature matrix for the patient's actual history."""
    ctx = series_context(series, neutro, anc_arrays)
    return feature_tensor(signal_matrix(series), baseline, **ctx)[0]
