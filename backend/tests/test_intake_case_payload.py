"""Offline PDF upload regressions at the actual multipart/API boundary."""

from __future__ import annotations

import hashlib
import io
from pathlib import Path

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from fhir.resources.R4B import construct_fhir_element

from app.agents.clinical_extractor.schemas import FHIRResourceValidatorInput
from app.agents.clinical_extractor.sub_agents.fhir_resource_validator import fhir_resource_validator
from app.api import intake
from app.auth import get_current_user

DEMOS = Path(__file__).resolve().parents[2] / "demo_pdfs"


def test_pdf_provenance_preserves_page_numbers_including_blank_pages(client):
    from reportlab.pdfgen import canvas

    output = io.BytesIO()
    pdf = canvas.Canvas(output)
    pdf.showPage()  # an empty cover page must still count
    pdf.drawString(40, 750, "Patient initials: A.P.")
    pdf.drawString(40, 725, "Diagnosis: Invasive breast carcinoma")
    pdf.drawString(40, 700, "Requested treatment: trastuzumab")
    pdf.save()
    response = client.post(
        "/api/v1/intake/parse-document",
        files={"file": ("two-page.pdf", output.getvalue(), "application/pdf")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["ocr"]["pages"] == 2
    assert body["audit"]["source_fields"]
    assert all(field["page"] == 2 for field in body["audit"]["source_fields"])


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(intake.router, prefix="/api/v1")
    app.dependency_overrides[get_current_user] = lambda: {
        "organization_id": "test-org",
        "id": "tester",
    }
    with TestClient(app) as test_client:
        yield test_client


def _upload(client, filename):
    data = (DEMOS / filename).read_bytes()
    response = client.post(
        "/api/v1/intake/parse-document", files={"file": (filename, data, "application/pdf")}
    )
    assert response.status_code == 200, response.text
    return data, response.json()


@pytest.mark.parametrize(
    "filename,initials",
    [
        ("01_APPROVE_breast_cancer_her2pos.pdf", "P.S."),
        ("02_DENY_breast_cancer_lvef_low.pdf", "L.W."),
        ("03_REFER_breast_cancer_her2_equivocal.pdf", "J.D."),
        ("04_APPROVE_hepc_daa_genotype1.pdf", "K.M."),
    ],
)
async def test_multipart_pdf_produces_case_payload_accepted_by_agent1(client, filename, initials):
    raw, result = _upload(client, filename)
    assert result["case_ready"] is True and result["missing_fields"] == []
    assert result["patient_initials"] == initials
    assert result["requested_treatment"]["name"]
    bundle = result["fhir_bundle"]
    # Structural FHIR model checks complement the actual agent-1 gate.
    construct_fhir_element("Bundle", bundle)
    validation = await fhir_resource_validator._execute_deterministic(
        FHIRResourceValidatorInput(fhir_bundle=bundle),
        None,
    )
    assert validation.is_valid
    resources = [e["resource"] for e in bundle["entry"]]
    patient = next(r for r in resources if r["resourceType"] == "Patient")
    assert "birthDate" not in patient  # documented age does not imply an invented DOB
    document = next(r for r in resources if r["resourceType"] == "DocumentReference")
    assert document["identifier"][0]["value"] == hashlib.sha256(raw).hexdigest()
    ids = {f"{r['resourceType']}/{r['id']}" for r in resources}
    provenance = next(r for r in resources if r["resourceType"] == "Provenance")
    assert all(t["reference"] in ids for t in provenance["target"])
    assert provenance["entity"][0]["what"]["reference"] in ids
    assert result["audit"]["source_fields"]
    assert "__VERDICT_HINT_" not in result["ocr"]["full_text"]


def test_safety_relevant_biomarkers_remain_source_facts(client):
    _, deny = _upload(client, "02_DENY_breast_cancer_lvef_low.pdf")
    observations = [
        e["resource"]
        for e in deny["fhir_bundle"]["entry"]
        if e["resource"]["resourceType"] == "Observation"
    ]
    assert next(r for r in observations if r["code"]["text"] == "LVEF")["valueString"].startswith(
        "32%"
    )
    _, refer = _upload(client, "03_REFER_breast_cancer_her2_equivocal.pdf")
    observations = [
        e["resource"]
        for e in refer["fhir_bundle"]["entry"]
        if e["resource"]["resourceType"] == "Observation"
    ]
    assert (
        "2+ (equivocal)"
        in next(r for r in observations if r["code"]["text"] == "HER2 IHC")["valueString"]
    )
    fish = next(r for r in observations if r["code"]["text"] == "HER2 FISH")
    assert "valueString" not in fish and "NOT YET PERFORMED" in fish["dataAbsentReason"]["text"]
    assert all(r["code"]["text"] not in {"LVEF", "ECOG"} for r in observations)


def test_policy_pdf_is_not_fabricated_into_patient_case(client):
    _, result = _upload(client, "policy_aetna_hcv_daa.pdf")
    assert result["case_ready"] is False and result["requires_human_review"] is True
    assert "patient" in result["missing_fields"] and "primary_diagnosis" in result["missing_fields"]
    assert all(
        e["resource"]["resourceType"] not in {"Patient", "Condition"}
        for e in result["fhir_bundle"]["entry"]
    )


@pytest.mark.parametrize(
    "text,missing",
    [
        (
            "Patient initials: A.B.\nDiagnosis: C50.9 Breast carcinoma\nClinical oncology note; biopsy confirmed cancer.",
            "requested_treatment",
        ),
        (
            "Patient initials: A.B.\nDrug: Trastuzumab\nPathology and oncology clinical report without a diagnosis.",
            "primary_diagnosis",
        ),
        (
            "Patient initials: A.B.\nPatient initials: C.D.\nDiagnosis: C50.9 Breast cancer\nDrug: Trastuzumab\nHER2: positive",
            "conflicting_document_fields",
        ),
        (
            "An ordinary software architecture diagram, service documentation, and deployment guide.",
            "readable_clinical_document",
        ),
    ],
)
def test_incomplete_and_conflicting_documents_show_actionable_fields(client, text, missing):
    response = client.post(
        "/api/v1/intake/parse-document", files={"file": ("note.txt", text.encode(), "text/plain")}
    )
    assert response.status_code == 200
    result = response.json()
    assert not result["case_ready"] and result["requires_human_review"]
    assert missing in result["missing_fields"]


@pytest.mark.parametrize(
    "bundle,note",
    [
        ({"resourceType": "Bundle", "type": "collection", "entry": []}, None),
        (
            {"resourceType": "Bundle", "type": "collection", "entry": []},
            "Clinical oncology note, patient needs treatment. No diagnosis supplied.",
        ),
        (
            {
                "resourceType": "Bundle",
                "entry": [
                    {"resource": {"resourceType": "Patient"}},
                    {"resource": {"resourceType": "Condition", "code": {}}},
                ],
            },
            None,
        ),
    ],
)
async def test_create_rejects_incomplete_data_before_database_access(monkeypatch, bundle, note):
    from app.api import cases

    async def fail_if_saved(*args):
        pytest.fail("Incomplete case reached persistence")

    monkeypatch.setattr(cases.db, "execute", fail_if_saved)
    with pytest.raises(HTTPException, match="") as exc:
        await cases.create_case(
            cases.CreateCaseRequest(
                payer_id="aetna",
                patient_initials="A.B.",
                fhir_bundle=bundle,
                physician_note=note,
                requested_treatment={"name": "Trastuzumab"},
            ),
            {"organization_id": "test-org", "id": "tester"},
        )
    assert exc.value.status_code == 422
    assert "documented diagnosis" in exc.value.detail


async def test_legacy_empty_bundle_note_maps_real_diagnosis_before_save(monkeypatch):
    from app.api import cases

    saved = []

    async def record_save(*args):
        saved.append(args)

    monkeypatch.setattr(cases.db, "execute", record_save)
    request = cases.CreateCaseRequest(
        payer_id="aetna",
        patient_initials="A.B.",
        fhir_bundle={"resourceType": "Bundle", "entry": []},
        physician_note="Diagnosis: C50.9 Breast carcinoma\nHER2: positive\n__VERDICT_HINT_DENY__",
        requested_treatment={"name": "Trastuzumab"},
    )
    await cases.create_case(request, {"organization_id": "test-org", "id": "tester"})
    condition = next(
        e["resource"]
        for e in request.fhir_bundle["entry"]
        if e["resource"]["resourceType"] == "Condition"
    )
    assert condition["code"]["text"] == "C50.9 Breast carcinoma"
    assert "__VERDICT_HINT_" not in request.physician_note
    assert len(saved) == 1
