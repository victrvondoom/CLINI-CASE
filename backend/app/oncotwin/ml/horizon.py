"""Multi-horizon risk — a discrete-time survival (hazard) model.

For each eligible patient-day t and each lag k = 1..7, the patient is at risk
of an OT-ACUTE onset on day t+k if no onset occurred on t+1..t+k−1 and day
t+k is observed (right-censoring handled by construction). One L2 logistic
model estimates the daily hazard

    h_k(x_t) = σ(β0 + γ_k + β·z(x_t)),   k = 1..7   (γ_1 ≡ 0)

and the cumulative incidence F_h = 1 − Π_{k≤h} (1 − h_k). The 24 h, 72 h and
7-day risks are therefore CONSISTENT (monotone in the horizon) by
construction — independently trained per-horizon classifiers are not.

Horizon support policy — a horizon is displayed only when
  • the data cadence supports it: the twin's signals are DAILY aggregates, so
    nothing shorter than 24 h is predicted (a 6 h horizon would need intraday
    streams), and
  • on the untouched synthetic TEST patients: AUROC ≥ 0.70 with ≥ 20 positive
    patient-days.
Otherwise it is returned as "not supported" with the reason.

    python -m app.oncotwin.ml.horizon            # train on the cached cohort → artifact
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

from app.oncotwin import ONCOTWIN_VERSION
from app.oncotwin.engine.features import FEATURE_NAMES
from app.oncotwin.ml.logistic import (
    LogisticModel,
    auroc,
    average_precision,
    brier,
    calibration_bins,
    fit_logistic,
    log_loss,
)
from app.oncotwin.outcome import OUTCOME_ID

ARTIFACT_PATH = Path(__file__).resolve().parent / "artifacts" / "horizon_survival_v1.json"
MODEL_ID = "oncotwin-horizon-survival"
MODEL_VERSION = "1.0.0"
MAX_LAG = 7
LAG_NAMES = tuple(f"lag_{k}" for k in range(2, MAX_LAG + 1))
EVAL_HORIZONS = (1, 3, 7)
L2_GRID = (1.0, 3.0, 10.0, 30.0)
N_BOOT = 12
SUPPORT_MIN_AUROC = 0.70
SUPPORT_MIN_POSITIVES = 20
DATA_CADENCE_HOURS = 24
DISPLAY = {1: "24 h", 3: "72 h", 7: "7 days"}


def _lag_row(k: int) -> np.ndarray:
    v = np.zeros(len(LAG_NAMES))
    if k >= 2:
        v[k - 2] = 1.0
    return v


def person_period(patients) -> tuple[np.ndarray, np.ndarray]:
    """Expand eligible patient-days into (day × lag) at-risk rows; stop at the onset (censoring-aware)."""
    X, y = [], []
    for p in patients:
        d = p.data
        n = d.series.n
        onsets = set(d.onsets)
        on_tx = ~np.isnan(d.series.days_since_dose())
        for t in range(n):
            if not on_tx[t] or d.acute[t]:
                continue
            day = t + 1
            for k in range(1, MAX_LAG + 1):
                if day + k > n:
                    break
                lab = (day + k) in onsets
                X.append(np.concatenate([d.F[t], _lag_row(k)]))
                y.append(1.0 if lab else 0.0)
                if lab:
                    break
    return np.asarray(X), np.asarray(y)


def _cumulative(intercept: float, coef: np.ndarray, Xf: np.ndarray, mean: np.ndarray, std: np.ndarray) -> np.ndarray:
    """(N, 7) cumulative incidence for raw feature rows `Xf`."""
    out = np.zeros((len(Xf), MAX_LAG))
    surv = np.ones(len(Xf))
    for k in range(1, MAX_LAG + 1):
        full = np.hstack([Xf, np.repeat(_lag_row(k)[None, :], len(Xf), axis=0)])
        h = 1.0 / (1.0 + np.exp(-np.clip(intercept + ((full - mean) / std) @ coef, -35, 35)))
        surv = surv * (1.0 - h)
        out[:, k - 1] = 1.0 - surv
    return out


def horizon_labels(patients, h: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Eligible rows, labels (onset within h days) and patient index for horizon h."""
    X, y, pid = [], [], []
    for i, p in enumerate(patients):
        d = p.data
        n = d.series.n
        on_tx = ~np.isnan(d.series.days_since_dose())
        for t in range(n):
            if not on_tx[t] or d.acute[t]:
                continue
            day = t + 1
            lab = any(day < o <= day + h for o in d.onsets)
            if day + h > n and not lab:
                continue
            X.append(d.F[t])
            y.append(1.0 if lab else 0.0)
            pid.append(i)
    return np.asarray(X), np.asarray(y), np.asarray(pid)


def bootstrap_auroc_ci(y: np.ndarray, s: np.ndarray, pid: np.ndarray, reps: int = 200, seed: int = 7) -> list:
    """95 % CI for AUROC by resampling PATIENTS (days of one patient are not independent)."""
    rng = np.random.default_rng(seed)
    ids = np.unique(pid)
    groups = {i: np.nonzero(pid == i)[0] for i in ids}
    vals = []
    for _ in range(reps):
        take = np.concatenate([groups[i] for i in rng.choice(ids, size=len(ids), replace=True)])
        a = auroc(y[take], s[take])
        if not np.isnan(a):
            vals.append(a)
    return [round(float(np.percentile(vals, 2.5)), 4), round(float(np.percentile(vals, 97.5)), 4)] if vals else [None, None]


def train(n: int = 1000, *, write: bool = True, verbose: bool = True) -> dict[str, Any]:
    from app.oncotwin.ml.model import load_model
    from app.oncotwin.research.dataset import load_cohort

    t0 = time.time()
    cohort = load_cohort(n)
    tr, va, te = cohort.part("train"), cohort.part("valid"), cohort.part("test")
    Xtr, ytr = person_period(tr)
    Xva, yva = person_period(va)
    scores = {l2: log_loss(yva, fit_logistic(Xtr, ytr, l2).predict_proba(Xva)) for l2 in L2_GRID}
    best = min(scores, key=scores.get)
    model = fit_logistic(Xtr, ytr, best)
    rng = np.random.default_rng(cohort.seed + 11)
    boots = []
    for _ in range(N_BOOT):
        idx = rng.integers(0, len(tr), size=len(tr))
        Xb, yb = person_period([tr[i] for i in idx])
        if yb.sum() >= 10:
            mb = fit_logistic(Xb, yb, best, mean=model.mean, std=model.std)
            boots.append([mb.intercept, *mb.coef.tolist()])

    lr = load_model()
    metrics: dict[str, Any] = {}
    support: dict[str, Any] = {"6 h": {"supported": False, "reason": (
        f"Signals are {DATA_CADENCE_HOURS}-hour (daily) aggregates; a sub-daily horizon would need intraday streams.")}}
    for h in EVAL_HORIZONS:
        Xh, yh, pid = horizon_labels(te, h)
        cum = _cumulative(model.intercept, model.coef, Xh, model.mean, model.std)[:, h - 1]
        m = {"horizon_days": h, "n_patient_days": int(len(yh)), "n_positive": int(yh.sum()),
             "prevalence": round(float(yh.mean()), 4), "auroc": round(auroc(yh, cum), 4),
             "auroc_95ci_patient_bootstrap": bootstrap_auroc_ci(yh, cum, pid),
             "auprc": round(average_precision(yh, cum), 4), "brier": round(brier(yh, cum), 5),
             "calibration": calibration_bins(yh, cum, 10)}
        if h == 7:
            m["deployed_lr_auroc_same_rows"] = round(auroc(yh, lr.predict(Xh)), 4)
        metrics[DISPLAY[h]] = m
        ok = m["auroc"] >= SUPPORT_MIN_AUROC and m["n_positive"] >= SUPPORT_MIN_POSITIVES
        support[DISPLAY[h]] = {"supported": bool(ok), "reason": (
            f"test AUROC {m['auroc']:.3f} (policy ≥ {SUPPORT_MIN_AUROC}) with {m['n_positive']} positive patient-days"
            if ok else f"test AUROC {m['auroc']:.3f} / {m['n_positive']} positives below the support policy "
                       f"(AUROC ≥ {SUPPORT_MIN_AUROC}, ≥ {SUPPORT_MIN_POSITIVES} positives)")}
    artifact: dict[str, Any] = {
        "model_id": MODEL_ID, "version": MODEL_VERSION, "oncotwin_version": ONCOTWIN_VERSION,
        "algorithm": "discrete-time survival: L2 logistic hazard over (patient-day × lag 1..7), numpy IRLS",
        "outcome_id": OUTCOME_ID, "purpose": "consistent multi-horizon (24 h / 72 h / 7 d) risk of the OT-ACUTE outcome",
        "feature_names": list(FEATURE_NAMES), "lag_names": list(LAG_NAMES),
        "mean": model.mean.round(8).tolist(), "std": model.std.round(8).tolist(),
        "intercept": round(model.intercept, 8), "coef": model.coef.round(8).tolist(), "l2": best,
        "l2_validation_logloss": {str(k): round(v, 6) for k, v in scores.items()},
        "bootstrap": [[round(x, 8) for x in b] for b in boots],
        "metrics": {"data": "SYNTHETIC held-out test patients (same split as the deployed OT-ACUTE-7 model)", **metrics},
        "support_policy": {"data_cadence_hours": DATA_CADENCE_HOURS, "min_test_auroc": SUPPORT_MIN_AUROC,
                           "min_test_positives": SUPPORT_MIN_POSITIVES},
        "support": support,
        "training": {**cohort.meta(), "train_person_periods": int(len(ytr)), "train_events": int(ytr.sum()),
                     "trained_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                     "duration_seconds": round(time.time() - t0, 1)},
        "limitations": [
            "Synthetic identical-twin experiment (the generator shares structure with the twin); not clinical validation.",
            "The hazard depends on the lag only through an additive term (proportional odds across lags).",
        ],
    }
    payload = json.dumps({k: v for k, v in artifact.items() if k != "training"}, sort_keys=True).encode()
    artifact["sha256"] = hashlib.sha256(payload).hexdigest()
    if write:
        ARTIFACT_PATH.write_text(json.dumps(artifact, indent=1), encoding="utf-8")
        load_horizon_model.cache_clear()
    if verbose:
        print(json.dumps({"l2": best, "support": support,
                          "metrics": {k: {kk: v for kk, v in m.items() if kk != "calibration"} for k, m in metrics.items()}},
                         indent=1))
    return artifact


class HorizonModel:
    def __init__(self, artifact: dict[str, Any]):
        if tuple(artifact["feature_names"]) != FEATURE_NAMES:
            raise ValueError("Horizon artifact feature set does not match the running feature code — retrain.")
        self.artifact = artifact
        self.lr = LogisticModel(float(artifact["intercept"]), np.array(artifact["coef"]), np.array(artifact["mean"]),
                                np.array(artifact["std"]), float(artifact["l2"]))
        self.boots = np.array(artifact.get("bootstrap") or [[artifact["intercept"], *artifact["coef"]]])
        payload = json.dumps({k: v for k, v in artifact.items() if k not in ("training", "sha256")}, sort_keys=True).encode()
        self.integrity_verified = hashlib.sha256(payload).hexdigest() == artifact.get("sha256")

    def version_info(self) -> dict[str, Any]:
        a = self.artifact
        return {"model_id": a["model_id"], "version": a["version"], "artifact_sha256": a.get("sha256", ""),
                "integrity_verified": self.integrity_verified}

    def curve(self, x: np.ndarray) -> dict[str, Any]:
        x = np.atleast_2d(np.asarray(x, dtype=float))
        point = _cumulative(self.lr.intercept, self.lr.coef, x, self.lr.mean, self.lr.std)[0]
        draws = np.stack([_cumulative(b[0], b[1:], x, self.lr.mean, self.lr.std)[0] for b in self.boots])
        return {"days": list(range(1, MAX_LAG + 1)), "cumulative": [round(float(v), 4) for v in point],
                "p10": [round(float(v), 4) for v in np.percentile(draws, 10, axis=0)],
                "p90": [round(float(v), 4) for v in np.percentile(draws, 90, axis=0)]}

    def horizons(self, x: np.ndarray, primary_7d: float | None = None) -> dict[str, Any]:
        c = self.curve(x)
        sup = self.artifact["support"]
        rows = [{"horizon": "6 h", "supported": False, "reason": sup["6 h"]["reason"], "risk": None}]
        for h in EVAL_HORIZONS:
            label = DISPLAY[h]
            s, m = sup[label], self.artifact["metrics"][label]
            rows.append({"horizon": label, "days": h, "supported": s["supported"], "reason": s["reason"],
                         "risk": c["cumulative"][h - 1] if s["supported"] else None,
                         "p10": c["p10"][h - 1] if s["supported"] else None,
                         "p90": c["p90"][h - 1] if s["supported"] else None,
                         "test_auroc": m["auroc"], "test_auroc_95ci": m["auroc_95ci_patient_bootstrap"],
                         "test_brier": m["brier"]})
        agree = None
        if primary_7d is not None:
            agree = {"primary_lr_7d": round(primary_7d, 4), "survival_7d": c["cumulative"][6],
                     "abs_difference": round(abs(primary_7d - c["cumulative"][6]), 4),
                     "note": ("Two independently trained models; a large difference signals epistemic uncertainty. "
                              "Tiers are driven by the primary OT-ACUTE-7 model.")}
        return {"model": self.version_info(), "curve": c, "horizons": rows, "agreement_with_primary": agree,
                "method": "discrete-time survival — cumulative incidence is monotone in the horizon by construction"}


@lru_cache(maxsize=1)
def load_horizon_model() -> HorizonModel | None:
    """None when the artifact has not been trained yet — callers show 'horizon model unavailable'."""
    if not ARTIFACT_PATH.exists():
        return None
    return HorizonModel(json.loads(ARTIFACT_PATH.read_text(encoding="utf-8")))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    train(a.n, write=not a.dry_run)


if __name__ == "__main__":
    main()
