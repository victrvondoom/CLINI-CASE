"""OncoTwin 2.0 intelligence engines: state, change points, correlation, trajectory, memory,
consistency, uncertainty, explanation, graph, what-if, counterfactual, safety gates."""
from __future__ import annotations

import json
import re

import numpy as np
import pytest

from app.oncotwin.intel import changepoint, memory, trajectory
from app.oncotwin.intel.analysis import compute
from app.oncotwin.intel.counterfactual import synthetic_truth
from app.oncotwin.intel.state import DIMENSION_ORDER, build_states, transitions
from app.oncotwin.ml.model import load_model
from app.oncotwin.safety import gates
from app.oncotwin.service import compute_history_bundle, compute_twin
from app.oncotwin.simulator.archetypes import DEMO_SCRIPTS


@pytest.fixture(scope="module")
def ot001_bundle(demo_sims):
    rec = demo_sims["ot-001"].record
    b = compute_history_bundle(rec, 40)
    return rec, b, build_states(rec, b.snapshots, b.day_facts)


@pytest.fixture(scope="module")
def ot001_intel(ot001_bundle):
    rec, b, states = ot001_bundle
    return compute(rec, b.snapshots, b.day_facts, states, 26, load_model())


def test_incremental_history_equals_full_recompute(demo_sims):
    for pid in ("ot-001", "ot-002"):
        rec = demo_sims[pid].record
        full = compute_history_bundle(rec, 40)
        inc = compute_history_bundle(rec, 40, prior=compute_history_bundle(rec, 30))
        assert inc.extended_from == 30
        assert json.dumps(full.snapshots, sort_keys=True, default=str) == json.dumps(inc.snapshots, sort_keys=True, default=str)
        assert json.dumps(full.day_facts, sort_keys=True, default=str) == json.dumps(inc.day_facts, sort_keys=True, default=str)


def test_living_state_has_19_dimensions_with_provenance(ot001_bundle):
    _, _, states = ot001_bundle
    s = states[25]
    assert tuple(s["dimensions"]) == DIMENSION_ORDER and len(DIMENSION_ORDER) == 19
    for d in s["dimensions"].values():
        assert {"status", "severity", "basis", "fields", "confidence", "data_quality", "sources"} <= set(d)
    assert s["dimensions"]["risk"]["basis"] == "model-derived"
    assert re.fullmatch(r"[0-9a-f]{64}", s["sha256"])


def test_transitions_carry_required_fields_and_history_is_reproducible(ot001_bundle):
    rec, b, states = ot001_bundle
    tr = transitions(states, from_day=20, to_day=30)
    assert tr, "the infection episode must produce state transitions"
    for t in tr:
        assert {"day", "at", "dimension", "previous", "new", "reason", "sources", "confidence", "data_quality"} <= set(t)
        assert t["previous"] != t["new"] and t["reason"]
    again = build_states(rec, b.snapshots, b.day_facts)
    assert [s["sha256"] for s in again] == [s["sha256"] for s in states]      # never overwritten; recomputable


def test_bocpd_localises_a_known_step():
    rng = np.random.default_rng(0)
    z = rng.normal(0, 0.8, (40, 9))
    z[20:, :3] += 2.5
    R = changepoint.run_bocpd(z, np.full(9, 0.8))
    assert np.allclose(R.sum(axis=1), 1.0)
    assert 22 - int(np.argmax(R[21])) in (20, 21, 22)               # regime start found around Day 21


def test_changepoint_finds_the_infection_regime(ot001_intel):
    cps = [p for p in ot001_intel["change_points"]["change_points"] if p["significance"] == "significant"]
    assert any(21 <= p["day"] <= 25 and p["contributors"] for p in cps)
    assert "not proof" in ot001_intel["change_points"]["language_note"]


def test_cross_signal_engine_is_one_trajectory_and_avoids_causal_language(ot001_intel):
    co = ot001_intel["correlation"]
    assert co["headline"] == "Multi-signal trajectory change detected" and co["n_deviating"] >= 3
    for r in co["signals"]:
        assert {"direction", "z_adverse_3d", "baseline_median", "time_window", "model_contribution_logit"} <= set(r)
    text = json.dumps(co).lower()
    assert "caused" not in text and "due to" not in text


def test_trajectory_dynamics_names_the_state(ot001_bundle):
    _, b, _ = ot001_bundle
    m = load_model()
    d26 = trajectory.dynamics(b.snapshots, 26, m.thresholds)
    assert d26["dynamics"] == "persistent deterioration"
    assert d26["narrative"][-1]["offset"] == "Today" and d26["narrative"][-1]["label"] == "High concern"
    assert trajectory.dynamics(b.snapshots, 36, m.thresholds)["dynamics"] != "persistent deterioration"


def test_twin_memory_compares_cycles_as_statistics_not_equivalence(demo_sims):
    rec = demo_sims["ot-004"].record
    b = compute_history_bundle(rec, 50)
    c = compute_twin(rec, 50, history=b.snapshots)
    mem = memory.analyse(c.series, c.baseline, b.snapshots)
    assert len(mem["cycles"]) == 2 and mem["similarity"]
    assert any("not clinical equivalence" in n for n in mem["notes"])


def test_uncertainty_decomposition_and_readiness(ot001_intel):
    u = ot001_intel["uncertainty"]
    assert set(u["components"]) == {"model", "measurement", "missing_data"}
    assert "ood" in u["distribution_shift"]
    rd = ot001_intel["readiness"]
    assert 0 <= rd["score"] <= 1 and "not a health score" in rd["note"].lower()
    assert set(rd["components"]) == {"data_completeness", "temporal_coverage", "signal_reliability",
                                     "personalization_quality", "prediction_confidence", "model_validity"}


def test_why_now_numbers_are_computed_not_hardcoded(ot001_intel):
    w = ot001_intel["why_now"]
    rows = {r["signal"]: r for r in ot001_intel["correlation"]["signals"]}
    assert w["compared_with_baseline"]
    for v in w["compared_with_baseline"]:
        r = rows[v["signal"]]
        if r["pct_vs_baseline"] is not None:
            assert f"{abs(r['pct_vs_baseline']):.0f}%" in v["change"]
    assert w["model"]["horizon_days"] == 7
    assert w["confidence"]["p10"] <= w["confidence"]["risk"] <= w["confidence"]["p90"]


def test_state_graph_separates_facts_from_model_associations(ot001_intel):
    g = ot001_intel["graph"]
    assert {"clinical", "model", "data"} <= {e["kind"] for e in g["edges"]}
    for e in g["edges"]:
        if e["kind"] == "model":
            assert "log-odds" in e["label"] or "associated" in e["label"]
    assert any(n["group"] == "risk" and n["basis"] == "model" for n in g["nodes"])


def test_custom_what_if_runs_through_the_same_simulator(demo_sims):
    rec = demo_sims["ot-002"].record
    b = compute_history_bundle(rec, 24)
    c = compute_twin(rec, 24, history=b.snapshots, custom_scenario={"adherence": 0.95, "iv_hydration_day_offsets": [1, 2]})
    sc = c.simulation["scenarios"]
    assert set(sc) == {"current", "early_intervention", "improved_recovery", "reduced_adherence", "regimen_change", "custom"}
    assert sc["custom"]["event_probability_7d"] <= sc["current"]["event_probability_7d"]
    assert len(sc["custom"]["delta_vs_current"]["risk_median_by_day"]) == len(sc["custom"]["days"])
    assert sc["custom"]["assumptions"]


def test_counterfactual_ground_truth_validates_the_intervention():
    truth = synthetic_truth(DEMO_SCRIPTS["ot-001"], 25)
    assert truth["factual_first_event_after_anchor"] is None
    assert truth["counterfactual_first_event_after_anchor"]["condition"] == "febrile_neutropenia"


def test_safety_gates_pass_the_deterministic_statement_and_block_fabrication(ot001_bundle, ot001_intel):
    from app.oncotwin.intel.narrative import deterministic, gate_context

    rec, _, _ = ot001_bundle
    ctx = gate_context(rec, ot001_intel, True)
    det = deterministic(ot001_intel)
    text = " ".join([det["summary"], *[p["text"] for p in det["key_points"]], *det["caveats"]])
    ok = gates.check({"text": text, "as_of_day": 26, "risk": ot001_intel["prediction"]["risk"],
                      "evidence_ids": [i for p in det["key_points"] for i in p["evidence_ids"]]}, ctx)
    assert ok["passed"], ok["gates"]
    bad = gates.check({"text": "The patient has sepsis caused by neutropenia; start antibiotics. Temperature 39.9 °C.",
                       "as_of_day": 26, "evidence_ids": ["obs-FAKE"], "source": "llm"}, ctx)
    failed = {g["gate"] for g in bad["gates"] if not g["passed"]}
    assert not bad["passed"] and {"evidence", "safety"} <= failed and bad["action"] == "fallback"


def test_neutrophil_predictive_interval_contains_lab_noise(demo_sims):
    from app.oncotwin.engine.neutrophil import NeutrophilTwin
    from app.oncotwin.engine.series import build_series

    s = build_series(demo_sims["ot-001"].record, 30)
    fit = NeutrophilTwin(s).fit(27)
    est, pred = fit.estimate(28), fit.predictive(28)
    assert pred["p_lo"] < est["p10"] <= est["p90"] < pred["p_hi"]
