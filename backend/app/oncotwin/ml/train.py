"""Train + evaluate the OT-ACUTE-7 deterioration model on the synthetic cohort.

    python -m app.oncotwin.ml.train            # full run (≈800 patients, ~2 min)
    python -m app.oncotwin.ml.train --n 120    # quick run

Protocol (all splits are BY PATIENT, never by day):
  60 % train  → fit the model (+ 20 bootstrap refits for uncertainty)
  20 % valid  → choose the L2 penalty and DERIVE the tier thresholds
  20 % test   → every metric reported in the model card

Only on-treatment, not-in-acute-care, uncensored patient-days are scored.
Labels come from qualifying Encounter onsets in the record — never from the
simulator's latent state. The event-level evaluation runs the full tiering
system (thresholds + clinical rules + hysteresis), i.e. what a clinician
would actually see.

Every number written to the artifact is computed here on synthetic data and
is labelled as such; it is NOT evidence of clinical performance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from app.oncotwin import ONCOTWIN_VERSION
from app.oncotwin.engine.baseline import Baseline, SignalBaseline, compute_baseline
from app.oncotwin.engine.features import (
    FEATURE_NAMES,
    feature_tensor,
    series_context,
    series_features,
    signal_matrix,
)
from app.oncotwin.engine.neutrophil import NeutrophilTwin
from app.oncotwin.engine.series import PatientSeries, build_series
from app.oncotwin.engine.warning import RANK, apply_hysteresis, probability_tier, rule_tiers
from app.oncotwin.ml.logistic import (
    auroc,
    average_precision,
    brier,
    calibration_bins,
    fit_logistic,
    log_loss,
    threshold_for_ppv,
    threshold_for_sensitivity,
)
from app.oncotwin.outcome import HORIZON_DAYS, OUTCOME_DEFINITION, OUTCOME_ID
from app.oncotwin.signals import MODEL_SIGNALS, SIGNALS
from app.oncotwin.simulator.cohort import generate_cohort

ARTIFACT_DIR = Path(__file__).resolve().parent / "artifacts"
ARTIFACT_PATH = ARTIFACT_DIR / "deterioration_lr_v1.json"
MODEL_ID = "oncotwin-deterioration-lr"
MODEL_VERSION = "1.0.0"
COHORT_SEED = 20260923
L2_GRID = (0.3, 1.0, 3.0, 10.0, 30.0)
N_BOOTSTRAP = 20
PPV_TARGETS = {"watch": 0.10, "early_warning": 0.25, "high_priority": 0.50}
SENS_FALLBACK = {"watch": 0.85, "early_warning": 0.60, "high_priority": 0.30}


@dataclass
class PatientData:
    patient_id: str
    series: PatientSeries
    F: np.ndarray
    y: np.ndarray
    eligible: np.ndarray
    onsets: list[int]
    acute: np.ndarray
    nadir: np.ndarray               # expected-nadir timing weight (model feature + FN rule input)


def labels_from_record(series: PatientSeries, n_days: int) -> tuple[np.ndarray, np.ndarray, list[int]]:
    """y[t]=1 if a qualifying Encounter starts on t+1..t+7; eligibility mask."""
    onsets = sorted(a["day"] for a in series.admissions)
    n = series.n
    y = np.zeros(n)
    for t in range(n):
        day = t + 1
        if any(day < o <= day + HORIZON_DAYS for o in onsets):
            y[t] = 1.0
    first = series.first_dose_day
    dsd = series.days_since_dose()
    on_tx = ~np.isnan(dsd)
    acute = series.acute_care_mask()
    uncensored = np.array([(t + 1 + HORIZON_DAYS <= n_days) or y[t] == 1 for t in range(n)])
    eligible = on_tx & ~acute & uncensored
    if first is None:
        eligible[:] = False
    return y, eligible, onsets


def build_patient_dataset(sim) -> PatientData:
    rec = sim.record
    series = build_series(rec, rec.n_days)
    baseline = compute_baseline(series)
    ctx = series_context(series, NeutrophilTwin(series))
    F = feature_tensor(signal_matrix(series), baseline, **ctx)[0]
    y, eligible, onsets = labels_from_record(series, rec.n_days)
    return PatientData(rec.profile.patient_id, series, F, y, eligible, onsets, series.acute_care_mask(),
                       np.asarray(ctx["nadir"], dtype=float))


def _stack(data: list[PatientData]) -> tuple[np.ndarray, np.ndarray]:
    X = np.concatenate([d.F[d.eligible] for d in data])
    y = np.concatenate([d.y[d.eligible] for d in data])
    return X, y


def tier_sequence(d: PatientData, p: np.ndarray, thresholds: dict[str, float]) -> list[str]:
    """Exactly the deployed tiering: probability tier ∨ rule tier, then hysteresis."""
    rtiers, _ = rule_tiers(d.series, d.F, d.nadir, p, thresholds["watch"])
    raw = []
    for t in range(d.series.n):
        pt = probability_tier(float(p[t]), thresholds)
        raw.append(pt if RANK[pt] >= RANK[rtiers[t]] else rtiers[t])
    return apply_hysteresis(raw, d.acute)


def event_level(data: list[PatientData], alert_fn, min_rank: int) -> dict[str, Any]:
    """Sensitivity / lead time / false-alert burden for any per-day alert function."""
    detected, leads, n_events = 0, [], 0
    false_alerts, patient_days = 0, 0
    for d in data:
        alerts = alert_fn(d)        # list of per-day ranks
        first = d.series.first_dose_day
        for o in d.onsets:
            if first is None or o <= first:
                continue
            n_events += 1
            window = list(range(max(0, o - 1 - HORIZON_DAYS), o - 1))
            hits = [t for t in window if alerts[t] >= min_rank and not d.acute[t]]
            if hits:
                detected += 1
                leads.append(o - (min(hits) + 1))
        patient_days += int(d.eligible.sum())
        prev = 0
        for t in range(d.series.n):
            if d.acute[t]:
                prev = 0
                continue
            on = alerts[t] >= min_rank
            if on and prev < min_rank and d.eligible[t]:
                day = t + 1
                if not any(day < o <= day + HORIZON_DAYS for o in d.onsets):
                    false_alerts += 1
            prev = alerts[t]
    return {
        "events": n_events,
        "events_detected": detected,
        "sensitivity": round(detected / n_events, 3) if n_events else None,
        "median_lead_time_days": float(np.median(leads)) if leads else None,
        "lead_time_days_iqr": [float(np.percentile(leads, 25)), float(np.percentile(leads, 75))] if leads else None,
        "false_alert_onsets_per_100_patient_days": round(100.0 * false_alerts / max(1, patient_days), 2),
        "patient_days": patient_days,
    }


def population_baseline(train: list[PatientData]) -> Baseline:
    """Cohort-level 'normal' (no personalisation) — for the ablation comparator."""
    sigs: dict[str, SignalBaseline] = {}
    for key in MODEL_SIGNALS:
        meds, spreads = [], []
        for d in train:
            b = compute_baseline(d.series).signals[key]
            if b.n_days:
                meds.append(b.median_t)
                spreads.append(b.spread_t)
        med = float(np.median(meds))
        between = float(np.median(np.abs(np.array(meds) - med)) * 1.4826)
        within = float(np.median(spreads))
        sigs[key] = SignalBaseline(key, med, max(SIGNALS[key].spread_floor, float(np.hypot(between, within))), len(meds), True)
    return Baseline(sigs, (1, 13), "population", 1.0, np.eye(len(MODEL_SIGNALS)))


def population_threshold_alerts(d: PatientData) -> list[int]:
    """Standard single-reading vital-sign thresholds (no personalisation)."""
    v = d.series.values
    out = []
    for t in range(d.series.n):
        hit = (
            (v["temperature"][t] >= 38.0) or (v["resting_hr"][t] >= 100)
            or (v["spo2"][t] < 92) or (v["sbp"][t] < 90)
        )
        out.append(RANK["EARLY WARNING"] if bool(hit) else 0)
    return out


def train(n_patients: int = 800, seed: int = COHORT_SEED, *, write: bool = True, verbose: bool = True) -> dict[str, Any]:
    t0 = datetime.now(UTC)
    sims = generate_cohort(n_patients, seed)
    data = [build_patient_dataset(s) for s in sims]
    order = np.random.default_rng(seed).permutation(len(data))
    n_tr, n_va = int(0.6 * len(data)), int(0.2 * len(data))
    train_d = [data[i] for i in order[:n_tr]]
    valid_d = [data[i] for i in order[n_tr:n_tr + n_va]]
    test_d = [data[i] for i in order[n_tr + n_va:]]
    Xtr, ytr = _stack(train_d)
    Xva, yva = _stack(valid_d)
    Xte, yte = _stack(test_d)

    # L2 selection on validation log-loss
    scores = {}
    for l2 in L2_GRID:
        m = fit_logistic(Xtr, ytr, l2)
        scores[l2] = log_loss(yva, m.predict_proba(Xva))
    best_l2 = min(scores, key=scores.get)
    model = fit_logistic(Xtr, ytr, best_l2)

    # Bootstrap (resample training PATIENTS) for prediction intervals
    rng = np.random.default_rng(seed + 1)
    boots: list[list[float]] = []
    for _ in range(N_BOOTSTRAP):
        idx = rng.integers(0, len(train_d), size=len(train_d))
        Xb, yb = _stack([train_d[i] for i in idx])
        if yb.sum() < 5:
            continue
        mb = fit_logistic(Xb, yb, best_l2, mean=model.mean, std=model.std)
        boots.append([mb.intercept, *mb.coef.tolist()])

    # Tier thresholds derived on validation
    pva = model.predict_proba(Xva)
    thresholds: dict[str, float] = {}
    derivation: dict[str, str] = {}
    for tier in ("watch", "early_warning", "high_priority"):
        thr = threshold_for_ppv(yva, pva, PPV_TARGETS[tier])
        if thr is None:
            thr = threshold_for_sensitivity(yva, pva, SENS_FALLBACK[tier])
            derivation[tier] = f"validation sensitivity {SENS_FALLBACK[tier]:.0%} (PPV target {PPV_TARGETS[tier]:.0%} unattainable)"
        else:
            derivation[tier] = f"lowest threshold with validation PPV ≥ {PPV_TARGETS[tier]:.0%}"
        thresholds[tier] = thr
    thresholds["early_warning"] = max(thresholds["early_warning"], thresholds["watch"] * 1.5)
    thresholds["high_priority"] = max(thresholds["high_priority"], thresholds["early_warning"] * 1.5)

    # ---- Test-set evaluation ----------------------------------------------
    pte = model.predict_proba(Xte)
    day_level = {
        "auroc": round(auroc(yte, pte), 4),
        "auprc": round(average_precision(yte, pte), 4),
        "brier": round(brier(yte, pte), 5),
        "prevalence": round(float(yte.mean()), 4),
        "n_patient_days": int(len(yte)),
        "n_positive_days": int(yte.sum()),
    }
    for tier in ("watch", "early_warning", "high_priority"):
        flag = pte >= thresholds[tier]
        tp = float((flag & (yte == 1)).sum())
        day_level[f"{tier}_sensitivity"] = round(tp / max(1, yte.sum()), 3)
        day_level[f"{tier}_ppv"] = round(tp / max(1, flag.sum()), 3)

    def system_alerts(d: PatientData) -> list[int]:
        p = model.predict_proba(d.F)
        return [RANK.get(t, 0) for t in tier_sequence(d, p, thresholds)]

    event = {
        "early_warning_or_higher": event_level(test_d, system_alerts, RANK["EARLY WARNING"]),
        "high_priority": event_level(test_d, system_alerts, RANK["HIGH PRIORITY"]),
    }

    # ---- Comparators --------------------------------------------------------
    pop_rule = event_level(test_d, population_threshold_alerts, RANK["EARLY WARNING"])
    # Ablation: identical pipeline, but deviations measured against a pooled
    # cohort "normal" instead of each patient's own baseline. Thresholds are
    # re-derived on validation the same way, then the full tiering system is
    # evaluated event-by-event — a like-for-like comparison.
    pop_base = population_baseline(train_d)
    abl_data: dict[str, list[PatientData]] = {}
    for split, ds in (("train", train_d), ("valid", valid_d), ("test", test_d)):
        out = []
        for d in ds:
            Fp = series_features(d.series, pop_base, NeutrophilTwin(d.series))
            out.append(PatientData(d.patient_id, d.series, Fp, d.y, d.eligible, d.onsets, d.acute, d.nadir))
        abl_data[split] = out
    m_pop = fit_logistic(*_stack(abl_data["train"]), best_l2)
    Xa_va, ya_va = _stack(abl_data["valid"])
    Xa_te, ya_te = _stack(abl_data["test"])
    ablation_auroc = auroc(ya_te, m_pop.predict_proba(Xa_te))
    pa_va = m_pop.predict_proba(Xa_va)
    abl_thr = {}
    for tier in ("watch", "early_warning", "high_priority"):
        thr = threshold_for_ppv(ya_va, pa_va, PPV_TARGETS[tier])
        abl_thr[tier] = thr if thr is not None else threshold_for_sensitivity(ya_va, pa_va, SENS_FALLBACK[tier])
    abl_thr["early_warning"] = max(abl_thr["early_warning"], abl_thr["watch"] * 1.5)
    abl_thr["high_priority"] = max(abl_thr["high_priority"], abl_thr["early_warning"] * 1.5)

    def ablation_alerts(d: PatientData) -> list[int]:
        return [RANK.get(t, 0) for t in tier_sequence(d, m_pop.predict_proba(d.F), abl_thr)]

    ablation_event = event_level(abl_data["test"], ablation_alerts, RANK["EARLY WARNING"])
    sig_idx = [i for i, f in enumerate(FEATURE_NAMES) if f.startswith(("z_", "slope3_"))]
    m_sig = fit_logistic(Xtr[:, sig_idx], ytr, best_l2)
    signals_only_auroc = auroc(yte, m_sig.predict_proba(Xte[:, sig_idx]))

    n_events_all = sum(len(d.onsets) for d in data)
    artifact: dict[str, Any] = {
        "model_id": MODEL_ID,
        "version": MODEL_VERSION,
        "oncotwin_version": ONCOTWIN_VERSION,
        "algorithm": "L2-regularised logistic regression (Newton/IRLS, numpy); bootstrap ensemble for intervals",
        "outcome": OUTCOME_DEFINITION,
        "outcome_id": OUTCOME_ID,
        "horizon_days": HORIZON_DAYS,
        "feature_names": list(FEATURE_NAMES),
        "mean": model.mean.round(8).tolist(),
        "std": model.std.round(8).tolist(),
        "intercept": round(model.intercept, 8),
        "coef": model.coef.round(8).tolist(),
        "l2": best_l2,
        "l2_validation_logloss": {str(k): round(v, 5) for k, v in scores.items()},
        "bootstrap": [[round(x, 8) for x in b] for b in boots],
        "thresholds": {**{k: round(v, 5) for k, v in thresholds.items()}, "derivation": derivation},
        "metrics": {
            "data": "SYNTHETIC held-out test patients — not clinical performance",
            "day_level": day_level,
            "event_level": event,
            "calibration_test": calibration_bins(yte, pte, 10),
        },
        "comparators": {
            "population_threshold_rule": {
                "definition": "alert on any single reading: temp ≥ 38.0 °C, resting HR ≥ 100, SpO₂ < 92 %, SBP < 90",
                **pop_rule,
            },
            "same_model_without_personal_baseline": {
                "definition": "identical features, z-scores against a pooled cohort 'normal' instead of each patient's baseline",
                "test_auroc": round(ablation_auroc, 4),
                "early_warning_or_higher": ablation_event,
            },
            "wearable_deviation_features_only": {
                "definition": "only personal-baseline z / slope features (no labs, treatment timing, adherence)",
                "test_auroc": round(signals_only_auroc, 4),
            },
        },
        "training": {
            "cohort": "synthetic (app/oncotwin/simulator/cohort.py)",
            "cohort_seed": seed,
            "n_patients": len(data),
            "n_train": len(train_d), "n_valid": len(valid_d), "n_test": len(test_d),
            "n_events_total": n_events_all,
            "patients_with_event": sum(1 for d in data if d.onsets),
            "train_patient_days": int(len(ytr)), "train_positive_days": int(ytr.sum()),
            "trained_at": t0.isoformat().replace("+00:00", "Z"),
            "duration_seconds": round((datetime.now(UTC) - t0).total_seconds(), 1),
        },
        "limitations": [
            "Trained and evaluated only on synthetic patients generated by a model that shares structure with the twin (identical-twin experiment).",
            "Not validated on real patients; not a medical device; for clinical decision SUPPORT only.",
            "Outcome is limited to the OP-35 conditions represented in the simulator (febrile neutropenia / sepsis / pneumonia, dehydration).",
        ],
    }
    payload = json.dumps({k: v for k, v in artifact.items() if k != "training"}, sort_keys=True).encode()
    artifact["sha256"] = hashlib.sha256(payload).hexdigest()
    if write:
        ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
        ARTIFACT_PATH.write_text(json.dumps(artifact, indent=1), encoding="utf-8")
    if verbose:
        print(json.dumps({k: artifact[k] for k in ("l2", "thresholds", "metrics", "comparators")}, indent=1))
        print(json.dumps(artifact["training"], indent=1))
    return artifact


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, default=800)
    ap.add_argument("--seed", type=int, default=COHORT_SEED)
    ap.add_argument("--dry-run", action="store_true", help="do not write the artifact")
    args = ap.parse_args()
    train(args.n, args.seed, write=not args.dry_run)


if __name__ == "__main__":
    main()
