"""Additive authenticated Track 7 interoperability gateway."""

import json
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field

from app.auth import require_role
from app.config import settings
from app.interop import adapter, adapters, external_fhir, repository, service, triage
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
from app.onehealth import evidence, fhir, passport
from app.onehealth import repository as exposures
from app.onehealth.models import AuditEvent, ExposureRecord, LabSample, StrictModel
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
    if any(
        m.source_field.strip().lower().replace(" ", "_")
        in {"arsenic", "arsenic_dissolved", "total_arsenic", "inorganic_arsenic"}
        and (m.concept or m.source_field.strip().lower() != "arsenic")
        for m in j.mappings
    ):
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
    data["loss_report"] = service.loss_report(j)
    data["trust_states"] = service.trust_states(j)
    data["passport_integrity"] = passport.verify(j.model_dump(mode="json"))
    data["mapping_mode"] = (
        "AI suggestions; human approval required"
        if j.ai_status.startswith("model_suggestions_received")
        else "Deterministic reference mapping"
    )
    data["semantic_firewall"] = {
        "status": "review_required"
        if any(m.decision == "pending" for m in j.mappings)
        else "review_complete"
        if j.mappings
        else "not_started",
        "ai_authority": "Suggest allowlisted field targets only; AI cannot assign analyte concepts or approve mappings.",
        "ai_input": "Source field names and the target allowlist; no measurements or patient context.",
        "ambiguous_fields": [
            m.source_field
            for m in j.mappings
            if m.source_field.strip().lower() == "arsenic" and not m.concept
        ],
        "blocked_inferences": [
            "A generic arsenic label cannot establish total versus inorganic arsenic.",
            "Dissolved arsenic does not establish inorganic speciation.",
            "A human-approved mapping does not verify a laboratory result or establish health causation.",
        ],
    }
    data["terminology"] = [
        adapters.LocalArsenicTerminology().resolve(code)
        for code in {m.concept for m in j.mappings if m.concept}
    ]
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
    adapters.SyntheticLabAdapter().discover(j)
    return view(await repository.save(j))


@router.post("/demo", status_code=201)
async def demo(
    variant: Literal["ambiguous", "dissolved"] = "ambiguous",
    user: dict[str, Any] = Depends(reviewer),
) -> dict[str, Any]:
    filename = "environmental-dissolved.json" if variant == "dissolved" else "environmental.json"
    payload = json.loads(
        (Path(__file__).parents[2] / "data" / "interop" / filename).read_text()
    )
    return await ingest(
        Source(
            source_system="Synthetic Environmental Lab A",
            original_record_id="SYN-AS-DISS-001" if variant == "dissolved" else "SYN-AS-001",
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
    return await detail_view(await repository.get(user["organization_id"], job_id))


async def detail_view(j: Job) -> dict[str, Any]:
    """The consent-aware job view; shared by the detail routes and the unified journey."""
    data = view(j)
    if j.exposure_id and (await exposures.get(j.organization_id, j.exposure_id)).consent_withdrawn:
        data.update(
            bundle=None,
            validation=None,
            normalized=None,
            assessment=None,
            consent_status="WITHDRAWN",
        )
        data["source"]["payload"] = "Sharing withdrawn; historical source remains in scoped storage"
        data["trust_states"].append("WITHDRAWN")
        for transfer in data["transfers"]:
            if transfer.get("acknowledgement"):
                transfer["acknowledgement"].pop("representation", None)
    return data


@router.post("/analyze-schema")
@router.post("/map")
async def analyze(payload: Analyze, user: dict[str, Any] = Depends(reviewer)) -> dict[str, Any]:
    j = await current(payload, user)
    if j.exposure_id:
        raise HTTPException(
            409, "Mapping is bound to an evidence record; import a new source to remap"
        )
    await service.analyze(j, payload.use_ai)
    return view(await repository.save(j, payload.expected_version))


async def decide(
    job_id: str, payload: Decision, user: dict[str, Any], decision: Literal["accepted", "rejected"]
) -> dict[str, Any]:
    if payload.job_id != job_id:
        raise HTTPException(422, "Job identity mismatch")
    j = await current(payload, user)
    if j.exposure_id:
        raise HTTPException(
            409, "Mapping is bound to an evidence record; import a new source to remap"
        )
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
        if m.source_field.strip().lower().replace(" ", "_") == "arsenic" and payload.concept not in (
            "total_arsenic",
            "inorganic_arsenic",
        ):
            raise HTTPException(422, "Generic arsenic requires explicit total or inorganic review")
        if payload.concept:
            m.concept = payload.concept
            m.terminology_status = adapters.LocalArsenicTerminology().resolve(payload.concept)[
                "status"
            ].lower()
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


@router.post("/mappings/{job_id}/approve-safe")
async def approve_safe(
    job_id: str, payload: Command, user: dict[str, Any] = Depends(reviewer)
) -> dict[str, Any]:
    """Approve only mappings that triage classifies as safe, atomically, one audit event each.

    The generic arsenic label, unresolved targets, AI-only and low-confidence mappings never qualify;
    they stay individual reviewer decisions. Eligibility is decided here, never by the client.
    """
    if payload.job_id != job_id:
        raise HTTPException(422, "Job identity mismatch")
    j = await current(payload, user)
    if j.exposure_id:
        raise HTTPException(
            409, "Mapping is bound to an evidence record; import a new source to remap"
        )
    safe = [m for m in j.mappings if triage.classify(m.model_dump()) == "safe"]
    if not safe:
        raise HTTPException(409, "No pending mapping is eligible for batch approval")
    for m in safe:
        assert m.target is not None  # guaranteed by triage: safe mappings have an allowlisted target
        m.fhir_target = TARGETS[m.target]
        m.decision = "accepted"
        m.reviewer = str(user["id"])
        j.mapping_version += 1
        service.event(
            j,
            "mapping_accepted",
            user["id"],
            source_field=m.source_field,
            target=m.target,
            previous_target=m.target,
            concept=m.concept,
            mapping_version=j.mapping_version,
            batch="safe",
        )
    j.bundle = j.validation = j.normalized = None
    return view(await repository.save(j, payload.expected_version))


@router.post("/mappings/{job_id}/reject")
async def reject(
    job_id: str, payload: Decision, user: dict[str, Any] = Depends(reviewer)
) -> dict[str, Any]:
    return await decide(job_id, payload, user, "rejected")


@router.post("/generate-fhir")
async def generate(payload: Command, user: dict[str, Any] = Depends(reviewer)) -> dict[str, Any]:
    j = await current(payload, user)
    record = (
        await exposures.get(j.organization_id, j.exposure_id)
        if j.exposure_id
        else service.normalize(j)
    )
    if record.consent_withdrawn:
        raise HTTPException(409, "Exchange disabled after consent withdrawal")
    if j.exposure_id:
        j.exposure_version = record.version
    normalized = record.sample.model_dump(mode="json")
    j.normalized = normalized
    j.bundle = adapters.OAHFHIRAdapter().generate(record)
    j.validation = service.validate(j.bundle)
    decoded = fhir.read_evidence(j.bundle)
    preserved = [k for k, v in normalized.items() if decoded["sample"].get(k) == v]
    j.validation["roundtrip"] = {
        "fields_preserved": len(preserved),
        "fields_total": len(normalized),
        "sample_preserved": decoded["sample"] == normalized,
        "waterbody_preserved": decoded["waterbody_name"] == record.waterbody_name,
    }
    if not (
        j.validation["roundtrip"]["sample_preserved"]
        and j.validation["roundtrip"]["waterbody_preserved"]
    ):
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
    await check_binding(j)
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
    correlation = j.id + "-v" + str(j.exposure_version) if j.exposure_id else j.id
    transfer = {
        "id": "tr-" + uuid4().hex,
        "correlation_id": correlation,
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
        ack = await adapters.SyntheticClinicalReceiver().send(
            user["organization_id"], correlation, j.bundle
        )
        if (
            ack.get("status") != "delivered"
            or ack.get("sha256") != result["sha256"]
            or ack.get("correlation_id") != correlation
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
    await check_binding(j)
    if not j.bundle or not any(
        t["status"] == "delivered" and t["sha256"] == fhir.digest(j.bundle) for t in j.transfers
    ):
        raise HTTPException(409, "Return requires a delivered current bundle")
    correlation = next(
        t["correlation_id"]
        for t in reversed(j.transfers)
        if t["status"] == "delivered" and t["sha256"] == fhir.digest(j.bundle)
    )
    try:
        received = await adapter.exchange(user["organization_id"], correlation)
    except httpx.HTTPError as exc:
        raise HTTPException(502, "Receiver return exchange failed") from exc
    validation = service.validate(received["bundle"])
    if not validation["valid"]:
        raise HTTPException(422, validation)
    original = fhir.read_evidence(j.bundle)
    decoded = fhir.read_evidence(received["bundle"])
    expected_observation_id = j.source.original_record_id
    if j.exposure_id:
        expected_observation_id = (await exposures.get(j.organization_id, j.exposure_id)).observation_id
    semantic_fields = [
        {
            "field": key,
            "preserved": original["sample"].get(key)
            == decoded["sample"].get(key)
            == (j.normalized or {}).get(key),
        }
        for key in LabSample.model_fields
    ]
    semantic_fields.extend(
        [
            {
                "field": "waterbody_name",
                "preserved": original["waterbody_name"] == decoded["waterbody_name"],
            },
            {
                "field": "source_observation_id",
                "preserved": original["source_observation_id"]
                == decoded["source_observation_id"]
                == expected_observation_id,
            },
            {"field": "exposure_history", "preserved": original["history"] == decoded["history"]},
            {"field": "provenance", "preserved": original["provenance"] == decoded["provenance"]},
        ]
    )
    original_ids = {
        (entry["resource"]["resourceType"], entry["resource"]["id"])
        for entry in j.bundle.get("entry", [])
    }
    returned_ids = {
        (entry["resource"]["resourceType"], entry["resource"]["id"])
        for entry in received["bundle"].get("entry", [])
    }
    ids_reassigned = (
        len(original_ids) == len(returned_ids) == len(j.bundle.get("entry", []))
        and not original_ids.intersection(returned_ids)
        and received.get("resource_ids_reassigned") is True
    )
    roundtrip = {
        "status": "passed"
        if all(field["preserved"] for field in semantic_fields) and ids_reassigned
        else "failed",
        "fields": semantic_fields,
        "fields_preserved": sum(field["preserved"] for field in semantic_fields),
        "fields_total": len(semantic_fields),
        "resource_ids_reassigned": ids_reassigned,
        "source_sha256": fhir.digest(j.bundle),
        "returned_sha256": validation["sha256"],
    }
    if roundtrip["status"] != "passed":
        raise HTTPException(409, "Returned FHIR failed semantic round-trip verification")
    try:
        lab_ack = await adapter.exchange(
            user["organization_id"], correlation, received["bundle"], destination="lab"
        )
    except httpx.HTTPError as exc:
        raise HTTPException(502, "Lab A rejected return exchange") from exc
    if (
        lab_ack.get("sha256") != validation["sha256"]
        or lab_ack.get("status") != "delivered"
        or lab_ack.get("correlation_id") != correlation
        or lab_ack.get("resources_acknowledged") != len(received["bundle"]["entry"])
    ):
        raise HTTPException(502, "Lab A return acknowledgement mismatch")
    service.event(
        j,
        "return_exchange_validated",
        "external-adapter",
        sha256=validation["sha256"],
        sample_preserved=all(field["preserved"] for field in semantic_fields),
        resource_ids_reassigned=ids_reassigned,
        source_sha256=roundtrip["source_sha256"],
        returned_sha256=roundtrip["returned_sha256"],
    )
    saved_validation = dict(j.validation or {})
    saved_validation["roundtrip"] = roundtrip
    j.validation = saved_validation
    for transfer in reversed(j.transfers):
        if transfer.get("status") == "delivered" and transfer.get("sha256") == fhir.digest(j.bundle):
            transfer["roundtrip"] = roundtrip
            break
    saved = await repository.save(j, j.version)
    return {
        "job": view(saved),
        "returned_bundle": received["bundle"],
        "lab_representation": decoded,
        "receiver_representation": received["representation"],
        "validation": validation,
        "roundtrip": roundtrip,
        "lab_acknowledgement": lab_ack,
    }


@router.post("/external-check")
async def external_check(payload: Command, user: dict[str, Any] = Depends(reviewer)) -> dict[str, Any]:
    """Optional third-party FHIR R4 check: POST the exact validated Bundle, read it back, compare.

    Synthetic data only. Failure never changes the workflow; the attempt is recorded as an event.
    """
    j = await current(payload, user)
    await check_binding(j)
    if not j.bundle or not service.validate(j.bundle)["valid"]:
        raise HTTPException(409, "Generate and validate a bundle before the third-party check")
    try:
        result = await external_fhir.exchange(
            j.bundle,
            synthetic=j.source.synthetic,
            base_url=settings.EXTERNAL_FHIR_BASE_URL,
            request_timeout_s=settings.EXTERNAL_FHIR_TIMEOUT_S,
            system_trust=settings.EXTERNAL_FHIR_SYSTEM_TRUST,
        )
    except external_fhir.ExternalFhirRefusedError as exc:
        raise HTTPException(422, str(exc)) from exc
    semantic = result["semantic"] or {}
    service.event(
        j,
        "external_fhir_check_" + result["status"],
        str(user["id"]),
        status=result["status"],
        endpoint=result["endpoint"],
        resource_type=result["resource_type"],
        resource_id=result["resource_id"],
        fields_preserved=semantic.get("fields_preserved"),
        fields_total=semantic.get("fields_total"),
        detail=result["detail"],
        scope_note=result["scope_note"],
    )
    saved = await repository.save(j, payload.expected_version)
    return {"job": view(saved), "external": result}


async def check_binding(j: Job) -> None:
    if j.exposure_id:
        record = await exposures.get(j.organization_id, j.exposure_id)
        if record.consent_withdrawn:
            raise HTTPException(409, "Clinical sharing disabled after consent withdrawal")
        if j.exposure_version != record.version:
            raise HTTPException(
                409, "Evidence changed; regenerate and validate the current record before exchange"
            )


class Bind(Command):
    observation_id: str | None = Field(default=None, max_length=100)


@router.post("/bind-evidence")
async def bind(payload: Bind, user: dict[str, Any] = Depends(reviewer)) -> dict[str, Any]:
    """One explicit connection to the existing workflow; never imports clinical trust."""
    from app.api.aquahealth import org_store
    from app.aquahealth import service as aqua_service
    from app.aquahealth.models import ObservationCreate

    j = await current(payload, user)
    if j.exposure_id:
        return view(j)
    normalized = service.normalize(j)
    if not j.bundle or not service.validate(j.bundle)["valid"]:
        raise HTTPException(409, "Generate a validated bundle before binding evidence")
    st = await org_store(user)
    obs = st.observation(payload.observation_id) if payload.observation_id else None
    if payload.observation_id and not obs:
        raise HTTPException(404, "Observation not found in this organisation")
    if not obs:
        if not j.source.synthetic:
            raise HTTPException(
                422, "Select an existing citizen observation for non-synthetic evidence"
            )
        obs = await aqua_service.create_observation(
            st,
            ObservationCreate(
                waterbody_name=normalized.waterbody_name,
                observed_at=normalized.sample.collected_at,
                observer_note="SYNTHETIC volunteer Mira: source investigation requested; no contaminant inferred from appearance.",
            ),
            observer_id=user["id"],
            observer_label="SYNTHETIC community volunteer",
            is_demo=True,
        )
    if obs.is_demo != j.source.synthetic:
        raise HTTPException(422, "Synthetic classifications must match")
    eid = "oh-" + fhir.digest(j.id)[:20]
    try:
        record = await exposures.get(j.organization_id, eid)
    except HTTPException as exc:
        if exc.status_code != 404:
            raise
        record = ExposureRecord(
            id=eid,
            organization_id=j.organization_id,
            observation_id=obs.id,
            waterbody_id=obs.waterbody_id,
            waterbody_name=obs.waterbody_name,
            synthetic=j.source.synthetic,
            sample=normalized.sample,
            gateway_job_id=j.id,
            incoming_bundle=j.bundle,
        )
        record.audit.append(
            AuditEvent(
                action="gateway_bound",
                actor_id=str(user["id"]),
                note="Confirmed mapping from "
                + j.id
                + "; local laboratory verification, consent and clinical review required",
            )
        )
        try:
            record = await exposures.save(record)
        except HTTPException as exc:
            if exc.status_code != 409:
                raise
            record = await exposures.get(j.organization_id, eid)
    if record.gateway_job_id != j.id or record.sample != normalized.sample:
        raise HTTPException(409, "Existing binding differs from this confirmed mapping")
    j.exposure_id = record.id
    j.exposure_version = None  # Must generate again from locally reviewed evidence.
    service.event(
        j,
        "onehealth_evidence_bound",
        str(user["id"]),
        exposure_id=record.id,
        observation_id=record.observation_id,
    )
    return view(await repository.save(j, payload.expected_version))


class ReviewedSource(StrictModel):
    exposure_id: str = Field(max_length=100)
    expected_version: int = Field(ge=1)


@router.post("/from-evidence", status_code=201)
async def from_evidence(
    payload: ReviewedSource, user: dict[str, Any] = Depends(reviewer)
) -> dict[str, Any]:
    record = await exposures.get(user["organization_id"], payload.exposure_id)
    if record.version != payload.expected_version:
        raise HTTPException(409, "Record changed; reload before retrying")
    if record.consent_withdrawn:
        raise HTTPException(409, "Exchange disabled after consent withdrawal")
    # Existing normalized record is the source; no fabricated AI mapping decisions.
    source = Source(
        source_system="CLINI-CASE One Health reviewed evidence",
        original_record_id=record.id,
        payload={**record.sample.model_dump(mode="json"), "waterbody_name": record.waterbody_name},
        synthetic=record.synthetic,
    )
    j = Job(
        organization_id=user["organization_id"],
        source=source,
        exposure_id=record.id,
        exposure_version=record.version,
    )
    service.discover(j)
    j.normalized = record.sample.model_dump(mode="json")
    j.bundle = fhir.export(record)
    j.validation = service.validate(j.bundle)
    j.ai_status = "normalized_application_record; no model called"
    service.event(
        j,
        "reviewed_evidence_exchange_created",
        str(user["id"]),
        exposure_id=record.id,
        exposure_version=record.version,
        sha256=fhir.digest(j.bundle),
    )
    return view(await repository.save(j))


@router.post("/passport/{job_id}/verify-integrity")
async def verify_integrity(job_id: str, user: dict[str, Any] = Depends(reviewer)) -> dict[str, Any]:
    j = await repository.get(user["organization_id"], job_id)
    return passport.verify(j.model_dump(mode="json"))


@router.get("/passport/{job_id}/export")
async def passport_export(job_id: str, user: dict[str, Any] = Depends(reviewer)) -> dict[str, Any]:
    j = await repository.get(user["organization_id"], job_id)
    await check_binding(j)
    return passport.portable(
        j.model_dump(mode="json"),
        bundle=j.bundle,
        validation=j.validation,
        evidence=service.assessment(j.bundle) if j.bundle else None,
        loss_report=service.loss_report(j),
    )


class PassportVerifyRequest(StrictModel):
    package: dict[str, Any]


@router.get("/passport-signing")
async def passport_signing(user: dict[str, Any] = Depends(reviewer)) -> dict[str, Any]:
    """Whether exports are signed and by which key (id only; never key material)."""
    return passport.signing_status()


@router.post("/passport/verify")
async def passport_verify(
    payload: PassportVerifyRequest, user: dict[str, Any] = Depends(reviewer)
) -> dict[str, Any]:
    """Stateless: verify a submitted passport package. Persists nothing, so it is safe to tamper with."""
    if len(json.dumps(payload.package)) > 1_000_000:
        raise HTTPException(413, "Passport package exceeds the 1 MB verification limit")
    return passport.verify_package(payload.package)


@router.post("/challenge-receiver")
async def challenge(
    payload: ValidationRequest, user: dict[str, Any] = Depends(reviewer)
) -> dict[str, Any]:
    j = await current(payload, user)
    await check_binding(j)
    result = service.validate(payload.bundle)
    if result["valid"]:
        raise HTTPException(422, "This challenge accepts deliberately invalid bundles only")
    attempt: dict[str, Any] = {
        "id": "tr-" + uuid4().hex,
        "correlation_id": j.id + "-challenge-" + uuid4().hex[:12],
        "receiver": "clinical",
        "status": "processing",
        "sha256": fhir.digest(payload.bundle),
        "challenge": True,
    }
    j.transfers.append(attempt)
    service.event(j, "receiver_challenge_processing", str(user["id"]), sha256=attempt["sha256"])
    j = await repository.save(j, payload.expected_version)
    attempt = j.transfers[-1]
    try:
        await adapter.exchange(j.organization_id, attempt["correlation_id"], payload.bundle)
        attempt.update(status="failed", error="Receiver unexpectedly accepted invalid package")
    except httpx.HTTPStatusError as exc:
        attempt.update(
            status="rejected" if exc.response.status_code == 422 else "failed",
            receiver_http=exc.response.status_code,
            rejection=exc.response.json(),
        )
    except httpx.HTTPError:
        attempt.update(
            status="failed", error="Receiver unavailable; rejection was not demonstrated"
        )
    j.validation = result
    service.event(
        j,
        "receiver_challenge_" + attempt["status"],
        "external-adapter",
        status=attempt["status"],
        sha256=attempt["sha256"],
        correction_required=True,
    )
    return view(await repository.save(j, j.version))
