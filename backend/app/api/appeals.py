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
    pdf_bytes = render_appeal_pdf(draft)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'inline; filename="appeal-{draft.patient_initials}-'
                f'{draft.payer_id}.pdf"'
            ),
            "X-ClinCase-Source": "preview",
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
    """Production path — read the appeal from the DB, render, stream."""
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT
                a.appeal_body,
                a.structured_arguments_json,
                c.id                       AS case_id,
                c.payer_id,
                c.patient_initials,
                c.requested_treatment_name,
                c.created_at
            FROM appeals a
            JOIN cases c ON c.id = a.case_id
            WHERE a.case_id = $1
              AND c.organization_id = $2
            ORDER BY a.created_at DESC
            LIMIT 1
            """,
            case_id,
            user["organization_id"],
        )

    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"No appeal letter found for case {case_id}",
        )

    structured_args_raw = row["structured_arguments_json"]
    if isinstance(structured_args_raw, str):
        structured_args_raw = json.loads(structured_args_raw)

    draft = AppealDraft(
        patient_initials=row["patient_initials"] or "—",
        payer_id=row["payer_id"],
        requested_treatment=row["requested_treatment_name"] or "—",
        denial_date=row["created_at"].strftime("%Y-%m-%d"),
        appeal_body=row["appeal_body"],
        structured_arguments=[AppealArgument(**a) for a in structured_args_raw],
        attachments_referenced=[],
        requested_action=(
            f"Overturn the denial and authorise {row['requested_treatment_name']}."
        ),
    )

    pdf_bytes = render_appeal_pdf(draft, case_id=case_id)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'inline; filename="appeal-{case_id}.pdf"'
            ),
            "X-ClinCase-Case-Id": case_id,
            "X-ClinCase-Source": "live",
        },
    )
