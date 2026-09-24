"""End-to-end twin behaviour: state vector, warnings, explanations, simulation, agents, FHIR."""
from __future__ import annotations

import pytest

from app.oncotwin.engine.warning import RANK
from app.oncotwin.fhir.mapping import build_bundle, fhir_to_observation, observation_to_fhir, wearable_sample_to_observation
from app.oncotwin.service import compute_history, compute_twin, key_moments, twin_card


@pytest.fixture(scope="module")
def ot001(demo_sims):
    rec = demo_sims["ot-001"].record
    return rec, compute_history(rec, 40)


def _at(hist, day):
    return [h for h in hist if h["day"] <= day]


def test_state_vector_has_every_section(ot001):
    rec, hist = ot001
    c = compute_twin(rec, 26, history=_at(hist, 26))
    for section in ("baseline_state", "cancer_treatment_state", "physiological_state", "symptom_recovery_state",
                    "adherence_state", "data_quality"):
        assert section in c.state
    assert c.prediction["horizon_days"] == 7
    assert 0.0 <= c.prediction["risk_p10"] <= c.prediction["risk"] <= c.prediction["risk_p90"] <= 1.0 + 1e-9
    assert set(c.prediction["confidence"]["components"]) >= {"input_completeness_7d", "input_freshness",
                                                            "baseline_adequacy", "model_agreement"}


def test_recovery_patient_warns_before_intervention_and_recovers(ot001):
    _, hist = ot001
    tiers = {h["day"]: h["tier"] for h in hist}
    first_ew = min(d for d, t in tiers.items() if RANK.get(t, 0) >= RANK["EARLY WARNING"])
    assert first_ew < 28, "early warning must precede the Day-28 intervention"
    assert tiers[35] == "NORMAL"


def test_gradual_patient_warns_days_before_admission(demo_sims):
    hist = compute_history(demo_sims["ot-002"].record, 28)
    onset = demo_sims["ot-002"].truth.event_onsets[0]["day"]
    warned = [h["day"] for h in hist if RANK.get(h["tier"], 0) >= RANK["EARLY WARNING"] and h["day"] < onset]
    assert warned and onset - min(warned) >= 2


def test_stable_patient_never_reaches_early_warning(demo_sims):
    hist = compute_history(demo_sims["ot-004"].record, 56)
    assert max(RANK.get(h["tier"], 0) for h in hist) < RANK["EARLY WARNING"]


def test_explanation_answers_the_six_questions(ot001):
    rec, hist = ot001
    c = compute_twin(rec, 26, history=_at(hist, 26))
    ev = c.evidence
    assert ev["what_changed"] and all("SD" in w["text"] for w in ev["what_changed"])        # what changed
    assert ev["why"].startswith("Pattern:")                                                # why
    assert "Personal baseline from Day 1" in ev["compared_with"]                           # vs what baseline
    assert ev["period"]["start_day"] is not None                                            # over what period
    assert ev["contributors"] and "logit" in ev["contributors"][0]                         # which signals
    assert ev["review"]                                                                     # what to review
    assert ev["evidence"] and all(e["observation_id"] for e in ev["evidence"])              # supporting obs
    assert c.prediction["logit_check"]["probability_from_logit"] == pytest.approx(c.prediction["risk"], abs=1e-4)


def test_simulation_scenarios_are_ordered_sensibly(ot001, demo_sims):
    rec, hist = ot001
    c = compute_twin(rec, 26, history=_at(hist, 26), simulate=True)
    sc = c.simulation["scenarios"]
    assert set(sc) == {"current", "early_intervention", "improved_recovery", "reduced_adherence", "regimen_change"}
    assert sc["early_intervention"]["event_probability_7d"] <= sc["current"]["event_probability_7d"]
    assert "not a guaranteed outcome" in c.simulation["disclaimer"]
    rec2 = demo_sims["ot-002"].record
    c2 = compute_twin(rec2, 21, history=compute_history(rec2, 21), simulate=["current", "reduced_adherence"])
    s2 = c2.simulation["scenarios"]
    assert s2["reduced_adherence"]["event_probability_7d"] >= s2["current"]["event_probability_7d"]


def test_simulation_is_reproducible(ot001):
    rec, hist = ot001
    a = compute_twin(rec, 26, history=_at(hist, 26), simulate=["current"]).simulation["scenarios"]["current"]
    b = compute_twin(rec, 26, history=_at(hist, 26), simulate=["current"]).simulation["scenarios"]["current"]
    assert a["risk"] == b["risk"] and a["event_probability_cumulative"] == b["event_probability_cumulative"]


def test_key_moments_are_computed_not_scripted(ot001):
    rec, hist = ot001
    kinds = [m["kind"] for m in key_moments(rec, hist)]
    for k in ("baseline", "treatment", "tier_change", "intervention", "recovery"):
        assert k in kinds


def test_twin_card_has_every_field(ot001):
    rec, hist = ot001
    card = twin_card(compute_twin(rec, 26, history=_at(hist, 26), simulate=["current"]))
    for k in ("patient", "current_state", "baseline", "trajectory", "risk", "treatment", "symptoms", "wearables",
              "predicted_changes", "recommended_review"):
        assert card.get(k) is not None, k


def test_twin_graph_runs_all_agents_through_the_clincase_framework(ot001):
    from app.oncotwin.agents.graph import run_twin_graph
    rec, hist = ot001
    comp, meta = run_twin_graph(rec, 26, "org_test", history=_at(hist, 26))
    agents = [s["agent"] for s in meta["agent_trace"]]
    # OncoTwin 2.0 graph: validation first, explanation last; the original five agents keep their relative order.
    assert agents[0] == "data_quality_agent" and agents[-1] == "explanation_agent"
    original = [a for a in agents if a in ("twin_state_agent", "trajectory_intelligence_agent",
                                           "deterioration_prediction_agent", "simulation_agent", "clinical_evidence_agent")]
    assert original == ["twin_state_agent", "trajectory_intelligence_agent", "deterioration_prediction_agent",
                        "simulation_agent", "clinical_evidence_agent"]
    assert "temporal_intelligence_agent" in agents and "clinical_context_agent" in agents   # tier ≥ WATCH on Day 26
    assert all(s["status"] == "ok" for s in meta["agent_trace"])
    assert comp.evidence["headline"]
    assert comp.intel["explanation"]["safety_gates"]["passed"]


def test_clincase_seven_agent_architecture_is_unchanged():
    from app.agents.manifest import AGENT_MANIFEST
    from app.graph.build import build_full_graph
    assert sorted(a["name"] for a in AGENT_MANIFEST) == sorted([
        "clinical_extractor", "policy_retriever", "necessity_reasoner", "decision_composer",
        "denial_forecaster", "appeals_drafter", "patient_communicator"])
    nodes = set(build_full_graph().get_graph().nodes)
    assert {"clinical_extractor", "policy_retriever", "necessity_reasoner", "decision_composer",
            "denial_forecaster", "appeals_drafter", "patient_communicator", "review_gate"} <= nodes
    assert not any(n.startswith("twin_") for n in nodes)


# ---------------------------------------------------------------------------- FHIR


def test_every_bundle_resource_validates_as_fhir(demo_sims):
    from fhir.resources.R4B import construct_fhir_element
    bundle = build_bundle(demo_sims["ot-002"].record, 30)
    types = set()
    for entry in bundle["entry"]:
        res = entry["resource"]
        construct_fhir_element(res["resourceType"], res)
        types.add(res["resourceType"])
    assert {"Patient", "Observation", "Condition", "MedicationRequest", "MedicationAdministration",
            "DiagnosticReport", "Procedure", "CarePlan", "Encounter"} <= types
    construct_fhir_element("Bundle", bundle)


def test_wearable_and_fhir_ingestion_mapping(demo_sims):
    hk = wearable_sample_to_observation({"type": "HKQuantityTypeIdentifierOxygenSaturation", "value": 0.97,
                                         "start": "2026-08-10T06:00:00Z"}, "p1")
    assert hk.signal == "spo2" and hk.value == 97.0 and hk.day == 15
    hc = wearable_sample_to_observation({"recordType": "StepsRecord", "count": 5321,
                                         "endTime": "2026-08-10T23:00:00Z"}, "p1")
    assert hc.signal == "steps" and hc.value == 5321
    obs = demo_sims["ot-001"].record.observations[0]
    back = fhir_to_observation(observation_to_fhir(obs, "p1"), "p1")
    assert (back.signal, back.value, back.day) == (obs.signal, obs.value, obs.day)
    with pytest.raises(ValueError):
        wearable_sample_to_observation({"type": "HKQuantityTypeIdentifierUnknown", "value": 1}, "p1")
