"""FHIR-facing capability, media-type, tenant-auth and validation contract tests."""

import copy
import json
from datetime import timedelta

import httpx
import pytest
from fastapi import FastAPI
from fhir.resources.R4B.capabilitystatement import CapabilityStatement

from app.api import fhir_interop, fhir_pas
from app.auth import get_current_user
from app.config import settings
from app.db import db
from app.interop import repository
from app.onehealth import fhir
from app.onehealth.models import AuditEvent, ExposureRecord, LabSample, now


@pytest.fixture
async def client(monkeypatch):
    monkeypatch.setattr(db, "_pool", None)
    monkeypatch.setattr(settings, "TRACK7_DEMO_DB", "")
    repository._memory.clear()
    app = FastAPI()
    app.include_router(fhir_pas.router)
    app.include_router(fhir_interop.router)
    user = {"id": "fhir-reviewer", "role": "reviewer", "organization_id": "fhir-org"}
    app.dependency_overrides[get_current_user] = lambda: user
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as session:
        yield session, user, app
    repository._memory.clear()


def valid_bundle():
    time = now()
    record = ExposureRecord(
        organization_id="fhir-org",
        observation_id="source-record-1",
        waterbody_id="waterbody-1",
        waterbody_name="Synthetic river",
        synthetic=True,
        sample=LabSample(
            sample_id="sample-1",
            location_name="Synthetic site",
            kind="stream",
            laboratory="Synthetic lab",
            collector="Synthetic team",
            report_reference="report-1",
            method="Synthetic method",
            collected_at=time - timedelta(days=1),
            reported_at=time,
            analyte="dissolved_arsenic",
            value=18.2,
        ),
        audit=[AuditEvent(action="mapping_approved", actor_id="reviewer-1", note="Synthetic")],
    )
    return fhir.export(record)


def fhir_headers():
    return {"content-type": "application/fhir+json"}


async def test_capability_statement_is_public_fhir_json_and_only_advertises_supported_types(
    client,
):
    session, _, _ = client
    response = await session.get("/fhir/metadata")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/fhir+json")
    statement = response.json()
    assert statement["resourceType"] == "CapabilityStatement"
    CapabilityStatement.parse_obj(statement)
    assert statement["fhirVersion"] == "4.0.1"
    assert "application/fhir+json" in statement["format"]
    resources = statement["rest"][0]["resource"]
    assert {resource["type"] for resource in resources} == {"Bundle", "Claim"}
    bundle = next(resource for resource in resources if resource["type"] == "Bundle")
    assert {row["code"] for row in bundle["interaction"]} == {"create", "read"}
    assert [operation["name"] for operation in bundle["operation"]] == ["validate"]
    claim = next(resource for resource in resources if resource["type"] == "Claim")
    assert [operation["name"] for operation in claim["operation"]] == ["submit"]


async def test_bundle_create_read_validate_media_types_and_authentication(client):
    session, user, app = client
    bundle = valid_bundle()

    app.dependency_overrides.clear()
    unauthorized = await session.post("/fhir/Bundle", json=bundle)
    assert unauthorized.status_code == 401

    async def authenticated_user():
        return user

    app.dependency_overrides[get_current_user] = authenticated_user
    unsupported_media = await session.post("/fhir/Bundle", json=bundle)
    assert unsupported_media.status_code == 415

    user["role"] = "coordinator"
    forbidden = await session.post(
        "/fhir/Bundle", content="{}", headers=fhir_headers()
    )
    assert forbidden.status_code == 403
    user["role"] = "reviewer"

    created = await session.post(
        "/fhir/Bundle", json=bundle, headers=fhir_headers()
    )
    assert created.status_code == 201, created.text
    assert created.headers["content-type"].startswith("application/fhir+json")
    stored = created.json()
    read = await session.get(f"/fhir/Bundle/{stored['id']}")
    assert read.status_code == 200
    assert read.headers["content-type"].startswith("application/fhir+json")
    assert read.json() == stored

    valid = await session.post(
        "/fhir/Bundle/$validate", json=bundle, headers=fhir_headers()
    )
    assert valid.status_code == 200
    assert valid.headers["content-type"].startswith("application/fhir+json")
    assert valid.json()["resourceType"] == "OperationOutcome"
    assert all(issue["severity"] != "error" for issue in valid.json()["issue"])

    invalid_bundle = copy.deepcopy(bundle)
    observation = next(
        entry["resource"]
        for entry in invalid_bundle["entry"]
        if entry["resource"]["resourceType"] == "Observation"
    )
    observation["valueQuantity"]["code"] = "banana/kg"
    invalid = await session.post(
        "/fhir/$validate", json=invalid_bundle, headers=fhir_headers()
    )
    assert invalid.status_code == 200
    assert invalid.json()["resourceType"] == "OperationOutcome"
    assert invalid.json()["issue"][0]["severity"] == "error"
    assert "quantity" in invalid.json()["issue"][0]["diagnostics"].lower()

    wrong_content_type = await session.post(
        "/fhir/$validate", json=bundle
    )
    assert wrong_content_type.status_code == 415


@pytest.mark.parametrize(
    ("diagnosis", "expected"),
    [
        ([{"diagnosisCodeableConcept": {"coding": [{"code": "C50.911"}]}}], "C50.911"),
        ([{"diagnosisCodeableConcept": {"coding": [{"code": ["C50.911"]}]}}], None),
        ([{"diagnosisCodeableConcept": {"coding": [{"code": 50911}]}}], None),
        ([], None),
    ],
)
def test_pas_diagnosis_code_is_a_string_or_absent(diagnosis, expected):
    # A non-string ICD-10 code must not be interpolated into the queued physician note.
    assert fhir_pas._claim_diagnosis({"diagnosis": diagnosis}) == expected


def _observation(bundle):
    return next(
        entry["resource"]
        for entry in bundle["entry"]
        if entry["resource"]["resourceType"] == "Observation"
    )


def _diagnostics(result):
    return [issue["diagnostics"] for issue in result["operation_outcome"]["issue"]]


def test_validate_summarizes_model_errors_without_echoing_input():
    model_error = valid_bundle()
    _observation(model_error)["valueQuantity"]["value"] = -7.25
    fhir_error = valid_bundle()
    fhir_error["entry"] = {"unexpected": "shape"}

    for bundle, field in ((model_error, "value"), (fhir_error, "entry")):
        result = fhir.validate(bundle)
        assert result["valid"] is False
        [message] = _diagnostics(result)
        assert message.startswith("Resource does not match the exchange model: " + field)
        assert "-7.25" not in message and "input_value" not in message
        assert "errors.pydantic.dev" not in message


def test_validate_never_echoes_unexpected_exception_internals(monkeypatch):
    def broken_selector(_bundle):
        raise KeyError("internal_index_name")

    monkeypatch.setattr(fhir, "_exchange_resources", broken_selector)
    result = fhir.validate(valid_bundle())
    assert result["valid"] is False
    assert _diagnostics(result) == [fhir.STRUCTURE_ISSUE]
    assert "internal_index_name" not in json.dumps(result)
