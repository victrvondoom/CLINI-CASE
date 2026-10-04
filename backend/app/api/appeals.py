"""Appeals API — render an appeal letter to PDF.

Two endpoints, sharing the same `app.render.appeal_pdf.render_appeal_pdf`
implementation:

  POST /api/v1/appeals/render.pdf
        Body: AppealDraft JSON. No DB lookup. Returns a PDF byte stream.
        Used by the standalone showcase (no case persisted) and by any
        client that wants a preview before committing to the DB.

  GET  /api/v1/cases/{case_id}/appeal.pdf
        Reads the persisted appeal from `appeals` JOIN `cases`, reconstructs
        an AppealDraft, renders, and streams the PDF. Org-scoped via the
        authenticated user.

Per AAOSA bounded responsibility: this router is a thin adapter — it does
NOT perform agent reasoning, citation work, or template logic. All of that
lives in the Appeals Drafter agent and `app.render.appeal_pdf`.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response

from app.auth import get_current_user
from app.db import db
from app.models.appeal import AppealArgument, AppealDraft
from app.render import render_appeal_pdf
from app.review.pause_state import load_pause_state

router = APIRouter(tags=["appeals"])


@router.post(
    "/appeals/render.pdf",
    summary="Render an AppealDraft to PDF (preview path; no DB lookup)",
    responses={200: {"content": {"application/pdf": {}}}},
)
async def render_appeal_pdf_preview(
    draft: AppealDraft,
) -> Response:
    """Stateless render — accepts an AppealDraft and returns PDF bytes.

    Useful for the standalone showcase and live previews from the React
    frontend before a case is committed. No auth requirement on this
    endpoint mirrors the existing `/llm/ping` pattern; production deploys
    can layer auth at the ingress / WAF level.
    """
    pdf_bytes = render_appeal_pdf(draft, requires_review=True)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'inline; filename="appeal-{draft.patient_initials}-' f'{draft.payer_id}.pdf"'
            ),
            "X-ClinCase-Source": "preview",
            "X-ClinCase-Document-Status": "draft",
        },
    )


@router.get(
    "/cases/{case_id}/appeal.pdf",
    summary="Render the persisted appeal letter for a case",
    responses={
        200: {"content": {"application/pdf": {}}},
        404: {"description": "Case or appeal not found"},
    },
)
async def render_case_appeal_pdf(
    case_id: str,
    user: dict[str, Any] = Depends(get_current_user),
) -> Response:
    """Render the current run's letter; pending DENY previews remain clearly drafts."""
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT id, payer_id, patient_initials, requested_treatment_name, status, created_at
               FROM cases WHERE id = $1 AND organization_id = $2""",
            case_id,
            user["organization_id"],
        )
        if row is None:
            raise HTTPException(status_code=404, detail="Case or appeal not found")
        latest_run = await conn.fetchrow(
            "SELECT run_id, status FROM case_runs WHERE case_id = $1 ORDER BY attempt_no DESC LIMIT 1",
            case_id,
        )
        requires_review = row["status"] == "awaiting_review"
        if requires_review:
            paused = (
                await load_pause_state(conn, latest_run["run_id"])
                if latest_run and latest_run["status"] == "paused"
                else None
            )
            raw_draft = ((paused or {}).get("state", {}).get("draft_outputs") or {}).get(
                "appeal_draft"
            )
            if not raw_draft:
                raise HTTPException(status_code=404, detail="No draft appeal for the current review")
            draft = AppealDraft.model_validate(raw_draft)
            return _case_pdf_response(draft, case_id, requires_review=True)
        appeal = await conn.fetchrow(
            """SELECT appeal_body, structured_arguments_json FROM appeals
               WHERE case_id = $1 AND run_id IS NOT DISTINCT FROM $2
               ORDER BY created_at DESC, id DESC LIMIT 1""",
            case_id,
            latest_run["run_id"] if latest_run else None,
        )
    if appeal is None:
        raise HTTPException(status_code=404, detail="No appeal for the current case run")

    structured_args_raw = appeal["structured_arguments_json"]
    if isinstance(structured_args_raw, str):
        structured_args_raw = json.loads(structured_args_raw)

    draft = AppealDraft(
        patient_initials=row["patient_initials"] or "—",
        payer_id=row["payer_id"],
        requested_treatment=row["requested_treatment_name"] or "—",
        denial_date=row["created_at"].strftime("%Y-%m-%d"),
        appeal_body=appeal["appeal_body"],
        structured_arguments=[AppealArgument(**a) for a in structured_args_raw],
        attachments_referenced=[],
        requested_action=(f"Overturn the denial and authorise {row['requested_treatment_name']}."),
    )

    return _case_pdf_response(draft, case_id, requires_review=False)


def _case_pdf_response(draft: AppealDraft, case_id: str, *, requires_review: bool) -> Response:
    pdf_bytes = render_appeal_pdf(draft, case_id=case_id, requires_review=requires_review)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (f'inline; filename="appeal-{case_id}.pdf"'),
            "X-ClinCase-Case-Id": case_id,
            "X-ClinCase-Source": "live",
            "X-ClinCase-Document-Status": "draft" if requires_review else "case-record",
        },
    )
