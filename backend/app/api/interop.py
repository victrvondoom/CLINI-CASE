"""Additive authenticated Track 7 interoperability gateway."""

import json
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

import httpx
from fastapi import APIRouter, Depends, HTTPException

from app.auth import require_role
from app.config import settings
from app.interop import adapter, repository, service
from app.interop.models import (
    TARGETS,
    Analyze,
    Command,
    Decision,
    Job,
    Source,
    Transfer,
    ValidationRequest,
)
from app.onehealth import evidence, fhir
from app.onehealth.models import LabSample
from app.onehealth.repository import mode

router = APIRouter(prefix="/interop", tags=["interop-track7"])
reviewer = require_role("reviewer", "admin")


def view(j: Job) -> dict[str, Any]:
    data = j.model_dump(mode="json")
    mapped = {m.target for m in j.mappings if m.target and m.decision != "rejected"}
    required = {k for k, field in LabSample.model_fields.items() if field.is_required()} | {
        "unit",
        "analyte",
        "waterbody_name",
    }
    if any(m.source_field.lower() == "arsenic" and m.concept for m in j.mappings):
        mapped.add("analyte")
    data["schema"] = {
        "fields": [{"name": k, "detected_type": type(v).__name__} for k, v in j.fields.items()],
        "missing_required_fields": sorted(required - mapped),
        "ambiguities": [
            m.source_field
            for m in j.mappings
            if m.decision == "pending"
            and (
                not m.target
                or m.confidence < 0.8
                or (m.source_field.lower() == "arsenic" and not m.concept)
            )
        ],
    }
    data["metrics"] = {
        "fields_detected": len(j.fields),
        "fields_mapped": sum(m.target is not None and m.decision != "rejected" for m in j.mappings),
        "mappings_requiring_review": sum(m.decision == "pending" for m in j.mappings),
        "resources_generated": len(j.bundle.get("entry", [])) if j.bundle else 0,
        "checks_passed": sum(c["passed"] is True for c in (j.validation or {}).get("checks", [])),
        "checks_failed": sum(c["passed"] is False for c in (j.validation or {}).get("checks", [])),
    }
    data["assessment"] = (
        service.assessment(j.bundle) if j.bundle and service.validate(j.bundle)["valid"] else None
    )
    return data


async def current(c: Command, user: dict[str, Any]) -> Job:
    j = await repository.get(user["organization_id"], c.job_id)
    if j.version != c.expected_version:
        raise HTTPException(409, "Job changed; reload before retrying")
    return j


@router.get("/meta")
async def meta(user: dict[str, Any] = Depends(reviewer)) -> dict[str, Any]:
    return {
        "product": "CLINI-CASE One Health Interoperability Gateway",
        "standards": fhir.STANDARDS,
        "targets": TARGETS,
        "persistence": mode(),
        "notice": evidence.NOTICE,
        "receiver_mode": "HTTP network"
        if settings.INTEROP_RECEIVER_URL
        else "Independent ASGI app over in-process HTTP; separate SQLite storage",
    }


@router.post("/import", status_code=201)
@router.post("/simulators/lab/send", status_code=201)
async def ingest(payload: Source, user: dict[str, Any] = Depends(reviewer)) -> dict[str, Any]:
    j = Job(organization_id=user["organization_id"], source=payload)
    service.event(
        j,
        "source_received",
        user["id"],
        source_system=payload.source_system,
        original_record_id=payload.original_record_id,
        source_sha256=fhir.digest(payload.payload),
    )
    service.discover(j)
    return view(await repository.save(j))


@router.post("/demo", status_code=201)
async def demo(user: dict[str, Any] = Depends(reviewer)) -> dict[str, Any]:
    payload = json.loads(
        (Path(__file__).parents[2] / "data" / "interop" / "environmental.json").read_text()
    )
    return await ingest(
        Source(
            source_system="Synthetic Environmental Lab A",
            original_record_id="SYN-AS-001",
            payload=payload,
            synthetic=True,
        ),
        user,
    )


@router.get("/jobs/{job_id}")
@router.get("/events/{job_id}")
@router.get("/bundle/{job_id}")
@router.get("/transfers/{job_id}")
async def detail(job_id: str, user: dict[str, Any] = Depends(reviewer)) -> dict[str, Any]:
    return view(await repository.get(user["organization_id"], job_id))


@router.post("/analyze-schema")
@router.post("/map")
async def analyze(payload: Analyze, user: dict[str, Any] = Depends(reviewer)) -> dict[str, Any]:
    j = await current(payload, user)
    await service.analyze(j, payload.use_ai)
    return view(await repository.save(j, payload.expected_version))


async def decide(
    job_id: str, payload: Decision, user: dict[str, Any], decision: Literal["accepted", "rejected"]
) -> dict[str, Any]:
    if payload.job_id != job_id:
        raise HTTPException(422, "Job identity mismatch")
    j = await current(payload, user)
    m = next((m for m in j.mappings if m.source_field == payload.source_field), None)
    if not m:
        raise HTTPException(404, "Source mapping not found")
    previous_target = m.target
    if decision == "accepted":
        target = payload.target or m.target
        if target not in TARGETS:
            raise HTTPException(422, "Choose a supported target; unknown fields may be rejected")
        m.target = target
        m.fhir_target = TARGETS[target]
        if payload.concept:
            m.concept = payload.concept
            m.terminology_status = "local_code"
        if m.source_field.strip().lower() == "arsenic" and not m.concept:
            raise HTTPException(422, "Explicitly confirm total or inorganic arsenic")
    m.decision = decision
    m.reviewer = str(user["id"])
    j.mapping_version += 1
    j.bundle = j.validation = j.normalized = None
    service.event(
        j,
        "mapping_" + decision,
        user["id"],
        source_field=m.source_field,
        target=m.target,
        previous_target=previous_target,
        concept=m.concept,
        mapping_version=j.mapping_version,
    )
    return view(await repository.save(j, payload.expected_version))


@router.post("/mappings/{job_id}/approve")
async def approve(
    job_id: str, payload: Decision, user: dict[str, Any] = Depends(reviewer)
) -> dict[str, Any]:
    return await decide(job_id, payload, user, "accepted")


@router.post("/mappings/{job_id}/reject")
async def reject(
    job_id: str, payload: Decision, user: dict[str, Any] = Depends(reviewer)
) -> dict[str, Any]:
    return await decide(job_id, payload, user, "rejected")


@router.post("/generate-fhir")
async def generate(payload: Command, user: dict[str, Any] = Depends(reviewer)) -> dict[str, Any]:
    j = await current(payload, user)
    record = service.normalize(j)
    j.normalized = record.sample.model_dump(mode="json")
    j.bundle = fhir.export(record)
    j.validation = service.validate(j.bundle)
    decoded = fhir.read_evidence(j.bundle)
    preserved = [k for k, v in j.normalized.items() if decoded["sample"].get(k) == v]
    j.validation["roundtrip"] = {
        "fields_preserved": len(preserved),
        "fields_total": len(j.normalized),
        "sample_preserved": decoded["sample"] == j.normalized,
    }
    if not j.validation["roundtrip"]["sample_preserved"]:
        raise HTTPException(422, "Round-trip preservation failed")
    service.event(
        j,
        "bundle_generated",
        user["id"],
        sha256=fhir.digest(j.bundle),
        mapping_version=j.mapping_version,
    )
    service.event(
        j,
        "validation_passed" if j.validation["valid"] else "validation_failed",
        "validation-gate",
        status="ok" if j.validation["valid"] else "rejected",
        sha256=j.validation["sha256"],
    )
    return view(await repository.save(j, payload.expected_version))


@router.post("/validate")
async def validate(
    payload: ValidationRequest, user: dict[str, Any] = Depends(reviewer)
) -> dict[str, Any]:
    j = await current(payload, user)
    j.validation = service.validate(payload.bundle)
    # Editable challenge payload is retained independently of the approved generated bundle.
    service.event(
        j,
        "validation_passed" if j.validation["valid"] else "validation_failed",
        user["id"],
        status="ok" if j.validation["valid"] else "rejected",
        sha256=j.validation["sha256"],
    )
    return view(await repository.save(j, payload.expected_version))


@router.post("/transfer")
async def transfer(payload: Transfer, user: dict[str, Any] = Depends(reviewer)) -> dict[str, Any]:
    j = await current(payload, user)
    if not j.bundle:
        raise HTTPException(409, "Generate a bundle first")
    result = service.validate(j.bundle)
    if (
        not result["valid"]
        or not j.validation
        or not j.validation["valid"]
        or j.validation["sha256"] != result["sha256"]
    ):
        raise HTTPException(409, "Validate the exact generated bundle before transfer")
    transfer = {
        "id": "tr-" + uuid4().hex,
        "correlation_id": j.id,
        "receiver": "clinical",
        "status": "processing",
        "sha256": result["sha256"],
    }
    j.transfers.append(transfer)
    service.event(
        j, "transfer_processing", user["id"], receiver="clinical", sha256=result["sha256"]
    )
    j = await repository.save(j, payload.expected_version)
    transfer = j.transfers[-1]
    assert j.bundle is not None
    try:
        ack = await adapter.exchange(user["organization_id"], j.id, j.bundle)
        if (
            ack.get("status") != "delivered"
            or ack.get("sha256") != result["sha256"]
            or ack.get("correlation_id") != j.id
            or ack.get("resources_acknowledged") != len(j.bundle["entry"])
        ):
            raise ValueError("Receiver acknowledgement does not match package")
        transfer.update(status="delivered", acknowledgement=ack)
    except httpx.HTTPStatusError as exc:
        transfer.update(
            status="rejected" if exc.response.status_code < 500 else "failed",
            error="Receiver HTTP " + str(exc.response.status_code),
        )
    except Exception as exc:
        transfer.update(
            status="failed",
            error=type(exc).__name__ + ": receiver unavailable or invalid acknowledgement",
        )
    service.event(
        j,
        "transfer_" + transfer["status"],
        "external-adapter",
        status=transfer["status"],
        receiver="clinical",
        sha256=result["sha256"],
    )
    return view(await repository.save(j, j.version))


@router.post("/return")
async def returned(payload: Command, user: dict[str, Any] = Depends(reviewer)) -> dict[str, Any]:
    j = await current(payload, user)
    if not j.bundle or not any(
        t["status"] == "delivered" and t["sha256"] == fhir.digest(j.bundle) for t in j.transfers
    ):
        raise HTTPException(409, "Return requires a delivered current bundle")
    try:
        received = await adapter.exchange(user["organization_id"], j.id)
    except httpx.HTTPError as exc:
        raise HTTPException(502, "Receiver return exchange failed") from exc
    validation = service.validate(received["bundle"])
    if not validation["valid"]:
        raise HTTPException(422, validation)
    if validation["sha256"] != fhir.digest(j.bundle):
        raise HTTPException(409, "Returned package does not match the delivered bundle")
    decoded = fhir.read_evidence(received["bundle"])
    try:
        lab_ack = await adapter.exchange(
            user["organization_id"], j.id, received["bundle"], destination="lab"
        )
    except httpx.HTTPError as exc:
        raise HTTPException(502, "Lab A rejected return exchange") from exc
    if (
        lab_ack.get("sha256") != validation["sha256"]
        or lab_ack.get("status") != "delivered"
        or lab_ack.get("correlation_id") != "lab-" + j.id
        or lab_ack.get("resources_acknowledged") != len(received["bundle"]["entry"])
    ):
        raise HTTPException(502, "Lab A return acknowledgement mismatch")
    service.event(
        j,
        "return_exchange_validated",
        "external-adapter",
        sha256=validation["sha256"],
        sample_preserved=decoded["sample"] == j.normalized,
    )
    saved = await repository.save(j, j.version)
    return {
        "job": view(saved),
        "returned_bundle": received["bundle"],
        "lab_representation": decoded,
        "receiver_representation": received["representation"],
        "validation": validation,
        "lab_acknowledgement": lab_ack,
    }
