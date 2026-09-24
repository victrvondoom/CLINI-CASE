"""Patient Trajectory Engine — dynamics of the risk trajectory, not just today's number.

Works on the as-of history snapshots (each day's risk was computed with only
the data available that day). Risk is analysed on the log-odds scale, smoothed
with a causal 3-day mean:

  slope          change in smoothed log-odds per day over the last 3 days
  acceleration   slope now minus slope 3 days earlier

Dynamics (first match wins, evaluated on day t):
  in acute care            patient is in qualifying acute care (dynamics paused)
  persistent deterioration ≥ WATCH for ≥ 3 consecutive days and still rising
  trajectory acceleration  rising and the rise is speeding up
  failed recovery          after a peak ≥ EARLY WARNING threshold the risk fell
                           ≥ 30 %, then rose again ≥ 50 % above its trough
  recovery                 after such a peak, risk ≤ half the peak and falling
  trajectory reversal      slope changed sign (either direction)
  stabilization            flat for 3 days after a recent rise
  rising / falling / stable

Thresholds are returned in the payload; nothing is hidden.
"""
from __future__ import annotations

from typing import Any

import numpy as np

from app.oncotwin.engine.warning import RANK

SLOPE_RISE = 0.10          # log-odds per day
SLOPE_FLAT = 0.05
ACCEL = 0.15


def _logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(p, 1e-4, 1 - 1e-4)
    return np.log(p / (1 - p))


def _smooth(x: np.ndarray) -> np.ndarray:
    return np.array([x[max(0, i - 2): i + 1].mean() for i in range(len(x))])


def _slope(y: np.ndarray, i: int, w: int = 3) -> float:
    if i < 1:
        return 0.0
    seg = y[max(0, i - w + 1): i + 1]
    return float(np.polyfit(np.arange(len(seg)), seg, 1)[0]) if len(seg) >= 2 else 0.0


def _label(h: dict[str, Any], slope: float) -> str:
    tier = h["tier"]
    if tier == "IN ACUTE CARE":
        return "In acute care"
    if tier == "HIGH PRIORITY":
        return "High concern"
    if tier == "EARLY WARNING":
        return "Multi-signal deterioration" if h["n_concordant"] >= 3 else "Elevated risk"
    if tier == "WATCH":
        return "Increasing deviation" if slope > SLOPE_RISE else "Mild deviation"
    return "Mild deviation" if h["n_concordant"] >= 2 else "Stable"


def dynamics(history: list[dict[str, Any]], t: int, thresholds: dict[str, float]) -> dict[str, Any]:
    hist = [h for h in history if h["day"] <= t]
    if not hist:
        return {"as_of_day": t, "dynamics": "no history", "explanation": "", "narrative": []}
    L = _smooth(_logit(np.array([h["risk"] for h in hist])))
    i = len(hist) - 1
    slope = _slope(L, i)
    slope_prev = _slope(L, i - 3) if i >= 4 else 0.0
    accel = slope - slope_prev
    cur = hist[-1]
    ew = thresholds["early_warning"]

    recent = [h for h in hist[-14:] if h["tier"] != "IN ACUTE CARE"]
    peak = max(recent, key=lambda h: h["risk"]) if recent else None
    after_peak = [h for h in recent if peak and h["day"] > peak["day"]]
    trough = min(after_peak, key=lambda h: h["risk"]) if after_peak else None
    run = 0
    for h in reversed(hist):
        if RANK.get(h["tier"], 0) < RANK["WATCH"]:
            break
        run += 1

    if cur["tier"] == "IN ACUTE CARE":
        name, why = "in acute care", "Patient is in qualifying acute care; alerting and dynamics are paused."
    elif run >= 3 and slope > SLOPE_RISE:
        name, why = "persistent deterioration", (f"WATCH-or-higher for {run} consecutive days and still rising "
                                                 f"({slope:+.2f} log-odds/day).")
    elif run >= 3 and RANK.get(cur["tier"], 0) >= RANK["EARLY WARNING"] and slope >= -SLOPE_RISE:
        name, why = "persistent deterioration", (f"{cur['tier']} sustained — WATCH-or-higher for {run} consecutive days "
                                                 f"without improvement ({slope:+.2f} log-odds/day).")
    elif slope > SLOPE_RISE and accel > ACCEL:
        name, why = "trajectory acceleration", f"Rising {slope:+.2f} log-odds/day, {accel:+.2f} faster than 3 days earlier."
    elif (peak and peak["risk"] >= ew and trough and trough["risk"] <= 0.7 * peak["risk"]
          and cur["day"] > trough["day"] and cur["risk"] >= 1.5 * max(trough["risk"], 1e-4) and slope > 0):
        name, why = "failed recovery", (f"Risk fell from {peak['risk']:.1%} (Day {peak['day']}) to {trough['risk']:.1%} "
                                        f"(Day {trough['day']}) and has risen again to {cur['risk']:.1%}.")
    elif peak and peak["risk"] >= ew and peak["day"] < cur["day"] and cur["risk"] <= 0.5 * peak["risk"] and slope <= 0:
        name, why = "recovery", f"Risk {cur['risk']:.1%}, down from a peak of {peak['risk']:.1%} on Day {peak['day']}."
    elif slope_prev > SLOPE_RISE and slope < -SLOPE_RISE:
        name, why = "trajectory reversal (improving)", f"Slope changed from {slope_prev:+.2f} to {slope:+.2f} log-odds/day."
    elif slope_prev < -SLOPE_RISE and slope > SLOPE_RISE:
        name, why = "trajectory reversal (worsening)", f"Slope changed from {slope_prev:+.2f} to {slope:+.2f} log-odds/day."
    elif abs(slope) < SLOPE_FLAT and any(_slope(L, j) > SLOPE_RISE for j in range(max(1, i - 7), max(1, i - 2))):
        name, why = "stabilization", "Flat over the last 3 days after a rise earlier this week."
    elif slope > SLOPE_RISE:
        name, why = "rising", f"{slope:+.2f} log-odds/day."
    elif slope < -SLOPE_RISE:
        name, why = "falling", f"{slope:+.2f} log-odds/day."
    else:
        name, why = "stable", "No material change in the risk trajectory."

    narrative = []
    for h in hist[-8:]:
        j = h["day"] - hist[0]["day"]
        off = h["day"] - t
        narrative.append({"day": h["day"], "offset": "Today" if off == 0 else f"Day {off}",
                          "label": _label(h, _slope(L, j)), "tier": h["tier"], "risk": h["risk"],
                          "n_concordant": h["n_concordant"]})
    return {
        "as_of_day": t, "dynamics": name, "explanation": why,
        "slope_logit_per_day": round(slope, 3), "acceleration": round(accel, 3),
        "peak_14d": None if not peak else {"day": peak["day"], "risk": peak["risk"], "tier": peak["tier"]},
        "days_at_watch_or_higher": run, "narrative": narrative,
        "thresholds": {"slope_rise": SLOPE_RISE, "slope_flat": SLOPE_FLAT, "acceleration": ACCEL,
                       "peak_reference_early_warning": ew},
        "method": "causal 3-day mean of log-odds risk; slopes by least squares over 3 days",
    }
