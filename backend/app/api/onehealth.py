"""Track 7: tenant-scoped exposure evidence, HITL review and staged FHIR exchange."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import Field

from app.api.aquahealth import org_store
from app.aquahealth import service as aqua_service
from app.aquahealth.models import ObservationCreate
from app.auth import get_current_user, require_role
from app.db import db
from app.onehealth import evidence, fhir, repository
from app.onehealth.models import (
    Attestation,
    AuditEvent,
    CaseLinkRequest,
    ExposureCreate,
    ExposureRecord,
    FollowupRequest,
    LabSample,
    LinkRequest,
    ReviewRequest,
    StrictModel,
    now,
)

router = APIRouter(prefix="/onehealth", tags=["onehealth-track7"])
reviewer = require_role("reviewer", "admin")


def event(record: ExposureRecord, user: dict, action: str, note: str) -> None:
    record.audit.append(AuditEvent(action=action, actor_id=str(user["id"]), note=note))


def view(record: ExposureRecord) -> dict:
    return {
        **record.model_dump(mode="json", exclude={"incoming_bundle"}),
        "assessment": evidence.assess(record),
        "ablation": evidence.ablation(record),
        "source_bundle_sha256": fhir.digest(record.incoming_bundle)
        if record.incoming_bundle
        else None,
        "persistence": repository.mode(),
    }


async def current(record_id: str, user: dict, version: int) -> ExposureRecord:
    record = await repository.get(user["organization_id"], record_id)
    if record.version != version:
        raise HTTPException(409, "Record changed; reload before retrying")
    return record


def patient(org: str, patient_id: str):
    from app.oncotwin.store import get_store

    try:
        return get_store(org).patient(patient_id).record().profile
    except KeyError as exc:
        raise HTTPException(404, "Patient not found in this organisation") from exc


@router.get("/meta")
async def meta() -> dict:
    return {
        "product": "ClinCase One Health",
        "primary_track": "Track 7 — Digital Health Standards",
        "supporting_track": "Track 3 — AI-Supported Assessment",
        "standards": fhir.STANDARDS,
        "persistence": repository.mode(),
        "notice": evidence.NOTICE,
        "novelty": [
            "Evidence-gated clinical connection",
            "Missing-evidence ablation",
            "FHIR semantic round-trip",
            "Consent-aware cross-module context",
        ],
    }


@router.get("/patients")
async def patients(user: dict = Depends(reviewer)) -> dict:
    from app.oncotwin.store import get_store

    return {
        "patients": [
            {
                "id": pid,
                "label": p.record().profile.label,
                "synthetic": p.record().profile.synthetic,
            }
            for pid, p in get_store(user["organization_id"]).patients.items()
        ]
    }


@router.get("/exposures")
async def records(
    patient_id: str | None = Query(None, max_length=80),
    case_id: str | None = Query(None, max_length=100),
    user: dict = Depends(reviewer),
) -> dict:
    rows = await repository.list_records(user["organization_id"])
    if patient_id:
        patient(user["organization_id"], patient_id)
        rows = [
            r
            for r in rows
            if r.history and r.history.patient_id == patient_id and not r.consent_withdrawn
        ]
    if case_id:
        rows = [r for r in rows if r.case_id == case_id and not r.consent_withdrawn]
    return {
        "records": [view(r) for r in sorted(rows, key=lambda r: r.created_at, reverse=True)],
        "persistence": repository.mode(),
    }


@router.post("/exposures", status_code=201)
async def create(
    payload: ExposureCreate, user: dict = Depends(reviewer), st=Depends(org_store)
) -> dict:
    obs = st.observation(payload.observation_id)
    if not obs:
        raise HTTPException(404, "Source observation not found in this organisation")
    record = ExposureRecord(
        organization_id=user["organization_id"],
        observation_id=obs.id,
        waterbody_id=obs.waterbody_id,
        waterbody_name=obs.waterbody_name,
        synthetic=obs.is_demo,
        sample=payload.sample,
    )
    event(record, user, "created", "Laboratory report submitted; independent verification required")
    return view(await repository.save(record))


@router.get("/exposures/{record_id}")
async def detail(record_id: str, user: dict = Depends(reviewer)) -> dict:
    return view(await repository.get(user["organization_id"], record_id))


@router.post("/exposures/{record_id}/verify")
async def verify(record_id: str, payload: Attestation, user: dict = Depends(reviewer)) -> dict:
    record = await current(record_id, user, payload.expected_version)
    record.lab_verified = True
    event(record, user, "laboratory_verified", payload.note)
    return view(await repository.save(record, payload.expected_version))


@router.post("/exposures/{record_id}/link")
async def link(record_id: str, payload: LinkRequest, user: dict = Depends(reviewer)) -> dict:
    record = await current(record_id, user, payload.expected_version)
    h = payload.history
    if not h.consent_recorded:
        raise HTTPException(422, "Record consent before linking clinical context")
    profile = patient(user["organization_id"], h.patient_id)
    if profile.synthetic != record.synthetic:
        raise HTTPException(422, "Synthetic and non-synthetic evidence cannot be linked")
    if record.history and record.history.patient_id != h.patient_id:
        raise HTTPException(409, "Patient binding is immutable; create another evidence record")
    if record.consent_withdrawn:
        raise HTTPException(
            409, "Withdrawn evidence cannot be reactivated; create a new record with new consent"
        )
    record.history = h
    record.review = "pending"
    record.case_id = None
    event(
        record,
        user,
        "exposure_linked",
        "Recorded consent and source-to-person history; previous review invalidated",
    )
    return view(await repository.save(record, payload.expected_version))


@router.post("/exposures/{record_id}/review")
async def review(record_id: str, payload: ReviewRequest, user: dict = Depends(reviewer)) -> dict:
    record = await current(record_id, user, payload.expected_version)
    if payload.decision == "reviewed" and not evidence.assess(record)["eligible_for_review"]:
        raise HTTPException(409, "Evidence gates are incomplete; request more information instead")
    record.review = payload.decision
    if payload.decision != "reviewed":
        record.case_id = None
    event(record, user, "clinical_" + payload.decision, payload.note)
    return view(await repository.save(record, payload.expected_version))


@router.post("/exposures/{record_id}/withdraw-consent")
async def withdraw(record_id: str, payload: Attestation, user: dict = Depends(reviewer)) -> dict:
    record = await current(record_id, user, payload.expected_version)
    if not record.history:
        raise HTTPException(409, "No patient consent has been recorded")
    record.consent_withdrawn = True
    record.case_id = None
    record.review = "pending"
    event(record, user, "consent_withdrawn", payload.note)
    return view(await repository.save(record, payload.expected_version))


@router.post("/exposures/{record_id}/case-link")
async def case_link(
    record_id: str, payload: CaseLinkRequest, user: dict = Depends(reviewer)
) -> dict:
    record = await current(record_id, user, payload.expected_version)
    if evidence.assess(record)["state"] != "reviewed_exposure_context":
        raise HTTPException(
            409, "Review the complete exposure evidence before linking a clinical case"
        )
    if repository.mode() != "postgresql":
        raise HTTPException(503, "ClinCase case linking requires the clinical database")
    row = await db.fetchrow(
        "SELECT id FROM cases WHERE id=$1 AND organization_id=$2",
        payload.case_id,
        user["organization_id"],
    )
    if not row:
        raise HTTPException(404, "Clinical case not found in this organisation")
    record.case_id = payload.case_id
    event(
        record,
        user,
        "case_linked",
        "Same-patient relationship attested by reviewer: " + payload.note,
    )
    return view(await repository.save(record, payload.expected_version))


@router.get("/case-candidates")
async def case_candidates(
    limit: int = Query(100, ge=1, le=200), user: dict = Depends(reviewer)
) -> dict:
    """List same-tenant cases for an explicit reviewer-attested connection."""
    if repository.mode() != "postgresql":
        return {
            "available": False,
            "cases": [],
            "reason": "Persistent PostgreSQL case storage is required",
        }
    rows = await db.fetch(
        """SELECT id, patient_initials, requested_treatment_name, status
           FROM cases WHERE organization_id=$1
           ORDER BY created_at DESC, id LIMIT $2""",
        user["organization_id"],
        limit,
    )
    return {
        "available": True,
        "cases": [
            {
                "id": row["id"],
                "patient_initials": row["patient_initials"],
                "treatment": row["requested_treatment_name"],
                "status": row["status"],
            }
            for row in rows
        ],
    }


@router.get("/environmental-tasks")
async def environmental_tasks(user: dict = Depends(get_current_user)) -> dict:
    # Deliberate allowlist: never expose patient IDs, consent, clinical status or free text.
    rows = await repository.list_records(user["organization_id"])
    return {
        "tasks": [
            {
                "id": r.id,
                "waterbody_name": r.waterbody_name,
                "observation_id": r.observation_id,
                "status": r.followup_status,
                "synthetic": r.synthetic,
                "action": "Investigate source and obtain a documented retest",
            }
            for r in rows
        ]
    }


@router.post("/exposures/{record_id}/followup")
async def followup(
    record_id: str, payload: FollowupRequest, user: dict = Depends(reviewer)
) -> dict:
    record = await current(record_id, user, payload.expected_version)
    record.followup_status = payload.status
    record.followup_evidence_reference = payload.evidence_reference or None
    event(record, user, "environmental_" + payload.status, payload.note)
    return view(await repository.save(record, payload.expected_version))


@router.get("/exposures/{record_id}/fhir")
async def export(record_id: str, user: dict = Depends(reviewer)) -> dict:
    record = await repository.get(user["organization_id"], record_id)
    if record.consent_withdrawn:
        raise HTTPException(409, "Clinical exchange disabled after consent withdrawal")
    bundle = fhir.export(record)
    result = fhir.validate(bundle)
    decoded = fhir.read_evidence(bundle)
    result["roundtrip"] = {
        "sample_preserved": decoded["sample"] == record.sample.model_dump(mode="json"),
        "history_preserved": decoded["history"]
        == (record.history.model_dump(mode="json") if record.history else None),
        "trust_policy": "Incoming reviewer identity and consent claims are retained as source evidence, never auto-approved locally.",
    }
    return {"bundle": bundle, "validation": result}


class ExchangeRequest(StrictModel):
    bundle: dict[str, Any]


class ImportRequest(ExchangeRequest):
    observation_id: str = Field(min_length=1, max_length=100)


@router.post("/exchange/validate")
async def validate_exchange(payload: ExchangeRequest, _user: dict = Depends(reviewer)) -> dict:
    result = fhir.validate(payload.bundle)
    return {
        **result,
        "preview": fhir.read_evidence(payload.bundle) if result["valid"] else None,
        "import_policy": "New unverified record; local observation and consent must be re-established. No patient record is overwritten.",
    }


@router.post("/exchange/import", status_code=201)
async def import_exchange(
    payload: ImportRequest, user: dict = Depends(reviewer), st=Depends(org_store)
) -> dict:
    result = fhir.validate(payload.bundle)
    if not result["valid"]:
        raise HTTPException(422, result["operation_outcome"])
    obs = st.observation(payload.observation_id)
    if not obs:
        raise HTTPException(404, "Local source observation not found")
    is_synthetic = {"system": fhir.SYSTEM, "code": "synthetic"} in payload.bundle["meta"]["tag"]
    if is_synthetic != obs.is_demo:
        raise HTTPException(422, "Source and destination demonstration labels differ")
    # Reject duplicate imports in normal use; IDs scoped to tenant make the write atomic.
    decoded = fhir.read_evidence(payload.bundle)
    record = ExposureRecord(
        id="oh-" + fhir.digest([payload.observation_id, result["sha256"]])[:20],
        organization_id=user["organization_id"],
        observation_id=obs.id,
        waterbody_id=obs.waterbody_id,
        waterbody_name=obs.waterbody_name,
        sample=LabSample.model_validate(decoded["sample"]),
        synthetic=obs.is_demo,
        incoming_bundle=payload.bundle,
    )
    event(
        record,
        user,
        "fhir_imported",
        "Source digest " + result["sha256"] + "; verification and patient consent reset",
    )
    return view(await repository.save(record))


@router.post("/demo", status_code=201)
async def demo(user: dict = Depends(reviewer), st=Depends(org_store)) -> dict:
    # No pre-approved findings: users perform every trust transition in the UI.
    time = now()
    obs = await aqua_service.create_observation(
        st,
        ObservationCreate(
            waterbody_name="DEMO Urban Brook",
            observed_at=time - timedelta(days=4),
            observer_note="Synthetic citizen report triggering source investigation. No contaminant inferred from appearance.",
        ),
        observer_id=user["id"],
        observer_label="Synthetic demonstration",
        is_demo=True,
    )
    record = ExposureRecord(
        organization_id=user["organization_id"],
        observation_id=obs.id,
        waterbody_id=obs.waterbody_id,
        waterbody_name=obs.waterbody_name,
        synthetic=True,
        sample=LabSample(
            sample_id="DEMO-AS-001",
            location_name="DEMO household drinking-water outlet",
            kind="drinking_water",
            laboratory="Synthetic laboratory",
            collector="Synthetic sampling team",
            report_reference="DEMO-REPORT-001",
            method="Synthetic ICP-MS result (not a real assay)",
            collected_at=time - timedelta(days=3),
            reported_at=time - timedelta(days=2),
            value=25,
            unit="ug/L",
        ),
    )
    event(
        record,
        user,
        "demo_created",
        "Synthetic lab evidence; reviewer verification and consent still required",
    )
    return view(await repository.save(record))
