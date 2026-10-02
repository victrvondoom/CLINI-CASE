"""Unified journey: the projection must follow the real gateway, cite real events, and stay scoped."""

import copy

import httpx
import pytest
from fastapi import FastAPI, HTTPException

from app.api import interop as interop_api
from app.api import journey as journey_api
from app.api import onehealth as onehealth_api
from app.auth import get_current_user
from app.config import settings
from app.db import db
from app.interop import repository
from app.journey import projection
from app.onehealth import fhir

STAGE_IDS = [stage_id for stage_id, _, _ in projection.STAGES]


@pytest.fixture
async def client(monkeypatch):
    monkeypatch.setattr(db, "_pool", None)
    monkeypatch.setattr(settings, "TRACK7_DEMO_DB", "")
    repository._memory.clear()
    app = FastAPI()
    for router in (interop_api.router, onehealth_api.router, journey_api.router):
        app.include_router(router, prefix="/api/v1")
    user = {"id": "journey-reviewer", "role": "reviewer", "organization_id": "journey-org"}
    app.dependency_overrides[get_current_user] = lambda: user
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as session:
        yield session, user
    repository._memory.clear()


async def _post(session, path, body=None):
    response = await session.post("/api/v1/interop" + path, json=body or {})
    assert response.status_code in (200, 201), response.text
    data = response.json()
    return data["job"] if "job" in data and "id" not in data else data


async def _journey(session, job_id):
    response = await session.get(f"/api/v1/journey/{job_id}")
    assert response.status_code == 200, response.text
    return response.json()


def _stage(journey, stage_id):
    return next(s for s in journey["stages"] if s["id"] == stage_id)


def _command(job):
    return {"job_id": job["id"], "expected_version": job["version"]}


async def _review_all(session, job):
    for mapping in [m for m in job["mappings"] if m["decision"] == "pending"]:
        decision = "approve" if mapping["target"] else "reject"
        job = await _post(
            session,
            f"/mappings/{job['id']}/{decision}",
            {**_command(job), "source_field": mapping["source_field"], "target": mapping["target"]},
        )
    return job


async def test_journey_follows_the_real_gateway_flow_stage_by_stage(client):
    session, _ = client
    job = await _post(session, "/demo?variant=dissolved")
    journey = await _journey(session, job["id"])
    assert [s["id"] for s in journey["stages"]] == STAGE_IDS
    assert journey["current_stage"] == "map"
    assert _stage(journey, "map")["next_action"]["id"] == "map"

    job = await _post(session, "/map", _command(job))
    journey = await _journey(session, job["id"])
    review = _stage(journey, "review")
    assert journey["current_stage"] == "review" and review["status"] == "ready"
    pending = sum(m["decision"] == "pending" for m in job["mappings"])
    assert review["summary"].startswith(f"{pending} mapping decision")
    assert {m["source_field"] for m in review["detail"]["mappings"]} == {
        m["source_field"] for m in job["mappings"]
    }

    job = await _review_all(session, job)
    assert (await _journey(session, job["id"]))["current_stage"] == "standardize"

    job = await _post(session, "/generate-fhir", _command(job))
    journey = await _journey(session, job["id"])
    assert _stage(journey, "validate")["status"] == "complete"  # generation validates
    assert journey["current_stage"] == "exchange"

    job = await _post(session, "/transfer", _command(job))
    journey = await _journey(session, job["id"])
    exchange = _stage(journey, "exchange")
    assert exchange["status"] == "complete" and journey["current_stage"] == "verify"
    assert exchange["evidence"][0]["event_type"] == "transfer_delivered"
    assert exchange["evidence"][0]["correlation_id"] == job["id"]

    job = await _post(session, "/return", _command(job))
    journey = await _journey(session, job["id"])
    verify = _stage(journey, "verify")
    preserved = next(f["value"] for f in verify["facts"] if f["label"] == "Fields preserved")
    kept, total = (int(n) for n in preserved.split("/"))
    assert verify["status"] == "complete" and kept == total > 0
    assert journey["current_stage"] == "clinical_context"
    assert _stage(journey, "clinical_context")["next_action"]["id"] == "bind"

    job = await _post(session, "/bind-evidence", _command(job))
    journey = await _journey(session, job["id"])
    context = _stage(journey, "clinical_context")
    assert journey["exposure_id"] == job["exposure_id"]
    assert context["status"] == "ready" and context["next_action"]["id"] == "open_evidence"
    connections = context["detail"]["connections"]
    # Patient-linked capabilities stay closed until consent is recorded.
    closed = {c["capability"] for c in connections if not c["href"]}
    assert "OncoTwin patient context" in closed and "ClinCase authorization context" in closed
    assert _stage(journey, "follow_up")["status"] == "ready"
    assert journey["progress"] == {"complete": 8, "total": 10}


async def test_every_complete_stage_cites_an_event_from_the_job_log(client):
    session, _ = client
    job = await _post(session, "/demo?variant=dissolved")
    job = await _review_all(session, await _post(session, "/map", _command(job)))
    job = await _post(session, "/generate-fhir", _command(job))
    job = await _post(session, "/transfer", _command(job))
    job = await _post(session, "/return", _command(job))
    logged = {e["event_type"] for e in (await session.get(f"/api/v1/interop/jobs/{job['id']}")).json()["events"]}
    journey = await _journey(session, job["id"])
    complete = [s for s in journey["stages"] if s["status"] == "complete"]
    assert [s["id"] for s in complete] == STAGE_IDS[:8]
    for stage in complete:
        assert stage["evidence"], stage["id"]
        assert {e["event_type"] for e in stage["evidence"]} <= logged, stage["id"]


async def test_ambiguous_arsenic_holds_review_until_a_concept_is_confirmed(client):
    session, _ = client
    job = await _post(session, "/demo?variant=ambiguous")
    job = await _post(session, "/map", _command(job))
    journey = await _journey(session, job["id"])
    assert journey["current_stage"] == "review"
    assert "arsenic" in next(
        f["value"] for f in _stage(journey, "review")["facts"] if f["label"] == "Ambiguous fields"
    )
    arsenic = next(m for m in job["mappings"] if m["source_field"] == "arsenic")
    refused = await session.post(
        f"/api/v1/interop/mappings/{job['id']}/approve",
        json={**_command(job), "source_field": "arsenic", "target": arsenic["target"]},
    )
    assert refused.status_code == 422  # the gateway's own rule, reflected not re-implemented
    assert (await _journey(session, job["id"]))["current_stage"] == "review"


async def test_journey_is_tenant_scoped_and_reviewer_only(client):
    session, user = client
    job = await _post(session, "/demo?variant=dissolved")
    user["organization_id"] = "another-org"
    assert (await session.get(f"/api/v1/journey/{job['id']}")).status_code == 404
    assert (await session.get("/api/v1/journey")).json()["journeys"] == []
    user["organization_id"], user["role"] = "journey-org", "coordinator"
    assert (await session.get(f"/api/v1/journey/{job['id']}")).status_code == 403
    assert (await session.get("/api/v1/journey")).status_code == 403


async def test_recent_journeys_are_newest_first_and_limited(client):
    session, _ = client
    first = await _post(session, "/demo?variant=dissolved")
    second = await _post(session, "/demo?variant=ambiguous")
    first = await _post(session, "/map", _command(first))  # most recent activity
    listing = (await session.get("/api/v1/journey?limit=2")).json()
    assert [row["job_id"] for row in listing["journeys"]] == [first["id"], second["id"]]
    assert listing["journeys"][0]["current_stage"] == "review"
    assert [s["id"] for s in listing["stages"]] == STAGE_IDS
    assert (await session.get("/api/v1/journey?limit=99")).status_code == 422


def _job(**changes):
    base = {
        "id": "ig-test",
        "version": 3,
        "source": {"source_system": "Lab", "original_record_id": "r1", "format": "json", "synthetic": True},
        "schema": {"fields": [{"name": "a", "detected_type": "str"}], "missing_required_fields": [], "ambiguities": []},
        "metrics": {"fields_detected": 1, "fields_mapped": 1, "resources_generated": 1, "checks_passed": 3},
        "mappings": [{"source_field": "a", "target": "value", "decision": "accepted"}],
        "bundle": {"resourceType": "Bundle", "entry": [{"resource": {"resourceType": "Observation", "id": "o"}}]},
        "validation": None,
        "transfers": [],
        "events": [],
        "passport_integrity": {"valid": True, "status": "CHAIN_VALID"},
    }
    base["validation"] = {"valid": True, "sha256": fhir.digest(base["bundle"])}
    base.update(changes)
    return base


def _status(job, stage_id):
    return _stage(projection.project(job), stage_id)["status"]


def test_interrupted_transfer_is_retryable_not_complete():
    job = _job()
    job["transfers"] = [{"id": "t1", "status": "processing", "sha256": job["validation"]["sha256"]}]
    stage = _stage(projection.project(job), "exchange")
    assert stage["status"] == "ready" and stage["next_action"]["id"] == "transfer"


def test_failed_transfer_and_failed_round_trip_surface_as_failures():
    job = _job()
    digest = job["validation"]["sha256"]
    job["transfers"] = [{"id": "t1", "status": "failed", "sha256": digest, "error": "Receiver HTTP 503"}]
    assert _status(job, "exchange") == "failed"
    job["transfers"] = [
        {"id": "t2", "status": "delivered", "sha256": digest, "acknowledgement": {}, "roundtrip": {"status": "failed"}}
    ]
    assert _status(job, "verify") == "failed"


def test_broken_passport_chain_fails_verification():
    job = _job(passport_integrity={"valid": False, "status": "CHAIN_BROKEN"})
    digest = job["validation"]["sha256"]
    job["transfers"] = [
        {
            "id": "t1",
            "status": "delivered",
            "sha256": digest,
            "acknowledgement": {},
            "roundtrip": {"status": "passed", "fields_preserved": 17, "fields_total": 17},
        }
    ]
    assert _status(job, "verify") == "failed"


def test_validation_of_a_different_payload_asks_for_revalidation_not_failure():
    job = _job()
    job["validation"] = {"valid": False, "sha256": "edited-challenge-payload"}
    stage = _stage(projection.project(job), "validate")
    assert stage["status"] == "ready" and stage["next_action"]["id"] == "validate"


def test_withdrawn_consent_blocks_hidden_artefacts():
    job = _job(bundle=None, validation=None, consent_status="WITHDRAWN")
    assert _status(job, "standardize") == "blocked"
    assert _status(job, "validate") == "blocked"


def test_projection_is_pure():
    job = _job()
    snapshot = copy.deepcopy(job)
    projection.project(job)
    assert job == snapshot


def _evidence(version=5):
    return {
        "record": {"id": "oh-1", "version": version, "review": "pending", "lab_verified": False, "followup_status": "requested"},
        "consent_status": "NOT_ESTABLISHED",
        "connections": [],
    }


def test_stale_evidence_before_exchange_requires_regeneration_like_the_gateway():
    # /bind-evidence resets exposure_version to None; the gateway then refuses transfer with 409.
    job = _job(exposure_id="oh-1", exposure_version=None)
    projected = projection.project(job, _evidence())
    standardize = _stage(projected, "standardize")
    assert projected["evidence_stale"] is True
    assert standardize["status"] == "ready" and standardize["next_action"]["id"] == "generate"
    assert _stage(projected, "validate")["status"] == "waiting"
    assert _stage(projected, "exchange")["status"] == "waiting"
    assert projected["current_stage"] == "standardize"


def test_current_evidence_does_not_force_regeneration():
    job = _job(exposure_id="oh-1", exposure_version=5)
    projected = projection.project(job, _evidence(version=5))
    assert projected["evidence_stale"] is False
    assert _stage(projected, "standardize")["status"] == "complete"
    assert _stage(projected, "exchange")["status"] == "ready"


def test_completed_exchange_stays_complete_but_flags_changed_evidence():
    job = _job(exposure_id="oh-1", exposure_version=4)
    job["transfers"] = [
        {"id": "t1", "status": "delivered", "sha256": job["validation"]["sha256"], "acknowledgement": {}, "correlation_id": "c"}
    ]
    exchange = _stage(projection.project(job, _evidence(version=5)), "exchange")
    assert exchange["status"] == "complete"
    assert any(f["label"] == "Evidence changed since this exchange" for f in exchange["facts"])


async def test_one_unreadable_job_does_not_break_the_journey_list(client, monkeypatch):
    session, _ = client
    good = await _post(session, "/demo?variant=dissolved")
    bad = await _post(session, "/demo?variant=ambiguous")

    original = journey_api.interop_api.detail_view

    async def flaky(job):
        if job.id == bad["id"]:
            raise HTTPException(404, "bound evidence is gone")
        return await original(job)

    monkeypatch.setattr(journey_api.interop_api, "detail_view", flaky)
    rows = {r["job_id"]: r for r in (await session.get("/api/v1/journey")).json()["journeys"]}
    assert rows[good["id"]]["current_stage"] == "map"
    assert rows[bad["id"]]["current_status"] == "failed" and rows[bad["id"]]["current_stage"] is None
    assert rows[bad["id"]]["progress"] == {"complete": 0, "total": 10}
