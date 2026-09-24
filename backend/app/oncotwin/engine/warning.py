"""Early-Warning Engine: tiers, transparent clinical rules, hysteresis, explanations.

Tier = max(probability tier, rule tier), where

  probability tier — the model's 7-day risk against thresholds that were
                     DERIVED on a held-out validation cohort (see model card),
                     not hand-picked;
  rule tier        — a small set of transparent safety rules:
      HIGH PRIORITY  possible febrile neutropenia: temperature ≥ 38.3 °C, or
                     ≥ 38.0 °C on two consecutive days, while ANC is measured
                     or twin-estimated < 1.0 ×10³/µL or the patient is in the
                     expected nadir window (definition adapted from the IDSA
                     neutropenic-fever guideline, Freifeld et al., Clin Infect
                     Dis 2011;52:e56–93)
      HIGH PRIORITY  systolic BP < 90 mmHg (possible hemodynamic compromise)
      WATCH          ≥ 3 signals ≥ 1.5 SD adverse for ≥ 2 days AND model risk
                     ≥ half the WATCH threshold (trajectory rule — the floor
                     stops expected on-treatment fatigue alone from escalating)

Hysteresis: escalation is immediate; de-escalation drops one tier only after
two consecutive days below the current tier, so the display does not flap.
"""
from __future__ import annotations

from typing import Any

import numpy as np

from app.oncotwin.engine.baseline import DEVIATION_Z, Baseline
from app.oncotwin.engine.features import FEATURE_NAMES, IDX, N_SIG
from app.oncotwin.engine.series import PatientSeries
from app.oncotwin.signals import MODEL_SIGNALS, SIGNALS

TIERS = ("NORMAL", "WATCH", "EARLY WARNING", "HIGH PRIORITY")
RANK = {t: i for i, t in enumerate(TIERS)}
ACUTE_CARE = "IN ACUTE CARE"
FN_TEMP_SINGLE = 38.3
FN_TEMP_SUSTAINED = 38.0

FEATURE_GROUP: dict[str, str] = {}
for _s in MODEL_SIGNALS:
    FEATURE_GROUP[f"z_{_s}"] = _s
    FEATURE_GROUP[f"slope3_{_s}"] = _s
FEATURE_GROUP.update({
    "n_concordant": "multi_signal", "anomaly": "multi_signal", "persist_max": "multi_signal",
    "nadir_risk": "neutrophil", "anc_twin_log": "neutrophil", "anc_twin_low": "neutrophil",
    "anc_lab_low": "neutrophil", "adherence_7d": "adherence", "adherence_gap": "adherence",
    "age65": "context", "on_treatment": "context", "myelotox": "context",
})
GROUP_LABEL = {
    **{s: SIGNALS[s].label for s in MODEL_SIGNALS},
    "multi_signal": "Multi-signal pattern (concordance, anomaly, persistence)",
    "neutrophil": "Neutrophil state (twin estimate, labs, nadir timing)",
    "adherence": "Supportive-medication adherence",
    "context": "Baseline risk context (regimen, age, on-treatment)",
}


def probability_tier(p: float, thresholds: dict[str, float]) -> str:
    if p >= thresholds["high_priority"]:
        return "HIGH PRIORITY"
    if p >= thresholds["early_warning"]:
        return "EARLY WARNING"
    if p >= thresholds["watch"]:
        return "WATCH"
    return "NORMAL"


def rule_tiers(
    series: PatientSeries,
    F: np.ndarray,
    nadir_weight: np.ndarray,
    probs: np.ndarray | None = None,
    watch_threshold: float | None = None,
) -> tuple[list[str], list[list[dict[str, Any]]]]:
    """Per-day rule tier and the rules that fired (with their evidence).

    `nadir_weight` is the expected-nadir timing weight per day (features.nadir_risk);
    `probs` / `watch_threshold` enable the model-risk floor on the trajectory rule.
    """
    n = series.n
    temp = series.values["temperature"]
    sbp = series.values["sbp"]
    tiers = ["NORMAL"] * n
    fired: list[list[dict[str, Any]]] = [[] for _ in range(n)]
    floor = 0.5 * watch_threshold if watch_threshold is not None else 0.0
    for t in range(n):
        nadir = nadir_weight[t] >= 0.25 * max(series.regimen.myelotox, 1e-6)
        neutro = F[t, IDX["anc_lab_low"]] > 0 or F[t, IDX["anc_twin_low"]] >= 0.5 or nadir
        tt = temp[t]
        prev = temp[t - 1] if t > 0 else np.nan
        febrile = (not np.isnan(tt)) and (tt >= FN_TEMP_SINGLE or (tt >= FN_TEMP_SUSTAINED and not np.isnan(prev) and prev >= FN_TEMP_SUSTAINED))
        if febrile and neutro:
            tiers[t] = "HIGH PRIORITY"
            fired[t].append({
                "rule": "possible_febrile_neutropenia", "tier": "HIGH PRIORITY",
                "text": (f"Temperature {tt:.1f} °C with neutropenia risk "
                         f"(twin P[ANC<1.0] {F[t, IDX['anc_twin_low']]:.0%}"
                         f"{', measured ANC < 1.0 in last 7 d' if F[t, IDX['anc_lab_low']] > 0 else ''}"
                         f"{', expected nadir window' if nadir else ''})."),
                "basis": "IDSA neutropenic fever definition (Freifeld et al., Clin Infect Dis 2011;52:e56-93)",
            })
        if not np.isnan(sbp[t]) and sbp[t] < 90:
            tiers[t] = "HIGH PRIORITY"
            fired[t].append({"rule": "hypotension", "tier": "HIGH PRIORITY",
                             "text": f"Systolic BP {sbp[t]:.0f} mmHg (< 90).", "basis": "hemodynamic safety rule"})
        risk_ok = probs is None or float(probs[t]) >= floor
        if (RANK[tiers[t]] < RANK["WATCH"] and F[t, IDX["n_concordant"]] >= 3
                and F[t, IDX["persist_max"]] >= 2 and risk_ok):
            tiers[t] = "WATCH"
            fired[t].append({"rule": "multi_signal_trajectory", "tier": "WATCH",
                             "text": (f"{int(F[t, IDX['n_concordant']])} signals ≥ {DEVIATION_Z} SD adverse, "
                                      f"sustained {int(F[t, IDX['persist_max']])} days"
                                      + (f", model risk {float(probs[t]):.1%}" if probs is not None else "") + "."),
                             "basis": "trajectory rule (personal baseline + model-risk floor)"})
    return tiers, fired


def apply_hysteresis(raw: list[str], acute: np.ndarray, *, hold_days: int = 2) -> list[str]:
    out: list[str] = []
    current = "NORMAL"
    below = 0
    for t, r in enumerate(raw):
        if acute[t]:
            out.append(ACUTE_CARE)
            current, below = "NORMAL", 0
            continue
        if RANK[r] >= RANK[current]:
            current, below = r, 0
        else:
            below += 1
            if below >= hold_days:
                current = TIERS[max(RANK[r], RANK[current] - 1)]
                below = 0
        out.append(current)
    return out


def classify_trajectory(F: np.ndarray, t: int) -> dict[str, Any]:
    """Name the current trajectory from the last few days of features."""
    zs = F[max(0, t - 3): t + 1, :N_SIG]
    slopes = F[t, N_SIG:2 * N_SIG]
    conc = F[max(0, t - 3): t + 1, IDX["n_concordant"]]
    n_now = int(conc[-1])
    jump = (zs[-1] - zs[-2]) if len(zs) >= 2 else np.zeros(N_SIG)
    adverse_now = [MODEL_SIGNALS[i] for i in range(N_SIG) if zs[-1, i] >= DEVIATION_Z]
    rising = [MODEL_SIGNALS[i] for i in range(N_SIG) if slopes[i] >= 0.5 and zs[-1, i] >= 1.0]
    if int(np.sum(jump >= 2.5)) >= 2:
        name = "sudden multi-signal change"
    elif n_now >= 3 and (len(rising) >= 2 or F[t, IDX["persist_max"]] >= 2):
        name = "multi-signal concordant deterioration"
    elif len(conc) >= 3 and conc[:-1].max() >= 3 and n_now < conc[:-1].max() and np.nanmean(slopes) < 0:
        name = "recovering toward baseline"
    elif n_now <= 1 and zs[-1].max() >= 2.0 and F[t, IDX["persist_max"]] <= 1:
        name = "isolated deviation"
    elif n_now >= 2:
        name = "emerging deviation"
    else:
        name = "stable at personal baseline"
    return {"pattern": name, "signals_adverse": adverse_now, "signals_rising": rising,
            "n_concordant": n_now}


def group_contributions(contrib: np.ndarray) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for i, name in enumerate(FEATURE_NAMES):
        g = FEATURE_GROUP[name]
        entry = groups.setdefault(g, {"group": g, "label": GROUP_LABEL[g], "logit": 0.0, "features": []})
        entry["logit"] += float(contrib[i])
        entry["features"].append({"feature": name, "logit": round(float(contrib[i]), 3)})
    out = sorted(groups.values(), key=lambda e: -abs(e["logit"]))
    for e in out:
        e["logit"] = round(e["logit"], 3)
        e["direction"] = "raises risk" if e["logit"] > 0 else "lowers risk"
        e["features"].sort(key=lambda f: -abs(f["logit"]))
    return out


def describe_signal(series: PatientSeries, baseline: Baseline, key: str, t: int, F: np.ndarray) -> dict[str, Any] | None:
    spec = SIGNALS[key]
    b = baseline.signals.get(key)
    if b is None or not b.n_days:
        return None
    v = series.values[key][t]
    day = t + 1
    if np.isnan(v) and t > 0:
        v, day = series.values[key][t - 1], t
    if np.isnan(v):
        return None
    disp = b.display()
    z = F[t, IDX[f"z_{key}"]]
    slope = F[t, IDX[f"slope3_{key}"]]
    direction = "above" if (v > disp["median"]) else "below"
    return {
        "signal": key, "label": spec.label, "value": round(float(v), spec.decimals), "unit": spec.unit_display,
        "day": day, "baseline_median": disp["median"], "baseline_low": disp["low"], "baseline_high": disp["high"],
        "z_adverse": round(float(z), 2), "slope3_per_day": round(float(slope), 2),
        "text": (f"{spec.label} {v:.{spec.decimals}f} {spec.unit_display} on Day {day}: "
                 f"{abs(z):.1f} SD {direction} personal baseline {disp['median']} "
                 f"(range {disp['low']}–{disp['high']})"
                 + (f", worsening {slope:+.1f} SD/day over 3 days" if slope >= 0.4 else "")),
        "observation_id": series.obs_ids[key][day - 1],
    }


def review_items(series: PatientSeries, t: int, F: np.ndarray, top_groups: list[str], neutro_est: dict[str, Any] | None) -> list[str]:
    """Clinical information a reviewer may want — phrased as considerations, never orders."""
    items: list[str] = []
    day = t + 1
    infection_like = any(g in top_groups for g in ("temperature", "resting_hr", "hrv_sdnn", "spo2", "neutrophil"))
    volume_like = any(g in top_groups for g in ("weight", "sbp", "symptom_score", "adherence"))
    anc_v, anc_d, _ = series.last_lab("anc", day, max_age=60)
    if infection_like:
        est = ""
        if neutro_est and neutro_est.get("source") == "fitted twin":
            est = (f"; twin-estimated ANC today {neutro_est['mean']:.2f} ×10³/µL "
                   f"(80% interval {neutro_est['p10']:.2f}–{neutro_est['p90']:.2f})")
        last = f"last measured {anc_v:.2f} ×10³/µL on Day {anc_d}" if anc_v is not None else "no ANC on file"
        items.append(f"CBC with differential (ANC) — {last}{est}.")
        items.append("Review temperature trend against the institutional febrile-neutropenia pathway "
                     "(≥ 38.3 °C single reading or ≥ 38.0 °C sustained).")
        first = series.first_dose_day or 0
        last_dose = max(series.dose_days) if series.dose_days else first
        gcsf_this_cycle = any(g >= last_dose for g in series.gcsf_days)
        items.append(f"Review G-CSF prophylaxis status for the current cycle "
                     f"({'given' if gcsf_this_cycle else 'none recorded'}).")
    if volume_like:
        cr_v, cr_d, _ = series.last_lab("creatinine", day, max_age=60)
        last_cr = f"last creatinine {cr_v:.2f} mg/dL on Day {cr_d}" if cr_v is not None else "no creatinine on file"
        items.append(f"Basic metabolic panel (creatinine, electrolytes) — {last_cr}; assess oral intake, "
                     f"emesis/diarrhea frequency and orthostatic symptoms.")
    adh = F[t, IDX["adherence_7d"]]
    if F[t, IDX["adherence_gap"]] > 0.2:
        items.append(f"Supportive-medication adherence {adh:.0%} over 7 days — explore barriers "
                     f"(nausea, cost, understanding) with the patient.")
    if "spo2" in top_groups:
        items.append("Respiratory assessment — SpO₂ below personal baseline.")
    if series.profile.diabetic and not np.isnan(series.values["glucose_cgm"][t]):
        items.append("Glycemic review — CGM daily mean relative to personal baseline "
                     "(steroid premedication and infection both raise glucose).")
    affected = {f.signal for f in series.flags if f.kind in ("stuck", "implausible", "conflict", "stale")
                and any(d >= day - 6 for d in f.days)}
    for sig in sorted(affected & (set(top_groups) | {"weight", "spo2", "resting_hr", "temperature"})):
        items.append(f"Verify {SIGNALS[sig].label.lower()} data before acting on it (data-quality flag active).")
    return items
