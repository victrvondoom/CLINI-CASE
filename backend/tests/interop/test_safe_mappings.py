"""Batch approval of safe mappings reduces review effort without removing human decisions."""

import httpx
import pytest
from fastapi import FastAPI

from app.api import interop as interop_api
from app.api import journey as journey_api
from app.auth import get_current_user
from app.config import settings
from app.db import db
from app.interop import repository, triage

BASE = "/api/v1/interop"


def row(**changes):
    return {
        "source_field": "sample_no",
        "target": "sample_id",
        "origin": "deterministic",
        "confidence": 1.0,
        "concept": None,
        "terminology_status": "unresolved",
        "decision": "pending",
        **changes,
    }


@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        ({}, "safe"),
        ({"origin": "ai_suggested"}, "review"),
        ({"confidence": 0.65}, "review"),
        ({"source_field": "arsenic", "target": "value"}, "review"),
        ({"source_field": " Arsenic ", "target": "value", "confidence": 1.0}, "review"),
        ({"target": "not_an_allowlisted_target"}, "unresolved"),
        ({"target": None, "origin": "unresolved", "confidence": 0}, "unresolved"),
        ({"concept": "dissolved_arsenic", "terminology_status": "unresolved"}, "review"),
        ({"concept": "dissolved_arsenic", "terminology_status": "oah_verified_preferred"}, "safe"),
        ({"decision": "accepted"}, "decided"),
    ],
)
def test_only_deterministic_allowlisted_unambiguous_mappings_are_safe(changes, expected):
    assert triage.classify(row(**changes)) == expected


@pytest.fixture
async def session(monkeypatch):
    monkeypatch.setattr(db, "_pool", None)
    monkeypatch.setattr(settings, "TRACK7_DEMO_DB", "")
    monkeypatch.setattr(settings, "INTEROP_RECEIVER_URL", "")
    repository._memory.clear()
    app = FastAPI()
    app.include_router(interop_api.router, prefix="/api/v1")
    app.include_router(journey_api.router, prefix="/api/v1")
    user = {"id": "triage-reviewer", "role": "reviewer", "organization_id": "triage-org"}
    app.dependency_overrides[get_current_user] = lambda: user
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client, user
    repository._memory.clear()


async def mapped(client, variant):
    job = (await client.post(f"{BASE}/demo?variant={variant}", json={})).json()
    response = await client.post(
        f"{BASE}/map", json={"job_id": job["id"], "expected_version": job["version"]}
    )
    return response.json()


async def approve_safe(client, job):
    return await client.post(
        f"{BASE}/mappings/{job['id']}/approve-safe",
        json={"job_id": job["id"], "expected_version": job["version"]},
    )


def pending(job):
    return sorted(m["source_field"] for m in job["mappings"] if m["decision"] == "pending")


async def test_generic_arsenic_and_unresolved_fields_stay_manual(session):
    client, _ = session
    job = await mapped(client, "ambiguous")
    safe = triage.summarize(job["mappings"])["safe"]
    response = await approve_safe(client, job)
    assert response.status_code == 200
    after = response.json()
    assert pending(after) == ["arsenic", "legacy_note"]
    assert after["version"] == job["version"] + 1  # atomic: one version bump for the whole batch
    batch_events = [e for e in after["events"] if e["provenance"].get("batch") == "safe"]
    assert sorted(e["provenance"]["source_field"] for e in batch_events) == sorted(safe)
    assert all(e["actor"] == "triage-reviewer" for e in batch_events)  # one audit event per mapping


async def test_a_bundle_cannot_be_generated_until_a_person_decides_the_ambiguous_field(session):
    client, _ = session
    job = (await approve_safe(client, await mapped(client, "ambiguous"))).json()
    blocked = await client.post(
        f"{BASE}/generate-fhir", json={"job_id": job["id"], "expected_version": job["version"]}
    )
    assert blocked.status_code == 409  # batch approval did not finish the review
    arsenic = next(m for m in job["mappings"] if m["source_field"] == "arsenic")
    refused = await client.post(
        f"{BASE}/mappings/{job['id']}/approve",
        json={
            "job_id": job["id"],
            "expected_version": job["version"],
            "source_field": "arsenic",
            "target": arsenic["target"],
        },
    )
    assert refused.status_code == 422  # the explicit total/inorganic confirmation is still required


async def test_the_dissolved_path_needs_only_the_one_unresolved_decision_after_batch_approval(session):
    client, _ = session
    job = (await approve_safe(client, await mapped(client, "dissolved"))).json()
    assert pending(job) == ["legacy_note"]
    job = (
        await client.post(
            f"{BASE}/mappings/{job['id']}/reject",
            json={"job_id": job["id"], "expected_version": job["version"], "source_field": "legacy_note"},
        )
    ).json()
    generated = await client.post(
        f"{BASE}/generate-fhir", json={"job_id": job["id"], "expected_version": job["version"]}
    )
    assert generated.status_code == 200 and generated.json()["validation"]["valid"] is True


async def test_nothing_eligible_is_a_conflict_and_the_role_is_enforced(session):
    client, user = session
    job = (await approve_safe(client, await mapped(client, "dissolved"))).json()
    assert (await approve_safe(client, job)).status_code == 409
    user["role"] = "coordinator"
    assert (await approve_safe(client, job)).status_code == 403


async def test_the_journey_reports_the_three_groups_and_offers_the_bulk_action(session):
    client, _ = session
    job = await mapped(client, "ambiguous")
    stages = (await client.get(f"/api/v1/journey/{job['id']}")).json()["stages"]
    review = next(s for s in stages if s["id"] == "review")
    facts = {f["label"]: f["value"] for f in review["facts"]}
    assert (facts["Safe to batch-approve"], facts["Requires individual review"], facts["Unresolved"]) == (11, 1, 1)
    assert review["secondary_actions"] == [{"id": "approve_safe", "label": "Approve 11 safe mappings"}]
    assert review["detail"]["triage"]["review"] == ["arsenic"]
    assert {r["source_field"]: r["triage"] for r in review["detail"]["mappings"]}["arsenic"] == "review"
