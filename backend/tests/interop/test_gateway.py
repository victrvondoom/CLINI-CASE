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
from app.onehealth.models import ExposureRecord, LabSample


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


def semantic_content(bundle):
    evidence = fhir.read_evidence(bundle)
    sample = LabSample.model_validate(evidence["sample"])
    roles = fhir._exchange_resources(bundle)
    observation = roles["observation"]
    specimen = roles["specimen"]
    site = roles["site"]
    return {
        "source_record_identity": evidence["source_observation_id"],
        "sample": sample.model_dump(mode="json"),
        "location": site["name"],
        "waterbody": evidence["waterbody_name"],
        "laboratory": roles["laboratory"]["name"],
        "specimen_relationship": {
            "observation_resolves_specimen": fhir._resolve(
                roles["index"], observation.get("specimen"), "Specimen"
            )
            == specimen,
            "observation_and_specimen_share_location": fhir._resolve(
                roles["index"], specimen.get("subject"), "Location"
            )
            == site
            == fhir._resolve(roles["index"], observation.get("subject"), "Location"),
        },
        "provenance": sorted(
            evidence["provenance"],
            key=lambda row: (row["at"], row["actor_id"], row["action"]),
        ),
    }


def rename_every_resource_id(bundle):
    renamed = copy.deepcopy(bundle)
    identity_map = {}
    full_url_map = {}
    for index, entry in enumerate(renamed["entry"]):
        resource = entry["resource"]
        old_id = resource["id"]
        resource_type = resource["resourceType"]
        new_id = f"renamed-{index:02d}-{resource_type.lower()}"
        identity_map[f"{resource_type}/{old_id}"] = f"{resource_type}/{new_id}"
        if entry.get("fullUrl"):
            full_url_map[entry["fullUrl"]] = (
                f"https://independent.example/fhir/{resource_type}/{new_id}"
            )
        resource["id"] = new_id
    replacements = {**identity_map, **full_url_map}

    def update_references(value):
        if isinstance(value, dict):
            if isinstance(value.get("reference"), str):
                value["reference"] = replacements.get(value["reference"], value["reference"])
            for nested in value.values():
                update_references(nested)
        elif isinstance(value, list):
            for nested in value:
                update_references(nested)

    for entry in renamed["entry"]:
        if entry.get("fullUrl"):
            entry["fullUrl"] = full_url_map[entry["fullUrl"]]
        update_references(entry["resource"])
    renamed["id"] = "renamed-bundle-id"
    update_references(renamed)
    return renamed


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
    assert returned["returned_bundle"] != j["bundle"]
    assert returned["roundtrip"]["status"] == "passed"
    assert returned["roundtrip"]["resource_ids_reassigned"]
    assert all(field["preserved"] for field in returned["roundtrip"]["fields"])
    assert semantic_content(returned["returned_bundle"]) == semantic_content(j["bundle"])
    assert semantic_content(j["bundle"])["source_record_identity"] == j["source"][
        "original_record_id"
    ]
    assert all(semantic_content(returned["returned_bundle"])["specimen_relationship"].values())
    assert returned["roundtrip"]["source_sha256"] != returned["roundtrip"]["returned_sha256"]
    assert returned["lab_acknowledgement"]["correlation_id"] == j["transfers"][-1][
        "correlation_id"
    ]
    assert returned["lab_acknowledgement"]["status"] == "delivered"
    assert all(e["correlation_id"] == j["id"] for e in returned["job"]["events"])
    notes = returned["lab_representation"]["provenance"]
    assert "source_system" in notes[-1]["note"]


def test_every_resource_id_can_change_when_references_follow():
    original = fhir.export(
        ExposureRecord(
            organization_id="org-a",
            observation_id="source-record-42",
            waterbody_id="lake-7",
            waterbody_name="Synthetic lake",
            synthetic=True,
            sample=LabSample(
                sample_id="sample-91",
                location_name="Synthetic site",
                kind="stream",
                laboratory="Synthetic lab",
                collector="Synthetic collector",
                report_reference="report-91",
                method="Synthetic method",
                collected_at="2026-09-27T10:00:00Z",
                reported_at="2026-09-28T10:00:00Z",
                value=18.2,
                analyte="dissolved_arsenic",
            ),
        )
    )
    received = rename_every_resource_id(original)
    assert fhir.validate(received)["valid"]
    assert fhir.read_evidence(received) == fhir.read_evidence(original)
    assert all(
        entry["resource"]["id"].startswith("renamed-") for entry in received["entry"]
    )


async def test_generic_arsenic_cannot_be_assigned_dissolved_by_reviewer(client):
    c, _, _ = client
    created = await c.post("/interop/demo", json={})
    job = created.json()
    analyzed = await c.post(
        "/interop/analyze-schema",
        json={"job_id": job["id"], "expected_version": job["version"]},
    )
    job = analyzed.json()
    generic = next(m for m in job["mappings"] if m["source_field"] == "arsenic")
    assert generic["decision"] == "pending"
    assert generic["concept"] is None
    assert generic["source_field"] in job["schema"]["ambiguities"]
    rejected = await c.post(
        f"/interop/mappings/{job['id']}/approve",
        json={
            "job_id": job["id"],
            "expected_version": job["version"],
            "source_field": "arsenic",
            "concept": "dissolved_arsenic",
        },
    )
    assert rejected.status_code == 422
    assert (await c.post(
        "/interop/generate-fhir",
        json={"job_id": job["id"], "expected_version": job["version"]},
    )).status_code == 409
    assert (await c.post(
        "/interop/transfer",
        json={"job_id": job["id"], "expected_version": job["version"]},
    )).status_code == 409


async def test_explicit_dissolved_field_uses_verified_oah_coding():
    payload = json.loads(
        (Path(__file__).parents[2] / "data/interop/environmental-dissolved.json").read_text()
    )
    job = Job(
        organization_id="org-a",
        source=Source(
            source_system="Synthetic Lab",
            original_record_id="source-dissolved-1",
            payload=payload,
            synthetic=True,
        ),
    )
    await service.analyze(job, False)
    analyte_mapping = next(m for m in job.mappings if m.source_field == "arsenic_dissolved")
    assert analyte_mapping.concept == "dissolved_arsenic"
    assert analyte_mapping.terminology_status == "oah_verified_preferred"
    for mapping in job.mappings:
        mapping.decision = "accepted" if mapping.target else "rejected"
        mapping.reviewer = "human-reviewer"
    record = service.normalize(job)
    assert isinstance(record, ExposureRecord)
    observation = next(
        item["resource"]
        for item in fhir.export(record)["entry"]
        if item["resource"]["resourceType"] == "Observation"
    )
    assert observation["code"]["coding"] == [
        {
            "system": "http://hl7.eu/fhir/ig/oah/CodeSystem/temporarySystem-oah-eu",
            "code": "arsenic-dissolved",
            "display": "Arsenic dissolved",
        }
    ]
    assert service.validate(fhir.export(record))["valid"]


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
        o["code"] = {"coding": [{"system": "http://loinc.org", "code": "unknown"}]}
    j = await cmd("validate", bundle=b)
    assert not j["validation"]["valid"]
    assert j["validation"]["operation_outcome"]["resourceType"] == "OperationOutcome"
    if failure == "unit":
        assert j["validation"]["operation_outcome"]["issue"][0]["severity"] == "error"
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


async def test_model_cannot_assign_analyte_concept_or_terminology_code(monkeypatch):
    import app.llm

    class InventingModel:
        async def complete(self, **kwargs):
            return LLMResponse(
                text=json.dumps(
                    {
                        "mappings": [
                            {
                                "source_field": "arsenic",
                                "target": "value",
                                "confidence": 1,
                                "reason": "Invented speciation",
                                "concept": "inorganic_arsenic",
                                "code": "arsenic-inorganic",
                            }
                        ]
                    }
                ),
                model_id="malicious-test-model",
                input_tokens=1,
                output_tokens=1,
                stop_reason="end",
            )

    monkeypatch.setattr(app.llm, "get_llm_client", lambda: InventingModel())
    job = Job(
        organization_id="org-a",
        source=Source(
            source_system="Synthetic lab",
            original_record_id="source-generic-arsenic",
            payload={"arsenic": 18.2},
            synthetic=True,
        ),
    )
    await service.analyze(job, True)
    mapping = job.mappings[0]
    assert job.ai_status.startswith("unresolved fields require manual review")
    assert mapping.concept is None
    assert mapping.decision == "pending"
    assert mapping.terminology_status == "unresolved"


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
    assert j.ai_status.startswith("unresolved fields require manual review")
    assert j.mappings[0].origin == "unresolved"
    assert j.events[-2].status == "manual_review"


@pytest.mark.parametrize(
    ("answer", "expected_target", "accepted"),
    [
        ("Location.name (waterbody)", "waterbody_name", True),  # FHIR path → its allowlisted key
        ("waterbody_name", "waterbody_name", True),
        ("Patient.name", None, False),  # off-allowlist stays fail-closed
    ],
)
async def test_model_target_path_maps_to_key(monkeypatch, answer, expected_target, accepted):
    import app.llm

    class PathModel:
        async def complete(self, **kwargs):
            return LLMResponse(
                text=json.dumps(
                    {
                        "mappings": [
                            {
                                "source_field": "stream",
                                "target": answer,
                                "confidence": 0.8,
                                "reason": "Name of the stream",
                            }
                        ]
                    }
                ),
                model_id="path-test-model",
                input_tokens=1,
                output_tokens=1,
                stop_reason="end",
            )

    monkeypatch.setattr(app.llm, "get_llm_client", lambda: PathModel())
    j = Job(
        organization_id="a",
        source=Source(
            source_system="SYN", original_record_id="s", payload={"stream": "Mill Brook"}, synthetic=True
        ),
    )
    await service.analyze(j, True)
    assert j.mappings[0].target == expected_target
    assert j.mappings[0].origin == ("ai_suggested" if accepted else "unresolved")
    assert j.ai_status.startswith("model_suggestions_received" if accepted else "unresolved fields")


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
