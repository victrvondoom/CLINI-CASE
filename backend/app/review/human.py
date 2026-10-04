"""Human review: the reviewer's decision as data, and the Decision it becomes.

One source of truth for both the `/cases/{id}/resume` endpoint (which records the decision durably) and the
`human_decision` graph node (which feeds it to the remaining agents), so the stored row and the graph's
`Decision` can never disagree.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel

from app.models import Citation, Decision

if TYPE_CHECKING:
    from app.graph.state import ClinCaseState

# Why a run may stop for a human. Only the first two are produced today; the others are reserved so the
# verifier / evidence checks can pause through the same mechanism without a schema change.
PAUSE_KINDS = (
    "low_confidence",
    "missing_assessment",
    "verification_disagreement",
    "evidence_conflict",
    "ai_denial",
)

STATUS_FOR_VERDICT = {"APPROVE": "approved", "DENY": "denied", "REFER": "referred"}


def ai_case_status(verdict: str) -> str:
    """Every AI denial requires an authenticated human decision before finalization."""
    return "awaiting_review" if verdict == "DENY" else STATUS_FOR_VERDICT.get(verdict, "pending")


def require_denial_review(final: ClinCaseState) -> ClinCaseState:
    """Hold an AI DENY after drafting, without promoting it to an authoritative decision.

    Applies at both persistence boundaries, even to older/custom graph implementations.
    The provisional decision remains in the run state for draft generation and audit only.
    """
    if final.decision is None or final.decision.verdict != "DENY" or final.human_review:
        return final
    return final.model_copy(
        update={
            "paused_for_review": True,
            "pause_kind": final.pause_kind or "ai_denial",
            "pause_reason": final.pause_reason
            or "AI-proposed denial requires a clinician's review. Documents are drafts until review.",
        }
    )


def public_run_outputs(final: ClinCaseState) -> dict[str, Any]:
    """Separate the reviewed outcome from a proposed decision and provisional documents."""
    pending = final.paused_for_review
    decision = final.decision.model_dump(mode="json") if final.decision else None
    return {
        "clinical_snapshot": final.clinical_snapshot.model_dump(mode="json")
        if final.clinical_snapshot
        else None,
        "policy_excerpts": [e.model_dump(mode="json") for e in final.policy_excerpts],
        "necessity_assessment": final.necessity_assessment.model_dump(mode="json")
        if final.necessity_assessment
        else None,
        "decision": None if pending else decision,
        "provisional_decision": decision if pending else None,
        "denial_forecast": final.denial_forecast.model_dump(mode="json")
        if final.denial_forecast
        else None,
        "appeal_draft": final.appeal_draft.model_dump(mode="json") if final.appeal_draft else None,
        "patient_communication": final.patient_communication.model_dump(mode="json")
        if final.patient_communication
        else None,
        "paused_for_review": pending,
        "human_review_required": pending,
        "documents_draft": pending,
        "pause_reason": final.pause_reason,
        "pause_kind": final.pause_kind,
    }


class HumanReview(BaseModel):
    verdict: Literal["APPROVE", "DENY", "REFER"]
    reviewer_id: str
    reviewer_email: str
    reviewer_role: str
    note: str | None = None
    pause_kind: str | None = None
    pause_run_id: str | None = None


def build_human_decision(review: HumanReview) -> Decision:
    """The Decision a human sign-off produces (confidence 1.0; cites the reviewer action)."""
    reason = {
        "low_confidence": "low Necessity Reasoner confidence",
        "missing_assessment": "a missing necessity assessment",
        "verification_disagreement": "a verification disagreement",
        "evidence_conflict": "an evidence conflict",
        "ai_denial": "an AI-proposed denial",
    }.get(review.pause_kind or "", "an automatic pause")
    rationale = (
        f"HUMAN REVIEWER OVERRIDE — clinician {review.reviewer_email} (role={review.reviewer_role}) "
        f"reviewed this case after ClinCase paused at the review_gate due to {reason}. "
        f"Reviewer verdict: {review.verdict}. "
        f"Reviewer note: {review.note or '(none)'}. "
        f"Provenance per CMS-0057-F § IV.C and CA SB 1120."
    )
    return Decision(
        verdict=review.verdict,
        rationale=rationale,
        citations=[
            Citation(
                kind="human_override",
                text=f"Reviewer {review.reviewer_email} clinical sign-off",
                pointer=f"reviewer_action:{review.reviewer_id}",
            )
        ],
        confidence=1.0,
        risk_flags=[],
    )
