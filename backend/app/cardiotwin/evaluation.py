"""Metrics, calibration diagnostics and paired model-comparison statistics.

Pure functions over (y_true, probability) arrays. Everything reported by
CardioTwin's evaluation page is produced by these helpers from real
out-of-fold predictions — nothing is hand-entered.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    log_loss,
    precision_recall_curve,
    roc_auc_score,
    roc_curve,
)

EPS = 1e-6


def ece(y: np.ndarray, p: np.ndarray, bins: int = 10) -> float:
    """Expected calibration error with equal-width bins."""
    edges = np.linspace(0, 1, bins + 1)
    idx = np.clip(np.digitize(p, edges[1:-1]), 0, bins - 1)
    total = 0.0
    for b in range(bins):
        m = idx == b
        if m.any():
            total += m.mean() * abs(float(y[m].mean()) - float(p[m].mean()))
    return float(total)


def calibration_curve(y: np.ndarray, p: np.ndarray, bins: int = 8) -> list[dict[str, float]]:
    """Quantile-binned reliability points (equal counts, so sparse bins stay readable)."""
    order = np.argsort(p)
    out = []
    for chunk in np.array_split(order, bins):
        if len(chunk):
            out.append(
                {
                    "mean_predicted": round(float(p[chunk].mean()), 4),
                    "observed_rate": round(float(y[chunk].mean()), 4),
                    "n": int(len(chunk)),
                }
            )
    return out


def threshold_metrics(y: np.ndarray, p: np.ndarray, thr: float) -> dict[str, float | int]:
    pred = (p >= thr).astype(int)
    tp = int(((pred == 1) & (y == 1)).sum())
    fp = int(((pred == 1) & (y == 0)).sum())
    tn = int(((pred == 0) & (y == 0)).sum())
    fn = int(((pred == 0) & (y == 1)).sum())
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    spec = tn / (tn + fp) if tn + fp else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return {
        "threshold": round(float(thr), 4),
        "accuracy": round((tp + tn) / len(y), 4),
        "precision": round(prec, 4),
        "recall": round(rec, 4),
        "specificity": round(spec, 4),
        "f1": round(f1, 4),
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
    }


def youden_threshold(y: np.ndarray, p: np.ndarray) -> float:
    """Threshold maximising sensitivity + specificity - 1 (chosen on TRAINING predictions only)."""
    fpr, tpr, thr = roc_curve(y, p)
    j = tpr - fpr
    k = int(np.argmax(j))
    t = float(thr[k])
    return float(np.clip(t, 0.0, 1.0))


def point_metrics(y: np.ndarray, p: np.ndarray) -> dict[str, float]:
    pc = np.clip(p, EPS, 1 - EPS)
    return {
        "roc_auc": float(roc_auc_score(y, p)),
        "pr_auc": float(average_precision_score(y, p)),
        "brier": float(brier_score_loss(y, p)),
        "log_loss": float(log_loss(y, pc)),
        "ece": ece(y, p),
    }


def bootstrap_ci(
    y: np.ndarray, p: np.ndarray, *, n_boot: int = 1000, seed: int = 0
) -> dict[str, dict[str, float]]:
    """Patient-level percentile bootstrap 95% CIs for the headline metrics."""
    rng = np.random.default_rng(seed)
    n = len(y)
    keys = ("roc_auc", "pr_auc", "brier", "ece")
    draws: dict[str, list[float]] = {k: [] for k in keys}
    for _ in range(n_boot):
        i = rng.integers(0, n, n)
        if y[i].min() == y[i].max():
            continue
        m = point_metrics(y[i], p[i])
        for k in keys:
            draws[k].append(m[k])
    base = point_metrics(y, p)
    return {
        k: {
            "estimate": round(base[k], 4),
            "ci95_low": round(float(np.percentile(draws[k], 2.5)), 4),
            "ci95_high": round(float(np.percentile(draws[k], 97.5)), 4),
        }
        for k in keys
    }


def curve_points(
    y: np.ndarray, p: np.ndarray, max_points: int = 60
) -> dict[str, list[list[float]]]:
    fpr, tpr, _ = roc_curve(y, p)
    prec, rec, _ = precision_recall_curve(y, p)

    def thin(a: np.ndarray, b: np.ndarray) -> list[list[float]]:
        step = max(1, len(a) // max_points)
        pts = [[round(float(a[i]), 4), round(float(b[i]), 4)] for i in range(0, len(a), step)]
        pts.append([round(float(a[-1]), 4), round(float(b[-1]), 4)])
        return pts

    return {"roc": thin(fpr, tpr), "pr": thin(rec, prec)}


def corrected_paired_t(diffs: np.ndarray, n_train: int, n_test: int) -> dict[str, float]:
    """Nadeau & Bengio (2003) corrected resampled t-test on per-fold metric differences.

    Repeated CV folds overlap, so the naive variance is too small; the correction
    inflates it by (1/k + n_test/n_train). Returns the mean difference and a two-sided p.
    """
    from scipy import stats

    d = np.asarray(diffs, dtype=float)
    k = len(d)
    mean = float(d.mean())
    var = float(d.var(ddof=1)) if k > 1 else 0.0
    denom = np.sqrt((1.0 / k + n_test / n_train) * var)
    if denom == 0:
        return {"mean_diff": mean, "t": 0.0, "p_value": 1.0}
    t = mean / denom
    p = float(2 * stats.t.sf(abs(t), k - 1))
    return {"mean_diff": round(mean, 4), "t": round(float(t), 3), "p_value": round(p, 4)}


def summarize_folds(values: list[float]) -> dict[str, float]:
    v = np.asarray(values, dtype=float)
    return {
        "mean": round(float(v.mean()), 4),
        "sd": round(float(v.std(ddof=1)), 4),
        "folds": int(len(v)),
    }


def spearman(a: np.ndarray, b: np.ndarray) -> float:
    from scipy import stats

    if np.std(a) == 0 or np.std(b) == 0:
        return 0.0
    return float(stats.spearmanr(a, b).statistic)


def as_jsonable(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): as_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list | tuple):
        return [as_jsonable(v) for v in obj]
    if isinstance(obj, np.generic):
        return obj.item()
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj
