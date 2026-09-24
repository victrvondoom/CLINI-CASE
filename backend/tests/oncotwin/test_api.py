"""OncoTwin API: demo flow, HITL enforcement, ClinCase handoff, tamper-evident audit.

Runs DB-less (the ClinCase fail-soft path): case creation still returns a
case_id and the ledger stays in-process.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.auth import get_current_user
from app.main import app

BASE = "/api/v1/oncotwin"


def _user(role: str, org: str) -> dict:
    return {"id": f"user_{role}", "email": f"{role}@aerofyta.health", "full_name": role,
            "organization_id": org, "role": role}


@pytest.fixture()
def client_as():
    org = f"org_test_{uuid.uuid4().hex[:6]}"
    current = {"user": _user("reviewer", org)}
    app.dependency_overrides[get_current_user] = lambda: current["user"]
    client = TestClient(app)

    def switch(role: str) -> TestClient:
        current["user"] = _user(role, org)
        return client

    yield switch
    app.dependency_overrides.pop(get_current_user, None)


def test_demo_flow_alert_hitl_handoff_audit(client_as):
    c = client_as("reviewer")
    pts = c.get(f"{BASE}/patients").json()["patients"]
    # The original four demo twins are unchanged; OncoTwin 2.0 adds four archetypes (closed loop, delayed
    # deterioration, relapse, noisy sensors / missing data).
    assert {p["patient"]["label"] for p in pts} == {"OT-001", "OT-002", "OT-003", "OT-004",
                                                   "OT-005", "OT-006", "OT-007", "OT-008"}
    assert all(p["patient"]["synthetic"] for p in pts)

    adv = c.post(f"{BASE}/patients/ot-001/advance", json={"days": 5}).json()
    assert adv["live_day"] == 27 and len(adv["alerts"]) == 1
    alert_id = adv["alerts"][0]

    why = c.get(f"{BASE}/alerts/{alert_id}/why").json()
    assert why["alert"]["tier"] in ("EARLY WARNING", "HIGH PRIORITY") and why["alert"]["as_of_day"] < 28
    assert why["alert"]["tier"] in why["answer"] and why["chain_verification"]["valid"]
    assert why["alert"]["provenance"]["input_sha256"] and why["alert"]["prediction"]["model"]["artifact_sha256"]

    # Hand-off is refused until a clinician has reviewed the alert.
    assert c.post(f"{BASE}/alerts/{alert_id}/handoff", json={}).status_code == 409

    # Coordinators cannot make clinical decisions on alerts.
    assert client_as("coordinator").post(f"{BASE}/alerts/{alert_id}/action",
                                         json={"action": "accept"}).status_code == 403
    c = client_as("reviewer")
    act = c.post(f"{BASE}/alerts/{alert_id}/action", json={"action": "accept", "note": "reviewed"}).json()
    assert act["alert"]["status"] == "accepted"

    h = c.post(f"{BASE}/alerts/{alert_id}/handoff", json={}).json()["handoff"]
    assert h["case_id"].startswith("case_")
    assert h["requested_treatment"]["name"] == "pegfilgrastim"
    assert h["policy_preview"], "ClinCase keyword_filter should match the pegfilgrastim demo policy"
    assert "DRAFT" in h["physician_note_draft"]

    audit = c.get(f"{BASE}/audit").json()
    assert audit["verification"]["valid"]
    assert {"evaluation", "alert", "alert_action", "handoff"} <= {e["kind"] for e in audit["entries"]}

    # The bundle handed to ClinCase (incl. the twin's RiskAssessment) is valid FHIR.
    from fhir.resources.R4B import construct_fhir_element

    from app.oncotwin.handoff import build_clincase_bundle
    from app.oncotwin.store import get_store
    store = get_store(audit["organization_id"])
    bundle = build_clincase_bundle(store.patient("ot-001").record(), store.alerts[alert_id])
    for entry in bundle["entry"]:
        construct_fhir_element(entry["resource"]["resourceType"], entry["resource"])
    assert any(e["resource"]["resourceType"] == "RiskAssessment" for e in bundle["entry"])


def test_audit_ledger_detects_tampering(client_as):
    from app.oncotwin.store import get_store
    c = client_as("reviewer")
    c.post(f"{BASE}/patients/ot-003/advance", json={"days": 1})
    ledger = get_store(c.get(f"{BASE}/audit").json()["organization_id"]).ledger
    assert ledger.verify()["valid"]
    ledger.entries[0]["payload"]["risk"] = 0.0001
    assert not ledger.verify()["valid"]


def test_replay_timeline_fhir_simulate_inject_ingest(client_as):
    c = client_as("reviewer")
    rp = c.get(f"{BASE}/patients/ot-002/replay").json()
    assert len(rp["snapshots"]) == rp["live_day"]
    tl = c.get(f"{BASE}/patients/ot-002/timeline").json()
    assert {"labs", "treatment", "wearables", "twin"} <= set(tl["lanes"])
    fb = c.get(f"{BASE}/patients/ot-002/fhir").json()
    assert fb["resourceType"] == "Bundle" and fb["meta"]["tag"][0]["code"] == "SYNTHETIC"
    sim = c.post(f"{BASE}/patients/ot-002/simulate", json={"scenarios": ["current", "early_intervention"]}).json()
    assert set(sim["simulation"]["scenarios"]) == {"current", "early_intervention"}
    inj = c.post(f"{BASE}/patients/ot-004/inject", json={"kind": "infection"}).json()
    assert inj["injection"]["past_data_unchanged"] is True
    ing = c.post(f"{BASE}/patients/ot-004/observations", json={"wearable_samples": [
        {"recordType": "RestingHeartRateRecord", "beatsPerMinute": 70, "time": "2026-09-19T07:00:00Z"}]}).json()
    assert len(ing["accepted"]) == 1 and ing["accepted"][0]["signal"] == "resting_hr"
    d = c.get(f"{BASE}/patients/ot-001", params={"as_of_day": 10}).json()
    assert d["is_replay"] and d["as_of_day"] == 10


def test_demo_reset_keeps_the_audit_ledger(client_as):
    c = client_as("reviewer")
    c.post(f"{BASE}/patients/ot-001/advance", json={"days": 1})
    before = c.get(f"{BASE}/audit").json()["total"]
    assert client_as("coordinator").post(f"{BASE}/demo/reset").status_code == 403
    c = client_as("admin")
    assert c.post(f"{BASE}/demo/reset").json()["reset"] is True
    after = c.get(f"{BASE}/audit").json()
    assert after["total"] == before + 1 and after["verification"]["valid"]
    assert c.get(f"{BASE}/patients").json()["patients"][0]["live_day"] == 22
