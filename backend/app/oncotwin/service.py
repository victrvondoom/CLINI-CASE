"""OncoTwin orchestration: the stages every twin evaluation runs through.

    state → trajectory → prediction → (simulation) → evidence

Each stage is a pure function over a shared `TwinComputation`. The OncoTwin
agents (app/oncotwin/agents) wrap one stage each and are chained by the twin
LangGraph; read-only API views call `compute_twin` directly. Either way the
same code produces the same numbers.

History / replay snapshots are computed EXACTLY as-of each day (only data
dated ≤ that day), so Time-Travel shows what the twin knew at the time.
"""
from __future__ import annotations

import hashlib
import json
import zlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from app.oncotwin import ONCOTWIN_VERSION
from app.oncotwin.engine.baseline import (
    DEVIATION_Z,
    Baseline,
    adverse_z,
    compute_baseline,
    cusum,
    jumps,
    persistence,
    rolling_slope,
)
from app.oncotwin.engine.features import (
    FEATURE_NAMES,
    IDX,
    feature_tensor,
    series_context,
    signal_matrix,
)
from app.oncotwin.engine.neutrophil import NeutrophilFit, NeutrophilTwin
from app.oncotwin.engine.series import PatientSeries, build_series
from app.oncotwin.engine.simulate import simulate_scenarios
from app.oncotwin.engine.state import LATENT_LABELS, confidence, estimate_latent, neutrophil_projection
from app.oncotwin.engine.warning import (
    ACUTE_CARE,
    RANK,
    TIERS,
    apply_hysteresis,
    classify_trajectory,
    describe_signal,
    group_contributions,
    probability_tier,
    review_items,
    rule_tiers,
)
from app.oncotwin.ml.model import DeteriorationModel, load_model
from app.oncotwin.outcome import HORIZON_DAYS, OUTCOME_ID
from app.oncotwin.records import PatientRecord, day_to_iso
from app.oncotwin.signals import DAILY_SIGNALS, MODEL_SIGNALS, SIGNALS
from app.oncotwin.simulator import physiology as P

_NCCN_PATH = Path(__file__).resolve().parents[1] / "data" / "oncology" / "nccn_corpus.json"


@dataclass
class TwinComputation:
    record: PatientRecord
    as_of_day: int
    model: DeteriorationModel
    history: list[dict[str, Any]] | None = None
    series: PatientSeries | None = None
    baseline: Baseline | None = None
    neutro: NeutrophilTwin | None = None
    fit: NeutrophilFit | None = None
    ctx: dict[str, Any] | None = None
    F: np.ndarray | None = None
    latent: dict[str, Any] | None = None
    state: dict[str, Any] = field(default_factory=dict)
    trajectory: dict[str, Any] = field(default_factory=dict)
    prediction: dict[str, Any] = field(default_factory=dict)
    simulation: dict[str, Any] | None = None
    evidence: dict[str, Any] = field(default_factory=dict)
    # Outputs of the OncoTwin 2.0 agents (data validation, temporal intelligence,
    # clinical context, explanation) — populated by the twin graph.
    intel: dict[str, Any] = field(default_factory=dict)


# =============================================================================
# Exact per-day history (replay / risk timeline)
# =============================================================================


@dataclass
class HistoryBundle:
    """Per-day as-of history: compact snapshots + (optionally) the per-day facts
    the Living Twin State engine is built from. Both lists are indexed day-1."""
    until_day: int
    snapshots: list[dict[str, Any]]
    day_facts: list[dict[str, Any]]
    extended_from: int | None = None          # prior until_day when built incrementally


def compute_history(record: PatientRecord, until_day: int, model: DeteriorationModel | None = None) -> list[dict[str, Any]]:
    """One compact snapshot per day 1..until_day, each computed as-of that day."""
    return compute_history_bundle(record, until_day, model, with_facts=False).snapshots


def _can_extend(prior: HistoryBundle, full: PatientSeries, until_day: int, with_facts: bool) -> bool:
    """A prior history on the SAME data can be extended instead of recomputed when
    nothing it depends on can still change: the first dose is known (so the
    neutrophil twin's pre-treatment ANC and the baseline window are fixed)."""
    first = full.first_dose_day
    return (prior.until_day < until_day and first is not None and prior.until_day >= max(first, 10)
            and len(prior.snapshots) == prior.until_day
            and (not with_facts or len(prior.day_facts) == prior.until_day))


def compute_history_bundle(record: PatientRecord, until_day: int, model: DeteriorationModel | None = None, *,
                           prior: HistoryBundle | None = None, with_facts: bool = True) -> HistoryBundle:
    """Exact per-day history. With `prior` (computed earlier on the same record)
    only the NEW days are recomputed — the event-driven incremental update.

    Every per-day computation reads only data dated ≤ that day, so earlier days
    never change when later data arrive. The two whole-series quantities
    (displayed latent loads and the acute-care mask) are refreshed for all days,
    and hysteresis is re-applied over the full tier sequence; a test pins
    incremental == full recomputation.
    """
    from app.oncotwin.intel.state import day_facts

    model = model or load_model()
    full = build_series(record, until_day)
    anc_arrays = NeutrophilTwin(full).daily_features()       # causal: day d uses labs ≤ d
    latent = estimate_latent(full, compute_baseline(full))
    acute = full.acute_care_mask()
    snaps: list[dict[str, Any]] = []
    facts: list[dict[str, Any]] = []
    start = 1
    extended_from = None
    if prior is not None and _can_extend(prior, full, until_day, with_facts):
        snaps = [dict(s) for s in prior.snapshots]
        facts = list(prior.day_facts)
        start = prior.until_day + 1
        extended_from = prior.until_day
    for d in range(start, until_day + 1):
        s = build_series(record, d)
        b = compute_baseline(s)
        ctx = series_context(s, anc_arrays=anc_arrays)
        F = feature_tensor(signal_matrix(s), b, **ctx)[0]
        x = F[d - 1]
        p, lo, hi = (float(v[0]) for v in model.predict_interval(x))
        rtiers, fired = rule_tiers(s, F, np.asarray(ctx["nadir"]), model.predict(F), model.thresholds["watch"])
        ptier = probability_tier(p, model.thresholds)
        raw = ptier if RANK[ptier] >= RANK[rtiers[d - 1]] else rtiers[d - 1]
        contrib = group_contributions(model.contributions(x))
        snaps.append({
            "day": d, "date": day_to_iso(d, 23, 59), "risk": round(p, 4), "risk_p10": round(lo, 4),
            "risk_p90": round(hi, 4), "probability_tier": ptier, "rule_tier": rtiers[d - 1], "raw_tier": raw,
            "rules": fired[d - 1], "pattern": classify_trajectory(F, d - 1)["pattern"],
            "n_concordant": int(x[IDX["n_concordant"]]), "anomaly": round(float(x[IDX["anomaly"]]), 2),
            "top_contributors": [{"label": c["label"], "group": c["group"], "logit": c["logit"]} for c in contrib[:3]],
            "on_treatment": bool(x[IDX["on_treatment"]] > 0),
        })
        if with_facts:
            facts.append(day_facts(s, b, F, ctx, p, lo, hi))
    for snap in snaps:
        d = snap["day"]
        snap["latent"] = {name: round(float(latent["series"][d - 1, i]), 3) for i, name in enumerate(P.LATENT)}
        snap["in_acute_care"] = bool(acute[d - 1])
    tiers = apply_hysteresis([s["raw_tier"] for s in snaps], acute)
    for snap, tier in zip(snaps, tiers, strict=True):
        snap["tier"] = tier
    return HistoryBundle(until_day=until_day, snapshots=snaps, day_facts=facts, extended_from=extended_from)


def key_moments(record: PatientRecord, history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Replay bookmarks derived from COMPUTED results + recorded events — never scripted."""
    if not history:
        return []
    until = history[-1]["day"]
    moments: list[dict[str, Any]] = [{"day": 1, "kind": "baseline", "text": "Monitoring starts — personal baseline accrues"}]
    seen: set[str] = set()
    for e in record.events_until(until):
        if e.day < 1:
            continue
        if e.kind == "chemo_dose":
            tag = f"dose{e.detail.get('cycle')}"
            if tag not in seen:
                seen.add(tag)
                moments.append({"day": e.day, "kind": "treatment", "text": f"Cycle {e.detail.get('cycle')} administered"})
        elif e.kind == "encounter" and e.detail.get("qualifying"):
            moments.append({"day": e.day, "kind": "acute_care", "text": e.display})
        elif (e.kind == "encounter" or e.kind in ("antibiotic", "hydration")
              or (e.kind == "gcsf_dose" and e.detail.get("indication") == "treatment")):
            tag = f"iv{e.day}"
            if tag not in seen:
                seen.add(tag)
                moments.append({"day": e.day, "kind": "intervention", "text": e.display})
    prev = "NORMAL"
    first_dev = multi = False
    for h in history:
        if h["on_treatment"] and h["tier"] in TIERS:
            if not first_dev and RANK[h["tier"]] >= RANK["WATCH"]:
                first_dev = True
                moments.append({"day": h["day"], "kind": "first_deviation",
                                "text": f"Subtle deviation — twin moves to {h['tier']} (risk {h['risk']:.1%})"})
            if not multi and h["n_concordant"] >= 3 and RANK[h["tier"]] >= RANK["WATCH"]:
                multi = True
                moments.append({"day": h["day"], "kind": "multi_signal",
                                "text": f"{h['n_concordant']} signals diverge from personal baseline together"})
        if h["tier"] in TIERS and RANK[h["tier"]] >= RANK["EARLY WARNING"] and RANK[h["tier"]] > RANK.get(prev, 0):
            moments.append({"day": h["day"], "kind": "tier_change",
                            "text": f"Twin escalates {prev} → {h['tier']} (risk {h['risk']:.0%})"})
        prev = h["tier"] if h["tier"] in TIERS else "NORMAL"
    peak_day = None
    for h in history:
        if RANK.get(h["tier"], 0) >= RANK["EARLY WARNING"]:
            peak_day = h["day"]
        elif peak_day is not None and h["tier"] == "NORMAL":
            moments.append({"day": h["day"], "kind": "recovery",
                            "text": "Back to NORMAL — deviations resolved toward personal baseline"})
            break
    moments.sort(key=lambda m: (m["day"], m["kind"]))
    return moments


# =============================================================================
# Stages
# =============================================================================


def stage_validate(c: TwinComputation) -> PatientSeries:
    """Build the as-of view once (data-quality agent); later stages reuse it."""
    if c.series is None or c.series.as_of_day != c.as_of_day:
        c.series = build_series(c.record, c.as_of_day)
    return c.series


def stage_state(c: TwinComputation) -> dict[str, Any]:
    s = stage_validate(c)
    b = c.baseline = compute_baseline(s)
    c.neutro = NeutrophilTwin(s)
    c.fit = c.neutro.fit(c.as_of_day)
    c.ctx = series_context(s, anc_arrays=c.neutro.daily_features())
    c.latent = estimate_latent(s, b)
    t = c.as_of_day
    idx = t - 1
    reg = s.regimen
    dsd = s.days_since_dose()
    last_dose = max(s.dose_days) if s.dose_days else None
    next_planned = next((d for d in s.planned_dose_days if d > t and not any(abs(d - g) <= 3 for g in s.dose_days)), None)
    est = c.fit.estimate(t)
    anc_v, anc_d, anc_id = s.last_lab("anc", t, max_age=60)
    projection = neutrophil_projection(s, c.fit, horizon=HORIZON_DAYS, seed=_seed(s.profile.patient_id))
    lat_now = c.latent["series"][idx]
    adh, sched = c.ctx["adherence_7d"], c.ctx["adherence_sched"]
    missed7 = sum(sch - tk for d, (tk, sch) in s.adherence.items() if t - 6 <= d <= t)
    sym = s.values["symptom_score"]
    sym_now = _last_valid(sym, idx)
    sym_prev = _last_valid(sym, idx - 3) if idx >= 3 else None
    adm = s.in_acute_care_now()
    c.state = {
        "as_of_day": t,
        "as_of_time": day_to_iso(t, 23, 59),
        "clock": "twin clock — synthetic feed replayed day by day",
        "baseline_state": b.to_dict(),
        "cancer_treatment_state": {
            "diagnosis": {"text": s.profile.cancer, "icd10": s.profile.icd10, "stage": s.profile.stage},
            "biomarkers": s.profile.biomarkers,
            "regimen": {"code": reg.code, "name": reg.name, "cycle_days": reg.cycle_days,
                        "myelosuppression_tier": reg.myelo_tier, "tier_basis": "simulation parameter"},
            "cycle_number": len(s.dose_days),
            "day_of_cycle": None if np.isnan(dsd[idx]) else int(dsd[idx]) + 1,
            "last_dose_day": last_dose,
            "next_planned_dose_day": next_planned,
            "gcsf_this_cycle": bool(last_dose is not None and any(g >= last_dose for g in s.gcsf_days)),
            "in_expected_nadir_window": bool(c.ctx["nadir"][idx] >= 0.25 * max(reg.myelotox, 1e-6)),
            "neutrophil": {
                "twin_estimate_today": {k: (round(v, 2) if isinstance(v, float) else v) for k, v in est.items()},
                "last_lab": {"value": anc_v, "day": anc_d, "observation_id": anc_id} if anc_v is not None else None,
                "fitted_sensitivity": c.fit.sensitivity_summary() if c.fit.labs_used else None,
                "baseline_anc": {"value": round(c.fit.circ0, 2), "source": c.fit.circ0_source},
                "projection": projection,
            },
            "performance_status_ecog": s.profile.ecog,
        },
        "physiological_state": {
            "latent_loads": {
                name: {"label": LATENT_LABELS[name], "value": round(float(lat_now[i]), 3),
                       "event_threshold": P.EVENT_THRESHOLDS.get(name)}
                for i, name in enumerate(P.LATENT)
            },
            "observation_model_fit_r2": None if np.isnan(c.latent["r2"][idx]) else round(float(c.latent["r2"][idx]), 3),
            "method": "weighted NNLS inversion of the twin observation model, EWMA-smoothed",
        },
        "symptom_recovery_state": {
            "symptom_score": None if sym_now is None else round(sym_now, 1),
            "symptom_baseline": b.signals["symptom_score"].display()["median"],
            "symptom_change_3d": None if (sym_now is None or sym_prev is None) else round(sym_now - sym_prev, 1),
            "recovery_index": _recovery_index(c.latent["series"], idx),
        },
        "adherence_state": {
            "supportive_medication_7d": round(float(adh[idx]), 3),
            "scheduled_doses_7d": int(sched[idx]),
            "missed_doses_7d": int(missed7),
            "applicable": bool(sched[idx] > 0),
        },
        "care_setting": "inpatient (qualifying acute care)" if adm else "outpatient",
        "acute_care_episode": adm,
        "data_quality": {
            "flags": [f.to_dict() for f in s.flags if f.kind != "gap" or f.severity != "info"],
            "signals": {k: s.quality[k].to_dict() for k in DAILY_SIGNALS if k in s.quality},
        },
    }
    return c.state


def stage_trajectory(c: TwinComputation) -> dict[str, Any]:
    s, b = c.series, c.baseline
    assert s is not None and b is not None and c.ctx is not None
    c.F = feature_tensor(signal_matrix(s), b, **c.ctx)[0]
    idx = c.as_of_day - 1
    z = adverse_z(signal_matrix(s), b)
    sl3 = rolling_slope(z, 3)[0]
    sl7 = rolling_slope(z, 7)[0]
    pers = persistence(z)[0]
    cus = cusum(z)[0]
    jmp = jumps(z)[0]
    signals = {}
    for i, k in enumerate(MODEL_SIGNALS):
        zi = z[0, :, i]
        signals[k] = {
            "label": SIGNALS[k].label,
            "z_adverse": None if np.isnan(zi[idx]) else round(float(zi[idx]), 2),
            "slope3_per_day": None if np.isnan(sl3[idx, i]) else round(float(sl3[idx, i]), 2),
            "slope7_per_day": None if np.isnan(sl7[idx, i]) else round(float(sl7[idx, i]), 2),
            "persistence_days": int(pers[idx, i]),
            "cusum": round(float(cus[idx, i]), 2),
            "cusum_alarm": bool(cus[idx, i] >= 4.0),
            "sudden_jump": bool(not np.isnan(jmp[idx, i]) and jmp[idx, i] >= 2.5),
            "status": _signal_status(zi[idx], pers[idx, i]),
            "z_history": [None if np.isnan(v) else round(float(v), 2) for v in zi[max(0, idx - 13): idx + 1]],
        }
    c.trajectory = {
        **classify_trajectory(c.F, idx),
        "analysed_as": "one multivariate trajectory, not independent per-signal alarms",
        "anomaly_score": round(float(c.F[idx, IDX["anomaly"]]), 2),
        "signals": signals,
        "sudden_changes": [k for k, v in signals.items() if v["sudden_jump"]],
        "drift_alarms": [k for k, v in signals.items() if v["cusum_alarm"]],
        "deviation_threshold_sd": DEVIATION_Z,
        "window_days": 14,
    }
    return c.trajectory


def stage_prediction(c: TwinComputation) -> dict[str, Any]:
    assert c.F is not None and c.series is not None and c.baseline is not None
    t = c.as_of_day
    idx = t - 1
    x = c.F[idx]
    p, lo, hi = (float(v[0]) for v in c.model.predict_interval(x))
    contrib = c.model.contributions(x)
    logit = c.model.lr.intercept + float(contrib.sum())
    rtiers, fired = rule_tiers(c.series, c.F, np.asarray(c.ctx["nadir"]), c.model.predict(c.F),
                               c.model.thresholds["watch"])
    ptier = probability_tier(p, c.model.thresholds)
    raw_today = ptier if RANK[ptier] >= RANK[rtiers[idx]] else rtiers[idx]
    prior_raw = [h["raw_tier"] for h in (c.history or []) if h["day"] < t]
    acute = c.series.acute_care_mask()
    tiers = apply_hysteresis(prior_raw + [raw_today], acute[: len(prior_raw) + 1])
    tier = tiers[-1]
    prev_tier = tiers[-2] if len(tiers) >= 2 else "NORMAL"
    c.prediction = {
        "outcome_id": OUTCOME_ID,
        "outcome": "Unplanned ED visit / admission for a chemotherapy-related (OP-35) condition",
        "horizon_days": HORIZON_DAYS,
        "risk": round(p, 4), "risk_p10": round(lo, 4), "risk_p90": round(hi, 4),
        "interval": "80% bootstrap interval (refits on resampled training patients)",
        "probability_tier": ptier, "rule_tier": rtiers[idx], "raw_tier": raw_today,
        "tier": tier, "previous_tier": prev_tier,
        "escalated": tier in TIERS and RANK[tier] > RANK.get(prev_tier, -1),
        "rules_fired": fired[idx],
        "thresholds": c.model.thresholds,
        "contributors": group_contributions(contrib)[:8],
        "logit_check": {"intercept": round(c.model.lr.intercept, 4), "sum_contributions": round(float(contrib.sum()), 4),
                        "logit": round(logit, 4), "probability_from_logit": round(1 / (1 + np.exp(-logit)), 4)},
        "features": {name: round(float(x[i]), 4) for i, name in enumerate(FEATURE_NAMES)},
        "confidence": confidence(c.series, c.baseline, p, lo, hi),
        "model": c.model.version_info(),
    }
    return c.prediction


def stage_simulation(c: TwinComputation, scenarios: list[str] | None = None,
                     custom: dict[str, Any] | None = None) -> dict[str, Any]:
    assert c.series is not None and c.baseline is not None and c.fit is not None and c.latent is not None
    # Start from today's DIRECT (unsmoothed) latent estimate: the EWMA used for
    # display lags a rising load, which would bias every scenario optimistic.
    c.simulation = simulate_scenarios(
        c.series, c.baseline, c.fit, c.latent["raw"][c.as_of_day - 1], c.ctx, c.model, scenarios=scenarios,
        custom=custom,
    )
    return c.simulation


def stage_evidence(c: TwinComputation) -> dict[str, Any]:
    s, b, F, pred = c.series, c.baseline, c.F, c.prediction
    assert s is not None and b is not None and F is not None
    t = c.as_of_day
    idx = t - 1
    changed = []
    for k in MODEL_SIGNALS:
        if F[idx, IDX[f"z_{k}"]] >= DEVIATION_Z:
            d = describe_signal(s, b, k, idx, F)
            if d:
                changed.append(d)
    changed.sort(key=lambda d: -d["z_adverse"])
    top_groups = [g["group"] for g in pred["contributors"] if g["logit"] > 0][:5]
    traj = c.trajectory
    ct = c.state.get("cancer_treatment_state", {})
    neut = ct.get("neutrophil", {})
    why_parts = [f"Pattern: {traj.get('pattern')}"]
    if traj.get("signals_adverse"):
        why_parts.append("signals beyond 1.5 SD of personal baseline in the adverse direction: " +
                         ", ".join(SIGNALS[k].label.lower() for k in traj["signals_adverse"]))
    pos = [g for g in pred["contributors"] if g["logit"] > 0.05][:3]
    if pos:
        why_parts.append("largest contributions to the risk: " +
                         "; ".join(f"{g['label']} (+{g['logit']:.2f} log-odds)" for g in pos))
    if ct.get("in_expected_nadir_window"):
        est = neut.get("twin_estimate_today", {})
        why_parts.append(f"patient is in the expected neutrophil nadir window (day {ct.get('day_of_cycle')} of cycle "
                         f"{ct.get('cycle_number')}; twin-estimated ANC {est.get('mean')} ×10³/µL)")
    for r in pred["rules_fired"]:
        why_parts.append(f"rule — {r['text']}")
    evidence = []
    for d in changed[:6]:
        for back in range(3):
            day = d["day"] - back
            if day >= 1:
                oid = s.obs_ids[d["signal"]][day - 1]
                v = s.values[d["signal"]][day - 1]
                if oid and not np.isnan(v):
                    evidence.append({"observation_id": oid, "signal": d["signal"], "day": day, "value": float(v),
                                     "unit": SIGNALS[d["signal"]].unit_display})
    for key in ("anc", "creatinine"):
        v, day, oid = s.last_lab(key, t, max_age=14)
        if v is not None:
            evidence.append({"observation_id": oid, "signal": key, "day": day, "value": v, "unit": SIGNALS[key].unit_display})
    c.evidence = {
        "tier": pred["tier"],
        "headline": (f"{pred['tier']} — {pred['risk']:.0%} probability of unplanned acute care within {HORIZON_DAYS} days "
                     f"(80% interval {pred['risk_p10']:.0%}–{pred['risk_p90']:.0%}); confidence {pred['confidence']['label']}"),
        "what_changed": changed[:6],
        "why": "; ".join(why_parts) + ".",
        "compared_with": (f"Personal baseline from Day {b.window[0]}–{b.window[1]} ({b.kind}; "
                          f"adequacy {b.adequacy:.0%}), median ± 2 robust SD per signal"),
        "period": _episode_period(c.history or [], t, pred["risk"]),
        "contributors": pred["contributors"][:6],
        "review": review_items(s, idx, F, top_groups, neut.get("twin_estimate_today")),
        "evidence": evidence,
        "rules_fired": pred["rules_fired"],
        "references": _references(s, pred),
        "decision_support_notice": ("Clinical decision support only. OncoTwin does not diagnose or treat; "
                                    "a clinician must review, and accept, dismiss or investigate every alert."),
    }
    return c.evidence


# =============================================================================
# Public entry points
# =============================================================================


def compute_twin(record: PatientRecord, as_of_day: int, *, history: list[dict[str, Any]] | None = None,
                 simulate: bool | list[str] = False, model: DeteriorationModel | None = None,
                 custom_scenario: dict[str, Any] | None = None) -> TwinComputation:
    model = model or load_model()
    c = TwinComputation(record=record, as_of_day=as_of_day, model=model,
                        history=history if history is not None else compute_history(record, as_of_day, model))
    stage_state(c)
    stage_trajectory(c)
    stage_prediction(c)
    if simulate or custom_scenario is not None:
        stage_simulation(c, simulate if isinstance(simulate, list) else None, custom=custom_scenario)
    stage_evidence(c)
    return c


def twin_card(c: TwinComputation) -> dict[str, Any]:
    st, pred, traj, ev = c.state, c.prediction, c.trajectory, c.evidence
    prof = c.record.profile
    ct = st["cancer_treatment_state"]
    sim_cur = (c.simulation or {}).get("scenarios", {}).get("current")
    quality = st["data_quality"]["signals"]
    fresh = sum(1 for k in MODEL_SIGNALS if quality.get(k, {}).get("fresh"))
    lat = st["physiological_state"]["latent_loads"]
    dominant = max(lat.values(), key=lambda v: v["value"])
    return {
        "patient": {"id": prof.patient_id, "label": prof.label, "age": prof.age, "sex": prof.sex,
                    "cancer": prof.cancer, "stage": prof.stage, "biomarkers": prof.biomarkers,
                    "payer_id": prof.payer_id, "synthetic": prof.synthetic, "archetype": prof.archetype},
        "current_state": {"tier": pred["tier"], "care_setting": st["care_setting"],
                          "dominant_latent_load": dominant["label"], "dominant_latent_value": dominant["value"],
                          "as_of_day": c.as_of_day, "as_of_time": st["as_of_time"]},
        "baseline": {"window": st["baseline_state"]["window"], "adequacy": st["baseline_state"]["adequacy"],
                     "kind": st["baseline_state"]["kind"]},
        "trajectory": {"pattern": traj["pattern"], "signals_adverse": traj["signals_adverse"],
                       "signals_rising": traj["signals_rising"]},
        "risk": {"probability": pred["risk"], "p10": pred["risk_p10"], "p90": pred["risk_p90"],
                 "horizon_days": pred["horizon_days"], "outcome_id": pred["outcome_id"],
                 "confidence": pred["confidence"]["label"], "confidence_score": pred["confidence"]["score"]},
        "treatment": {"regimen": ct["regimen"]["code"], "regimen_name": ct["regimen"]["name"],
                      "cycle": ct["cycle_number"], "day_of_cycle": ct["day_of_cycle"],
                      "next_dose_day": ct["next_planned_dose_day"], "gcsf_this_cycle": ct["gcsf_this_cycle"],
                      "nadir_window": ct["in_expected_nadir_window"],
                      "anc_estimate": ct["neutrophil"]["twin_estimate_today"]},
        "symptoms": st["symptom_recovery_state"],
        "wearables": {"model_signals_fresh": fresh, "model_signals_total": len(MODEL_SIGNALS),
                      "completeness_7d": pred["confidence"]["components"]["input_completeness_7d"],
                      "active_quality_flags": len([f for f in st["data_quality"]["flags"] if f["kind"] != "gap"])},
        "predicted_changes": None if not sim_cur else {
            "risk_day7_median": sim_cur["risk_day7_median"],
            "event_probability_7d": sim_cur["event_probability_7d"],
            "anc_nadir_projection": ct["neutrophil"]["projection"].get("nadir_median"),
            "source": "current-trajectory simulation",
        },
        "recommended_review": ev["review"][:4],
    }


def signal_panels(c: TwinComputation) -> dict[str, Any]:
    """Per-signal history (as-of) + personal baseline band + current-trajectory forecast."""
    s, b = c.series, c.baseline
    assert s is not None and b is not None
    sim_cur = (c.simulation or {}).get("scenarios", {}).get("current")
    out: dict[str, Any] = {}
    for k in DAILY_SIGNALS:
        if k == "glucose_cgm" and not s.profile.diabetic:
            continue
        spec = SIGNALS[k]
        base = b.signals.get(k)
        out[k] = {
            "label": spec.label, "unit": spec.unit_display, "code_system": spec.code_system, "code": spec.code,
            "device": spec.device, "adverse_direction": spec.adverse, "category": spec.category,
            "days": list(range(1, s.n + 1)),
            "values": [None if np.isnan(x) else round(float(x), spec.decimals) for x in s.values[k]],
            "baseline": base.display() if base and base.n_days else None,
            "quality": s.quality[k].to_dict() if k in s.quality else None,
            "forecast": ({"days": sim_cur["days"], **sim_cur["signals"][k]}
                         if sim_cur and k in sim_cur["signals"] else None),
        }
    twin_anc = []
    if c.neutro is not None:
        for d in range(1, s.n + 1):
            e = c.neutro.fit(d).estimate(d)
            if e.get("source") == "fitted twin":
                twin_anc.append({"day": d, "mean": round(e["mean"], 2), "p10": round(e["p10"], 2), "p90": round(e["p90"], 2)})
    out["anc"] = {"label": SIGNALS["anc"].label, "unit": SIGNALS["anc"].unit_display,
                  "labs": [{"day": d, "value": v, "observation_id": oid} for d, v, oid in s.labs.get("anc", [])],
                  "twin_estimate": twin_anc,
                  "projection": c.state["cancer_treatment_state"]["neutrophil"]["projection"]}
    return out


def provenance(c: TwinComputation) -> dict[str, Any]:
    """Exactly which inputs this evaluation used, with a reproducible SHA-256."""
    s = c.series
    assert s is not None
    t = c.as_of_day
    lo = max(1, t - 6)
    items: list[dict[str, Any]] = []
    for k in MODEL_SIGNALS:
        for d in range(lo, t + 1):
            oid = s.obs_ids[k][d - 1]
            if oid:
                items.append({"id": oid, "signal": k, "day": d, "value": float(s.values[k][d - 1])})
    for d, v, oid in s.labs.get("anc", []):
        items.append({"id": oid, "signal": "anc", "day": d, "value": v})
    for e in s.events:
        if e.kind in ("chemo_dose", "gcsf_dose", "supportive_dose", "encounter") and e.day >= t - 21:
            items.append({"id": e.id, "kind": e.kind, "day": e.day, "status": e.detail.get("status")})
    digest = hashlib.sha256(json.dumps(items, sort_keys=True).encode()).hexdigest()
    return {"input_sha256": digest, "n_inputs": len(items), "feature_window_days": [lo, t],
            "inputs": items, "oncotwin_version": ONCOTWIN_VERSION, "model": c.model.version_info()}


# =============================================================================
# Helpers
# =============================================================================


def _seed(pid: str) -> int:
    return zlib.crc32(pid.encode())


def _last_valid(arr: np.ndarray, idx: int) -> float | None:
    for j in range(idx, max(-1, idx - 3), -1):
        if j >= 0 and not np.isnan(arr[j]):
            return float(arr[j])
    return None


def _recovery_index(latent_series: np.ndarray, idx: int) -> float | None:
    """Fraction of the recent peak latent load that has resolved (None if no recent peak)."""
    window = latent_series[max(0, idx - 10): idx + 1].sum(axis=1)
    peak = float(window.max())
    if peak < 0.3:
        return None
    return round(float(np.clip(1.0 - window[-1] / peak, 0.0, 1.0)), 3)


def _signal_status(z: float, pers: float) -> str:
    if np.isnan(z):
        return "no recent data"
    if z >= 3.0:
        return "marked adverse deviation"
    if z >= DEVIATION_Z:
        return "adverse deviation" + (f" ({int(pers)} d)" if pers >= 2 else "")
    if z <= -DEVIATION_Z:
        return "better than baseline"
    return "within personal range"


def _episode_period(history: list[dict[str, Any]], t: int, risk_now: float) -> dict[str, Any]:
    # An episode is the current contiguous run at WATCH or above — expected
    # on-treatment fatigue alone (which the WATCH floor filters) does not start one.
    start = None
    for h in reversed([h for h in history if h["day"] <= t]):
        if RANK.get(h["tier"], 0) >= RANK["WATCH"]:
            start = h
        else:
            break
    if start is None:
        return {"start_day": None, "days": 0, "text": "No active deviation episode."}
    days = t - start["day"] + 1
    return {"start_day": start["day"], "days": days, "risk_at_start": start["risk"], "risk_now": round(risk_now, 4),
            "text": (f"Deviation episode began Day {start['day']} ({days} day{'s' if days != 1 else ''} ago); "
                     f"risk {start['risk']:.0%} → {risk_now:.0%}.")}


_NCCN_CACHE: list[dict[str, Any]] | None = None


def _nccn() -> list[dict[str, Any]]:
    """Reuse ClinCase's curated NCCN-style corpus (app/data/oncology/nccn_corpus.json)."""
    global _NCCN_CACHE
    if _NCCN_CACHE is None:
        try:
            _NCCN_CACHE = json.loads(_NCCN_PATH.read_text(encoding="utf-8")).get("guidelines", [])
        except (OSError, ValueError):
            _NCCN_CACHE = []
    return _NCCN_CACHE


def _references(s: PatientSeries, pred: dict[str, Any]) -> list[dict[str, str]]:
    refs = [{"id": "CMS-OP-35", "text": "CMS OP-35: Admissions and ED visits for patients receiving outpatient "
                                         "chemotherapy (outcome definition basis).", "source": "CMS Hospital OQR program"}]
    if any(r["rule"] == "possible_febrile_neutropenia" for r in pred["rules_fired"]) or \
            any(g["group"] in ("temperature", "neutrophil") for g in pred["contributors"][:3]):
        refs.append({"id": "IDSA-FN-2010", "text": "Neutropenic fever: single oral temperature ≥ 38.3 °C or ≥ 38.0 °C "
                     "sustained over 1 h, with ANC < 500/µL or expected to fall below 500/µL within 48 h.",
                     "source": "Freifeld AG et al., Clin Infect Dis 2011;52:e56–93"})
    drugs = {d.name for d in s.regimen.drugs}
    cancer = s.profile.cancer.lower()
    markers = " ".join(f"{k} {v}" for k, v in s.profile.biomarkers.items()).lower()
    for g in _nccn():
        text = (g.get("regimen", "") + " " + g.get("biomarker", "")).lower()
        tumor = g.get("tumor_type", "").lower()
        marker_key = g.get("biomarker", "").split()[0].lower() if g.get("biomarker") else ""
        tumor_ok = tumor != "any" and tumor in cancer
        agnostic_ok = tumor == "any" and marker_key and marker_key in markers
        if any(drug in text for drug in drugs) and (tumor_ok or agnostic_ok):
            refs.append({"id": g["id"], "text": f"{g['guideline']} — {g['section_heading']}: {g['excerpt'][:220]}…",
                         "source": "ClinCase curated NCCN-style corpus (demo; licensed feed required in production)"})
    return refs
