"""Human review: the reviewer's decision as data, and the Decision it becomes.

One source of truth for both the `/cases/{id}/resume` endpoint (which records the decision durably) and the
`human_decision` graph node (which feeds it to the remaining agents), so the stored row and the graph's
`Decision` can never disagree.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from app.models import Citation, Decision

# Why a run may stop for a human. Only the first two are produced today; the others are reserved so the
# verifier / evidence checks can pause through the same mechanism without a schema change.
PAUSE_KINDS = (
    "low_confidence",
    "missing_assessment",
    "verification_disagreement",
    "evidence_conflict",
)

STATUS_FOR_VERDICT = {"APPROVE": "approved", "DENY": "denied", "REFER": "referred"}


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
