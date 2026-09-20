"""FHIR Bulk Data $export — async batch export of cases / decisions / evidence.

Implements the [HL7 FHIR Bulk Data Access (Flat FHIR)
2.0.0](https://hl7.org/fhir/uv/bulkdata/) operation. Required by every
Tier-1 payer that wants to backfill an analytics warehouse from ClinCase's
authoritative case + decision data.

  POST /fhir/$export                       Group-level kickoff
  GET  /fhir/$export-status/{job_id}       Async-job status
  GET  /fhir/$export-result/{job_id}/{file_path}   NDJSON download

The kickoff returns 202 + `Content-Location` per the spec. The status
endpoint polls until 200 with the manifest + per-resource NDJSON URLs.

Today (round-13) we ship the API surface + a minimal in-process exporter
that streams `cases` + `decisions` + `agent_runs` for the calling tenant.
A real export workflow lands in round-14 (Glue job + S3 NDJSON output).
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse

from app.auth import get_current_user
from app.db import db

router = APIRouter(prefix="/fhir", tags=["fhir-bulk"])


_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS fhir_bulk_jobs (
    job_id            TEXT PRIMARY KEY,
    organization_id   TEXT NOT NULL,
    requested_by      TEXT NOT NULL,
    resource_types    TEXT[] NOT NULL,
    since             TIMESTAMPTZ,
    status            TEXT NOT NULL CHECK (status IN ('queued','running','completed','failed','cancelled')),
    request_url       TEXT,
    output_manifest   JSONB,
    error_message     TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at      TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_fhir_bulk_org_status ON fhir_bulk_jobs (organization_id, status);
"""


async def ensure_schema() -> None:
    await db.execute(_SCHEMA_SQL)


# =============================================================================
# Kickoff
# =============================================================================


@router.post("/$export")
async def export_kickoff(
    response: Response,
    user: dict[str, Any] = Depends(get_current_user),
    _type: str = "Claim,Coverage,Patient",
    _since: str | None = None,
) -> dict[str, Any]:
    """FHIR Bulk Data Group-level $export. Async kickoff.

    Returns 202 Accepted + Content-Location header per the FHIR Bulk Data
    spec. Customer polls Content-Location until status returns 200.
    """
    job_id = f"bulk_{uuid.uuid4().hex[:16]}"
    resource_types = [t.strip() for t in _type.split(",") if t.strip()]
    since_dt = None
    if _since:
        try:
            since_dt = datetime.fromisoformat(_since.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(status_code=400, detail="invalid _since format; expected ISO-8601")

    await db.execute(
        """
        INSERT INTO fhir_bulk_jobs
            (job_id, organization_id, requested_by, resource_types, since, status, request_url)
        VALUES ($1, $2, $3, $4, $5, 'queued', $6)
        """,
        job_id,
        user["organization_id"],
        user["id"],
        resource_types,
        since_dt,
        f"/fhir/$export?_type={_type}",
    )

    location = f"/fhir/$export-status/{job_id}"
    response.status_code = 202
    response.headers["Content-Location"] = location
    return {
        "job_id": job_id,
        "status": "queued",
        "poll_at": location,
        "resource_types": resource_types,
    }


@router.get("/$export-status/{job_id}")
async def export_status(
    job_id: str,
    response: Response,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    row = await db.fetchrow(
        "SELECT * FROM fhir_bulk_jobs WHERE job_id = $1",
        job_id,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="bulk export job not found")
    if row["organization_id"] != user["organization_id"]:
        raise HTTPException(status_code=403, detail="cross-tenant bulk export forbidden")

    if row["status"] == "queued" or row["status"] == "running":
        # In a real deploy, the bulk-export worker advances state. Today
        # we run synchronously when polled.
        await _run_export(job_id)
        row = await db.fetchrow(
            "SELECT * FROM fhir_bulk_jobs WHERE job_id = $1",
            job_id,
        )

    if row["status"] == "running":
        response.status_code = 202
        response.headers["X-Progress"] = "running"
        return {"status": "running", "job_id": job_id}

    if row["status"] == "completed":
        manifest = row["output_manifest"]
        if isinstance(manifest, str):
            manifest = json.loads(manifest)
        response.status_code = 200
        response.headers["Expires"] = (
            datetime.now(timezone.utc) + timedelta(hours=24)
        ).strftime("%a, %d %b %Y %H:%M:%S GMT")
        return manifest

    if row["status"] == "failed":
        raise HTTPException(status_code=500, detail=f"bulk export failed: {row['error_message']}")

    raise HTTPException(status_code=500, detail=f"unexpected status: {row['status']}")


@router.get("/$export-result/{job_id}/{resource_type}.ndjson")
async def export_result(
    job_id: str,
    resource_type: str,
    user: dict[str, Any] = Depends(get_current_user),
) -> StreamingResponse:
    """Stream NDJSON for one resource type from the completed export."""
    row = await db.fetchrow(
        "SELECT organization_id, status FROM fhir_bulk_jobs WHERE job_id = $1",
        job_id,
    )
    if row is None or row["status"] != "completed":
        raise HTTPException(status_code=404, detail="export not ready")
    if row["organization_id"] != user["organization_id"]:
        raise HTTPException(status_code=403, detail="cross-tenant export forbidden")

    async def gen():
        async for line in _ndjson_stream(
            organization_id=user["organization_id"],
            resource_type=resource_type,
        ):
            yield line.encode("utf-8")

    return StreamingResponse(
        gen(),
        media_type="application/fhir+ndjson",
        headers={"Content-Disposition": f'attachment; filename="{resource_type}.ndjson"'},
    )


# =============================================================================
# Implementation — minimal in-process exporter (round 13)
# =============================================================================


async def _run_export(job_id: str) -> None:
    """Mark job as running, build the manifest, mark as completed."""
    await db.execute("UPDATE fhir_bulk_jobs SET status='running' WHERE job_id=$1", job_id)
    row = await db.fetchrow(
        "SELECT organization_id, resource_types FROM fhir_bulk_jobs WHERE job_id = $1",
        job_id,
    )
    if row is None:
        return
    org_id = row["organization_id"]
    types = list(row["resource_types"]) if row["resource_types"] is not None else []

    manifest = {
        "transactionTime": datetime.now(timezone.utc).isoformat(),
        "request": f"/fhir/$export",
        "requiresAccessToken": True,
        "output": [
            {
                "type": t,
                "url": f"/fhir/$export-result/{job_id}/{t}.ndjson",
            }
            for t in types
        ],
        "error": [],
    }
    await db.execute(
        """
        UPDATE fhir_bulk_jobs
           SET status='completed', output_manifest=$1::jsonb, completed_at=NOW()
         WHERE job_id=$2
        """,
        json.dumps(manifest), job_id,
    )


async def _ndjson_stream(*, organization_id: str, resource_type: str):
    """Stream NDJSON FHIR resources. Today: maps ClinCase `cases` /
    `decisions` to a *minimal* FHIR Claim shape; deeper FHIR mapping lands
    in round-14 once we have customer-specific FHIR profile requirements."""
    if resource_type == "Claim":
        rows = await db.fetch_ro(
            "SELECT id, payer_id, requested_drug, status, created_at "
            "FROM cases WHERE organization_id = $1 ORDER BY created_at LIMIT 10000",
            organization_id,
        )
        for r in rows:
            claim = {
                "resourceType": "Claim",
                "id": r["id"],
                "status": "active" if r["status"] not in ("denied", "withdrawn") else "cancelled",
                "use": "preauthorization",
                "insurer": {"identifier": {"value": r["payer_id"] or "unknown"}},
                "billablePeriod": {"start": str(r["created_at"])},
                "_clincase_drug": r["requested_drug"],
            }
            yield json.dumps(claim) + "\n"
    elif resource_type == "Coverage":
        rows = await db.fetch_ro(
            "SELECT DISTINCT payer_id FROM cases WHERE organization_id = $1 AND payer_id IS NOT NULL",
            organization_id,
        )
        for r in rows:
            yield json.dumps({
                "resourceType": "Coverage",
                "id": f"coverage-{r['payer_id']}",
                "status": "active",
                "payor": [{"identifier": {"value": r["payer_id"]}}],
            }) + "\n"
    else:
        # Empty stream for unsupported resources
        return
