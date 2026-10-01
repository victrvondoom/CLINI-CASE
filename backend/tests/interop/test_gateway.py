"""Deterministic golden path and adversarial cross-system contract tests."""

import copy
import json
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI, HTTPException

from app.api import interop as api
from app.auth import get_current_user
from app.db import db
from app.interop import adapter, receiver, repository, service
from app.interop.models import Job, Source
from app.llm.base import LLMResponse
from app.onehealth import fhir


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    monkeypatch.setattr(db, "_pool", None)
    repository._memory.clear()
    receiver._connection.execute("DELETE FROM receipts")
    receiver._connection.commit()


@pytest.fixture
async def client():
    app = FastAPI()
    app.include_router(api.router)
    user = {"id": "reviewer-a", "role": "reviewer", "organization_id": "org-a"}
    app.dependency_overrides[get_current_user] = lambda: user
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c, user, app


def source():
    return json.loads((Path(__file__).parents[2] / "data/interop/environmental.json").read_text())


async def ready(c):
    response = await c.post("/interop/demo", json={})
    assert response.status_code == 201, response.text
    j = response.json()

    async def command(path, **kw):
        nonlocal j
        r = await c.post(
            "/interop/" + path, json={"job_id": j["id"], "expected_version": j["version"], **kw}
        )
        assert r.status_code == 200, r.text
        j = r.json()
        return j

    await command("analyze-schema")
    assert j["ai_status"].startswith("deterministic_offline")
    assert next(m for m in j["mappings"] if m["source_field"] == "arsenic")["confidence"] < 0.8
    r = await c.post(
        "/interop/generate-fhir", json={"job_id": j["id"], "expected_version": j["version"]}
    )
    assert r.status_code == 409
    for m in list(j["mappings"]):
        action = "approve" if m["target"] else "reject"
        await command(
            f"mappings/{j['id']}/{action}",
            source_field=m["source_field"],
            concept="total_arsenic" if m["source_field"] == "arsenic" else None,
        )
    await command("generate-fhir")
    return j, command


async def test_golden_path_and_return(client):
    c, _, _ = client
    j, cmd = await ready(c)
    assert j["validation"]["valid"]
    assert j["validation"]["roundtrip"]["sample_preserved"]
    assert j["assessment"]["gates"][0]["passed"] is False
    j = await cmd("transfer")
    ack = j["transfers"][-1]["acknowledgement"]
    assert ack["resources_acknowledged"] == len(j["bundle"]["entry"])
    assert ack["representation"]["local_review"] == "pending"
    r = await c.post("/interop/return", json={"job_id": j["id"], "expected_version": j["version"]})
    assert r.status_code == 200, r.text
    returned = r.json()
    assert returned["lab_representation"]["sample"] == j["normalized"]
    assert returned["returned_bundle"] == j["bundle"]
    assert returned["lab_acknowledgement"]["status"] == "delivered"
    assert all(e["correlation_id"] == j["id"] for e in returned["job"]["events"])
    notes = returned["lab_representation"]["provenance"]
    assert "source_system" in notes[-1]["note"]


@pytest.mark.parametrize(
    "failure", ["unit", "reference", "duplicate", "date", "unsupported", "provenance", "coding"]
)
async def test_broken_contracts(client, failure):
    c, _, _ = client
    j, cmd = await ready(c)
    b = copy.deepcopy(j["bundle"])
    entries = b["entry"]
    o = next(e["resource"] for e in entries if e["resource"]["resourceType"] == "Observation")
    if failure == "unit":
        o["valueQuantity"]["code"] = "ppm"
    elif failure == "reference":
        b["entry"] = [e for e in entries if e["resource"]["resourceType"] != "Specimen"]
    elif failure == "duplicate":
        entries.append(copy.deepcopy(entries[0]))
    elif failure == "date":
        o["effectiveDateTime"] = "invalid"
    elif failure == "unsupported":
        entries.append(
            {
                "fullUrl": "https://x/Basic/x",
                "resource": {"resourceType": "Basic", "id": "x", "code": {"text": "unsupported"}},
            }
        )
    elif failure == "provenance":
        b["entry"] = [e for e in entries if e["resource"]["resourceType"] != "Provenance"]
    else:
        o["code"]["coding"][0]["system"] = "http://loinc.org"
    j = await cmd("validate", bundle=b)
    assert not j["validation"]["valid"]
    r = await c.post(
        "/interop/transfer", json={"job_id": j["id"], "expected_version": j["version"]}
    )
    assert r.status_code == 409


async def test_transfer_failure_retry_and_idempotence(client, monkeypatch):
    c, _, _ = client
    j, cmd = await ready(c)
    original = adapter.exchange

    async def failed(*args, **kwargs):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(adapter, "exchange", failed)
    j = await cmd("transfer")
    assert j["transfers"][-1]["status"] == "failed"
    monkeypatch.setattr(adapter, "exchange", original)
    j = await cmd("transfer")
    assert j["transfers"][-1]["status"] == "delivered"
    j = await cmd("transfer")
    assert j["transfers"][-1]["status"] == "delivered"
    assert receiver._connection.execute("SELECT COUNT(*) FROM receipts").fetchone()[0] == 1


async def test_scope_role_and_version(client):
    c, user, app = client
    j, _ = await ready(c)
    r = await c.post("/interop/map", json={"job_id": j["id"], "expected_version": 1})
    assert r.status_code == 409
    user["organization_id"] = "org-b"
    assert (await c.get("/interop/jobs/" + j["id"])).status_code == 404
    user["role"] = "citizen"
    assert (await c.get("/interop/meta")).status_code == 403
    app.dependency_overrides.clear()
    assert (await c.get("/interop/meta")).status_code == 401


async def test_csv_missing_fields_and_ambiguity():
    text = (Path(__file__).parents[2] / "data/interop/laboratory.csv").read_text()
    j = Job(
        organization_id="a",
        source=Source(
            source_system="SYN Lab",
            original_record_id="s",
            format="csv",
            payload=text,
            synthetic=True,
        ),
    )
    await service.analyze(j, False)
    assert len(j.fields) == 13
    for m in j.mappings:
        m.decision = "accepted" if m.target else "rejected"
        m.reviewer = "r"
    with pytest.raises(HTTPException):
        service.normalize(j)
    next(m for m in j.mappings if m.source_field == "arsenic").concept = "total_arsenic"
    assert service.normalize(j).sample.value == 18.2
    del j.fields["method"]
    j.mappings = [m for m in j.mappings if m.source_field != "method"]
    with pytest.raises(HTTPException):
        service.normalize(j)


async def test_real_model_adapter_typed_output(monkeypatch):
    import app.llm

    class Model:
        async def complete(self, **kw):
            assert "targets" in kw["user"]
            return LLMResponse(
                text=json.dumps(
                    {
                        "mappings": [
                            {
                                "source_field": "weird_time",
                                "target": "collected_at",
                                "confidence": 0.4,
                                "reason": "Possible collection time",
                            }
                        ]
                    }
                ),
                model_id="test-model",
                input_tokens=1,
                output_tokens=1,
                stop_reason="end",
            )

    monkeypatch.setattr(app.llm, "get_llm_client", lambda: Model())
    j = Job(
        organization_id="a",
        source=Source(
            source_system="SYN",
            original_record_id="s",
            payload={"weird_time": "2026-09-28T10:00:00Z"},
            synthetic=True,
        ),
    )
    await service.analyze(j, True)
    assert j.mappings[0].origin == "ai_suggested"
    assert j.mappings[0].decision == "pending"
    assert j.mappings[0].confidence == 0.4


async def test_receiver_auth_and_tenant(client):
    c, _, _ = client
    j, _ = await ready(c)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=receiver.app), base_url="http://receiver"
    ) as external:
        r = await external.post(
            "/fhir",
            headers={"X-Tenant": "a", "X-Receiver-Token": "wrong"},
            json={"correlation_id": j["id"], "bundle": j["bundle"]},
        )
        assert r.status_code == 401
    await adapter.exchange("a", j["id"], j["bundle"])
    with pytest.raises(httpx.HTTPStatusError):
        await adapter.exchange("b", j["id"])


async def test_nonsynthetic_needs_database():
    j = Job(
        organization_id="a",
        source=Source(source_system="Lab", original_record_id="s", payload=source()),
    )
    with pytest.raises(HTTPException) as exc:
        await repository.save(j)
    assert exc.value.status_code == 503


async def test_patient_consent_review_and_import_preservation(client):
    from app.onehealth.models import AuditEvent, ExposureHistory, ExposureRecord, LabSample

    c, _, _ = client
    j, _ = await ready(c)
    sample = LabSample.model_validate(j["normalized"])
    h = ExposureHistory(
        patient_id="SYN-PATIENT",
        consent_reference="SYN-CONSENT",
        consent_recorded=True,
        route="drinking",
        pathway_confirmed=True,
        pathway_evidence="SYNTHETIC interview",
        treatment_context="SYNTHETIC filtered water",
        started_on="2026-09-01T00:00:00Z",
        ended_on="2026-09-30T00:00:00Z",
    )
    r = ExposureRecord(
        organization_id="a",
        observation_id="s",
        waterbody_id="w",
        waterbody_name="SYN Lake",
        synthetic=True,
        sample=sample,
        history=h,
        lab_verified=True,
        review="reviewed",
        audit=[
            AuditEvent(
                action="source_review",
                actor_id="source-reviewer",
                note="SYNTHETIC source claims; receiver must review",
            )
        ],
    )
    bundle = fhir.export(r)
    assert service.validate(bundle)["valid"]
    assert not service.assessment(bundle)["gates"][1]["passed"]
    for failure in ("patient", "consent", "review"):
        broken = copy.deepcopy(bundle)
        resources = {
            e["resource"]["resourceType"] + "/" + e["resource"]["id"]: e["resource"]
            for e in broken["entry"]
        }
        if failure == "patient":
            resources["Consent/exposure-consent"]["patient"]["reference"] = "Patient/missing"
        elif failure == "consent":
            resources["Consent/exposure-consent"]["status"] = "inactive"
        else:
            resources["Task/clinical-review"]["status"] = "requested"
        assert not service.validate(broken)["valid"]
    imported = Job(
        organization_id="a",
        source=Source(
            source_system="SYN Clinical B",
            original_record_id="s",
            format="fhir",
            payload=bundle,
            synthetic=True,
        ),
    )
    await service.analyze(imported, False)
    for m in imported.mappings:
        m.decision = "accepted"
        m.reviewer = "local-reviewer"
    normalized = service.normalize(imported)
    assert normalized.history == h
    assert not normalized.lab_verified
    assert normalized.review == "pending"
    assert any(e.actor_id == "source-reviewer" for e in normalized.audit)
    assert service.validate(fhir.export(normalized))["valid"]
    r.consent_withdrawn = True
    assert not service.validate(fhir.export(r))["valid"]


async def test_model_failure_is_not_fake_success(monkeypatch):
    import app.llm

    class BrokenModel:
        async def complete(self, **kwargs):
            raise RuntimeError("offline")

    monkeypatch.setattr(app.llm, "get_llm_client", lambda: BrokenModel())
    j = Job(
        organization_id="a",
        source=Source(
            source_system="SYN", original_record_id="s", payload={"unknown": 18}, synthetic=True
        ),
    )
    await service.analyze(j, True)
    assert j.ai_status.startswith("model_failed")
    assert j.mappings[0].origin == "unresolved"
    assert j.events[-2].status == "failed"


@pytest.mark.parametrize("failure", ["rejected", "ack_mismatch"])
async def test_receiver_rejection_and_false_acknowledgement(client, monkeypatch, failure):
    c, _, _ = client
    j, cmd = await ready(c)

    async def broken(*args, **kwargs):
        if failure == "rejected":
            r = httpx.Response(422, request=httpx.Request("POST", "http://receiver/fhir"))
            raise httpx.HTTPStatusError("rejected", request=r.request, response=r)
        return {
            "status": "delivered",
            "sha256": "wrong",
            "correlation_id": j["id"],
            "resources_acknowledged": 1000,
        }

    monkeypatch.setattr(adapter, "exchange", broken)
    j = await cmd("transfer")
    assert j["transfers"][-1]["status"] == ("rejected" if failure == "rejected" else "failed")
    assert "acknowledgement" not in j["transfers"][-1]


async def test_unapproved_reanalysis_cannot_return_stale_receipt(client):
    c, _, _ = client
    j, cmd = await ready(c)
    j = await cmd("transfer")
    j = await cmd("analyze-schema")
    r = await c.post("/interop/return", json={"job_id": j["id"], "expected_version": j["version"]})
    assert r.status_code == 409
