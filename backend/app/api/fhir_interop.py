"""FHIR R4 facade for the Track 7 collection-Bundle exchange contract."""

import json
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.auth import require_role
from app.interop import repository, service
from app.interop.models import Job, Source
from app.onehealth import fhir

router = APIRouter(prefix="/fhir", tags=["fhir-interop"])
reviewer = require_role("reviewer", "admin")
FHIR_JSON = "application/fhir+json"


def _require_fhir_json(request: Request) -> None:
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type != FHIR_JSON:
        raise HTTPException(415, f"Use Content-Type: {FHIR_JSON}")


def _outcome(message: str, severity: str = "error", code: str = "invalid") -> dict[str, Any]:
    return {
        "resourceType": "OperationOutcome",
        "issue": [{"severity": severity, "code": code, "diagnostics": message[:500]}],
    }


def _fhir_response(resource: dict[str, Any], status_code: int = 200, **headers: str) -> Response:
    return Response(
        content=json.dumps(resource, separators=(",", ":")),
        status_code=status_code,
        media_type=FHIR_JSON,
        headers=headers,
    )


async def _body(request: Request) -> dict[str, Any]:
    _require_fhir_json(request)
    try:
        payload = await request.json()
    except (ValueError, UnicodeDecodeError) as exc:
        raise HTTPException(400, "Request body is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise HTTPException(400, "FHIR request body must be a resource object")
    return payload


@router.post("/Bundle", status_code=201)
async def create_bundle(
    request: Request, user: dict[str, Any] = Depends(reviewer)
) -> Response:
    """Store one validated collection Bundle; this endpoint does not execute transactions."""
    payload = await _body(request)
    result = service.validate(payload)
    if not result["valid"]:
        return _fhir_response(result["operation_outcome"], status_code=400)
    identifier = uuid4().hex
    stored_bundle = dict(payload)
    stored_bundle["id"] = identifier
    tags = payload.get("meta", {}).get("tag", [])
    synthetic = {"system": fhir.SYSTEM, "code": "synthetic"} in tags
    job = Job(
        id=identifier,
        organization_id=user["organization_id"],
        source=Source(
            source_system="FHIR R4 client",
            original_record_id=identifier,
            format="fhir",
            payload=stored_bundle,
            synthetic=synthetic,
        ),
    )
    service.event(
        job,
        "fhir_bundle_created",
        str(user["id"]),
        sha256=fhir.digest(stored_bundle),
        source_sha256=result["sha256"],
    )
    saved = await repository.save(job)
    return _fhir_response(
        stored_bundle,
        status_code=201,
        Location=f"/fhir/Bundle/{identifier}",
        ETag=f'W/"{saved.version}"',
    )


@router.get("/Bundle/{bundle_id}")
async def read_bundle(
    bundle_id: str, user: dict[str, Any] = Depends(reviewer)
) -> Response:
    try:
        job = await repository.get(user["organization_id"], bundle_id)
    except HTTPException as exc:
        if exc.status_code == 404:
            return _fhir_response(_outcome("Bundle not found", code="not-found"), 404)
        raise
    if job.source.format != "fhir" or not isinstance(job.source.payload, dict):
        return _fhir_response(_outcome("Bundle not found", code="not-found"), 404)
    return _fhir_response(job.source.payload, ETag=f'W/"{job.version}"')


@router.post("/Bundle/$validate")
@router.post("/$validate", include_in_schema=False)
async def validate_bundle(request: Request, _user: dict[str, Any] = Depends(reviewer)) -> Response:
    """Return a FHIR OperationOutcome; an invalid resource still yields HTTP 200."""
    try:
        payload = await _body(request)
    except HTTPException as exc:
        if exc.status_code == 415:
            raise
        return _fhir_response(_outcome(str(exc.detail)), status_code=400)
    result = service.validate(payload)
    return _fhir_response(result["operation_outcome"], status_code=200)
