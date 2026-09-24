"""OncoTwin 2.0 platform: event-driven incremental updates, ingestion, prediction log with
delayed ground truth, drift, stress test, feature store, multi-horizon model, model registry."""
from __future__ import annotations

import numpy as np
import pytest

from app.oncotwin import runtime
from app.oncotwin.store import OrgTwinStore


@pytest.fixture()
def store():
    return OrgTwinStore("org_platform_test")


def test_advance_is_event_driven_and_incremental(store):
    st = store.patient("ot-005")
    runtime.bundle_for(st)
    res = runtime.advance(store, "ot-005", 2, actor="test")
    assert [e["as_of_day"] for e in res["evaluations"]] == [21, 22]
    assert st.bundle_cache[1].extended_from == 21            # the second day only extended the history
    stats = store.bus.stats()["by_type"]
    assert stats["WearableObservationReceived"] > 0 and stats["TwinEvaluated"] == 2
    assert not store.dirty                                      # every data batch was consumed by one update
    ev = [e for e in store.ledger.entries if e["kind"] == "evaluation"][-1]["payload"]
    assert ev["twin_state_sha256"] and ev["trigger"].startswith("twin clock advanced to Day 22")


def test_same_day_wearable_ingestion_triggers_an_immediate_update(store):
    st = store.patient("ot-004")
    res = runtime.ingest(store, "ot-004", {"wearable_samples": [
        {"type": "HKQuantityTypeIdentifierRestingHeartRate", "value": 71, "start": "2026-09-10T07:00:00Z"}]}, actor="t")
    assert res["accepted"] and res["accepted"][0]["day"] <= st.live_day
    assert res["twin_update"] is not None and res["extra_entries"]
    assert store.bus.stats()["by_type"].get("WearableObservationReceived") == 1


def test_prediction_log_resolves_ground_truth_when_the_window_is_observable(store):
    from app.oncotwin.mlops.predictions import live_metrics
    runtime.advance(store, "ot-002", 3, actor="test")           # Day 26 → 29; qualifying admission on Day 28
    m = live_metrics(store)
    rows = [r for r in store.predictions if r["patient_id"] == "ot-002"]
    assert rows and all(r["feature_version"] and r["dataset_version"] and r["artifact_sha256"] for r in rows)
    assert any(r["label"] == 1 and r["label_evidence"]["day"] == 28 for r in rows)
    assert m["n_resolved"] >= 1


def test_drift_monitor_separates_case_mix_from_a_real_device_shift():
    from app.oncotwin import stress
    from app.oncotwin.mlops.drift import evaluate, load_reference
    if load_reference() is None:
        pytest.skip("reference profile not built")
    clean = evaluate(*stress._population_rows(False))
    shifted = evaluate(*stress._population_rows(True))
    assert clean["status"] != "drift"
    assert shifted["status"] == "drift" and "z_resting_hr" in shifted["drifted_features"]


def test_stress_test_fails_safe_on_every_scenario():
    from app.oncotwin.stress import run_all
    res = run_all()
    failed = [(r["id"], r.get("observed", r.get("error"))) for r in res["results"] if not r["passed"]]
    assert not failed, failed


def test_feature_store_lineage_versioning_and_model_consistency(demo_sims):
    from app.oncotwin.features.store import materialize, registry
    from app.oncotwin.service import compute_history, compute_twin

    reg = registry()
    assert reg["n_model_features"] == 30 and reg["n_features"] > 30 and reg["registry_version"]
    rec = demo_sims["ot-001"].record
    comp = compute_twin(rec, 26, history=compute_history(rec, 26))
    m1, m2 = materialize(comp), materialize(comp)
    assert m1["content_sha256"] == m2["content_sha256"]                          # reproducible
    assert m1["model_input_consistency"]["equal_to_model_input_row"]
    z = next(r for r in m1["rows"] if r["feature"] == "z_temperature")
    assert z["lineage"]["observation_ids"]
    assert all(i.startswith("ot-001-temperature-d") for i in z["lineage"]["observation_ids"])
    names = {r["feature"] for r in m1["rows"]}
    assert {"sleep_debt_7d", "weight_velocity_7d", "recovery_velocity", "multi_signal_deterioration_index"} <= names


def test_horizon_model_is_monotone_and_declines_unsupported_horizons(demo_sims):
    from app.oncotwin.ml.horizon import load_horizon_model
    from app.oncotwin.service import compute_history, compute_twin
    hm = load_horizon_model()
    if hm is None:
        pytest.skip("horizon model not trained")
    rec = demo_sims["ot-003"].record
    comp = compute_twin(rec, 26, history=compute_history(rec, 26))
    out = hm.horizons(comp.F[25], primary_7d=comp.prediction["risk"])
    cum = out["curve"]["cumulative"]
    assert all(b >= a for a, b in zip(cum, cum[1:]))
    six = next(h for h in out["horizons"] if h["horizon"] == "6 h")
    assert six["supported"] is False and six["risk"] is None and "daily" in six["reason"]
    assert hm.integrity_verified


def test_every_registered_model_has_a_purpose_and_a_metric():
    from app.oncotwin.ml.registry import registry
    reg = registry()
    for m in reg["models"]:
        assert m["purpose"] and m["metric_definition"], m["id"]
    assert reg["not_added_by_design"]


def test_command_center_triages_every_patient(store):
    cc = runtime.command_center(store)
    assert len(cc["patients"]) == 8 and sum(cc["counts"].values()) == 8
    cats = {r["patient"]["label"]: r["category"] for r in cc["patients"]}
    assert cats["OT-008"] == "Data Quality Issue" and cats["OT-002"] == "High Priority"
    assert all(np.isfinite(r["risk"]) for r in cc["patients"])


def test_what_the_twin_knew_is_reproduced_exactly(store):
    runtime.advance(store, "ot-001", 1, actor="test")
    ev = [e for e in store.ledger.entries if e["kind"] == "evaluation"][0]
    k = runtime.knowledge(store, "ot-001", entry_id=ev["id"])
    assert k["reproduction"]["reproduced"]
    assert all(v for v in k["reproduction"]["checks"].values() if v is not None)
