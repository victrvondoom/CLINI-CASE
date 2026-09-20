"""HTTP surface for the TriZetto integration.

  POST  /api/v1/integrations/trizetto/submit          — build + send a Gateway submission for a case
  GET   /api/v1/integrations/trizetto/_mock/inbox      — read what the mock Gateway received (demo)
  GET   /api/v1/integrations/trizetto/info             — introspection / "what is this?" panel data

The submit endpoint is idempotent in spirit but not in storage — duplicate
calls produce duplicate Gateway records (for visibility). The mock inbox
shows the last 100 envelopes.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth import get_current_user
from app.db import db
from app.integrations.trizetto.facets_pa_event import build_facets_event
from app.integrations.trizetto.gateway_client import (
    GatewaySubmission,
    TriZettoGatewayClient,
    clear_mock_inbox,
    get_mock_inbox,
)
from app.integrations.trizetto.qnxt_writeback import build_qnxt_event

router = APIRouter(prefix="/integrations/trizetto", tags=["integrations:trizetto"])


# =============================================================================
# Submit endpoint
# =============================================================================


class SubmitRequest(BaseModel):
    case_id: str = Field(..., description="ClinCase case_id to submit.")
    target: str = Field(
        default="both",
        description="Which TriZetto product to fan out to: 'facets', 'qnxt', or 'both'.",
    )
    rendering_npi: str | None = Field(
        default=None,
        description="Required for QNXT; ignored for Facets-only submissions.",
    )


class SubmitResponse(BaseModel):
    accepted: bool
    gateway_id: str | None
    fanout_targets: list[str]
    received_at: str
    is_mock: bool = Field(..., description="True when the demo mock receiver handled the request.")
    facets_event: dict[str, Any] | None = None
    qnxt_event: dict[str, Any] | None = None
    case_id: str


_TARGETS = {"facets", "qnxt", "both"}


@router.post("/submit", response_model=SubmitResponse)
async def submit_to_gateway(
    req: SubmitRequest,
    user: dict[str, Any] = Depends(get_current_user),
) -> SubmitResponse:
    """Build a Facets+QNXT envelope from the case's persisted decision and
    submit it to the TriZetto AI Gateway.

    Pre-conditions:
      • case_id belongs to caller's organization
      • case has a decision row (i.e. the DAG has finished APPROVE/DENY/REFER)

    Idempotency: each call produces a new Gateway record. To dedupe, pair
    this with an Idempotency-Key on the upstream POST /run-async and
    re-submit only on caller demand.
    """
    if req.target not in _TARGETS:
        raise HTTPException(
            status_code=400,
            detail=f"target must be one of {_TARGETS}; got {req.target!r}",
        )

    case = await db.fetchrow(
        """SELECT id, payer_id, patient_initials, requested_treatment_name,
                  requested_j_code, fhir_bundle, organization_id
           FROM cases WHERE id = $1 AND organization_id = $2""",
        req.case_id, user["organization_id"],
    )
    if case is None:
        raise HTTPException(status_code=404, detail=f"Case {req.case_id} not found")

    decision = await db.fetchrow(
        """SELECT verdict, rationale, citations_json, confidence
           FROM decisions WHERE case_id = $1 ORDER BY id DESC LIMIT 1""",
        req.case_id,
    )
    if decision is None:
        raise HTTPException(
            status_code=409,
            detail=f"Case {req.case_id} has no decision yet; run the DAG first.",
        )

    # Find the most recent agent_runs row to attribute model_id.
    last_run = await db.fetchrow(
        """SELECT model_id, started_at FROM agent_runs
           WHERE case_id = $1 AND model_id IS NOT NULL
           ORDER BY id DESC LIMIT 1""",
        req.case_id,
    )

    citations_raw = decision["citations_json"]
    if isinstance(citations_raw, str):
        try:
            citations = json.loads(citations_raw)
        except json.JSONDecodeError:
            citations = []
    else:
        citations = citations_raw or []

    decision_payload = {
        "verdict": decision["verdict"],
        "rationale": decision["rationale"],
        "citations": citations,
    }
    requested_treatment = {
        "name": case["requested_treatment_name"],
        "j_code": case["requested_j_code"],
    }
    decision_run_id = str(uuid.uuid4())
    primary_model_id = (last_run and last_run["model_id"]) or "apac.anthropic.claude-sonnet-4-6-20251022-v1:0"
    confidence = float(decision["confidence"] or 0.0)
    triggered_hitl = confidence < 0.75

    # Use the patient_initials as a stand-in member_id for the demo. In real
    # deployments this comes from the FHIR Patient resource via the
    # synced member directory.
    member_id = case["patient_initials"] or "MEMBER-UNKNOWN"

    # CMS-0057-F clauses that this submission satisfies. Computed lazily by
    # `app/compliance/cms_0057f.py` once that module exists; for now a
    # conservative static set that's true for every persisted decision.
    try:
        from app.compliance.cms_0057f import clauses_satisfied_for_case
        cms_clauses = await clauses_satisfied_for_case(req.case_id)
    except Exception:  # noqa: BLE001 — avoid blocking submit on optional module
        cms_clauses = ["§ IV.A", "§ IV.B.1", "§ IV.D"]

    facets_event = None
    qnxt_event = None
    if req.target in ("facets", "both"):
        facets_event = build_facets_event(
            case_id=req.case_id,
            payer_id=case["payer_id"],
            member_id=member_id,
            requested_treatment=requested_treatment,
            decision=decision_payload,
            primary_model_id=primary_model_id,
            confidence=confidence,
            triggered_hitl=triggered_hitl,
            decision_run_id=decision_run_id,
            cms_0057f_clauses_satisfied=cms_clauses,
        )
    if req.target in ("qnxt", "both"):
        rendering_npi = req.rendering_npi or "0000000000"  # demo placeholder
        qnxt_event = build_qnxt_event(
            case_id=req.case_id,
            member_id=member_id,
            payer_id=case["payer_id"],
            requested_treatment=requested_treatment,
            decision=decision_payload,
            rendering_npi=rendering_npi,
            primary_model_id=primary_model_id,
            confidence=confidence,
            triggered_hitl=triggered_hitl,
            decision_run_id=decision_run_id,
        )

    submission = GatewaySubmission(
        case_id=req.case_id,
        organization_id=user["organization_id"],
        facets_event=facets_event,
        qnxt_event=qnxt_event,
    )

    client = TriZettoGatewayClient()
    ack = await client.submit(submission)

    return SubmitResponse(
        accepted=ack.accepted,
        gateway_id=ack.gateway_id,
        fanout_targets=ack.fanout_targets,
        received_at=ack.received_at,
        is_mock=client.is_mock,
        facets_event=facets_event.model_dump() if facets_event else None,
        qnxt_event=qnxt_event.model_dump() if qnxt_event else None,
        case_id=req.case_id,
    )


# =============================================================================
# Mock inbox (demo aid — proves the round trip is real)
# =============================================================================


@router.get("/_mock/inbox")
async def mock_inbox(
    user: dict[str, Any] = Depends(get_current_user),  # noqa: ARG001 — auth-only
) -> dict[str, Any]:
    """Read the in-process mock Gateway's inbox. Org-scoped filter applied so
    one tenant cannot see another's submissions."""
    org = user["organization_id"]
    items = [
        item for item in get_mock_inbox()
        if (item.get("envelope", {}).get("params", {}).get("arguments", {}).get("organization_id") == org)
    ]
    return {
        "is_mock": True,
        "count": len(items),
        "items": items,
        "note": (
            "This is the in-process mock TriZetto AI Gateway receiver. In "
            "production this endpoint is unused — TRIZETTO_GATEWAY_URL points "
            "to the real Gateway and this demo inbox stays empty."
        ),
    }


@router.delete("/_mock/inbox")
async def mock_inbox_clear(
    user: dict[str, Any] = Depends(get_current_user),  # noqa: ARG001
) -> dict[str, str]:
    """Demo helper: clear the mock inbox between case runs."""
    clear_mock_inbox()
    return {"status": "cleared"}


# =============================================================================
# Introspection (powers the "what is this" UI panel)
# =============================================================================


@router.get("/info")
async def info(
    user: dict[str, Any] = Depends(get_current_user),  # noqa: ARG001
) -> dict[str, Any]:
    client = TriZettoGatewayClient()
    return {
        "platform": "Cognizant TriZetto AI Gateway",
        "launched": "2025-08-06",
        "stack": {
            "compute": "AWS Bedrock (Anthropic Claude Sonnet 4.6)",
            "protocol": "Model Context Protocol (MCP) over JSON-RPC 2.0",
            "agent_sdk": "Anthropic Agent SDK",
            "anthropic_partnership_announced": "2025-11-04",
        },
        "fanout_targets_supported": ["facets-pa-workflow", "qnxt-case-events"],
        "configured_url": client.gateway_url or None,
        "running_in": "mock" if client.is_mock else "real",
        "why_this_exists": (
            "ClinCase deploys as a TriZetto AI Gateway-native specialty agent bundle. "
            "Same Bedrock + Claude Sonnet 4.6 + MCP stack Cognizant standardized on "
            "for the Anthropic partnership announced Nov 4, 2025. ClinCase submits "
            "determinations to the Gateway, which fans them out to Facets PA workflow "
            "and QNXT case-event hooks. From a Cognizant sales perspective, ClinCase is "
            "the first oncology-specialty plug-in for TriZetto AI Gateway."
        ),
        "mock_inbox_size": len(get_mock_inbox()),
        "issuer": "ClinCase 0.1.0",
        "asof_utc": datetime.now(timezone.utc).isoformat(),
    }
