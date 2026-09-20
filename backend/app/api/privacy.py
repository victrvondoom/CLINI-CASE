"""GDPR/HIPAA right-to-erasure endpoints.

  POST /api/v1/privacy/erasure-request          file an erasure request
  GET  /api/v1/privacy/erasure-requests         list (admin)
  POST /api/v1/privacy/_run_hard_delete         operator job runner (admin)
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.auth import require_role
from app.privacy.erasure import (
    ErasureRequest,
    hard_delete_due,
    list_for_org,
    request_erasure,
)

router = APIRouter(prefix="/privacy", tags=["privacy"])


class ErasureRequestBody(BaseModel):
    subject_initials: str = Field(..., min_length=1, max_length=8)
    reason: str = Field(default="gdpr_art_17")
    legal_basis: str = Field(default="consent_withdrawn")


@router.post("/erasure-request")
async def file_request(
    body: ErasureRequestBody,
    user: dict[str, Any] = Depends(require_role("admin")),
) -> dict[str, Any]:
    res = await request_erasure(ErasureRequest(
        organization_id=user["organization_id"],
        subject_initials=body.subject_initials,
        requested_by=user["id"],
        reason=body.reason,
        legal_basis=body.legal_basis,
    ))
    return {
        "redaction_id":      res.redaction_id,
        "subject_token":     res.subject_token,
        "soft_deleted_at":   res.soft_deleted_at,
        "hard_delete_after": res.hard_delete_after,
        "status":            res.status,
        "note": (
            "Soft-deleted. After the 7-day legal-hold window, audit-trail "
            "patient identifiers will be tokenized irreversibly. Decision "
            "audit data is RETAINED per CMS-0057-F § IV.D conflict-of-laws "
            "reconciliation; subject identity is NOT."
        ),
    }


@router.get("/erasure-requests")
async def list_requests(
    user: dict[str, Any] = Depends(require_role("admin")),
) -> dict[str, Any]:
    rows = await list_for_org(organization_id=user["organization_id"])
    return {"organization_id": user["organization_id"], "count": len(rows), "redactions": rows}


@router.post("/_run_hard_delete")
async def run_hard_delete(
    user: dict[str, Any] = Depends(require_role("admin")),  # noqa: ARG001
) -> dict[str, Any]:
    """Operator job runner — reconciles past-grace-window soft-deletes."""
    n = await hard_delete_due()
    return {"hard_deleted_count": n}
