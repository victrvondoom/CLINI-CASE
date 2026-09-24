"""Change-point detection — Bayesian Online Change-Point Detection (BOCPD).

Algorithm: Adams RP, MacKay DJC. "Bayesian Online Changepoint Detection",
arXiv:0710.3742 (2007). A run-length posterior P(r_t | x_1:t) is updated day
by day; a change point is a day on which the posterior concludes a new
"physiological regime" began.

Observation model (per regime): the day's adverse-oriented deviation vector
from the patient's PERSONAL baseline, x_t ∈ R^S (S = model signals), with
    x_t,s ~ N(μ_s, σ_s²),  μ_s ~ N(0, V0)       (conjugate, known variance)
σ_s is the within-baseline noise of that signal's deviation (robust, per
patient). Missing signals simply drop out of the likelihood for that day.
Constant hazard H = 1/λ.

Why BOCPD here: it is online (causal — the posterior on day t uses only
days ≤ t, so as-of replay is exact), it returns a probability rather than a
threshold crossing, and it detects a SHIFT in the joint multi-signal level —
the "stable baseline → change point → new physiological regime" pattern.

Honest limits: the regime model assumes day-to-day independence, so a slow
drift can be segmented into steps; treatment itself produces expected
regime changes, which are therefore annotated with the clinical context
(e.g. "coincides with chemotherapy administration") rather than hidden.
Detection delay and false-change-point rate are measured on the synthetic
cohort by the research benchmark (never assumed).
"""
from __future__ import annotations

import warnings
from typing import Any

import numpy as np

from app.oncotwin.engine.baseline import Baseline, adverse_z
from app.oncotwin.engine.features import signal_matrix
from app.oncotwin.engine.series import PatientSeries
from app.oncotwin.signals import MODEL_SIGNALS, SIGNALS

HAZARD_LAMBDA_DAYS = 40.0
PRIOR_MEAN_VAR = 2.0 ** 2
SIGMA_BOUNDS = (0.6, 1.5)
CONFIRM_MASS = 0.6            # posterior mass on "regime began on day c" needed to report c
MAX_CONFIRM_DELAY_DAYS = 7    # a regime start first confirmed later than this is not an actionable detection
MIN_SEPARATION_DAYS = 3
CONTRIB_MIN_SHIFT = 0.75      # SD shift for a signal to count as contributing
MIN_JOINT_SHIFT = 1.0         # ‖Δ mean deviation‖ below this is negligible and not reported
SIGNIFICANT = {"posterior": 0.8, "max_shift_sd": 1.5}
ALGORITHM = {"id": "bocpd-gaussian-known-variance", "version": "1.1.0",
             "reference": "Adams & MacKay 2007, arXiv:0710.3742",
             "hazard_lambda_days": HAZARD_LAMBDA_DAYS, "prior_mean_sd": PRIOR_MEAN_VAR ** 0.5,
             "confirm_posterior_mass": CONFIRM_MASS, "max_confirm_delay_days": MAX_CONFIRM_DELAY_DAYS,
             "min_joint_shift_sd": MIN_JOINT_SHIFT, "significant_if": SIGNIFICANT}


def _noise_sd(z: np.ndarray, baseline: Baseline) -> np.ndarray:
    lo, hi = baseline.window
    zb = z[lo - 1: hi]
    out = []
    for i in range(z.shape[1]):
        col = zb[:, i]
        col = col[~np.isnan(col)]
        if col.size >= 4:
            med = np.median(col)
            sd = 1.4826 * float(np.median(np.abs(col - med)))
        else:
            sd = 1.0
        out.append(float(np.clip(sd, *SIGMA_BOUNDS)))
    return np.array(out)


def run_bocpd(z: np.ndarray, sigma: np.ndarray, *, hazard_lambda: float = HAZARD_LAMBDA_DAYS,
              prior_var: float = PRIOR_MEAN_VAR) -> np.ndarray:
    """Run-length posteriors. `z` is (T, S) with NaN = missing. Returns R (T, T+1):
    R[t, r] = P(run length r on day t+1 | x_1..x_{t+1}); every row sums to 1."""
    T, S = z.shape
    H = 1.0 / hazard_lambda
    var = sigma ** 2
    R = np.zeros((T, T + 1))
    n = np.zeros((1, S))            # sufficient statistics per candidate run length
    sx = np.zeros((1, S))
    prev = np.array([1.0])
    for t in range(T):
        x = z[t]
        obs = ~np.isnan(x)
        v_post = 1.0 / (1.0 / prior_var + n / var)            # posterior of μ per run length
        m_post = v_post * (sx / var)
        if obs.any():
            pv = v_post[:, obs] + var[obs]                     # predictive variance
            ll = -0.5 * (np.log(2 * np.pi * pv) + (x[obs] - m_post[:, obs]) ** 2 / pv)
            s = ll.sum(axis=1)
            pred = np.exp(s - s.max())
        else:
            pred = np.ones(len(prev))
        growth = prev * pred * (1 - H)
        cp = float(np.sum(prev * pred * H))
        post = np.concatenate([[cp], growth])
        post /= post.sum()
        R[t, : len(post)] = post
        xo = np.where(obs, x, 0.0)
        n = np.vstack([np.zeros((1, S)), n]) + obs.astype(float)
        sx = np.vstack([np.zeros((1, S)), sx]) + xo
        prev = post
    return R


def _context(series: PatientSeries, day: int) -> list[dict[str, Any]]:
    out, seen = [], set()
    for e in series.events:
        # ±3 days: BOCPD localises a regime start to within a couple of days.
        if not (day - 3 <= e.day <= day + 3) or e.day < 1:
            continue
        if e.kind == "chemo_dose":
            item = {"kind": "treatment", "day": e.day, "id": e.id,
                    "text": f"chemotherapy administered Day {e.day} (expected treatment-related shift)"}
        elif e.kind in ("gcsf_dose", "antibiotic", "hydration", "encounter"):
            qualifying = e.kind == "encounter" and e.detail.get("qualifying")
            item = {"kind": "acute_care" if qualifying else "intervention", "day": e.day, "id": e.id,
                    "text": f"{e.display} (Day {e.day})"}
        else:
            continue
        key = (item["kind"], item["day"], item["text"][:40])
        if key not in seen:
            seen.add(key)
            out.append(item)
    for f in series.flags:
        if f.kind in ("stuck", "implausible", "conflict") and any(day - 2 <= d <= day + 1 for d in f.days):
            out.append({"kind": "data_quality", "day": f.days[0], "id": (f.observation_ids or [None])[0],
                        "text": f"data-quality issue near this day: {f.kind} ({SIGNALS[f.signal].label})"})
    return out


def _nanmean0(a: np.ndarray) -> np.ndarray:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return np.nanmean(a, axis=0)


def detect(series: PatientSeries, baseline: Baseline) -> dict[str, Any]:
    """Change points up to the series' as-of day, each with contributing signals and context."""
    z = adverse_z(signal_matrix(series), baseline)[0]            # (T, S), NaN = missing
    T = z.shape[0]
    sigma = _noise_sd(z, baseline)
    R = run_bocpd(z, sigma)
    runs = np.arange(T + 1)
    map_run = [int(np.argmax(R[t])) for t in range(T)]
    # Confirmation: the first day t on which ≥ CONFIRM_MASS of the posterior says
    # the current regime began on day c (±1 day) — c is a change point detected on t.
    found: dict[int, dict[str, Any]] = {}
    for t in range(T):
        day = t + 1
        r = map_run[t]
        c = day - r
        if r == 0 or c <= 1:
            continue
        mass = float(R[t, max(0, r - 1): r + 2].sum())
        if mass < CONFIRM_MASS or day - c > MAX_CONFIRM_DELAY_DAYS \
                or any(abs(c - k) < MIN_SEPARATION_DAYS for k in found):
            continue
        found[c] = {"day": c, "detected_on_day": day, "posterior_mass": round(mass, 3),
                    "detection_delay_days": day - c}
    points = []
    for c, cp in sorted(found.items()):
        # Shift is measured with data available on the confirmation day only (as-of).
        new = z[c - 1: min(cp["detected_on_day"], c + 6)]
        old = z[max(0, c - 8): c - 1]
        if not len(old) or not len(new):
            continue
        dm = _nanmean0(new) - _nanmean0(old)
        joint = float(np.sqrt(np.nansum(dm ** 2)))
        if joint < MIN_JOINT_SHIFT:
            continue
        contrib = [{"signal": k, "label": SIGNALS[k].label, "shift_sd": round(float(dm[i]), 2),
                    "direction": "adverse" if dm[i] > 0 else "improving"}
                   for i, k in enumerate(MODEL_SIGNALS) if not np.isnan(dm[i]) and abs(dm[i]) >= CONTRIB_MIN_SHIFT]
        contrib.sort(key=lambda x: -abs(x["shift_sd"]))
        adverse = sum(x["shift_sd"] for x in contrib if x["shift_sd"] > 0)
        better = -sum(x["shift_sd"] for x in contrib if x["shift_sd"] < 0)
        kind = "adverse shift" if adverse > 1.5 * better else "recovery shift" if better > 1.5 * adverse else "mixed shift"
        ctx = _context(series, c)
        expected = any(x["kind"] == "treatment" for x in ctx)
        significant = (cp["posterior_mass"] >= SIGNIFICANT["posterior"]
                       and max((abs(x["shift_sd"]) for x in contrib), default=0.0) >= SIGNIFICANT["max_shift_sd"])
        points.append({
            **cp, "kind": kind, "joint_shift_sd": round(joint, 2), "significance": "significant" if significant else "possible",
            "contributors": contrib, "context": ctx, "expected_treatment_effect": expected,
            "statement": (
                (f"A significant trajectory change was detected: a new physiological regime began on Day {c} "
                 if significant else f"A possible regime change began on Day {c} ")
                + f"(posterior {cp['posterior_mass']:.0%}, confirmed Day {cp['detected_on_day']}). "
                + ("Contributing signals: " + ", ".join(f"{x['label']} {x['shift_sd']:+.1f} SD" for x in contrib[:4]) + ". "
                   if contrib else "No single signal shifted ≥ 0.75 SD; the change is in the joint level. ")
                + ("It coincides with chemotherapy administration, consistent with an expected on-treatment shift."
                   if expected else "No chemotherapy administration within 3 days — not explained by the treatment schedule.")
            ),
        })
    # "Unexplained": significant, adverse-leaning, and not coinciding with treatment, an
    # intervention, acute care or a data-quality issue.
    latest = next((p for p in reversed(points) if p["kind"] != "recovery shift" and not p["context"]
                   and p["significance"] == "significant"), None)
    return {
        "algorithm": ALGORITHM,
        "noise_sd": {k: round(float(sigma[i]), 3) for i, k in enumerate(MODEL_SIGNALS)},
        "days": list(range(1, T + 1)),
        "p_change_last_3d": [round(float(R[t, :4].sum()), 4) for t in range(T)],
        "map_run_length": map_run,
        "expected_run_length": [round(float((R[t] * runs).sum()), 2) for t in range(T)],
        "change_points": points,
        "latest_unexplained_adverse": latest,
        "language_note": ("A change point is a statistical regime shift in this patient's own signals; it is "
                          "associated with, not proof of, a clinical event."),
    }
