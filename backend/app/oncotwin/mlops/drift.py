"""Digital Twin Drift Monitor.

Compares the LIVE population the twin is scoring against the reference profile
of the data the deployed model was trained on:

  feature drift        PSI per model feature (training-decile bins)
  prediction drift     PSI of the predicted 7-day risk
  missing-data drift   share of patient-days with a missing reading, per signal
  population shift     summarised as the number of drifted features

PSI = Σ (live − ref) · ln(live / ref). Live windows are small and CLUSTERED
(a few patients × up to 14 days each — days of one patient are not
independent), so a feature is flagged only when PSI exceeds BOTH the
conventional 0.25 AND the 95 % sampling-noise level χ²₀.₉₅(k−1) / n_eff, where
n_eff = N / (1 + (m̄ − 1)·ICC) uses the feature's intra-patient correlation
estimated from the live rows (one-way ANOVA). Below 50 patient-days or 5
patients the monitor reports "insufficient data" rather than guessing.

When drift is detected the twin shows a MODEL RELIABILITY WARNING on every
prediction and lowers Twin Readiness — it never silently continues.

    python -m app.oncotwin.mlops.drift --build-reference     # from the cached training cohort
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

from app.oncotwin.engine.features import FEATURE_NAMES
from app.oncotwin.signals import MODEL_SIGNALS

REFERENCE_PATH = Path(__file__).resolve().parents[1] / "ml" / "artifacts" / "reference_profile_v1.json"
CHI2_95 = [3.84, 5.99, 7.81, 9.49, 11.07, 12.59, 14.07, 15.51, 16.92, 18.31, 19.68, 21.03]
PSI_CONVENTIONAL = 0.25
MIN_ROWS = 50
MIN_PATIENTS = 5
# Features describing WHO is being scored and WHEN in the cycle (not how they are measured).
CASE_MIX_FEATURES = {"nadir_risk", "anc_twin_log", "anc_twin_low", "anc_lab_low", "adherence_7d", "adherence_gap",
                     "age65", "on_treatment", "myelotox"}
LIVE_WINDOW_DAYS = 14
MISSING_ABS_DIFF = 0.15


def _edges(x: np.ndarray) -> list[float]:
    return [float(v) for v in np.unique(np.round(np.quantile(x, np.linspace(0.1, 0.9, 9)), 6))]


def _props(x: np.ndarray, edges: list[float]) -> np.ndarray:
    counts = np.bincount(np.digitize(x, edges, right=True), minlength=len(edges) + 1).astype(float)
    return counts / max(1.0, counts.sum())


def psi(ref: np.ndarray, live: np.ndarray, eps: float = 1e-4) -> float:
    a, e = np.maximum(live, eps), np.maximum(ref, eps)
    return float(np.sum((a - e) * np.log(a / e)))


def noise_threshold(k_bins: int, n_eff: float) -> float:
    df = max(1, k_bins - 1)
    return CHI2_95[min(df, len(CHI2_95)) - 1] / max(1.0, n_eff)


def effective_n(x: np.ndarray, groups: np.ndarray) -> tuple[float, float]:
    """Design-effect-adjusted sample size for clustered rows: (n_eff, ICC) — one-way ANOVA ICC estimator."""
    x = np.asarray(x, dtype=float)
    N = len(x)
    ids = np.unique(groups)
    G = len(ids)
    if G < 2 or N <= G:
        return float(G), 1.0
    means = {g: x[groups == g].mean() for g in ids}
    sizes = {g: int((groups == g).sum()) for g in ids}
    grand = x.mean()
    msb = sum(sizes[g] * (means[g] - grand) ** 2 for g in ids) / (G - 1)
    msw = sum(((x[groups == g] - means[g]) ** 2).sum() for g in ids) / (N - G)
    n0 = (N - sum(s * s for s in sizes.values()) / N) / (G - 1)
    icc = 0.0 if msb + (n0 - 1) * msw <= 0 else float(np.clip((msb - msw) / (msb + (n0 - 1) * msw), 0.0, 1.0))
    m_bar = N / G
    return N / (1.0 + (m_bar - 1.0) * icc), icc


def build_reference(n: int = 1000, *, write: bool = True) -> dict[str, Any]:
    from app.oncotwin.ml.model import load_model
    from app.oncotwin.research.dataset import load_cohort

    cohort = load_cohort(n)
    model = load_model()
    tr = cohort.part("train")
    X = np.concatenate([p.data.F[p.data.eligible] for p in tr])
    preds = model.predict(X)
    miss = {k: round(float(np.mean(np.isnan(np.concatenate([p.data.series.values[k][p.data.eligible] for p in tr])))), 4)
            for k in MODEL_SIGNALS}
    feats = {}
    for j, f in enumerate(FEATURE_NAMES):
        edges = _edges(X[:, j])
        feats[f] = {"edges": edges, "props": [round(float(v), 6) for v in _props(X[:, j], edges)],
                    "mean": round(float(X[:, j].mean()), 5), "informative": len(edges) >= 2}
    pe = _edges(preds)
    ref: dict[str, Any] = {
        "profile_id": "oncotwin-reference-profile", "version": "1.0.0",
        "built_from": {**cohort.meta(), "split": "train", "n_rows": int(len(X))},
        "model": model.version_info(), "features": feats,
        "prediction": {"edges": pe, "props": [round(float(v), 6) for v in _props(preds, pe)]},
        "missingness": miss, "built_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }
    ref["sha256"] = hashlib.sha256(json.dumps({k: v for k, v in ref.items() if k != "built_at"},
                                              sort_keys=True).encode()).hexdigest()
    if write:
        REFERENCE_PATH.write_text(json.dumps(ref), encoding="utf-8")
        load_reference.cache_clear()
    return ref


@lru_cache(maxsize=1)
def load_reference() -> dict[str, Any] | None:
    return json.loads(REFERENCE_PATH.read_text(encoding="utf-8")) if REFERENCE_PATH.exists() else None


def evaluate(rows: np.ndarray, preds: np.ndarray, missing: dict[str, list[bool]], n_patients: int,
             groups: np.ndarray | None = None) -> dict[str, Any]:
    ref = load_reference()
    if ref is None:
        return {"status": "unavailable",
                "message": "Reference profile not built (python -m app.oncotwin.mlops.drift --build-reference)."}
    n = int(len(rows))
    groups = np.zeros(n, dtype=int) if groups is None else np.asarray(groups)
    base = {"n_patient_days": n, "n_patients": n_patients, "window_days": LIVE_WINDOW_DAYS,
            "reference": {"sha256": ref["sha256"], "n_rows": ref["built_from"]["n_rows"],
                          "dataset_version": ref["built_from"]["version"]}}
    if n < MIN_ROWS or n_patients < MIN_PATIENTS:
        return {**base, "status": "insufficient data",
                "message": (f"{n} live patient-days from {n_patients} patient(s) (need ≥ {MIN_ROWS} and ≥ {MIN_PATIENTS}); "
                            "drift cannot be assessed reliably yet.")}
    feats = []
    for j, f in enumerate(FEATURE_NAMES):
        r = ref["features"][f]
        if not r["informative"]:
            continue
        n_eff, icc = effective_n(rows[:, j], groups)
        v = psi(np.array(r["props"]), _props(rows[:, j], r["edges"]))
        thr = max(PSI_CONVENTIONAL, noise_threshold(len(r["props"]), n_eff))
        feats.append({"feature": f, "psi": round(v, 4), "threshold": round(thr, 4), "drifted": bool(v > thr),
                      "n_eff": round(n_eff, 1), "icc": round(icc, 3),
                      "live_mean": round(float(rows[:, j].mean()), 4), "reference_mean": r["mean"]})
    for fe in feats:
        fe["category"] = "case-mix / treatment phase" if fe["feature"] in CASE_MIX_FEATURES else "signal"
    feats.sort(key=lambda d: -d["psi"])
    pr = ref["prediction"]
    p_neff, _ = effective_n(preds, groups)
    p_psi = psi(np.array(pr["props"]), _props(preds, pr["edges"]))
    p_thr = max(PSI_CONVENTIONAL, noise_threshold(len(pr["props"]), p_neff))
    miss = []
    for k in MODEL_SIGNALS:
        vals = missing.get(k, [])
        if not vals:
            continue
        m_neff, _ = effective_n(np.array(vals, dtype=float), groups)
        live_rate, r0 = float(np.mean(vals)), ref["missingness"][k]
        z = (live_rate - r0) / np.sqrt(max(r0 * (1 - r0), 1e-4) / max(1.0, m_neff))
        miss.append({"signal": k, "live_rate": round(live_rate, 3), "reference_rate": r0, "z": round(float(z), 2),
                     "n_eff": round(m_neff, 1), "drifted": bool(abs(live_rate - r0) > MISSING_ABS_DIFF and abs(z) > 3)})
    drifted = [f["feature"] for f in feats if f["drifted"] and f["category"] == "signal"]
    case_mix = [f["feature"] for f in feats if f["drifted"] and f["category"] != "signal"]
    miss_d = [m["signal"] for m in miss if m["drifted"]]
    pred_d = p_psi > p_thr
    # Signal / prediction / missing-data drift threatens the model's validity → reliability warning.
    # Case-mix / treatment-phase drift (e.g. every live patient in the same cycle phase) is shown, not escalated.
    status = ("drift" if (pred_d or len(drifted) >= 3 or miss_d)
              else "watch" if (drifted or case_mix) else "stable")
    msg = {"drift": ("Model reliability warning — the live population differs from the training data ("
                     + ", ".join((drifted[:3] + miss_d[:2]) or ["prediction distribution"])
                     + "). Predictions remain visible but are flagged; review before relying on them."),
           "watch": ("Monitoring: " + "; ".join(x for x in (
               f"minor signal shift in {', '.join(drifted)}" if drifted else "",
               f"case-mix / treatment-phase differs from training ({', '.join(case_mix)}) — expected when live "
               "patients share a cycle phase; not a measurement problem" if case_mix else "") if x) + "."),
           "stable": "Live signal, prediction and missing-data distributions are consistent with training."}[status]
    return {**base, "status": status, "message": msg,
            "n_eff_method": "N / (1 + (mean days per patient − 1) · ICC), ICC per feature from the live rows",
            "features": feats, "prediction": {"psi": round(p_psi, 4), "threshold": round(p_thr, 4), "n_eff": round(p_neff, 1),
                                              "drifted": bool(pred_d)},
            "missingness": miss, "drifted_features": drifted, "case_mix_shift": case_mix, "drifted_missingness": miss_d}


def live_window(store, *, window: int = LIVE_WINDOW_DAYS) -> dict[str, Any]:
    """The live scoring population from every twin's cached as-of facts (last `window` twin days)."""
    from app.oncotwin import runtime

    rows, preds, groups, n_pat = [], [], [], 0
    missing: dict[str, list[bool]] = {k: [] for k in MODEL_SIGNALS}
    for gi, pid in enumerate(list(store.patients)):
        b = runtime.bundle_for(store.patients[pid])
        took = False
        for snap, f in zip(b.snapshots[-window:], b.day_facts[-window:], strict=True):
            if not snap["on_treatment"] or snap["in_acute_care"] or "x" not in f:
                continue
            rows.append(f["x"])
            preds.append(snap["risk"])
            groups.append(gi)
            for k in MODEL_SIGNALS:
                missing[k].append(k in f.get("missing_today", []))
            took = True
        n_pat += int(took)
    return {"rows": np.array(rows) if rows else np.zeros((0, len(FEATURE_NAMES))), "preds": np.array(preds),
            "missing": missing, "n_patients": n_pat, "groups": np.array(groups)}


def monitor(store) -> dict[str, Any]:
    w = live_window(store)
    return evaluate(w["rows"], w["preds"], w["missing"], w["n_patients"], w["groups"])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--build-reference", action="store_true")
    ap.add_argument("--n", type=int, default=1000)
    a = ap.parse_args()
    if a.build_reference:
        ref = build_reference(a.n)
        print(json.dumps({"rows": ref["built_from"]["n_rows"], "sha256": ref["sha256"], "missingness": ref["missingness"]}))


if __name__ == "__main__":
    main()
