"""CardioTwin API: authorization, response schema, validation errors, degraded modes, end-to-end flow."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.auth import get_current_user
from app.cardiotwin.model import ModelArtifactError
from app.main import app

from .conftest import row_patient

BASE = "/api/v1/cardiotwin"


def _user(role: str = "coordinator") -> dict:
    return {
        "id": f"user_{role}",
        "email": f"{role}@clincase.health",
        "full_name": role,
        "organization_id": "org_cardio_test",
        "role": role,
    }


@pytest.fixture()
def client():
    app.dependency_overrides[get_current_user] = lambda: _user()
    yield TestClient(app)
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture()
def anon():
    app.dependency_overrides.pop(get_current_user, None)
    return TestClient(app)


ROUTES = [
    ("get", "/overview"),
    ("get", "/features"),
    ("get", "/scenarios"),
    ("get", "/model"),
    ("get", "/evaluation"),
    ("post", "/predict"),
    ("post", "/counterfactual"),
    ("post", "/sensitivity"),
]


@pytest.mark.parametrize(("method", "path"), ROUTES)
def test_every_route_requires_authentication(anon, method, path):
    r = getattr(anon, method)(
        BASE + path, **({"json": {"features": {}}} if method == "post" else {})
    )
    assert r.status_code in (401, 403)


def test_overview_features_scenarios(client):
    o = client.get(f"{BASE}/overview").json()
    assert o["name"] == "CardioTwin" and "not a substitute" in o["safety_notice"]
    assert set(o["headline_metrics"]) == {"CAD", "LAD", "LCX", "RCA"}
    assert "lesion location, length or morphology" in o["terminology"]["not_claimed"]
    f = client.get(f"{BASE}/features").json()
    names = {x["name"] for x in f["features"]}
    assert "Age" in names and not names & {"LAD", "LCX", "RCA", "Cath"}
    assert any(x["core"] for x in f["features"])
    s = client.get(f"{BASE}/scenarios").json()
    assert [x["id"] for x in s["scenarios"]] == ["A", "B", "C", "D", "E"]


def test_predict_response_schema(client, df):
    r = client.post(
        f"{BASE}/predict", json={"features": row_patient(df, 111), "scenario_id": "demo"}
    )
    assert r.status_code == 200
    p = r.json()
    assert set(p) >= {
        "cad",
        "vessels",
        "explanations",
        "representativeness",
        "feature_completeness",
        "warnings",
        "visualization",
        "provenance",
        "safety_notice",
        "claims",
    }
    assert set(p["vessels"]) == {"LAD", "LCX", "RCA"}
    for k in (
        "probability",
        "model_probability",
        "interval_80",
        "confidence",
        "band",
        "calibrated",
        "held_out_auc",
    ):
        assert k in p["cad"] and k in p["vessels"]["LAD"]
    assert (
        p["provenance"]["scenario_id"] == "demo" and p["provenance"]["integrity_verified"] is True
    )
    assert p["visualization"]["vessels"]["LAD"]["probability"] == p["vessels"]["LAD"]["probability"]


def test_predict_rejects_invalid_input_with_actionable_errors(client):
    r = client.post(f"{BASE}/predict", json={"features": {"Age": 999, "Sex": "robot"}})
    assert r.status_code == 422
    assert len(r.json()["detail"]["problems"]) == 2
    r = client.post(f"{BASE}/predict", json={"features": {"NotAFeature": 1}})
    assert r.status_code == 422 and "unknown features" in r.json()["detail"]["problems"][0]


def test_predict_refuses_label_columns_as_inputs(client):
    for label in ("LAD", "LCX", "RCA", "Cath"):
        r = client.post(f"{BASE}/predict", json={"features": {label: "Stenotic"}})
        assert r.status_code == 422
        assert r.json()["detail"]["error"] == "LeakageError"


def test_counterfactual_and_sensitivity_endpoints(client, df):
    pt = row_patient(df, 111)
    cf = client.post(
        f"{BASE}/counterfactual", json={"features": pt, "perturbations": {"LDL": 80}}
    ).json()
    assert set(cf["targets"]) == {"CAD", "LAD", "LCX", "RCA"}
    assert (
        cf["changes"][0]["after"] == 80.0
        and "not a treatment recommendation" in cf["label"].lower()
    )
    bad = client.post(f"{BASE}/counterfactual", json={"features": pt, "perturbations": {"LDL": -5}})
    assert bad.status_code == 422
    sv = client.post(
        f"{BASE}/sensitivity", json={"features": pt, "feature": "Age", "points": 7}
    ).json()
    assert len(sv["curve"]) == 7
    assert (
        client.post(f"{BASE}/sensitivity", json={"features": pt, "feature": "Nope"}).status_code
        == 422
    )


def test_model_card_and_evaluation_are_real_artifacts(client):
    card = client.get(f"{BASE}/model").json()
    assert card["integrity_verified"] and card["leakage_audit"]["status"] == "pass"
    assert card["limitations"]
    ev = client.get(f"{BASE}/evaluation").json()
    assert ev["artifact_sha256"] == card["artifact_sha256"]
    assert ev["targets"]["CAD"]["cv_summary"]["roc_auc"] == card["metrics"]["CAD"]["roc_auc"]


def test_missing_artifact_degrades_to_503_not_500(client, monkeypatch):
    def boom():
        raise ModelArtifactError("CardioTwin model artifact missing")

    monkeypatch.setattr("app.api.cardiotwin.load_model", boom)
    for method, path in ROUTES:
        if path in ("/features", "/scenarios"):
            continue  # these do not need the model
        r = getattr(client, method)(
            BASE + path,
            **({"json": {"features": {}, "feature": "Age"}} if method == "post" else {}),
        )
        assert r.status_code == 503, path
        assert "missing" in r.json()["detail"]


def test_end_to_end_scenario_to_selected_vessel(client, scenarios):
    """patient input -> backend -> model -> explanation -> selected-vessel payload the UI renders."""
    mixed = next(s for s in scenarios if s["id"] == "C")
    p = client.post(
        f"{BASE}/predict", json={"features": mixed["patient"], "scenario_id": "C"}
    ).json()
    lad = p["vessels"]["LAD"]
    assert lad["probability"] > 0.6 > p["vessels"]["RCA"]["probability"]
    top = p["explanations"]["LAD"]["features"][0]
    assert {"feature", "value", "contribution", "direction", "share"} <= set(top)
    assert p["explanations"]["LAD"]["features"] != p["explanations"]["RCA"]["features"]
