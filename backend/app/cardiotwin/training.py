"""Reproducible CardioTwin training + evaluation.  `python -m app.cardiotwin.training`

Protocol (all preprocessing lives INSIDE each CV fold; nothing is fit on held-out rows):

  1. load + validate the dataset; assert the leakage guard for every target
  2. repeated stratified 5-fold CV (3 repeats by default), SAME splits for all four
     targets (stratified on the number of stenotic vessels) so joint analyses are valid
  3. per fold and target, the SHIPPED model — L2 logistic regression with C tuned by an
     inner 5-fold CV — plus challengers (L1-LR, random forest, gradient boosting, and a
     multi-output random forest as a multi-task probe)
  4. calibration compared inside each fold: raw vs Platt vs isotonic, fit on inner
     out-of-fold predictions of the training fold only
  5. decision thresholds chosen on inner out-of-fold predictions only
  6. final models fit on all rows; bootstrap ensemble for uncertainty; shrinkage
     Mahalanobis model for representativeness; JSON artifact + SHA-256

The shipped family (regularised logistic regression) is pre-specified for exact
attribution; challengers are reported with corrected paired tests, not used to
select the shipped model after seeing the results.
"""

from __future__ import annotations

import argparse
import json
import warnings
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.covariance import LedoitWolf
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression, LogisticRegressionCV
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import (
    RepeatedStratifiedKFold,
    StratifiedKFold,
    cross_val_predict,
)
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from app.cardiotwin import CARDIOTWIN_VERSION
from app.cardiotwin.data import (
    DATASET_CSV,
    encode_frame,
    file_sha256,
    label_relationships,
    load_dataset,
    target_vector,
)
from app.cardiotwin.evaluation import (
    as_jsonable,
    bootstrap_ci,
    calibration_curve,
    corrected_paired_t,
    curve_points,
    point_metrics,
    spearman,
    summarize_folds,
    threshold_metrics,
    youden_threshold,
)
from app.cardiotwin.features import (
    ENCODED_NAMES,
    ENCODED_TO_RAW,
    assert_no_leakage,
    forbidden_inputs,
)
from app.cardiotwin.model import (
    ARTIFACT_PATH,
    EVALUATION_PATH,
    SCENARIOS_PATH,
    CardioModel,
    canonical_sha256,
)
from app.cardiotwin.schema import (
    FEATURES,
    LABEL_COLUMNS,
    SOURCE_DATASET,
    TARGET_ORDER,
    VESSELS,
)

CS = np.logspace(-3, 1, 9)
QLEVELS = list(range(0, 101, 5))


def _sig(z: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(z, -35, 35)))


def _lrcv(seed: int, penalty: str = "l2") -> Any:
    kw: dict[str, Any] = {"penalty": penalty} if penalty != "l2" else {}
    return LogisticRegressionCV(
        Cs=CS,
        cv=StratifiedKFold(5, shuffle=True, random_state=seed),
        solver="liblinear",
        scoring="neg_log_loss",
        max_iter=2000,
        random_state=seed,
        **kw,
    )


def _pipe(model: Any) -> Any:
    return make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), model)


def _platt(logit_oof: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    lr = LogisticRegression(C=1e6, solver="lbfgs", max_iter=1000)
    lr.fit(logit_oof.reshape(-1, 1), y)
    return float(lr.coef_[0, 0]), float(lr.intercept_[0])


# ---------------------------------------------------------------------------
# One CV fold, one target: shipped model + calibration variants + uncertainty
# ---------------------------------------------------------------------------


def _shipped_fold(
    Xtr: np.ndarray, ytr: np.ndarray, Xte: np.ndarray, seed: int, n_boot: int
) -> dict[str, Any]:
    pipe = _pipe(_lrcv(seed))
    pipe.fit(Xtr, ytr)
    C = float(pipe[-1].C_[0])
    dec_te = pipe.decision_function(Xte)

    inner = cross_val_predict(
        _pipe(LogisticRegression(C=C, solver="liblinear")),
        Xtr,
        ytr,
        cv=StratifiedKFold(5, shuffle=True, random_state=seed + 1),
        method="decision_function",
    )
    a, b = _platt(inner, ytr)
    iso = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0).fit(_sig(inner), ytr)

    p_raw = _sig(dec_te)
    p_platt = _sig(a * dec_te + b)
    p_iso = iso.predict(p_raw)
    thr = {
        "raw": youden_threshold(ytr, _sig(inner)),
        "platt": youden_threshold(ytr, _sig(a * inner + b)),
    }

    # bootstrap ensemble spread on the held-out rows (uncertainty diagnostics)
    prep = pipe[:2]
    Ztr, Zte = prep.transform(Xtr), prep.transform(Xte)
    rng = np.random.default_rng(seed + 2)
    draws = []
    for _ in range(n_boot):
        i = rng.integers(0, len(ytr), len(ytr))
        if ytr[i].min() == ytr[i].max():
            continue
        m = LogisticRegression(C=C, solver="liblinear").fit(Ztr[i], ytr[i])
        draws.append(_sig(a * m.decision_function(Zte) + b))
    draws_a = np.array(draws) if draws else np.zeros((1, len(Zte)))
    return {
        "C": C,
        "dec": dec_te,
        "p_raw": p_raw,
        "p_platt": p_platt,
        "p_iso": p_iso,
        "thr": thr,
        "boot_sd": draws_a.std(axis=0),
        "boot_width": np.percentile(draws_a, 90, axis=0) - np.percentile(draws_a, 10, axis=0),
    }


def _challenger_fold(
    name: str, Xtr: np.ndarray, ytr: np.ndarray, Xte: np.ndarray, seed: int
) -> np.ndarray:
    if name == "lr_l1":
        pipe = _pipe(_lrcv(seed, "l1"))
    elif name == "random_forest":
        pipe = _pipe(
            RandomForestClassifier(
                300, min_samples_leaf=3, max_features="sqrt", random_state=seed, n_jobs=-1
            )
        )
    elif name == "gradient_boosting":
        pipe = _pipe(
            GradientBoostingClassifier(
                n_estimators=120, max_depth=2, learning_rate=0.05, subsample=0.8, random_state=seed
            )
        )
    else:  # pragma: no cover
        raise KeyError(name)
    return pipe.fit(Xtr, ytr).predict_proba(Xte)[:, 1]  # type: ignore[no-any-return]


# ---------------------------------------------------------------------------
# Leakage audit
# ---------------------------------------------------------------------------


def leakage_audit(df: Any, X: np.ndarray, ys: dict[str, np.ndarray], seed: int) -> dict[str, Any]:
    per_target: dict[str, Any] = {}
    flagged: list[str] = []
    for t in TARGET_ORDER:
        assert_no_leakage(list(ENCODED_NAMES), t)  # raises LeakageError
        y = ys[t]
        best = ("", 0.0)
        for j, name in enumerate(ENCODED_NAMES):
            if X[:, j].std() == 0:
                continue
            auc = roc_auc_score(y, X[:, j])
            strength = abs(auc - 0.5) * 2
            if strength > best[1]:
                best = (name, strength)
            corr = abs(float(np.corrcoef(X[:, j], y)[0, 1]))
            if corr > 0.9 or strength > 0.9:
                flagged.append(f"{t}:{name}")
        # label-permutation canary: a leak-free pipeline scores ~0.5 on shuffled labels
        rng = np.random.default_rng(seed)
        yperm = rng.permutation(y)
        oof = cross_val_predict(
            _pipe(LogisticRegression(C=0.1, solver="liblinear")),
            X,
            yperm,
            cv=StratifiedKFold(5, shuffle=True, random_state=seed),
            method="decision_function",
        )
        per_target[t] = {
            "forbidden_columns_excluded": sorted(forbidden_inputs(t)),
            "n_input_features": int(len(ENCODED_NAMES)),
            "strongest_single_feature": {"feature": best[0], "separation": round(best[1], 3)},
            "shuffled_label_auc": round(float(roc_auc_score(yperm, oof)), 3),
        }
    # diagnostic ONLY (never a training path): how large the leak would be if the guard were bypassed
    y_cad = ys["CAD"]
    leak_X = np.column_stack([X, ys["LAD"], ys["LCX"], ys["RCA"]])
    leaky = cross_val_predict(
        _pipe(LogisticRegression(C=1.0, solver="liblinear")),
        leak_X,
        y_cad,
        cv=StratifiedKFold(5, shuffle=True, random_state=seed),
        method="decision_function",
    )
    return {
        "status": "pass" if not flagged else "flagged",
        "guard": "assert_no_leakage(): Cath, LAD, LCX, RCA rejected as inputs for every target",
        "excluded_label_columns": list(LABEL_COLUMNS),
        "constant_columns_dropped": ["Exertional CP"],
        "flagged_features": flagged,
        "per_target": per_target,
        "bypass_demonstration": {
            "description": (
                "DIAGNOSTIC ONLY: CAD AUC if LAD/LCX/RCA were (wrongly) allowed as inputs — shows why the "
                "guard exists. This configuration is never trained or shipped."
            ),
            "cad_auc_with_vessel_labels": round(float(roc_auc_score(y_cad, leaky)), 3),
        },
        "notes": [
            "Weight/Length/BMI are arithmetically related (BMI = kg/m²) — collinear inputs, not label leakage; "
            "L2 regularisation handles the collinearity.",
            "'Typical Chest Pain', 'Function Class', ST/T changes and RWMA are clinical findings available before "
            "angiography and are therefore legitimate inputs.",
        ],
    }


# ---------------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------------


def train(
    out_dir: Path | None = None,
    *,
    dataset_path: Path | None = None,
    n_splits: int = 5,
    n_repeats: int = 3,
    n_boot_cv: int = 20,
    n_boot_final: int = 100,
    challengers: bool = True,
    seed: int = 42,
) -> dict[str, Any]:
    warnings.filterwarnings("ignore")
    out = Path(out_dir) if out_dir else ARTIFACT_PATH.parent
    out.mkdir(parents=True, exist_ok=True)

    df = load_dataset(dataset_path)
    X, names = encode_frame(df)
    for t in (
        TARGET_ORDER
    ):  # leakage guard FIRST: a poisoned input set must abort before anything is fit
        assert_no_leakage(names, t)
    assert tuple(names) == ENCODED_NAMES
    ys = {t: target_vector(df, t) for t in TARGET_ORDER}
    n = len(df)

    strat = ys["LAD"] + ys["LCX"] + ys["RCA"]  # number of stenotic vessels (0..3)
    splits = list(
        RepeatedStratifiedKFold(n_splits=n_splits, n_repeats=n_repeats, random_state=seed).split(
            X, strat
        )
    )
    n_train = int(np.mean([len(a) for a, _ in splits]))
    n_test = int(np.mean([len(b) for _, b in splits]))

    audit = leakage_audit(df, X, ys, seed)
    rel = label_relationships(df)

    # ---------------- CV loop ------------------------------------------------
    fold: dict[str, list[dict[str, Any]]] = {t: [] for t in TARGET_ORDER}
    chall: dict[str, dict[str, list[float]]] = {t: {} for t in TARGET_ORDER}
    mt_auc: dict[str, list[float]] = {t: [] for t in TARGET_ORDER}
    d2_oof = np.zeros((n_repeats, n))
    for k, (tr, te) in enumerate(splits):
        r = k // n_splits
        for t in TARGET_ORDER:
            res = _shipped_fold(X[tr], ys[t][tr], X[te], seed + k, n_boot_cv)
            res["te"] = te
            res["auc_shipped"] = float(roc_auc_score(ys[t][te], res["p_platt"]))
            fold[t].append(res)
            if challengers:
                for cname in ("lr_l1", "random_forest", "gradient_boosting"):
                    p = _challenger_fold(cname, X[tr], ys[t][tr], X[te], seed + k)
                    chall[t].setdefault(cname, []).append(float(roc_auc_score(ys[t][te], p)))
        if challengers:  # multi-task probe: one RF whose trees are shared across all four outputs
            Y = np.column_stack([ys[t] for t in TARGET_ORDER])
            mt = _pipe(
                RandomForestClassifier(
                    300, min_samples_leaf=3, max_features="sqrt", random_state=seed + k, n_jobs=-1
                )
            ).fit(X[tr], Y[tr])
            probs = mt.predict_proba(X[te])
            for j, t in enumerate(TARGET_ORDER):
                mt_auc[t].append(float(roc_auc_score(ys[t][te], probs[j][:, 1])))
        # representativeness: distance of held-out rows under the fold-trained covariance
        sc = StandardScaler().fit(X[tr])
        lw = LedoitWolf().fit(sc.transform(X[tr]))
        Zte = sc.transform(X[te])
        d2_oof[r, te] = lw.mahalanobis(Zte)
    d2_cv = d2_oof.mean(axis=0)

    # ---------------- per-target aggregation -------------------------------
    def oof_avg(t: str, key: str) -> np.ndarray:
        acc = np.zeros((n_repeats, n))
        for k, f in enumerate(fold[t]):
            acc[k // n_splits, f["te"]] = f[key]
        return acc.mean(axis=0)

    targets_eval: dict[str, Any] = {}
    chosen_cal: dict[str, str] = {}
    oof_cal: dict[str, np.ndarray] = {}
    oof_boot_sd: dict[str, np.ndarray] = {}
    oof_boot_w: dict[str, np.ndarray] = {}
    for t in TARGET_ORDER:
        y = ys[t]
        F = fold[t]
        per_fold = {
            v: [point_metrics(y[f["te"]], f[key]) for f in F]
            for v, key in (("raw", "p_raw"), ("platt", "p_platt"), ("isotonic", "p_iso"))
        }
        cal_cmp: dict[str, Any] = {}
        for v in per_fold:
            cal_cmp[v] = {
                m: summarize_folds([pm[m] for pm in per_fold[v]])
                for m in ("brier", "ece", "log_loss", "roc_auc")
            }
        d = np.array(
            [
                a["brier"] - b["brier"]
                for a, b in zip(per_fold["raw"], per_fold["platt"], strict=True)
            ]
        )
        se = float(d.std(ddof=1) / np.sqrt(len(d))) if len(d) > 1 else 0.0
        choice = "platt" if d.mean() > se else "none"
        cal_cmp["decision"] = {
            "shipped": choice,
            "brier_improvement_raw_minus_platt": round(float(d.mean()), 4),
            "standard_error": round(se, 4),
            "rule": "ship Platt scaling only if the mean per-fold Brier improvement exceeds its standard error",
            "isotonic_note": (
                "Isotonic regression is evaluated for comparison but not shippable: with n≈300 it is a "
                "high-variance step function and it would break the exact additive attribution."
            ),
        }
        chosen_cal[t] = choice
        key = "p_platt" if choice == "platt" else "p_raw"
        thr_key = "platt" if choice == "platt" else "raw"
        oof_cal[t] = oof_avg(t, key)
        oof_boot_sd[t] = oof_avg(t, "boot_sd")
        oof_boot_w[t] = oof_avg(t, "boot_width")

        # headline (per-fold) + threshold-dependent metrics from inner-fold thresholds
        head = [point_metrics(y[f["te"]], f[key]) for f in F]
        thr_rows = [threshold_metrics(y[f["te"]], f[key], f["thr"][thr_key]) for f in F]
        conf_sum = {c: int(sum(r_[c] for r_ in thr_rows)) for c in ("tp", "fp", "tn", "fn")}
        oof_p = oof_cal[t]
        ci = bootstrap_ci(y, oof_p, n_boot=1000, seed=seed)
        cv_summary = {
            "roc_auc": ci["roc_auc"]["estimate"],
            "roc_auc_ci95": [ci["roc_auc"]["ci95_low"], ci["roc_auc"]["ci95_high"]],
            "roc_auc_fold_mean": summarize_folds([h["roc_auc"] for h in head])["mean"],
            "roc_auc_fold_sd": summarize_folds([h["roc_auc"] for h in head])["sd"],
            "pr_auc": ci["pr_auc"]["estimate"],
            "pr_auc_ci95": [ci["pr_auc"]["ci95_low"], ci["pr_auc"]["ci95_high"]],
            "brier": ci["brier"]["estimate"],
            "brier_ci95": [ci["brier"]["ci95_low"], ci["brier"]["ci95_high"]],
            "ece": ci["ece"]["estimate"],
            "prevalence": round(float(y.mean()), 4),
            "accuracy": summarize_folds([r_["accuracy"] for r_ in thr_rows]),
            "precision": summarize_folds([r_["precision"] for r_ in thr_rows]),
            "recall": summarize_folds([r_["recall"] for r_ in thr_rows]),
            "specificity": summarize_folds([r_["specificity"] for r_ in thr_rows]),
            "f1": summarize_folds([r_["f1"] for r_ in thr_rows]),
            "confusion_matrix_per_pass": {c: round(v / n_repeats, 1) for c, v in conf_sum.items()},
        }
        # challenger table + corrected paired tests vs the shipped model (per-fold AUC)
        shipped_auc = np.array([f["auc_shipped"] for f in F])
        comp = {
            "lr_l2_shipped": {"roc_auc": summarize_folds(list(shipped_auc))},
        }
        for cname, aucs in chall[t].items():
            comp[cname] = {
                "roc_auc": summarize_folds(aucs),
                "paired_vs_shipped": corrected_paired_t(
                    np.array(aucs) - shipped_auc, n_train, n_test
                ),
            }
        multitask = None
        if challengers:
            rf = np.array(chall[t]["random_forest"])
            mt = np.array(mt_auc[t])
            multitask = {
                "single_output_rf_auc": summarize_folds(list(rf)),
                "multi_output_rf_auc": summarize_folds(list(mt)),
                "paired_multi_minus_single": corrected_paired_t(mt - rf, n_train, n_test),
            }
        targets_eval[t] = {
            "cv_summary": cv_summary,
            "calibration": cal_cmp,
            "calibration_curve_raw": calibration_curve(y, oof_avg(t, "p_raw")),
            "calibration_curve_shipped": calibration_curve(y, oof_p),
            "curves": curve_points(y, oof_p),
            "comparators": comp,
            "multitask_probe": multitask,
            "selected_C": {
                "median": round(float(np.median([f["C"] for f in F])), 5),
                "range": [
                    round(float(min(f["C"] for f in F)), 5),
                    round(float(max(f["C"] for f in F)), 5),
                ],
            },
        }

    # ---------------- consistency (CAD ⊇ any vessel) -----------------------
    p_cad = oof_cal["CAD"]
    p_ves = np.stack([oof_cal[v] for v in VESSELS], axis=1)
    p_max = np.maximum(p_cad, p_ves.max(axis=1))
    p_noisy = 1 - np.prod(1 - p_ves, axis=1)
    y_cad = ys["CAD"]
    consistency = {
        "logical_constraint": "P(CAD) >= max(P(LAD), P(LCX), P(RCA))",
        "supported_by_data": (
            f"{rel['cad_equals_any_vessel']}/{rel['n']} rows have CAD == any target-vessel stenosis"
        ),
        "independent_model_violation_rate": round(float((p_ves.max(axis=1) > p_cad).mean()), 4),
        "cad_direct": {k: round(v, 4) for k, v in point_metrics(y_cad, p_cad).items()},
        "cad_max_projection": {k: round(v, 4) for k, v in point_metrics(y_cad, p_max).items()},
        "cad_noisy_or_of_vessels": {
            k: round(v, 4) for k, v in point_metrics(y_cad, p_noisy).items()
        },
        "decision": "ship max-projection (guarantees the logical constraint) — it is reported next to the direct model",
    }
    consistency["projection_changes_auc_by"] = round(
        consistency["cad_max_projection"]["roc_auc"] - consistency["cad_direct"]["roc_auc"], 4
    )

    # ---------------- OOD + uncertainty analyses ---------------------------
    p95, p99 = float(np.percentile(d2_cv, 95)), float(np.percentile(d2_cv, 99))
    top = d2_cv >= np.percentile(d2_cv, 90)
    ood_eval: dict[str, Any] = {
        "method": "Ledoit-Wolf shrinkage Mahalanobis distance on standardised features, plus per-feature range checks",
        "thresholds_from": "cross-validated (held-out) distances — 95th / 99th percentile",
        "borderline_above_d2": round(p95, 2),
        "outside_above_d2": round(p99, 2),
        "exploratory_error_vs_distance": {
            t: {
                "brier_top_decile_distance": round(
                    float(np.mean((oof_cal[t][top] - ys[t][top]) ** 2)), 4
                ),
                "brier_rest": round(float(np.mean((oof_cal[t][~top] - ys[t][~top]) ** 2)), 4),
            }
            for t in TARGET_ORDER
        },
        "caveat": "Exploratory (top decile = ~30 patients); not a validated OOD detector.",
    }
    unc_eval: dict[str, Any] = {
        t: {
            "spearman_ensemble_width_vs_abs_error": round(
                spearman(oof_boot_w[t], np.abs(oof_cal[t] - ys[t])), 3
            ),
            "median_interval_width": round(float(np.median(oof_boot_w[t])), 3),
        }
        for t in TARGET_ORDER
    }
    unc_eval["caveat"] = (
        "Ensemble width is largest near p = 0.5, where expected error is also largest, so part of this rank "
        "correlation is mechanical. It shows the interval is not noise; it does not prove the interval is a "
        "calibrated confidence statement."
    )

    # ---------------- final fit on all rows --------------------------------
    scaler = StandardScaler().fit(X)
    impute = SimpleImputer(strategy="median").fit(X).statistics_
    Z = scaler.transform(X)
    rng = np.random.default_rng(seed + 99)
    target_models: dict[str, Any] = {}
    importance: dict[str, Any] = {}
    for t in TARGET_ORDER:
        y = ys[t]
        cv = _lrcv(seed).fit(Z, y)
        C = float(cv.C_[0])
        lr = LogisticRegression(C=C, solver="liblinear").fit(Z, y)
        coef, b0 = lr.coef_[0], float(lr.intercept_[0])
        if chosen_cal[t] == "platt":
            a, b = _platt(oof_avg(t, "dec"), y)
        else:
            a, b = 1.0, 0.0
        thr_p = oof_cal[t]
        thr = youden_threshold(y, thr_p)
        boot = []
        for _ in range(n_boot_final):
            i = rng.integers(0, n, n)
            if y[i].min() == y[i].max():
                continue
            m = LogisticRegression(C=C, solver="liblinear").fit(Z[i], y[i])
            boot.append(
                [round(float(m.intercept_[0]), 6), *[round(float(c), 6) for c in m.coef_[0]]]
            )
        target_models[t] = {
            "intercept": round(b0, 6),
            "coef": [round(float(c), 6) for c in coef],
            "l2_C": round(C, 6),
            "calibration": {"method": chosen_cal[t], "a": round(a, 6), "b": round(b, 6)},
            "threshold": round(thr, 4),
            "threshold_rule": "Youden J on out-of-fold calibrated predictions",
            "bootstrap": boot,
            "cv_summary": targets_eval[t]["cv_summary"],
        }
        agg: dict[str, float] = {}
        for j, nm in enumerate(ENCODED_NAMES):
            agg[ENCODED_TO_RAW[nm]] = agg.get(ENCODED_TO_RAW[nm], 0.0) + abs(a * coef[j])
        signed: dict[str, float] = {}
        for j, nm in enumerate(ENCODED_NAMES):
            signed[ENCODED_TO_RAW[nm]] = signed.get(ENCODED_TO_RAW[nm], 0.0) + a * coef[j]
        top_feats = sorted(agg.items(), key=lambda kv: kv[1], reverse=True)[:12]
        importance[t] = [
            {
                "feature": f,
                "mean_abs_standardised_coef": round(v, 4),
                "sign": "+" if signed[f] > 0 else "-",
            }
            for f, v in top_feats
        ]

    lw_final = LedoitWolf().fit(Z)
    ranges: dict[str, Any] = {}
    for spec in FEATURES:
        if spec.kind != "numeric":
            continue
        col = X[:, ENCODED_NAMES.index(spec.name)]
        qv = np.percentile(col, QLEVELS)
        ranges[spec.name] = {
            "min": float(col.min()),
            "max": float(col.max()),
            "mean": round(float(col.mean()), 4),
            "sd": round(float(col.std()), 4),
            "p5": round(float(np.percentile(col, 5)), 4),
            "p50": round(float(np.percentile(col, 50)), 4),
            "p95": round(float(np.percentile(col, 95)), 4),
            "quantile_levels": QLEVELS,
            "quantile_values": [round(float(v), 4) for v in qv],
        }
    grid_levels = list(range(0, 101, 5))
    ood = {
        "mean": [round(float(v), 6) for v in scaler.mean_],
        "precision": [[round(float(v), 6) for v in row] for row in lw_final.precision_],
        "shrinkage": round(float(lw_final.shrinkage_), 4),
        "d2_p95": round(p95, 4),
        "d2_p99": round(p99, 4),
        "d2_quantile_levels": grid_levels,
        "d2_quantile_grid": [round(float(v), 4) for v in np.percentile(d2_cv, grid_levels)],
        "feature_ranges": ranges,
    }

    limitations = [
        "Single-centre research dataset, n = 303 (Iran, Shaheed Rajaei Cardiovascular Center); no external validation.",
        "Labels are angiographic stenosis >= 50% per vessel (overall CAD is the `Cath` column); the model estimates "
        "these labels, not future events or mortality.",
        "Tabular features only: no images, lesion coordinates or plaque geometry. The 3D view shows a probability "
        "per vessel, never a lesion location.",
        "LCX and RCA discrimination is modest (see per-target CIs); vessel-level estimates are far less reliable "
        "than the overall CAD estimate.",
        "Calibration is estimated on the same small sample; intervals reflect sampling uncertainty of the model fit "
        "(bootstrap), not distribution shift to other hospitals.",
        "Representativeness scoring is exploratory and cannot certify that a new patient resembles the cohort.",
    ]
    artifact: dict[str, Any] = {
        "model_id": "cardiotwin-lr-multivessel",
        "version": CARDIOTWIN_VERSION,
        "model_family": "L2-regularised logistic regression (one model per target) + Platt scaling where it helped "
        "+ bootstrap ensemble",
        "dataset": {
            "name": SOURCE_DATASET["name"],
            "uci_id": SOURCE_DATASET["uci_id"],
            "license": SOURCE_DATASET["license"],
            "rows": n,
            "csv_sha256": file_sha256(Path(dataset_path) if dataset_path else DATASET_CSV),
        },
        "encoded_names": list(ENCODED_NAMES),
        "impute": [round(float(v), 6) for v in impute],
        "mean": [round(float(v), 6) for v in scaler.mean_],
        "std": [round(float(v), 6) for v in scaler.scale_],
        "targets": target_models,
        "ood": ood,
        "leakage_audit": {
            "status": audit["status"],
            "excluded_label_columns": audit["excluded_label_columns"],
            "flagged_features": audit["flagged_features"],
        },
        "evaluation_protocol": (
            f"{n_repeats}x repeated stratified {n_splits}-fold CV (stratified on stenotic-vessel count, identical "
            "folds for all targets); L2 strength tuned by inner 5-fold CV; calibration and thresholds fit on inner "
            "out-of-fold predictions only; CIs = 1000x patient-level bootstrap of averaged out-of-fold predictions."
        ),
        "limitations": limitations,
        "training": {
            "trained_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "seed": seed,
            "n_splits": n_splits,
            "n_repeats": n_repeats,
            "n_boot_final": n_boot_final,
        },
    }
    artifact["sha256"] = canonical_sha256(artifact)

    evaluation = {
        "generated_from": "real out-of-fold predictions produced by app.cardiotwin.training",
        "artifact_sha256": artifact["sha256"],
        "dataset": {**artifact["dataset"], "source": SOURCE_DATASET},
        "protocol": artifact["evaluation_protocol"],
        "n_folds": len(splits),
        "label_relationships": rel,
        "targets": targets_eval,
        "feature_importance": importance,
        "consistency": consistency,
        "representativeness": ood_eval,
        "uncertainty": unc_eval,
        "out_of_fold": {
            "note": "Per-patient averaged out-of-fold shipped probabilities (row order = dataset order).",
            "labels": {t: ys[t].tolist() for t in TARGET_ORDER},
            "probabilities": {t: [round(float(v), 4) for v in oof_cal[t]] for t in TARGET_ORDER},
        },
        "leakage_audit": audit,
        "limitations": limitations,
        "challengers_evaluated": challengers,
    }

    (out / ARTIFACT_PATH.name).write_text(json.dumps(artifact, sort_keys=True))
    (out / EVALUATION_PATH.name).write_text(
        json.dumps(as_jsonable(evaluation), indent=1, sort_keys=True)
    )
    model = CardioModel(artifact)
    scenarios = build_scenarios(df, X, model, oof_cal, ys)
    (out / SCENARIOS_PATH.name).write_text(json.dumps(as_jsonable(scenarios), indent=1))
    return {"artifact": artifact, "evaluation": evaluation, "scenarios": scenarios}


# ---------------------------------------------------------------------------
# Reproducible demo scenarios (selected from OUT-OF-FOLD predictions)
# ---------------------------------------------------------------------------

_RAW_COLUMNS = [f.name for f in FEATURES]


def _patient_dict(df: Any, i: int) -> dict[str, Any]:
    row = df.iloc[i]
    out: dict[str, Any] = {}
    for c in _RAW_COLUMNS:
        v = row[c]
        out[c] = v.item() if hasattr(v, "item") else v
    return out


def build_scenarios(
    df: Any,
    X: np.ndarray,
    model: CardioModel,
    oof: dict[str, np.ndarray],
    ys: dict[str, np.ndarray],
) -> dict[str, Any]:
    from app.cardiotwin.features import RAW_TO_ENCODED_IDX, encode_record

    cad, lad, lcx, rca = (oof[t] for t in TARGET_ORDER)

    def labels(i: int) -> dict[str, str]:
        return {c: str(df.iloc[i][c]) for c in LABEL_COLUMNS}

    def pick_min(mask: np.ndarray, score: np.ndarray) -> int:
        idx = np.where(mask)[0]
        return int(idx[np.argmin(score[idx])])

    y_cad = ys["CAD"]
    ves_true = np.stack([ys[v] for v in VESSELS], axis=1)
    ves_p = np.stack([lad, lcx, rca], axis=1)

    # A: the most confidently-negative patient without CAD
    i_low = pick_min(y_cad == 0, cad)
    # B: a true multi-vessel patient the model scores high but not saturated (LAD closest to 0.80)
    cand = (ves_true.sum(axis=1) >= 2) & (cad >= 0.85) & (lad >= 0.6)
    i_high = pick_min(cand, np.abs(lad - 0.80))
    # C: exactly one true stenotic vessel, model agrees on all three, largest spread between vessels
    agree = ((ves_p >= 0.5) == (ves_true == 1)).all(axis=1) & (ves_true.sum(axis=1) == 1)
    spread = ves_p.max(axis=1) - ves_p.min(axis=1)
    i_mixed = pick_min(agree, -spread) if agree.any() else int(np.argmax(spread))

    ood_patient = _patient_dict(df, i_low)
    ood_patient.update(
        {"Age": 21, "Sex": "Female", "BMI": 46.0, "Weight": 140, "Length": 173, "FBS": 410, "CR": 6.5,
         "K": 6.9, "HB": 5.5, "WBC": 34000, "ESR": 120, "EF-TTE": 15, "TG": 900, "PLT": 40}
    )  # fmt: skip

    # E: among patients with a mid-range LAD estimate, the modifiable lab/vitals value whose move to its
    # reference bound changes P(LAD) the most (found by exhaustive search over the whole cohort).
    best: tuple[int, str, float, float] | None = None
    for i in np.where((lad >= 0.45) & (lad <= 0.8))[0]:
        patient = _patient_dict(df, int(i))
        rec = encode_record(patient, model.impute)
        base_vec = np.array(rec.vector)
        base = model._probabilities(base_vec)["LAD"]
        for spec in FEATURES:
            if spec.kind != "numeric" or spec.group not in ("lab", "exam"):
                continue
            cur = float(patient[spec.name])
            for bound in (spec.ref_lo, spec.ref_hi):
                if bound is None:
                    continue
                moves_toward = (
                    spec.ref_hi is not None and cur > spec.ref_hi and bound == spec.ref_hi
                ) or (spec.ref_lo is not None and cur < spec.ref_lo and bound == spec.ref_lo)
                if not moves_toward:
                    continue
                v = base_vec.copy()
                v[RAW_TO_ENCODED_IDX[spec.name][0]] = bound
                d = abs(model._probabilities(v)["LAD"] - base)
                if best is None or d > best[3]:
                    best = (int(i), spec.name, float(bound), float(d))
    if best is None:  # pragma: no cover - would need a cohort with no out-of-range values
        best = (i_high, "LDL", 100.0, 0.0)
    i_cf = best[0]

    def scen(
        sid: str, title: str, blurb: str, patient: dict[str, Any], **extra: Any
    ) -> dict[str, Any]:
        return {"id": sid, "title": title, "description": blurb, "patient": patient, **extra}

    def src(i: int) -> dict[str, Any]:
        return {
            "source": "dataset_sample",
            "dataset_row": int(i),
            "reference_labels": labels(i),
            "out_of_fold_probabilities": {
                "CAD": round(float(cad[i]), 3),
                "LAD": round(float(lad[i]), 3),
                "LCX": round(float(lcx[i]), 3),
                "RCA": round(float(rca[i]), 3),
            },
        }

    return {
        "note": (
            "Dataset samples are de-identified public research records; they were selected using OUT-OF-FOLD "
            "predictions, so the model had not seen them when scoring. Reference labels are shown for honesty — "
            "the model can be wrong."
        ),
        "scenarios": [
            scen(
                "A",
                "Low estimated CAD",
                "Most confidently negative out-of-fold estimate among patients without CAD.",
                _patient_dict(df, i_low),
                **src(i_low),
            ),  # fmt: skip
            scen(
                "B",
                "High estimated CAD",
                "A multi-vessel patient scored high (LAD ≈ 0.8) — elevated, not saturated.",
                _patient_dict(df, i_high),
                **src(i_high),
            ),  # fmt: skip
            scen(
                "C",
                "Mixed-vessel pattern",
                "One vessel elevated, the others low — vessel-specific, not one CAD colour painted on all arteries.",
                _patient_dict(df, i_mixed),
                **src(i_mixed),
            ),  # fmt: skip
            scen(
                "D",
                "Unrepresentative profile",
                "SYNTHETIC extreme profile far outside the cohort — expect a representativeness warning.",
                ood_patient,
                source="synthetic",
            ),  # fmt: skip
            scen(
                "E",
                "Sensitivity simulation",
                "Mid-range LAD estimate; one out-of-range value moved to its reference bound (largest model response found by exhaustive search).",
                _patient_dict(df, i_cf),
                **src(i_cf),
                perturbation={best[1]: best[2]},
                search_delta_lad=round(best[3], 4),
            ),  # fmt: skip
        ],
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Train CardioTwin models and write artifacts.")
    ap.add_argument("--quick", action="store_true", help="1 repeat, no challengers (smoke test)")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    res = train(
        args.out,
        n_repeats=1 if args.quick else 3,
        n_boot_cv=8 if args.quick else 20,
        n_boot_final=30 if args.quick else 100,
        challengers=not args.quick,
    )
    ev = res["evaluation"]
    print("artifact sha256:", res["artifact"]["sha256"])
    for t in TARGET_ORDER:
        s = ev["targets"][t]["cv_summary"]
        print(
            f"{t}: AUC {s['roc_auc']} {s['roc_auc_ci95']}  PR-AUC {s['pr_auc']}  Brier {s['brier']}  ECE {s['ece']}"
        )


if __name__ == "__main__":
    main()
