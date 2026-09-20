"""Async-job endpoints — POST/GET around the case_jobs queue.

Production scaling pattern:
  • POST /cases/{id}/run-async   enqueues a run_full job and returns 202
                                  immediately. The HTTP request lifetime is
                                  ~10 ms, regardless of how long the DAG takes.
  • GET  /jobs/{job_id}          returns current status + result_json (when done).
  • GET  /jobs/queue/depth       Prometheus / dashboard query — current queue depth
                                  by status.

The legacy synchronous POST /cases/{id}/run still exists for the demo flow
(blocks the request until the DAG finishes). New clients should prefer
`run-async` + SSE stream + `GET /jobs/{job_id}`.

Idempotency: pass an `Idempotency-Key` header on POST. If the key matches a
prior submission, the existing job is returned (HTTP 200) instead of a new
one (HTTP 202). Standard HTTP idempotency semantics — same as Stripe / AWS.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Response

from app.auth.dependencies import get_current_user
from app.db import db
from app.jobs import queue as jq
from app.quotas import QuotaExceeded, consume_case_quota, quota_exceeded_to_http

router = APIRouter(tags=["jobs"])


# =============================================================================
# Idempotency helpers
# =============================================================================


def _retry_after_seconds(resets_at_iso: str) -> str:
    """Compute Retry-After header for a 429 quota response.

    The HTTP spec accepts either an integer seconds value or an HTTP-date.
    We use seconds so clients don't need to parse a timestamp; floor at 1
    so we never tell a client to retry immediately when the cap is fresh.
    """
    from datetime import datetime

    if not resets_at_iso:
        return "60"
    try:
        dt = datetime.fromisoformat(resets_at_iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        delta = (dt - datetime.now(UTC)).total_seconds()
        return str(max(1, int(delta)))
    except (ValueError, TypeError):
        return "60"


def _derive_idempotency_key(
    *,
    explicit_key: str | None,
    case_id: str,
    organization_id: str,
    job_type: str,
) -> str:
    """If client provides Idempotency-Key, use it; else derive a deterministic
    key from (case_id, org, job_type) — the same case can't be queued twice
    for the same job type concurrently."""
    if explicit_key:
        # Scope the key to the org so a key from one tenant doesn't collide
        # with another tenant's key.
        return f"{organization_id}:{explicit_key}"
    raw = f"{organization_id}:{case_id}:{job_type}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


# =============================================================================
# Endpoints
# =============================================================================


@router.post("/cases/{case_id}/run-async", status_code=202)
async def run_full_async(
    case_id: str,
    response: Response,
    user: dict[str, Any] = Depends(get_current_user),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    """Enqueue a full-DAG run. Returns immediately with the job_id.

    Status code:
      202 Accepted    — new job enqueued
      200 OK          — idempotent replay; existing job_id returned

    Poll `GET /jobs/{job_id}` for status, OR subscribe to the SSE stream
    `GET /cases/{case_id}/stream` (already exists) for real-time agent traces.
    """
    row = await db.fetchrow(
        """SELECT id, organization_id, payer_id, fhir_bundle, physician_note,
                  requested_treatment_name, requested_j_code
           FROM cases WHERE id = $1 AND organization_id = $2""",
        case_id, user["organization_id"],
    )
    if row is None:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")

    fhir = (
        json.loads(row["fhir_bundle"])
        if isinstance(row["fhir_bundle"], str)
        else row["fhir_bundle"]
    )
    payload = {
        "fhir_bundle": fhir,
        "physician_note": row["physician_note"],
        "requested_treatment": {
            "name": row["requested_treatment_name"],
            "j_code": row["requested_j_code"],
        },
        "payer_id": row["payer_id"],
    }
    key = _derive_idempotency_key(
        explicit_key=idempotency_key,
        case_id=case_id,
        organization_id=user["organization_id"],
        job_type="run_full",
    )

    # Per-org daily/monthly quota gate (SCALE-8). We enforce on EVERY async
    # submit BEFORE inserting a row in case_jobs so the queue stays clean —
    # we never enqueue a job we wouldn't have been allowed to run. Idempotent
    # replays of an existing job DO NOT consume an additional slot, so we
    # check first whether the idempotency key already matches an existing job.
    existing = await db.fetchrow(
        "SELECT id FROM case_jobs WHERE idempotency_key = $1", key,
    )
    if existing is None:
        try:
            await consume_case_quota(user["organization_id"])
        except QuotaExceeded as exc:
            raise HTTPException(
                status_code=429,
                detail=quota_exceeded_to_http(exc),
                headers={"Retry-After": _retry_after_seconds(exc.resets_at_iso)},
            ) from exc

    job = await jq.enqueue(
        case_id=case_id,
        organization_id=user["organization_id"],
        job_type="run_full",
        payload=payload,
        idempotency_key=key,
    )

    # Idempotent replay → return 200 instead of 202
    if job.status != "queued" or job.attempts > 0:
        response.status_code = 200

    return {
        "job_id": str(job.id),
        "case_id": job.case_id,
        "status": job.status,
        "idempotency_key": key,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "poll_url": f"/api/v1/jobs/{job.id}",
        "stream_url": f"/api/v1/cases/{case_id}/stream",
    }


@router.get("/jobs/{job_id}", status_code=200)
async def get_job_status(
    job_id: uuid.UUID,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Return current job status (and result_json when status='done')."""
    job = await jq.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    if job.organization_id != user["organization_id"]:
        # Don't leak existence across orgs
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return {
        "job_id": str(job.id),
        "case_id": job.case_id,
        "job_type": job.job_type,
        "status": job.status,
        "attempts": job.attempts,
        "max_attempts": job.max_attempts,
        "result": job.result,
        "error": job.error,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "claimed_at": job.claimed_at.isoformat() if job.claimed_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
    }


@router.get("/jobs/case/{case_id}", status_code=200)
async def list_case_jobs(
    case_id: str,
    user: dict[str, Any] = Depends(get_current_user),
    limit: int = 20,
) -> dict[str, Any]:
    """List the most recent N jobs for a case."""
    # Tenant scope: confirm the case belongs to the user's org first
    case = await db.fetchrow(
        "SELECT id FROM cases WHERE id = $1 AND organization_id = $2",
        case_id, user["organization_id"],
    )
    if case is None:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")

    jobs = await jq.list_jobs_for_case(case_id, limit=limit)
    return {
        "case_id": case_id,
        "n_jobs": len(jobs),
        "jobs": [
            {
                "job_id": str(j.id),
                "job_type": j.job_type,
                "status": j.status,
                "attempts": j.attempts,
                "created_at": j.created_at.isoformat() if j.created_at else None,
                "finished_at": j.finished_at.isoformat() if j.finished_at else None,
            }
            for j in jobs
        ],
    }


@router.get("/jobs/queue/depth", status_code=200)
async def queue_depth() -> dict[str, Any]:
    """Public-ish — exposes current queue depth for monitoring dashboards.

    No tenant scoping (operational metric across all tenants). Auth is required
    via the global router prefix middleware in production.
    """
    depth = await jq.queue_depth()
    return {"depth": depth, "total": sum(depth.values())}
