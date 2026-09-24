"""Cross-Signal Correlation Engine.

Instead of N unrelated per-signal warnings, the engine describes ONE
multi-signal trajectory change over the current episode window:

  per signal   direction, magnitude (units, % where ratio-scaled, SD vs the
               personal baseline), onset day, persistence, baseline range and
               the signal's contribution to the model prediction (log-odds)
  ordering     which signal's deviation began first — "temporally preceded"
  lead / lag   cross-correlation of deviation series at lags −3…+3 days
  coupling     correlation between deviating signals inside the episode vs the
               same pair's correlation in the patient's own baseline window

Episode window: from the latest significant change point (if within 14 days),
else the start of the current WATCH-or-higher episode, else the last 7 days.

Language: "associated with", "temporally preceded", "contributed to the model
prediction". Correlation between signals is never presented as causation.
"""
from __future__ import annotations

import warnings
from typing import Any

import numpy as np

from app.oncotwin.engine.baseline import DEVIATION_Z, Baseline, adverse_z
from app.oncotwin.engine.features import signal_matrix
from app.oncotwin.engine.series import PatientSeries
from app.oncotwin.engine.warning import RANK
from app.oncotwin.signals import MODEL_SIGNALS, SIGNALS

RATIO_SCALED = {"resting_hr", "hrv_sdnn", "steps", "sleep_hours", "weight", "sbp"}
MAX_WINDOW_DAYS = 14
LAG_RANGE = 3
LEADLAG_MIN_R = 0.6
LEADLAG_MIN_PAIRS = 8
COUPLING_MIN_DAYS = 5
COUPLING_MIN_DELTA = 0.4


def _nanmean(a: np.ndarray) -> float | None:
    if not np.any(~np.isnan(a)):
        return None
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return float(np.nanmean(a))


def _corr(a: np.ndarray, b: np.ndarray) -> tuple[float | None, int]:
    m = ~np.isnan(a) & ~np.isnan(b)
    n = int(m.sum())
    if n < 3 or np.std(a[m]) < 1e-9 or np.std(b[m]) < 1e-9:
        return None, n
    return float(np.corrcoef(a[m], b[m])[0, 1]), n


def episode_window(t: int, history: list[dict[str, Any]], changepoints: dict[str, Any] | None) -> dict[str, Any]:
    cps = [p for p in (changepoints or {}).get("change_points", [])
           if p["significance"] == "significant" and p["kind"] != "recovery shift" and t - MAX_WINDOW_DAYS < p["day"] <= t]
    if cps:
        start = cps[-1]["day"]
        return {"start_day": start, "end_day": t, "basis": f"latest significant change point (Day {start})"}
    start = None
    for h in reversed([h for h in history if h["day"] <= t]):
        if RANK.get(h["tier"], 0) >= RANK["WATCH"]:
            start = h["day"]
        else:
            break
    if start is not None:
        start = max(start, t - MAX_WINDOW_DAYS + 1)
        return {"start_day": start, "end_day": t, "basis": f"current WATCH-or-higher episode (from Day {start})"}
    return {"start_day": max(1, t - 6), "end_day": t, "basis": "last 7 days (no active episode)"}


def _onset(z: np.ndarray, lo: int, t: int) -> int | None:
    """First day in [lo, t] with adverse deviation ≥ 1.5 SD that did not resolve the next observed days."""
    for d in range(max(1, lo), t + 1):
        v = z[d - 1]
        if np.isnan(v) or v < DEVIATION_Z:
            continue
        nxt = [x for x in z[d: min(t, d + 2)] if not np.isnan(x)]
        if all(x >= 1.0 for x in nxt):
            return d
    return None


def analyse(series: PatientSeries, baseline: Baseline, history: list[dict[str, Any]],
            contributors: list[dict[str, Any]], changepoints: dict[str, Any] | None = None) -> dict[str, Any]:
    t = series.as_of_day
    Z = adverse_z(signal_matrix(series), baseline)[0]          # (T, S)
    win = episode_window(t, history, changepoints)
    lo = win["start_day"]
    contrib_by_signal = {c["group"]: c["logit"] for c in contributors}
    rows = []
    for i, k in enumerate(MODEL_SIGNALS):
        spec = SIGNALS[k]
        base = baseline.signals.get(k)
        if base is None or not base.n_days:
            continue
        disp = base.display()
        recent = _nanmean(series.values[k][max(0, t - 3): t])
        z3 = _nanmean(Z[max(0, t - 3): t, i])
        onset = _onset(Z[:, i], lo - 3, t)
        pers = 0
        for d in range(t, 0, -1):
            v = Z[d - 1, i]
            if np.isnan(v):
                continue
            if v < DEVIATION_Z:
                break
            pers += 1
        delta = None if recent is None else recent - disp["median"]
        rows.append({
            "signal": k, "label": spec.label, "unit": spec.unit_display, "category": spec.category,
            "direction": None if delta is None else ("↑" if delta > 0 else "↓"),
            "adverse_direction": "↑" if spec.adverse == "up" else "↓",
            "deviating_adversely": bool(z3 is not None and z3 >= DEVIATION_Z),
            "recent_3d_mean": None if recent is None else round(recent, spec.decimals + 1),
            "baseline_median": disp["median"], "baseline_range": [disp["low"], disp["high"]],
            "delta": None if delta is None else round(delta, spec.decimals + 1),
            "pct_vs_baseline": (round(100 * delta / disp["median"], 1)
                                if delta is not None and k in RATIO_SCALED and disp["median"] else None),
            "z_adverse_3d": None if z3 is None else round(z3, 2),
            "onset_day": onset, "persistence_days": pers,
            "time_window": None if onset is None else f"Day {onset}–{t}",
            "model_contribution_logit": round(contrib_by_signal.get(k, 0.0), 3),
        })
    dev = sorted([r for r in rows if r["deviating_adversely"]], key=lambda r: -(r["z_adverse_3d"] or 0))
    ordered = sorted([r for r in dev if r["onset_day"] is not None], key=lambda r: (r["onset_day"], -(r["z_adverse_3d"] or 0)))
    precedence = []
    for a, b in zip(ordered, ordered[1:]):
        gap = b["onset_day"] - a["onset_day"]
        if gap >= 1:
            precedence.append({"first": a["signal"], "then": b["signal"], "gap_days": gap,
                               "text": f"{a['label']} deviation (Day {a['onset_day']}) temporally preceded "
                                       f"{b['label']} deviation (Day {b['onset_day']}) by {gap} day{'s' if gap > 1 else ''}."})

    idx = {k: i for i, k in enumerate(MODEL_SIGNALS)}
    w0 = max(0, t - MAX_WINDOW_DAYS)
    leadlag = []
    for ai, a in enumerate(dev):
        for b in dev[ai + 1:]:
            za, zb = Z[w0:t, idx[a["signal"]]], Z[w0:t, idx[b["signal"]]]
            best = None
            for lag in range(-LAG_RANGE, LAG_RANGE + 1):
                if lag > 0:
                    r, n = _corr(za[:-lag], zb[lag:])          # a leads b by `lag` days
                elif lag < 0:
                    r, n = _corr(za[-lag:], zb[:lag])          # b leads a
                else:
                    r, n = _corr(za, zb)
                if r is not None and n >= LEADLAG_MIN_PAIRS and (best is None or r > best[0]):
                    best = (r, lag, n)
            if best and best[0] >= LEADLAG_MIN_R and best[1] != 0:
                r, lag, n = best
                lead, follow = (a, b) if lag > 0 else (b, a)
                leadlag.append({"leader": lead["signal"], "follower": follow["signal"], "lag_days": abs(lag),
                                "r": round(r, 2), "n_pairs": n,
                                "text": (f"Over the last {t - w0} days {lead['label'].lower()} deviations were associated "
                                         f"with {follow['label'].lower()} deviations {abs(lag)} day(s) later (r = {r:.2f}, "
                                         f"{n} paired days).")})

    leadlag = sorted(leadlag, key=lambda x: -x["r"])[:3]      # strongest associations only

    coupling = []
    try:
        base_corr = np.linalg.inv(baseline.corr_inv)
    except np.linalg.LinAlgError:
        base_corr = None
    if base_corr is not None and t - lo + 1 >= COUPLING_MIN_DAYS:
        for ai, a in enumerate(dev):
            for b in dev[ai + 1:]:
                r, n = _corr(Z[lo - 1:t, idx[a["signal"]]], Z[lo - 1:t, idx[b["signal"]]])
                if r is None or n < COUPLING_MIN_DAYS:
                    continue
                r0 = float(base_corr[idx[a["signal"]], idx[b["signal"]]])
                if r - r0 >= COUPLING_MIN_DELTA:
                    coupling.append({"pair": [a["signal"], b["signal"]], "episode_r": round(r, 2), "baseline_r": round(r0, 2),
                                     "n_days": n, "text": (f"{a['label']} and {b['label']} moved together during the episode "
                                                          f"(r = {r:.2f}) versus r = {r0:.2f} in the baseline window.")})

    n_dev = len(dev)
    if n_dev >= 3:
        headline = "Multi-signal trajectory change detected"
        summary = (f"{n_dev} signals deviate adversely from this patient's own baseline together "
                   f"({', '.join(r['label'] for r in dev[:5])}). Treated as one trajectory, not {n_dev} separate warnings.")
    elif n_dev:
        headline = "Limited deviation"
        summary = f"{n_dev} signal(s) beyond {DEVIATION_Z} SD of the personal baseline: {', '.join(r['label'] for r in dev)}."
    else:
        headline = "No cross-signal change"
        summary = "No signal is beyond 1.5 SD of the personal baseline (3-day mean)."
    return {
        "as_of_day": t, "window": win, "headline": headline, "summary": summary,
        "n_deviating": n_dev, "signals": rows, "deviating": [r["signal"] for r in dev],
        "temporal_order": precedence, "lead_lag": leadlag, "coupling": coupling,
        "language_note": ("Relationships are statistical associations in this patient's data (temporal precedence, "
                          "co-movement); they do not establish causation. 'Contribution' is the signal's share of "
                          "the model's log-odds, not a causal effect."),
    }
