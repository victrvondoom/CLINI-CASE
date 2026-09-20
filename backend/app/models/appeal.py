"""Appeal draft - output of the Appeals Drafter agent.

Source of truth: PROPOSAL.md §9.5.
"""
from __future__ import annotations

from pydantic import BaseModel


class AppealArgument(BaseModel):
    contested_criterion: str
    payer_position: str
    counter_position: str
    cited_evidence: list[str]
    cited_policy_text: str
    cited_guideline: str  # e.g. "NCCN Breast Cancer v.4.2024 BINV-K"


class AppealDraft(BaseModel):
    patient_initials: str
    payer_id: str
    requested_treatment: str
    denial_date: str
    appeal_body: str                       # full letter text, ~500-800 words
    structured_arguments: list[AppealArgument]
    attachments_referenced: list[str]
    requested_action: str                  # e.g. "Overturn the denial and authorise..."
