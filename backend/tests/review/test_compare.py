"""Multi-payer comparison uses recorded data only: real policies, real decisions, sibling cases."""

from __future__ import annotations

import json
import uuid

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from app.auth.dependencies import get_current_user
from app.db import db
from app.main import app
from app.review.compare import PAYERS, policy_for, recommend


def col(pid, verdict=None, conf=0.9):
    return {
        "payer_id": pid,
        "name": PAYERS[pid],
        "decision": None if verdict is None else {"verdict": verdict, "confidence": conf},
    }


def test_policy_lookup_uses_the_real_corpus():
    assert policy_for("aetna", "Trastuzumab 440mg")["policy_id"] == "0048"
    assert policy_for("anthem", "olaparib")["policy_id"] == "MED-2026-044"
    assert policy_for("uhc", "pegfilgrastim") is None  # only Aetna has that policy on file
    assert (
        policy_for("aetna", "trastuzumab deruxtecan")["policy_id"] == "0468"
    )  # longest keyword wins over plain trastuzumab


def test_recommendation_needs_two_real_decisions():
    assert recommend([col("aetna"), col("uhc")])["primary"] is None
    one = recommend([col("aetna", "APPROVE"), col("uhc")])
    assert one["primary"] is None and "Only one payer" in one["summary"]


def test_recommendation_ranks_recorded_verdicts_only():
    r = recommend(
        [
            col("aetna", "DENY", 0.95),
            col("uhc", "APPROVE", 0.7),
            col("bcbs", "APPROVE", 0.9),
            col("anthem", "REFER", 0.8),
        ]
    )
    assert (r["primary"], r["fallback"]) == ("bcbs", "uhc")
    assert "Ranked from recorded decisions only" in r["summary"]


@pytest.fixture()
def client():
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "u1",
        "email": "a@b.c",
        "organization_id": "org_cmp",
        "role": "admin",
        "full_name": "x",
    }
    yield TestClient(app)
    app.dependency_overrides.pop(get_current_user, None)


def test_endpoint_errors_are_honest(client, monkeypatch):
    async def none(org, cid):
        return None

    monkeypatch.setattr("app.api.case_compare.compare_case", none)
    assert client.get("/api/v1/cases/x/compare").status_code == 404
    assert client.post("/api/v1/cases/x/compare/notapayer").status_code == 422

    async def boom(org, cid):
        raise RuntimeError("db")

    monkeypatch.setattr("app.api.case_compare.compare_case", boom)
    assert client.get("/api/v1/cases/x/compare").status_code == 503


def test_requires_auth():
    app.dependency_overrides.pop(get_current_user, None)
    assert TestClient(app).get("/api/v1/cases/x/compare").status_code in (401, 403)


@pytest.mark.integration
@pytest.mark.postgres
async def test_end_to_end_siblings_decisions_and_recommendation():
    org = f"org_cmp_{uuid.uuid4().hex[:5]}"
    await db.execute(
        "INSERT INTO organizations (id, name, slug) VALUES ($1,$1,$1) ON CONFLICT (id) DO NOTHING",
        org,
    )
    await db.execute(
        "INSERT INTO users (id, email, password_hash, organization_id, role) VALUES ($1,$2,'x',$3,'admin') ON CONFLICT (id) DO NOTHING",
        f"u_{org}",
        f"{org}@t.co",
        org,
    )
    bundle = {"resourceType": "Bundle", "entry": [{"k": uuid.uuid4().hex}]}
    cid = f"cmp-{uuid.uuid4().hex[:8]}"
    await db.execute(
        "INSERT INTO cases (id, organization_id, payer_id, patient_initials, requested_treatment_name, fhir_bundle, physician_note) VALUES ($1,$2,'aetna','S.D.','Trastuzumab',$3::jsonb,'n')",
        cid,
        org,
        json.dumps(bundle),
    )
    await db.execute(
        "INSERT INTO decisions (case_id, verdict, rationale, citations_json, confidence) VALUES ($1,'DENY','LVEF too low. more','[]'::jsonb,0.8)",
        cid,
    )
    app.dependency_overrides[get_current_user] = lambda: {
        "id": f"u_{org}",
        "email": "a@b.c",
        "organization_id": org,
        "role": "admin",
    }
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            first = (await c.get(f"/api/v1/cases/{cid}/compare")).json()
            by = {p["payer_id"]: p for p in first["payers"]}
            assert (
                by["aetna"]["state"] == "decided"
                and by["aetna"]["decision"]["verdict"] == "DENY"
                and by["aetna"]["is_this_case"]
            )
            assert by["aetna"]["decision"]["rationale"] == "LVEF too low."
            assert (
                by["uhc"]["state"] == "not_started"
                and by["uhc"]["can_create"]
                and by["uhc"]["policy"]["policy_id"] == "OnCG-2025-D012"
            )
            assert first["recommendation"]["primary"] is None  # only one recorded decision

            assert (
                await c.post(f"/api/v1/cases/{cid}/compare/aetna")
            ).status_code == 409  # already this payer
            created = (await c.post(f"/api/v1/cases/{cid}/compare/uhc")).json()
            assert created["created"] is True
            again = (await c.post(f"/api/v1/cases/{cid}/compare/uhc")).json()
            assert again == {**created, "created": False}  # idempotent

            sib = created["case_id"]
            mid = {
                p["payer_id"]: p
                for p in (await c.get(f"/api/v1/cases/{cid}/compare")).json()["payers"]
            }
            assert mid["uhc"]["state"] == "in_progress" and mid["uhc"]["case"]["case_id"] == sib

            await db.execute(
                "INSERT INTO decisions (case_id, verdict, rationale, citations_json, confidence) VALUES ($1,'APPROVE','ok.','[]'::jsonb,0.9)",
                sib,
            )
            final = (await c.get(f"/api/v1/cases/{cid}/compare")).json()
            assert (
                final["recommendation"]["primary"] == "uhc"
                and final["recommendation"]["fallback"] == "aetna"
            )
    finally:
        app.dependency_overrides.pop(get_current_user, None)
