"""QNXT decision writeback — POST ClinCase determination to QNXT case-event hook.

QNXT is the second Cognizant TriZetto admin platform (~20M lives) used by
smaller and regional payers. Its case-management module accepts
`case_event_v2` notifications via REST webhook, which downstream claims-
processing keys off (so an APPROVED auth becomes a payable claim).

This module mirrors `facets_pa_event.py` but produces the QNXT shape. The
event types differ:
  - QNXT uses `event_type` of "AUTHORIZATION_DETERMINED" / "AUTHORIZATION_PENDED"
  - QNXT requires the rendering provider NPI; Facets does not.

Like the Facets builder, we DO NOT call QNXT here — the gateway client
fan-out makes the real network call.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class QNXTProvider(BaseModel):
    rendering_npi: str = Field(..., description="10-digit NPI of the rendering oncologist.")
    tin: str | None = Field(None, description="Taxpayer ID. Required only for institutional billing.")
    facility_npi: str | None = None


class QNXTClinCaseProvenance(BaseModel):
    """Same provenance idea as Facets but with QNXT field names."""

    determination_engine: str = Field(default="ClinCase/0.1.0")
    bedrock_model_id: str
    confidence_pct: int = Field(..., ge=0, le=100, description="Confidence as integer percent for QNXT's UI.")
    case_id: str
    run_id: str
    decision_hash: str = Field(..., description="SHA-256 of the determination — tamper-evident.")
    routed_to_human: bool = Field(default=False, description="True if HITL gate triggered.")


class QNXTDecisionEvent(BaseModel):
    schema_name: str = Field(default="qnxt_case_event")
    schema_version: str = Field(default="v2")
    event_type: str = Field(..., description="AUTHORIZATION_DETERMINED | AUTHORIZATION_PENDED | AUTHORIZATION_DENIED")
    auth_id: str = Field(..., description="QNXT auth_id; we mint by namespacing case_id.")
    member_id: str
    payer_id: str
    occurred_at_utc: str
    cms_disposition: str = Field(
        ...,
        description="APPROVED | DENIED | REFERRED — QNXT's CMS-aligned disposition.",
    )
    rationale: str
    citations: list[str]
    cpt_or_jcode: str
    units: int | None = None
    rendering_provider: QNXTProvider
    provenance: QNXTClinCaseProvenance
    cms_0057f_tat_hours: int | None = Field(
        None,
        description=(
            "Decision TAT in hours. CMS-0057-F § IV.B.1: 72h expedited, 7 days standard. "
            "QNXT compares against the policy and flags violations."
        ),
    )


_VERDICT_TO_QNXT_TYPE = {
    "APPROVE": "AUTHORIZATION_DETERMINED",
    "DENY": "AUTHORIZATION_DENIED",
    "REFER": "AUTHORIZATION_PENDED",
}
_VERDICT_TO_DISPOSITION = {
    "APPROVE": "APPROVED",
    "DENY": "DENIED",
    "REFER": "REFERRED",
}


def _hash_decision(verdict: str, rationale: str, citations: list[str], model_id: str) -> str:
    return hashlib.sha256(
        f"{verdict}|{rationale}|{citations}|{model_id}".encode("utf-8")
    ).hexdigest()


def build_qnxt_event(
    *,
    case_id: str,
    member_id: str,
    payer_id: str,
    requested_treatment: dict[str, Any],
    decision: dict[str, Any],
    rendering_npi: str,
    primary_model_id: str,
    confidence: float,
    triggered_hitl: bool,
    decision_run_id: str,
    tat_hours: int | None = None,
    facility_npi: str | None = None,
    tin: str | None = None,
) -> QNXTDecisionEvent:
    verdict = decision.get("verdict", "REFER")
    rationale = decision.get("rationale", "")
    citations_raw = decision.get("citations") or []
    citations: list[str] = []
    for c in citations_raw:
        if isinstance(c, str):
            citations.append(c)
        elif isinstance(c, dict):
            citations.append(c.get("text") or c.get("pointer") or c.get("policy_id") or "citation")
        else:
            citations.append(str(c))

    return QNXTDecisionEvent(
        event_type=_VERDICT_TO_QNXT_TYPE.get(verdict, "AUTHORIZATION_PENDED"),
        auth_id=f"CLINCASE-{case_id}",
        member_id=member_id,
        payer_id=payer_id,
        occurred_at_utc=datetime.now(timezone.utc).isoformat(),
        cms_disposition=_VERDICT_TO_DISPOSITION.get(verdict, "REFERRED"),
        rationale=rationale,
        citations=citations,
        cpt_or_jcode=requested_treatment.get("j_code") or requested_treatment.get("cpt_code") or "UNKNOWN",
        units=requested_treatment.get("requested_units"),
        rendering_provider=QNXTProvider(
            rendering_npi=rendering_npi,
            facility_npi=facility_npi,
            tin=tin,
        ),
        provenance=QNXTClinCaseProvenance(
            bedrock_model_id=primary_model_id,
            confidence_pct=int(round(confidence * 100)),
            case_id=case_id,
            run_id=decision_run_id,
            decision_hash=_hash_decision(verdict, rationale, citations, primary_model_id),
            routed_to_human=triggered_hitl,
        ),
        cms_0057f_tat_hours=tat_hours,
    )
