"""Unified evidence journey: one read-only view over the existing gateway and One Health APIs.

Actions stay on the existing /interop and /onehealth endpoints; this router only composes their
persisted state so every client sees the same stage, proof and next legal action.
"""

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query

from app.api import interop as interop_api
from app.api import onehealth as onehealth_api
from app.auth import require_role
from app.interop import repository
from app.interop.models import Job
from app.journey import projection
from app.onehealth.repository import mode

log = structlog.get_logger()
router = APIRouter(prefix="/journey", tags=["journey"])
reviewer = require_role("reviewer", "admin")


async def _evidence(job: dict[str, Any], user: dict[str, Any]) -> dict[str, Any] | None:
    if not job.get("exposure_id"):
        return None
    try:
        return await onehealth_api.journey(job["exposure_id"], user)
    except HTTPException as exc:
        if exc.status_code == 404:
            return None
        raise


async def _project(job: Job, user: dict[str, Any]) -> dict[str, Any]:
    view = await interop_api.detail_view(job)  # the gateway's own consent-aware view
    return projection.project(view, await _evidence(view, user))


def _unavailable(job: Job) -> dict[str, Any]:
    """A list row for a journey that could not be projected; the rest of the list still renders."""
    return {
        "job_id": job.id,
        "source": {
            "system": job.source.source_system,
            "record_id": job.source.original_record_id,
            "format": job.source.format,
            "synthetic": job.source.synthetic,
        },
        "exposure_id": job.exposure_id,
        "current_stage": None,
        "current_status": "failed",
        "current_summary": "This journey could not be read; open it in the interop workbench.",
        "progress": {"complete": 0, "total": len(projection.STAGES)},
        "last_activity": job.events[-1].timestamp if job.events else None,
    }


@router.get("")
async def recent_journeys(
    limit: int = Query(12, ge=1, le=25), user: dict[str, Any] = Depends(reviewer)
) -> dict[str, Any]:
    rows = []
    for job in await repository.recent(user["organization_id"], limit):
        try:
            rows.append(projection.summary(await _project(job, user)))
        except Exception as exc:  # noqa: BLE001 - one broken job must not take down the whole list
            log.warning("journey.project_failed", job_id=job.id, error_type=type(exc).__name__)
            rows.append(_unavailable(job))
    return {
        "journeys": rows,
        "persistence": mode(),
        "stages": [
            {"id": stage_id, "label": label, "owner": owner}
            for stage_id, label, owner in projection.STAGES
        ],
    }


@router.get("/{job_id}")
async def get_journey(job_id: str, user: dict[str, Any] = Depends(reviewer)) -> dict[str, Any]:
    return await _project(await repository.get(user["organization_id"], job_id), user)
