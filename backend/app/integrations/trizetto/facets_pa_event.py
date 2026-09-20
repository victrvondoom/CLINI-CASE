"""Facets-PA-event DTO — ClinCase Decision -> Facets prior_auth_event schema.

The Facets prior-authorization workflow surface (post-G6) accepts events of
shape `prior_auth_event_v3`. Each event creates or updates a Facets PA task
that a clinical reviewer sees in the standard Facets UI.

This module is **schema-faithful** to the Facets G6 documentation but does
NOT call Facets — that's the job of `qnxt_writeback.py` (for QNXT) and
`gateway_client.py` (for the Gateway path that fans out to Facets).

Design notes:

  • Member identifiers are passed verbatim from the FHIR bundle's Patient
    resource. We do NOT derive PHI here.
  • The `external_decision_engine` block is what tells Facets the auth came
    from ClinCase (rather than a manual reviewer or a different AI tool).
    This is what makes "AI-attested decision" auditable downstream.
  • Citations are flattened to a string list because Facets' free-text
    `notes` field is the only place richer evidence lives in the v3 schema.
    The structured citation_json stays in ClinCase's audit trail.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


# =============================================================================
# Pydantic DTOs (schema-faithful to Facets G6 prior_auth_event v3)
# =============================================================================


class FacetsMember(BaseModel):
    member_id: str = Field(..., description="Facets member ID (subscriber + dependent suffix).")
    payer_id: str = Field(..., description="Payer LOB code as Facets configures it (CC=commercial, MA=Medicare Advantage).")


class FacetsTreatment(BaseModel):
    j_code: str | None = Field(None, description="HCPCS J-code (J9355 etc.).")
    cpt_code: str | None = Field(None, description="CPT code if drug is procedure-billed.")
    drug_name: str = Field(..., description="Generic / brand name as written by the prescriber.")
    requested_units: int | None = Field(None, description="Requested dose units (mg) for chemo.")
    site_of_service: str | None = Field(None, description="POS code (11 office, 22 outpatient hospital, etc.).")


class FacetsClinCaseAttestation(BaseModel):
    """The provenance block. This is the heart of why the decision is
    auditable: every Facets reviewer sees exactly which ClinCase agent + model
    produced the determination."""

    engine_name: str = Field(default="ClinCase")
    engine_version: str = Field(default="0.1.0")
    decision_run_id: str = Field(..., description="UUID of the LangGraph DAG run; ties back to agent_runs.")
    primary_model_id: str = Field(..., description="Bedrock model id, e.g. apac.anthropic.claude-sonnet-4-6-20251022-v1:0.")
    confidence: float = Field(..., ge=0.0, le=1.0)
    triggered_hitl: bool = Field(default=False, description="True if ClinCase routed the case to human review.")
    case_id: str = Field(..., description="ClinCase internal case_id; pivot for audit drill-down.")
    decision_hash_sha256: str = Field(..., description="Tamper-evident hash of (verdict|rationale|citations|model_id).")


class FacetsPAEvent(BaseModel):
    """Top-level event the Gateway forwards to Facets.

    Schema name: `prior_auth_event` v3. Action drives Facets workflow state:
    - `created`        - new auth task; reviewer sees it in their queue
    - `updated`        - clarification or HITL resume
    - `closed_approved` / `closed_denied` / `closed_referred` - terminal
    """

    schema_name: str = Field(default="prior_auth_event", description="Facets event schema family.")
    schema_version: str = Field(default="v3")
    action: str = Field(..., description="created | updated | closed_approved | closed_denied | closed_referred")
    occurred_at: str = Field(..., description="ISO-8601 UTC timestamp.")
    correlation_id: str = Field(..., description="ClinCase-side correlation ID (case_id).")
    member: FacetsMember
    treatment: FacetsTreatment
    determination: dict[str, Any] = Field(
        ...,
        description=(
            "{ verdict: APPROVE|DENY|REFER, rationale: str, citations: [str], "
            "tat_hours: int, decided_at_iso: str }"
        ),
    )
    external_decision_engine: FacetsClinCaseAttestation
    notes: str = Field(default="", description="Human-readable summary for reviewer eyes.")
    cms_0057f_clauses_satisfied: list[str] = Field(
        default_factory=list,
        description="CMS-0057-F clauses this case satisfies (e.g. ['§ IV.B.1', '§ IV.A']).",
    )


# =============================================================================
# Builder — ClinCase Decision -> FacetsPAEvent
# =============================================================================


def _hash_decision(verdict: str, rationale: str, citations: list[Any], model_id: str) -> str:
    """Tamper-evident SHA-256 over the determination payload.

    Facets reviewers + downstream auditors can rehash the rationale text +
    citations + model_id and verify it matches what's on file. Any subsequent
    edit invalidates the hash, exposing forgery.
    """
    material = f"{verdict}|{rationale}|{citations}|{model_id}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()


_VERDICT_TO_ACTION = {
    "APPROVE": "closed_approved",
    "DENY": "closed_denied",
    "REFER": "closed_referred",
}


def build_facets_event(
    *,
    case_id: str,
    payer_id: str,
    member_id: str,
    requested_treatment: dict[str, Any],
    decision: dict[str, Any],
    primary_model_id: str,
    confidence: float,
    triggered_hitl: bool,
    decision_run_id: str,
    cms_0057f_clauses_satisfied: list[str] | None = None,
    tat_hours: int | None = None,
) -> FacetsPAEvent:
    """Translate ClinCase's decision payload into a Facets PA event.

    Strict typing — Pydantic v2 catches every malformed input. This is the
    SINGLE place ClinCase schemas meet Facets schemas; there is no other
    coupling, by design.
    """
    verdict = decision.get("verdict", "REFER")
    rationale = decision.get("rationale", "")
    citations_raw = decision.get("citations") or []
    # Flatten structured citations to strings for Facets v3 notes field.
    citations_strs: list[str] = []
    for c in citations_raw:
        if isinstance(c, str):
            citations_strs.append(c)
        elif isinstance(c, dict):
            label = c.get("text") or c.get("pointer") or c.get("policy_id") or "citation"
            citations_strs.append(label)
        else:
            citations_strs.append(str(c))

    decided_at = datetime.now(timezone.utc).isoformat()

    return FacetsPAEvent(
        action=_VERDICT_TO_ACTION.get(verdict, "updated"),
        occurred_at=decided_at,
        correlation_id=case_id,
        member=FacetsMember(member_id=member_id, payer_id=payer_id),
        treatment=FacetsTreatment(
            j_code=requested_treatment.get("j_code"),
            cpt_code=requested_treatment.get("cpt_code"),
            drug_name=requested_treatment.get("name", "unspecified"),
            requested_units=requested_treatment.get("requested_units"),
            site_of_service=requested_treatment.get("site_of_service"),
        ),
        determination={
            "verdict": verdict,
            "rationale": rationale,
            "citations": citations_strs,
            "tat_hours": tat_hours,
            "decided_at_iso": decided_at,
        },
        external_decision_engine=FacetsClinCaseAttestation(
            decision_run_id=decision_run_id,
            primary_model_id=primary_model_id,
            confidence=confidence,
            triggered_hitl=triggered_hitl,
            case_id=case_id,
            decision_hash_sha256=_hash_decision(
                verdict, rationale, citations_strs, primary_model_id
            ),
        ),
        notes=(
            f"ClinCase AI determination: {verdict} (confidence {confidence:.2f}). "
            f"Run-id {decision_run_id}. {len(citations_strs)} citations attached. "
            + ("HITL-routed (CMS-0057-F § IV.C). " if triggered_hitl else "")
            + "Audit reproduction: GET /api/v1/cases/{}/audit".format(case_id)
        ),
        cms_0057f_clauses_satisfied=cms_0057f_clauses_satisfied or [],
    )
