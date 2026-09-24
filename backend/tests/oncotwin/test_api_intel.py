"""OncoTwin 2.0 API: authenticated routes, RBAC on clinical and developer actions, the closed loop
through HTTP, and the end-to-end synthetic journey (the one demo command)."""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.auth import get_current_user
from app.main import app

BASE = "/api/v1/oncotwin"


def _user(role: str, org: str) -> dict:
    return {"id": f"user_{role}", "email": f"{role}@clincase.health", "full_name": role, "organization_id": org, "role": role}


@pytest.fixture()
def client_as():
    org = f"org_intel_{uuid.uuid4().hex[:6]}"
    current = {"user": _user("reviewer", org)}
    app.dependency_overrides[get_current_user] = lambda: current["user"]
    client = TestClient(app)

    def switch(role: str) -> TestClient:
        current["user"] = _user(role, org)
        return client

    yield switch
    app.dependency_overrides.pop(get_current_user, None)


def test_command_center_and_patient_intelligence(client_as):
    c = client_as("coordinator")
    cc = c.get(f"{BASE}/command-center").json()
    assert len(cc["patients"]) == 8 and set(cc["counts"]) == set(cc["categories"])
    it = c.get(f"{BASE}/patients/ot-001/intelligence", params={"as_of_day": 20}).json()
    assert it["as_of_day"] == 20 and it["is_replay"] and len(it["state"]["dimensions"]) == 19
    for k in ("why_now", "what_changed", "change_points", "correlation", "trajectory", "memory", "uncertainty",
              "readiness", "horizons", "graph", "show_your_work", "consistency", "conflicts"):
        assert it[k] is not None, k
    assert c.get(f"{BASE}/patients/nope/intelligence").status_code == 404


def test_whatif_custom_scenario_is_labelled_simulation(client_as):
    c = client_as("coordinator")
    r = c.post(f"{BASE}/patients/ot-002/whatif", json={"scenarios": ["current"],
                                                       "custom": {"adherence": 0.95, "iv_hydration_day_offsets": [1]}})
    body = r.json()
    assert r.status_code == 200 and "Simulation" in body["label"]
    assert {"current", "custom"} <= set(body["simulation"]["scenarios"])
    assert c.post(f"{BASE}/patients/ot-002/whatif", json={"custom": {"adherence": 3}}).status_code == 422


def test_closed_loop_over_http_with_rbac(client_as):
    c = client_as("reviewer")
    adv = c.post(f"{BASE}/patients/ot-005/advance", json={"days": 3}).json()
    assert adv["alerts"], "the flagship patient escalates within 3 days"
    alert_id = adv["alerts"][0]
    assert client_as("coordinator").post(f"{BASE}/patients/ot-005/interventions",
                                         json={"kind": "urgent_eval_abx", "alert_id": alert_id}).status_code == 403
    c = client_as("reviewer")
    r = c.post(f"{BASE}/patients/ot-005/interventions",
               json={"kind": "urgent_eval_abx", "alert_id": alert_id, "note": "seen today"})
    assert r.status_code == 200 and r.json()["intervention"]["past_data_unchanged"]
    assert c.post(f"{BASE}/patients/ot-005/interventions", json={"kind": "teleport"}).status_code == 422
    after = c.post(f"{BASE}/patients/ot-005/advance", json={"days": 5}).json()
    assert all(e["tier"] != "IN ACUTE CARE" for e in after["evaluations"])
    cf = c.get(f"{BASE}/patients/ot-005/counterfactual").json()
    assert cf["synthetic_truth"]["counterfactual_first_event_after_anchor"] is not None
    assert "not a clinical prediction" in cf["disclaimer"]
    ev = c.get(f"{BASE}/events", params={"patient_id": "ot-005", "category": "hitl"}).json()
    assert "InterventionRecorded" in {e["type"] for e in ev["events"]}
    kn = c.get(f"{BASE}/patients/ot-005/knowledge", params={"day": 23}).json()
    assert kn["what_the_twin_knew"]["state"]["day"] == 23
    audit = c.get(f"{BASE}/audit", params={"patient_id": "ot-005"}).json()
    assert audit["verification"]["valid"] and any(e["kind"] == "intervention" for e in audit["entries"])


def test_developer_tools_are_admin_only(client_as):
    assert client_as("reviewer").post(f"{BASE}/stress-test").status_code == 403
    assert client_as("reviewer").post(f"{BASE}/research/experiments", json={}).status_code == 403
    assert client_as("admin").get(f"{BASE}/research/options").json()["horizons"] == [1, 3, 7]


def test_mlops_observability_and_health(client_as):
    c = client_as("coordinator")
    c.get(f"{BASE}/patients/ot-004/intelligence")
    assert c.get(f"{BASE}/models/registry").status_code == 200
    assert c.get(f"{BASE}/feature-store/registry").json()["n_model_features"] == 30
    obs = c.get(f"{BASE}/observability").json()
    assert "metrics" in obs and obs["ledger"]["valid"]
    prom = c.get(f"{BASE}/metrics")
    assert prom.status_code == 200 and "oncotwin_" in prom.text
    assert c.get(f"{BASE}/health").json()["checks"]["deterioration_model"]["ok"]
    assert c.get(f"{BASE}/architecture").json()["components"]


def test_end_to_end_synthetic_journey_one_command():
    from app.oncotwin.demo import run_journey
    r = run_journey(verbose=False)
    assert r["passed"], r["checks"]
    assert len(r["steps"]) >= 12 and r["synthetic"]
