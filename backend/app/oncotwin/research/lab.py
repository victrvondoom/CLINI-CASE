"""Twin Research Lab — configurable, reproducible experiments on the synthetic cohort.

An experiment = (feature groups, baseline type, horizon, model family). It is
trained on the TRAIN patients, tuned (L2, alert threshold) on VALIDATION
patients and evaluated once on the untouched TEST patients — the same split as
the deployed OT-ACUTE-7 model.

Feature groups
  wearables     personal-baseline z + 3-day slope: resting HR, HRV, temperature, SpO₂, steps, sleep
  home          z + slope: weight, systolic BP
  symptoms      z + slope: PRO symptom burden
  multi_signal  concordance / Mahalanobis anomaly / persistence — RECOMPUTED over
                whichever signal groups are included (so removing wearables really
                removes their information)
  labs_twin     neutrophil twin (ANC estimate, P[ANC<1]) + measured ANC < 1.0
  treatment     nadir timing, on-treatment flag, regimen myelotoxicity
  adherence     supportive-medication adherence
  demographics  age ≥ 65

Metrics (test): AUROC with a 95 % patient-bootstrap CI, AUPRC, Brier, expected
calibration error + calibration bins; at the validation-derived alert threshold
(lowest threshold reaching PPV ≥ 25 %, as the deployed EARLY WARNING tier):
precision, recall, F1, alert onsets that were false per 100 patient-days,
events detected and median lead time. Event-level numbers use the probability
threshold alone (no clinical rules, no hysteresis) so arms are comparable.
Paired ΔAUROC vs a reference arm uses the same bootstrap resamples.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

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
from app.oncotwin.engine.features import signal_matrix
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
from app.oncotwin.ml.train import population_baseline
from app.oncotwin.signals import MODEL_SIGNALS, adverse_sign

SIGNAL_GROUPS = {
    "wearables": ("resting_hr", "hrv_sdnn", "temperature", "spo2", "steps", "sleep_hours"),
    "home": ("weight", "sbp"),
    "symptoms": ("symptom_score",),
}
CONTEXT_GROUPS = {
    "labs_twin": ("anc_twin_log", "anc_twin_low", "anc_lab_low"),
    "treatment": ("nadir_risk", "on_treatment", "myelotox"),
    "adherence": ("adherence_7d", "adherence_gap"),
    "demographics": ("age65",),
}
ALL_GROUPS = (*SIGNAL_GROUPS, "multi_signal", *CONTEXT_GROUPS)
GROUP_LABELS = {
    "wearables": "Wearables (HR, HRV, temperature, SpO₂, steps, sleep)", "home": "Home devices (weight, BP)",
    "symptoms": "Patient-reported symptoms", "multi_signal": "Multi-signal composites",
    "labs_twin": "Labs + neutrophil twin", "treatment": "Treatment context", "adherence": "Adherence",
    "demographics": "Demographics",
}
MODELS = {"logistic": "L2 logistic regression (numpy IRLS)",
          "anomaly_score": "Mahalanobis anomaly score alone (no training)",
          "vital_threshold_rule": "Population vital-sign thresholds (temp ≥ 38.0 °C, HR ≥ 100, SpO₂ < 92 %, SBP < 90)"}
L2_GRID = (0.3, 1.0, 3.0, 10.0, 30.0)
ALERT_PPV = 0.25
ALERT_SENS_FALLBACK = 0.60
BOOT_REPS = 200


@dataclass
class ExperimentConfig:
    name: str
    groups: tuple[str, ...] = ALL_GROUPS
    baseline: str = "personal"            # personal | population
    horizon: int = 7
    model: str = "logistic"
    notes: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def describe(self) -> dict[str, Any]:
        return {"name": self.name, "groups": list(self.groups), "group_labels": [GROUP_LABELS[g] for g in self.groups],
                "baseline": self.baseline, "horizon_days": self.horizon, "model": self.model,
                "model_label": MODELS[self.model], "notes": self.notes}


def _signals_for(groups: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(k for k in MODEL_SIGNALS if any(k in SIGNAL_GROUPS[g] for g in groups if g in SIGNAL_GROUPS))


def subset_features(p, groups: tuple[str, ...], baseline: Baseline) -> tuple[np.ndarray, list[str]]:
    """(T, F) features for one cohort patient restricted to `groups` (mirrors engine.features)."""
    series, ctx = p.data.series, p.ctx
    keys = _signals_for(groups)
    cols: list[np.ndarray] = []
    names: list[str] = []
    T = series.n
    if keys:
        idx = [MODEL_SIGNALS.index(k) for k in keys]
        z = adverse_z(signal_matrix(series)[:, :, idx], baseline, keys=keys)
        z_cf = carry_forward(z, 1)
        zf = np.clip(np.nan_to_num(z_cf, nan=0.0), -3.0, 8.0)[0]
        sf = np.clip(np.nan_to_num(rolling_slope(z, 3), nan=0.0), -4.0, 4.0)[0]
        for j, k in enumerate(keys):
            cols.append(zf[:, j])
            names.append(f"z_{k}")
        for j, k in enumerate(keys):
            cols.append(sf[:, j])
            names.append(f"slope3_{k}")
        if "multi_signal" in groups:
            pers = persistence(z_cf, DEVIATION_Z)[0]
            signs = np.array([adverse_sign(k) for k in keys])
            corr = np.linalg.inv(baseline.corr_inv)[np.ix_(idx, idx)]
            anom = anomaly_score(z_cf * signs, np.linalg.inv(corr))[0]
            cols += [np.nansum(z_cf[0] >= DEVIATION_Z, axis=-1).astype(float), np.clip(anom, 0.0, 10.0),
                     np.clip(pers.max(axis=-1), 0.0, 7.0)]
            names += ["n_concordant", "anomaly", "persist_max"]
    for g in groups:
        for f in CONTEXT_GROUPS.get(g, ()):
            if f == "adherence_gap":
                v = (1.0 - np.asarray(ctx["adherence_7d"])) * (np.asarray(ctx["adherence_sched"]) > 0)
            elif f == "nadir_risk":
                v = np.asarray(ctx["nadir"])
            else:
                v = ctx[f]
            cols.append(np.broadcast_to(np.asarray(v, dtype=float), (T,)).astype(float))
            names.append(f)
    return (np.stack(cols, axis=1) if cols else np.zeros((T, 0))), names


def labels(p, h: int) -> tuple[np.ndarray, np.ndarray]:
    """y[t] = qualifying onset on day t+1..t+h; eligibility as in ml/train.py (h = 7 reproduces it)."""
    d = p.data
    n = d.series.n
    on_tx = ~np.isnan(d.series.days_since_dose())
    y = np.zeros(n)
    ok = np.zeros(n, dtype=bool)
    for t in range(n):
        day = t + 1
        y[t] = 1.0 if any(day < o <= day + h for o in d.onsets) else 0.0
        ok[t] = bool(on_tx[t] and not d.acute[t] and (day + h <= n or y[t] == 1))
    return y, ok


def _stack(parts: list[tuple[np.ndarray, np.ndarray, np.ndarray]]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    X = np.concatenate([F[ok] for F, _, ok in parts])
    y = np.concatenate([y[ok] for _, y, ok in parts])
    pid = np.concatenate([np.full(int(ok.sum()), i) for i, (_, _, ok) in enumerate(parts)])
    return X, y, pid


def ece(y: np.ndarray, p: np.ndarray, bins: int = 10) -> float:
    order = np.argsort(p)
    tot = sum(len(c) * abs(float(np.mean(p[c])) - float(np.mean(y[c]))) for c in np.array_split(order, bins) if len(c))
    return round(tot / max(1, len(p)), 5)


def event_metrics(test, scores: list[np.ndarray], thr: float, h: int) -> dict[str, Any]:
    """Events caught within the horizon before onset, lead time, and false alert onsets."""
    detected, leads, n_events, false_on, pdays = 0, [], 0, 0, 0
    for p, s in zip(test, scores, strict=True):
        d = p.data
        first = d.series.first_dose_day
        alerts = s >= thr
        _, ok = labels(p, h)
        for o in d.onsets:
            if first is None or o <= first:
                continue
            n_events += 1
            window = [t for t in range(max(0, o - 1 - h), o - 1) if alerts[t] and not d.acute[t]]
            if window:
                detected += 1
                leads.append(o - (min(window) + 1))
        pdays += int(ok.sum())
        prev = False
        for t in range(d.series.n):
            if d.acute[t]:
                prev = False
                continue
            if alerts[t] and not prev and ok[t] and not any(t + 1 < o <= t + 1 + h for o in d.onsets):
                false_on += 1
            prev = bool(alerts[t])
    return {"events": n_events, "events_detected": detected,
            "event_sensitivity": round(detected / n_events, 3) if n_events else None,
            "median_lead_time_days": float(np.median(leads)) if leads else None,
            "lead_times_days": sorted(int(x) for x in leads),
            "false_alert_onsets_per_100_patient_days": round(100.0 * false_on / max(1, pdays), 2),
            "patient_days": pdays}


@dataclass
class ArmResult:
    config: ExperimentConfig
    metrics: dict[str, Any]
    test_scores: np.ndarray
    test_y: np.ndarray
    test_pid: np.ndarray
    seconds: float


def _boot_ci(y: np.ndarray, s: np.ndarray, pid: np.ndarray, reps: int = BOOT_REPS, seed: int = 17) -> list:
    rng = np.random.default_rng(seed)
    ids = np.unique(pid)
    groups = [np.nonzero(pid == i)[0] for i in ids]
    vals = []
    for _ in range(reps):
        take = np.concatenate([groups[i] for i in rng.integers(0, len(ids), size=len(ids))])
        a = auroc(y[take], s[take])
        if not np.isnan(a):
            vals.append(a)
    return [round(float(np.percentile(vals, 2.5)), 4), round(float(np.percentile(vals, 97.5)), 4)] if vals else [None, None]


def run_experiment(cohort, cfg: ExperimentConfig, *, pop_base: Baseline | None = None) -> ArmResult:
    t0 = time.time()
    tr, va, te = cohort.part("train"), cohort.part("valid"), cohort.part("test")

    if cfg.model == "vital_threshold_rule":
        from app.oncotwin.engine.warning import RANK
        from app.oncotwin.ml.train import population_threshold_alerts
        per = [np.array([1.0 if r >= RANK["EARLY WARNING"] else 0.0 for r in population_threshold_alerts(p.data)]) for p in te]
        ys, ss, ps = [], [], []
        for i, (p, s) in enumerate(zip(te, per, strict=True)):
            y, ok = labels(p, cfg.horizon)
            ys.append(y[ok]); ss.append(s[ok]); ps.append(np.full(int(ok.sum()), i))
        y, s, pid = np.concatenate(ys), np.concatenate(ss), np.concatenate(ps)
        tp = float(((s >= 0.5) & (y == 1)).sum())
        prec, rec = tp / max(1.0, float((s >= 0.5).sum())), tp / max(1.0, float(y.sum()))
        return ArmResult(cfg, {"auroc": None, "auroc_95ci": [None, None], "auprc": None, "brier": None, "ece": None,
                               "precision": round(prec, 3), "recall": round(rec, 3),
                               "f1": round(2 * prec * rec / max(1e-9, prec + rec), 3),
                               "threshold": None, "threshold_basis": "single-reading population rule",
                               **event_metrics(te, per, 0.5, cfg.horizon),
                               "n_features": 0, "n_patient_days": int(len(y)), "n_positive": int(y.sum())},
                         s, y, pid, time.time() - t0)

    base_of = (lambda p: p.baseline) if cfg.baseline == "personal" else (lambda p: pop_base)

    def part(ps):
        out, names = [], []
        for p in ps:
            F, names = subset_features(p, cfg.groups, base_of(p))
            out.append((F, *labels(p, cfg.horizon)))
        return out, names

    trp, names = part(tr)
    vap, _ = part(va)
    tep, _ = part(te)
    Xtr, ytr, _ = _stack(trp)
    Xva, yva, _ = _stack(vap)
    Xte, yte, pid = _stack(tep)
    coefs, chosen = None, None
    if cfg.model == "anomaly_score":
        j = names.index("anomaly")
        pva, pte = Xva[:, j], Xte[:, j]
        per = [F[:, j] for F, _, _ in tep]
    else:
        scores = {l2: log_loss(yva, fit_logistic(Xtr, ytr, l2).predict_proba(Xva)) for l2 in L2_GRID}
        chosen = min(scores, key=scores.get)
        m = fit_logistic(Xtr, ytr, chosen)
        pva, pte = m.predict_proba(Xva), m.predict_proba(Xte)
        coefs = sorted(({"feature": n, "coef_standardised": round(float(c), 4)} for n, c in zip(names, m.coef, strict=True)),
                       key=lambda d: -abs(d["coef_standardised"]))
        per = [m.predict_proba(F) for F, _, _ in tep]
    thr = threshold_for_ppv(yva, pva, ALERT_PPV)
    basis = f"lowest validation threshold with PPV ≥ {ALERT_PPV:.0%}"
    if thr is None:
        thr = threshold_for_sensitivity(yva, pva, ALERT_SENS_FALLBACK)
        basis = f"validation sensitivity {ALERT_SENS_FALLBACK:.0%} (PPV target unattainable)"
    flag = pte >= thr
    tp = float((flag & (yte == 1)).sum())
    prec, rec = tp / max(1.0, float(flag.sum())), tp / max(1.0, float(yte.sum()))
    is_prob = cfg.model == "logistic"
    metrics = {
        "auroc": round(auroc(yte, pte), 4), "auroc_95ci": _boot_ci(yte, pte, pid),
        "auprc": round(average_precision(yte, pte), 4),
        "brier": round(brier(yte, pte), 5) if is_prob else None, "ece": ece(yte, pte) if is_prob else None,
        "calibration": calibration_bins(yte, pte, 10) if is_prob else None,
        "threshold": round(float(thr), 5), "threshold_basis": basis,
        "precision": round(prec, 3), "recall": round(rec, 3), "f1": round(2 * prec * rec / max(1e-9, prec + rec), 3),
        **event_metrics(te, per, thr, cfg.horizon),
        "n_features": len(names), "features": names, "l2": chosen, "top_coefficients": (coefs or [])[:8],
        "n_train_days": int(len(ytr)), "n_patient_days": int(len(yte)), "n_positive": int(yte.sum()),
        "prevalence": round(float(yte.mean()), 4),
    }
    return ArmResult(cfg, metrics, pte, yte, pid, time.time() - t0)


def paired_delta(a: ArmResult, b: ArmResult, reps: int = BOOT_REPS, seed: int = 23) -> dict[str, Any] | None:
    """ΔAUROC (a − b) with a paired patient bootstrap; both arms must score the same test rows."""
    if a.metrics.get("auroc") is None or b.metrics.get("auroc") is None or not np.array_equal(a.test_y, b.test_y) \
            or not np.array_equal(a.test_pid, b.test_pid):
        return None
    rng = np.random.default_rng(seed)
    ids = np.unique(a.test_pid)
    groups = [np.nonzero(a.test_pid == i)[0] for i in ids]
    d = []
    for _ in range(reps):
        take = np.concatenate([groups[i] for i in rng.integers(0, len(ids), size=len(ids))])
        x, y = auroc(a.test_y[take], a.test_scores[take]), auroc(b.test_y[take], b.test_scores[take])
        if not (np.isnan(x) or np.isnan(y)):
            d.append(x - y)
    lo, hi = float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))
    return {"delta_auroc": round(a.metrics["auroc"] - b.metrics["auroc"], 4), "ci95": [round(lo, 4), round(hi, 4)],
            "significant": bool(lo > 0 or hi < 0),
            "interpretation": "better" if lo > 0 else "worse" if hi < 0 else "not distinguishable at 95 %"}


_POP_BASE: dict[tuple[int, int], Baseline] = {}


def pooled_baseline(train) -> Baseline:
    """Same math as ml.train.population_baseline, but from the cohort's cached per-patient
    baselines instead of recomputing each patient's baseline once per signal (a test pins
    equality)."""
    from app.oncotwin.engine.baseline import SignalBaseline
    from app.oncotwin.signals import SIGNALS

    sigs = {}
    for key in MODEL_SIGNALS:
        meds = [p.baseline.signals[key].median_t for p in train if p.baseline.signals[key].n_days]
        spreads = [p.baseline.signals[key].spread_t for p in train if p.baseline.signals[key].n_days]
        med = float(np.median(meds))
        between = float(np.median(np.abs(np.array(meds) - med)) * 1.4826)
        within = float(np.median(spreads))
        sigs[key] = SignalBaseline(key, med, max(SIGNALS[key].spread_floor, float(np.hypot(between, within))), len(meds), True)
    return Baseline(sigs, (1, 13), "population", 1.0, np.eye(len(MODEL_SIGNALS)))


def population_base(cohort) -> Baseline:
    key = (cohort.seed, cohort.n)
    if key not in _POP_BASE:
        _POP_BASE[key] = pooled_baseline(cohort.part("train"))
    return _POP_BASE[key]


def run(cohort, cfg: ExperimentConfig, reference: ExperimentConfig | None = None) -> dict[str, Any]:
    pb = population_base(cohort)
    arm = run_experiment(cohort, cfg, pop_base=pb)
    out = {"config": cfg.describe(), "metrics": arm.metrics, "seconds": round(arm.seconds, 1), "dataset": cohort.meta()}
    if reference is not None:
        ref = run_experiment(cohort, reference, pop_base=pb)
        out["reference"] = {"config": reference.describe(), "metrics": ref.metrics}
        out["paired_vs_reference"] = paired_delta(arm, ref)
    return out
