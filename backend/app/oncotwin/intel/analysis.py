"""Twin Intelligence orchestration — the stages shared by the agent graph and the API.

    quality      record consistency + data-quality summary          (Data Quality Agent)
    temporal     change points · risk dynamics · Twin Memory ·
                 trajectory conflicts                               (Temporal Intelligence Agent)
    intelligence cross-signal correlation · uncertainty decomposition ·
                 Twin Readiness · multi-horizon risk · WHY NOW ·
                 WHAT CHANGED · Show-your-work                      (Clinical Evidence Agent)
    context      treatment context + the ClinCase request the twin
                 evidence would support, previewed against ClinCase's
                 own policy corpus                                  (Clinical Context Agent)

Each stage writes into `TwinComputation.intel`; `compute()` runs them all for a
read-only API view. Same code, same numbers — whether an agent or a page asks.
"""
from __future__ import annotations

from typing import Any

from app.oncotwin.intel import changepoint, consistency, correlation, explain, graph, memory, trajectory, uncertainty
from app.oncotwin.intel.state import transitions
from app.oncotwin.ml.horizon import load_horizon_model
from app.oncotwin.service import TwinComputation, compute_twin, provenance
from app.oncotwin.signals import MODEL_SIGNALS, SIGNALS

ASSUMPTIONS = [
    "Personal baseline = robust median ± 2 × 1.4826·MAD over the pre-treatment window (per-signal spread floor).",
    "An adverse deviation is ≥ 1.5 SD from the personal baseline in the clinically adverse direction.",
    "Tier = max(probability tier, transparent rule tier); de-escalation needs 2 consecutive days (hysteresis).",
    "Risk refers to ONE outcome: OT-ACUTE-7 (unplanned acute care for an OP-35 condition within 7 days).",
    "Measurement-noise uncertainty assumes device error = ½ of the patient's baseline day-to-day spread.",
    "Latent loads and the neutrophil twin are model estimates, not measurements.",
    "All data are synthetic; metrics come from held-out synthetic patients, not clinical validation.",
]


def stage_quality(c: TwinComputation) -> dict[str, Any]:
    cs = consistency.consistency(c.record, c.series)
    s = c.series
    c.intel["consistency_record"] = cs
    c.intel["quality"] = {
        "completeness_7d": round(sum(s.quality[k].completeness_7d for k in MODEL_SIGNALS) / len(MODEL_SIGNALS), 3),
        "flags": [f.to_dict() for f in s.flags if f.kind != "gap" or f.severity != "info"],
        "consistency_status": cs["status"],
    }
    return c.intel["quality"]


def stage_temporal(c: TwinComputation, snapshots: list[dict[str, Any]], facts: list[dict[str, Any]]) -> dict[str, Any]:
    t = c.as_of_day
    cp = changepoint.detect(c.series, c.baseline)
    dyn = trajectory.dynamics(snapshots, t, c.model.thresholds)
    mem = memory.analyse(c.series, c.baseline, [h for h in snapshots if h["day"] <= t])
    conf = consistency.conflicts(c.series, facts[t - 1], snapshots[t - 1], cp, float(c.latent["r2"][t - 1]))
    c.intel.update(change_points=cp, trajectory_dynamics=dyn, memory=mem, conflicts=conf)
    return {"change_points": cp, "dynamics": dyn, "memory": mem, "conflicts": conf}


def stage_intelligence(c: TwinComputation, snapshots: list[dict[str, Any]], facts: list[dict[str, Any]],
                       states: list[dict[str, Any]], *, drift: dict[str, Any] | None = None) -> dict[str, Any]:
    t = c.as_of_day
    hist = [h for h in snapshots if h["day"] <= t]
    co = correlation.analyse(c.series, c.baseline, hist, c.prediction["contributors"], c.intel["change_points"])
    u = uncertainty.decompose(c.series, c.baseline, c.ctx, c.model, c.prediction, population_drift=drift)
    rd = uncertainty.readiness(facts[t - 1], c.series, c.prediction, c.model, u)
    hm = load_horizon_model()
    hz = (hm.horizons(c.F[t - 1], primary_7d=c.prediction["risk"]) if hm is not None else
          {"available": False, "reason": "horizon model not trained (python -m app.oncotwin.ml.horizon)"})
    w = explain.why_now(as_of_day=t, prediction=c.prediction, history=hist, correlation=co,
                        changepoints=c.intel["change_points"], trajectory=c.intel["trajectory_dynamics"],
                        state=states[t - 1], uncertainty=u, readiness=rd, horizons=hz)
    prov = provenance(c)
    lo = max(1, t - 2)
    swork = {
        "model": c.prediction["model"], "horizon_model": hz.get("model"),
        "input_sha256": prov["input_sha256"], "n_inputs": prov["n_inputs"], "feature_window_days": prov["feature_window_days"],
        "input_signals": [{"signal": k, "label": SIGNALS[k].label, "unit": SIGNALS[k].unit_display,
                           "readings": [{"day": d, "value": facts[d - 1]["signals"][k]["v"],
                                         "id": facts[d - 1]["signals"][k]["id"]} for d in range(lo, t + 1)]}
                          for k in MODEL_SIGNALS],
        "assumptions": ASSUMPTIONS,
        "uncertainty": {k: v["width_80"] for k, v in u["components"].items()},
        "timeline": {"from_day": max(1, t - 13), "to_day": t},
    }
    c.intel.update(correlation=co, uncertainty=u, readiness=rd, horizons=hz, why_now=w, show_your_work=swork)
    return c.intel


async def stage_context(c: TwinComputation, organization_id: str) -> dict[str, Any]:
    """Treatment context + the ClinCase request this evidence pattern would support (policy preview)."""
    from app.oncotwin.handoff import policy_preview, suggest_treatment

    st = c.state["cancer_treatment_state"]
    requested, rationale = suggest_treatment(c.record, {"prediction": {"contributors": c.prediction["contributors"]}})
    try:
        preview = await policy_preview(c.record.profile.payer_id, requested["name"], organization_id,
                                       f"{c.record.profile.patient_id}-d{c.as_of_day}")
    except Exception as e:  # noqa: BLE001 — ClinCase policy corpus unavailable → say so, never fabricate
        preview, rationale = [], rationale + f" (policy preview unavailable: {str(e)[:80]})"
    ctx = {
        "treatment": {k: st[k] for k in ("regimen", "cycle_number", "day_of_cycle", "last_dose_day",
                                         "next_planned_dose_day", "gcsf_this_cycle", "in_expected_nadir_window")},
        "clincase_request_if_accepted": requested, "rationale": rationale,
        "policy_preview": preview, "payer_id": c.record.profile.payer_id,
        "flow": ["twin evidence", "clinician review (HITL)", "FHIR bundle + RiskAssessment", "ClinCase case",
                 "7-agent prior-authorisation pipeline", "ClinCase HITL", "audit"],
        "note": "Nothing is submitted: a ClinCase case is created only after a clinician accepts or investigates the alert.",
    }
    c.intel["clinical_context"] = ctx
    return ctx


def compute(record, snapshots: list[dict[str, Any]], facts: list[dict[str, Any]], states: list[dict[str, Any]],
            day: int, model, *, drift: dict[str, Any] | None = None, alerts: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Every intelligence engine at one as-of day (read-only; no simulation, no LLM)."""
    c = compute_twin(record, day, history=[h for h in snapshots if h["day"] <= day], model=model)
    stage_quality(c)
    stage_temporal(c, snapshots, facts)
    stage_intelligence(c, snapshots, facts, states, drift=drift)
    g = graph.build(record, day, states[day - 1], c.prediction, c.intel["correlation"], c.intel["change_points"],
                    c.intel["memory"], alerts)
    return {
        "as_of_day": day,
        "prediction": {k: c.prediction[k] for k in ("outcome_id", "outcome", "horizon_days", "risk", "risk_p10", "risk_p90",
                                                    "interval", "tier", "previous_tier", "probability_tier", "rule_tier",
                                                    "rules_fired", "thresholds", "contributors", "confidence", "model")},
        "state": states[day - 1],
        "transitions_recent": transitions(states, from_day=max(2, day - 13), to_day=day),
        "what_changed": explain.what_changed(states, day),
        "change_points": c.intel["change_points"], "trajectory": c.intel["trajectory_dynamics"],
        "memory": c.intel["memory"], "correlation": c.intel["correlation"],
        "conflicts": c.intel["conflicts"], "consistency": c.intel["consistency_record"],
        "uncertainty": c.intel["uncertainty"], "readiness": c.intel["readiness"], "horizons": c.intel["horizons"],
        "why_now": c.intel["why_now"], "show_your_work": c.intel["show_your_work"], "graph": g,
        "evidence": c.evidence, "review": c.evidence["review"],
        "facts": {k: facts[day - 1][k] for k in ("signals", "quality", "confidence", "treatment", "labs")},
    }
