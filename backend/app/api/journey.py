"""Unified evidence journey: one read-only view over the existing gateway and One Health APIs.

Actions stay on the existing /interop and /onehealth endpoints; this router only composes their
persisted state so every client sees the same stage, proof and next legal action.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api import interop as interop_api
from app.api import onehealth as onehealth_api
from app.auth import require_role
from app.interop import repository
from app.journey import projection
from app.onehealth.repository import mode

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


async def _project(job_id: str, user: dict[str, Any]) -> dict[str, Any]:
    job = await interop_api.detail(job_id, user)  # the gateway's own consent-aware view
    return projection.project(job, await _evidence(job, user))


@router.get("")
async def recent_journeys(
    limit: int = Query(12, ge=1, le=25), user: dict[str, Any] = Depends(reviewer)
) -> dict[str, Any]:
    jobs = await repository.recent(user["organization_id"], limit)
    return {
        "journeys": [projection.summary(await _project(j.id, user)) for j in jobs],
        "persistence": mode(),
        "stages": [
            {"id": stage_id, "label": label, "owner": owner}
            for stage_id, label, owner in projection.STAGES
        ],
    }


@router.get("/{job_id}")
async def get_journey(job_id: str, user: dict[str, Any] = Depends(reviewer)) -> dict[str, Any]:
    return await _project(job_id, user)
