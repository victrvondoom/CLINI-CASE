from __future__ import annotations

import copy
from datetime import timedelta

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from pydantic import ValidationError

from app.api import onehealth as api
from app.api.aquahealth import org_store
from app.aquahealth.models import Observation
from app.aquahealth.store import OrgAquaStore
from app.auth import get_current_user
from app.db import db
from app.onehealth import evidence, fhir, repository
from app.onehealth.models import (
    ANALYTES,
    AuditEvent,
    ExposureHistory,
    ExposureRecord,
    LabSample,
    now,
)


@pytest.fixture
def record():
    time = now()
    return ExposureRecord(
        organization_id="org-a",
        observation_id="obs-1",
        waterbody_id="water-1",
        waterbody_name="Demo stream",
        synthetic=True,
        sample=LabSample(
            sample_id="lab-1",
            location_name="Demo tap",
            kind="drinking_water",
            laboratory="Demo lab",
            collector="Demo collector",
            report_reference="report-1",
            method="ICP-MS synthetic",
            collected_at=time - timedelta(days=3),
            reported_at=time - timedelta(days=2),
            value=25,
        ),
        history=ExposureHistory(
            patient_id="ot-005",
            consent_reference="demo-consent",
            consent_recorded=True,
            route="drinking",
            pathway_confirmed=True,
            pathway_evidence="Synthetic documented use",
            treatment_context="Synthetic point-of-use interview",
            started_on=time - timedelta(days=365),
            ended_on=time - timedelta(days=1),
        ),
        lab_verified=True,
        audit=[AuditEvent(action="created", actor_id="reviewer-a", note="Synthetic test evidence")],
    )


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    monkeypatch.setattr(db, "_pool", None)
    repository._memory.clear()
    yield
    repository._memory.clear()


@pytest.fixture
async def client(record):
    app = FastAPI()
    app.include_router(api.router)
    user = {"id": "reviewer-a", "role": "reviewer", "organization_id": "org-a"}
    st = OrgAquaStore("org-a")
    st.put_observation(
        Observation(
            id="obs-1",
            reference="AQUA-000001",
            organization_id="org-a",
            waterbody_id="water-1",
            waterbody_name="Demo stream",
            observed_at=now(),
            is_demo=True,
        )
    )
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[org_store] = lambda: st
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as session:
        yield session, user, st, app


def test_evidence_ready_is_not_disease_prediction(record):
    result = evidence.assess(record)
    assert result["eligible_for_review"]
    assert result["comparison"] == "above_provisional_guideline"
    assert "probability" not in result
    assert "Not a diagnosis" in result["notice"]
    assert all(not row["eligible_for_review"] for row in evidence.ablation(record))
    assert record.lab_verified  # ablation does not mutate live record


@pytest.mark.parametrize(
    "missing", ["lab", "consent", "pathway", "matrix", "treatment", "time", "route", "withdrawn"]
)
def test_every_missing_dependency_withholds_clinical_link(record, missing):
    if missing == "lab":
        record.lab_verified = False
    if missing == "consent":
        record.history.consent_recorded = False
    if missing == "pathway":
        record.history.pathway_confirmed = False
    if missing == "matrix":
        record.sample.kind = "stream"
    if missing == "treatment":
        record.history.treatment_context = ""
    if missing == "time":
        record.history.ended_on = now() - timedelta(days=100)
    if missing == "route":
        record.history.route = "other"
    if missing == "withdrawn":
        record.consent_withdrawn = True
    assert not evidence.assess(record)["eligible_for_review"]


def test_unit_normalization_and_censored_results(record):
    record.sample.value = 0.025
    record.sample.unit = "mg/L"
    assert evidence.assess(record)["concentration_ug_l"] == 25
    record.sample.qualifier = "lt"
    assert evidence.assess(record)["comparison"] == "below_reporting_limit_not_quantified"
    record.sample.kind = "stream"
    assert evidence.assess(record)["comparison"] == "not_applicable"


@pytest.mark.parametrize(
    "change",
    [
        {"value": float("nan")},
        {"value": float("inf")},
        {"value": -1},
        {"unit": "ppm"},
        {"lab_verified": True},
        {"collected_at": "2026-01-01"},
        {"report_reference": " "},
        {"reported_at": "2099-01-01T00:00:00Z"},
    ],
)
def test_invalid_inputs_rejected(record, change):
    with pytest.raises(ValidationError):
        LabSample.model_validate({**record.sample.model_dump(), **change})


def test_native_fhir_roundtrip_and_pinned_constraints(record):
    bundle = fhir.export(record)
    validation = fhir.validate(bundle)
    assert validation["valid"], validation
    assert not validation["standards"]["full_hl7_profile_validation"]
    assert validation["standards"]["oah_commit"] == fhir.OAH_COMMIT
    decoded = fhir.read_evidence(bundle)
    assert decoded["sample"] == record.sample.model_dump(mode="json")
    assert decoded["history"] == record.history.model_dump(mode="json")
    assert "organization_id" not in str(bundle)


@pytest.mark.parametrize(
    ("analyte", "expected_code"),
    [
        ("total_arsenic", {"text": "Total arsenic"}),
        ("inorganic_arsenic", {"text": "Inorganic arsenic"}),
        (
            "dissolved_arsenic",
            {
                "coding": [
                    {
                        "system": "http://hl7.eu/fhir/ig/oah/CodeSystem/temporarySystem-oah-eu",
                        "code": "arsenic-dissolved",
                        "display": "Arsenic dissolved",
                    }
                ],
                "text": "Arsenic dissolved",
            },
        ),
    ],
)
def test_verified_oah_profiles_and_analyte_codings(record, analyte, expected_code):
    changed = record.model_copy(
        update={"sample": record.sample.model_copy(update={"analyte": analyte})}
    )
    bundle = fhir.export(changed)
    resources = [entry["resource"] for entry in bundle["entry"]]
    profiles = {
        profile
        for resource in resources
        for profile in resource.get("meta", {}).get("profile", [])
    }
    assert profiles == {
        "http://hl7.eu/fhir/ig/oah/StructureDefinition/location-oah",
        "http://hl7.eu/fhir/ig/oah/StructureDefinition/specimen-oah",
        "http://hl7.eu/fhir/ig/oah/StructureDefinition/observation-indicators-oah",
    }
    specimen = next(resource for resource in resources if resource["resourceType"] == "Specimen")
    assert specimen["type"]["coding"] == [
        {
            "system": "http://snomed.info/sct",
            "code": "11713004",
            "display": "Water",
        }
    ]
    observation = next(
        resource for resource in resources if resource["resourceType"] == "Observation"
    )
    assert observation["code"] == expected_code
    assert fhir.read_evidence(bundle)["sample"]["analyte"] == analyte
    assert fhir.validate(bundle)["valid"]


@pytest.mark.parametrize(
    ("codeable", "expected"),
    [
        ({"coding": [{"system": fhir.SYSTEM, "code": "total_arsenic"}]}, "total_arsenic"),
        ({"coding": [{"system": fhir.SYSTEM, "code": "dissolved_arsenic"}]}, "dissolved_arsenic"),
        ({"text": "Inorganic arsenic"}, "inorganic_arsenic"),
    ],
)
def test_decode_analyte_reads_legacy_codes_and_local_text(codeable, expected):
    assert fhir._decode_analyte(codeable) == expected


def test_every_analyte_concept_has_a_label():
    # The decoder indexes ANALYTE_LABELS by every Analyte; a missing label would be a KeyError.
    assert set(fhir.ANALYTE_LABELS) == set(ANALYTES)


@pytest.mark.parametrize("code", [["total_arsenic"], {"code": "total_arsenic"}, None, 1])
def test_decode_analyte_rejects_non_string_legacy_code_as_value_error(code):
    # An unhashable code must surface as a contract ValueError, never a TypeError.
    with pytest.raises(ValueError, match="not supported"):
        fhir._decode_analyte({"coding": [{"system": fhir.SYSTEM, "code": code}]})


@pytest.mark.parametrize(
    "change",
    [
        "unit",
        "performer",
        "subject",
        "time",
        "status",
        "duplicate",
        "external",
        "comparator",
        "patient",
        "contract",
        "transaction",
    ],
)
def test_fhir_rejects_invalid_exchange(record, change):
    bundle = fhir.export(record)
    resources = fhir._resources(bundle)
    obs = resources["Observation/lab-result"]
    if change == "unit":
        obs["valueQuantity"]["code"] = "ppm"
    if change == "performer":
        obs.pop("performer")
    if change == "subject":
        obs["subject"] = {"reference": "Patient/linked-patient"}
    if change == "time":
        obs["effectiveDateTime"] = "2000-01-01T00:00:00Z"
    if change == "status":
        obs["status"] = "preliminary"
    if change == "duplicate":
        bundle["entry"].append(copy.deepcopy(bundle["entry"][0]))
    if change == "external":
        obs["subject"] = {"reference": "https://evil.invalid/Patient/1"}
    if change == "comparator":
        obs["valueQuantity"]["comparator"] = ">"
    if change == "patient":
        resources["Patient/linked-patient"]["identifier"][0]["value"] = "another-patient"
    if change == "contract":
        bundle["meta"]["tag"] = []
    if change == "transaction":
        bundle["type"] = "transaction"
    assert not fhir.validate(bundle)["valid"]


async def test_atomic_updates_isolation_and_real_data_fail_closed(record):
    saved = await repository.save(record)
    assert saved.version == 1
    with pytest.raises(HTTPException) as exc:
        await repository.get("org-b", saved.id)
    assert exc.value.status_code == 404
    saved.review = "reviewed"
    assert (await repository.save(saved, 1)).version == 2
    with pytest.raises(HTTPException) as exc:
        await repository.save(saved, 1)
    assert exc.value.status_code == 409
    real = record.model_copy(update={"id": "real", "synthetic": False})
    with pytest.raises(HTTPException) as exc:
        await repository.save(real)
    assert exc.value.status_code == 503


async def test_complete_api_journey_and_import_trust_reset(client, record):
    session, user, _, _ = client
    result = await session.post(
        "/onehealth/exposures",
        json={"observation_id": "obs-1", "sample": record.sample.model_dump(mode="json")},
    )
    assert result.status_code == 201, result.text
    r = result.json()
    rid = r["id"]

    async def action(name, **payload):
        nonlocal r
        response = await session.post(
            f"/onehealth/exposures/{rid}/{name}", json={"expected_version": r["version"], **payload}
        )
        assert response.status_code == 200, response.text
        r = response.json()

    premature = await session.post(
        f"/onehealth/exposures/{rid}/review",
        json={"expected_version": 1, "decision": "reviewed", "note": "Insufficient evidence"},
    )
    assert premature.status_code == 409
    await action("verify", note="Checked the synthetic lab report")
    await action("link", history=record.history.model_dump(mode="json"))
    await action(
        "review", decision="reviewed", note="Reviewed exposure relevance without diagnosing disease"
    )
    assert r["assessment"]["state"] == "reviewed_exposure_context"
    patient_rows = await session.get("/onehealth/exposures?patient_id=ot-005")
    assert patient_rows.json()["records"][0]["id"] == rid
    exported = (await session.get(f"/onehealth/exposures/{rid}/fhir")).json()
    assert exported["validation"]["valid"], exported
    assert exported["validation"]["roundtrip"]["history_preserved"]
    bundle = exported["bundle"]
    imported = await session.post(
        "/onehealth/exchange/import", json={"bundle": bundle, "observation_id": "obs-1"}
    )
    assert imported.status_code == 201, imported.text
    incoming = imported.json()
    assert (
        not incoming["lab_verified"]
        and incoming["history"] is None
        and incoming["review"] == "pending"
    )
    assert incoming["source_bundle_sha256"] == fhir.digest(bundle)
    duplicate = await session.post(
        "/onehealth/exchange/import", json={"bundle": bundle, "observation_id": "obs-1"}
    )
    assert duplicate.status_code == 409
    await action("withdraw-consent", note="Synthetic patient withdrew sharing consent")
    assert (await session.get(f"/onehealth/exposures/{rid}/fhir")).status_code == 409
    assert (await session.get("/onehealth/exposures?patient_id=ot-005")).json()["records"] == []
    user["role"] = "submitter"
    assert (await session.get("/onehealth/exposures")).status_code == 403
    tasks = (await session.get("/onehealth/environmental-tasks")).json()
    assert (
        "patient" not in str(tasks)
        and "consent" not in str(tasks)
        and "reviewer-a" not in str(tasks)
    )


async def test_no_role_or_tenant_bypass(client, record):
    session, user, _, app = client
    await repository.save(record)
    user["organization_id"] = "org-b"
    assert (await session.get(f"/onehealth/exposures/{record.id}")).status_code == 404
    assert (await session.get("/onehealth/exposures")).json()["records"] == []
    user["organization_id"] = "org-a"
    response = await session.post(
        f"/onehealth/exposures/{record.id}/verify",
        json={"expected_version": 1, "note": "Checked this report", "actor_id": "admin"},
    )
    assert response.status_code == 422
    app.dependency_overrides.clear()
    assert (await session.get("/onehealth/exposures")).status_code == 401


async def test_demo_is_unverified_and_metadata_primary_track7(client):
    session, _, _, _ = client
    result = await session.post("/onehealth/demo")
    assert result.status_code == 201, result.text
    assert result.json()["synthetic"] and not result.json()["lab_verified"]
    assert result.json()["history"] is None
    assert "Track 7" in (await session.get("/onehealth/meta")).json()["primary_track"]


async def test_case_candidates_are_dynamic_tenant_scoped_and_db_gated(client, monkeypatch):
    session, user, _, _ = client
    unavailable = await session.get("/onehealth/case-candidates")
    assert unavailable.status_code == 200
    assert unavailable.json() == {
        "available": False,
        "cases": [],
        "reason": "Persistent PostgreSQL case storage is required",
    }
    monkeypatch.setattr(repository, "mode", lambda: "postgresql")

    async def fetch(_query, *args):
        assert args == ("org-a", 100)
        return [
            {
                "id": "case-a",
                "patient_initials": "A.B.",
                "requested_treatment_name": "Synthetic treatment",
                "status": "awaiting_review",
            }
        ]

    monkeypatch.setattr(db, "fetch", fetch)
    available = await session.get("/onehealth/case-candidates?limit=100")
    assert available.status_code == 200
    assert available.json() == {
        "available": True,
        "cases": [
            {
                "id": "case-a",
                "patient_initials": "A.B.",
                "treatment": "Synthetic treatment",
                "status": "awaiting_review",
            }
        ],
    }
