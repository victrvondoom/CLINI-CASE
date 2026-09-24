"""Twin Memory + Recovery Velocity.

The twin remembers how THIS patient responded to previous treatment cycles and
compares the current cycle against them:

  cycles          the course is segmented at each chemotherapy administration
  response        per cycle and signal: peak adverse deviation (SD vs the
                  personal baseline), day-of-cycle of the peak, half-recovery
                  time and recovery velocity
  MSDI            multi-signal deterioration index per day = sum of positive
                  adverse deviations across the model signals (scaled for
                  missing signals), trailing 3-day mean
  recovery        velocity (SD/day) of the MSDI decline from its peak to half
                  its peak, and whether it recovered, is recovering, or failed
                  to recover
  similarity      Pearson r and RMS distance between the current cycle's
                  day-aligned multi-signal deviation profile and each earlier
                  cycle over the overlapping days
  episodes        previous deterioration episodes (WATCH-or-higher runs that
                  reached EARLY WARNING) and how each resolved

Statistical similarity of signal patterns is NOT clinical equivalence, and a
previous cycle's course is memory, not a forecast; both are stated in the payload.
Recovery velocity is an analytics measure, not a clinical diagnosis.
"""
from __future__ import annotations

import warnings
from typing import Any

import numpy as np

from app.oncotwin.engine.baseline import Baseline, adverse_z, carry_forward
from app.oncotwin.engine.features import signal_matrix
from app.oncotwin.engine.series import PatientSeries
from app.oncotwin.engine.warning import RANK
from app.oncotwin.signals import MODEL_SIGNALS, SIGNALS

PERTURBED_SD = 1.5            # per-signal peak (SD) that counts as a perturbation
PERTURBED_MSDI = 3.0          # multi-signal index peak that counts (e.g. three signals at 2 SD)
MIN_OVERLAP_DAYS = 4


def _trail3(x: np.ndarray) -> np.ndarray:
    out = np.full(len(x), np.nan)
    for i in range(len(x)):
        seg = x[max(0, i - 2): i + 1]
        seg = seg[~np.isnan(seg)]
        if seg.size:
            out[i] = seg.mean()
    return out


def msdi(z: np.ndarray) -> np.ndarray:
    """(T,) multi-signal deterioration index from (T, S) adverse z: the summed EXCESS adverse
    deviation beyond 1 SD across signals (NaN-aware, scaled to all S signals). Broad mild
    on-treatment shifts (~1 SD everywhere) stay near 0; marked concordant deviation scores high."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return np.nanmean(np.clip(z - 1.0, 0.0, None), axis=1) * z.shape[1]


def _recovery(curve: np.ndarray, threshold: float = PERTURBED_SD) -> dict[str, Any]:
    """Peak / half-recovery / velocity of a smoothed deviation curve indexed by day-of-cycle."""
    valid = ~np.isnan(curve)
    if not valid.any():
        return {"peak": None, "status": "no data"}
    i_peak = int(np.nanargmax(curve))
    peak = float(curve[i_peak])
    out: dict[str, Any] = {"peak": round(peak, 2), "peak_day_of_cycle": i_peak + 1}
    if peak < threshold:
        out.update({"status": "no significant perturbation", "half_recovery_days": None, "velocity_sd_per_day": None})
        return out
    half = next((j for j in range(i_peak + 1, len(curve)) if valid[j] and curve[j] <= 0.5 * peak), None)
    last = next((float(curve[j]) for j in range(len(curve) - 1, -1, -1) if valid[j]), peak)
    since = len(curve) - 1 - i_peak
    if half is not None:
        dh = half - i_peak
        rest = [curve[j] for j in range(half, len(curve)) if valid[j]]
        out.update({"status": "recovered" if len(rest) >= 2 and all(v < 1.0 for v in rest) else "half-recovered",
                    "half_recovery_days": dh, "velocity_sd_per_day": round((peak - float(curve[half])) / dh, 3)})
    elif since >= 4 and last >= 0.8 * peak:
        out.update({"status": "failed recovery (< 20 % decline within 4+ days of the peak)", "half_recovery_days": None,
                    "velocity_sd_per_day": round((peak - last) / since, 3)})
    else:
        out.update({"status": "recovering" if since else "at peak", "half_recovery_days": None,
                    "velocity_sd_per_day": round((peak - last) / since, 3) if since else None})
    return out


def _profile_corr(a: np.ndarray, b: np.ndarray) -> tuple[float | None, float | None, int]:
    m = ~np.isnan(a) & ~np.isnan(b)
    n = int(m.sum())
    if n < 6 or np.std(a[m]) < 1e-9 or np.std(b[m]) < 1e-9:
        return None, None, n
    return float(np.corrcoef(a[m], b[m])[0, 1]), float(np.sqrt(np.mean((a[m] - b[m]) ** 2))), n


def episodes(history: list[dict[str, Any]], t: int, events) -> list[dict[str, Any]]:
    """Previous and current deterioration episodes (WATCH-or-higher runs that reached EARLY WARNING)."""
    out, cur = [], None
    for h in [h for h in history if h["day"] <= t]:
        on = RANK.get(h["tier"], 0) >= RANK["WATCH"]
        if on and cur is None:
            cur = {"start_day": h["day"], "peak_day": h["day"], "peak_risk": h["risk"], "peak_tier": h["tier"]}
        if cur is not None and on:
            if h["risk"] > cur["peak_risk"]:
                cur.update(peak_day=h["day"], peak_risk=h["risk"])
            if RANK.get(h["tier"], 0) > RANK.get(cur["peak_tier"], 0):
                cur["peak_tier"] = h["tier"]
        if cur is not None and not on:
            cur.update(end_day=h["day"], resolution="acute care" if h["tier"] == "IN ACUTE CARE" else "returned to NORMAL")
            out.append(cur)
            cur = None
    if cur is not None:
        cur.update(end_day=None, resolution="ongoing")
        out.append(cur)
    out = [e for e in out if RANK.get(e["peak_tier"], 0) >= RANK["EARLY WARNING"]]
    for e in out:
        end = e["end_day"] or t
        e["duration_days"] = end - e["start_day"] + 1
        e["interventions"] = [
            {"day": ev.day, "display": ev.display, "id": ev.id} for ev in events
            if e["start_day"] <= ev.day <= end and (
                ev.kind in ("antibiotic", "hydration")
                or (ev.kind == "gcsf_dose" and ev.detail.get("indication") == "treatment")
                or (ev.kind == "encounter" and not ev.detail.get("qualifying")))]
    return out


def analyse(series: PatientSeries, baseline: Baseline, history: list[dict[str, Any]]) -> dict[str, Any]:
    t = series.as_of_day
    Z = carry_forward(adverse_z(signal_matrix(series), baseline), 1)[0]      # (T, S)
    M = _trail3(msdi(Z))
    Zs = np.stack([_trail3(Z[:, i]) for i in range(Z.shape[1])], axis=1)
    doses = sorted(series.dose_days)
    cycles = []
    for j, d0 in enumerate(doses):
        d1 = (doses[j + 1] - 1) if j + 1 < len(doses) else t
        seg = slice(d0 - 1, d1)
        per_signal = {}
        for i, k in enumerate(MODEL_SIGNALS):
            rec = _recovery(Zs[seg, i])
            if rec.get("peak") is not None and rec["peak"] >= PERTURBED_SD:
                per_signal[k] = {"label": SIGNALS[k].label, **rec}
        labs = [(d, v) for d, v, _ in series.labs.get("anc", []) if d0 <= d <= d1]
        nadir = min(labs, key=lambda x: x[1]) if labs else None
        cycles.append({
            "cycle": j + 1, "start_day": d0, "end_day": d1, "complete": j + 1 < len(doses),
            "length_days": d1 - d0 + 1, "dose_scale": series.dose_days[d0],
            "msdi": {**_recovery(M[seg], PERTURBED_MSDI),
                     "curve": [None if np.isnan(x) else round(float(x), 2) for x in M[seg]]},
            "perturbed_signals": per_signal,
            "anc_nadir_lab": None if nadir is None else {"day": nadir[0], "day_of_cycle": nadir[0] - d0 + 1, "value": nadir[1]},
            "gcsf_in_cycle": any(d0 <= g <= d1 for g in series.gcsf_days),
        })

    similarity = []
    if len(cycles) >= 2:
        cur = cycles[-1]
        m = cur["length_days"]
        for prev in cycles[:-1]:
            n = min(m, prev["length_days"])
            if n < MIN_OVERLAP_DAYS:
                continue
            a = Zs[cur["start_day"] - 1: cur["start_day"] - 1 + n].ravel()
            b = Zs[prev["start_day"] - 1: prev["start_day"] - 1 + n].ravel()
            r, rms, npairs = _profile_corr(a, b)
            if r is None:
                continue
            pm = prev["msdi"]
            similarity.append({
                "compared_with_cycle": prev["cycle"], "overlap_days": n, "pearson_r": round(r, 2),
                "rms_sd": round(rms, 2), "n_pairs": npairs,
                "previous_course": (f"In cycle {prev['cycle']} the multi-signal index peaked at {pm.get('peak')} on day "
                                    f"{pm.get('peak_day_of_cycle')} of the cycle ({pm.get('status')})."),
                "text": (f"Current cycle {cur['cycle']} (day {m}) {'statistically resembles' if r >= 0.6 else 'differs from'} "
                         f"cycle {prev['cycle']} over days 1–{n} (r = {r:.2f}, RMS difference {rms:.2f} SD)."),
            })
    return {
        "as_of_day": t, "cycles": cycles, "current_cycle": cycles[-1]["cycle"] if cycles else None,
        "similarity": similarity, "episodes": episodes(history, t, series.events),
        "msdi_series": [None if np.isnan(x) else round(float(x), 2) for x in M],
        "recovery_velocity": cycles[-1]["msdi"] if cycles else None,
        "notes": [
            "Similarity is statistical similarity of this patient's day-aligned deviation profiles — not clinical equivalence.",
            "A previous cycle's course is memory, not a forecast of this cycle.",
            "Recovery velocity (SD/day decline of the multi-signal index) is an analytics measure, not a diagnosis.",
        ],
        "method": {"msdi": "sum over model signals of adverse deviation beyond 1 SD (scaled for missing), trailing 3-day mean",
                   "perturbed_if_peak_sd_at_least": PERTURBED_SD, "perturbed_if_msdi_peak_at_least": PERTURBED_MSDI,
                   "half_recovery": "first day after the peak at or below half the peak",
                   "similarity": "Pearson r / RMS over day-aligned (signal × day) deviation profiles"},
    }
