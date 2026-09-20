"""Decision — output of the Decision Composer agent.

Source of truth: PROPOSAL.md §9.4.

Round 14 (prompt-engineering polish): Citation.kind expanded from
{clinical, policy} to also include {compendium, fda_label, guideline}.
This aligns the citation chain with how real payer denial / approval
letters cite authority — payers cite NCCN compendium entries, FDA
labels, and ASCO/ESMO guidelines as binding evidence, not just internal
policy bulletins. Backward compatible — existing tests with kind="clinical"
and kind="policy" continue to validate.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

CitationKind = Literal[
    "clinical",     # FHIR resource — patient evidence
    "policy",       # payer Clinical Policy Bulletin / Coverage Determination
    "compendium",   # NCCN, AHFS, Lexi-Drugs, Clinical Pharmacology, DrugDex
    "fda_label",    # FDA-approved drug label (Highlights of Prescribing Information)
    "guideline",    # ASCO, ESMO, ASH, ACS, NCCN-Guidelines (vs NCCN compendium)
]


class Citation(BaseModel):
    """A cited fact in a decision rationale or appeal letter.

    `pointer` follows kind-specific conventions:
      • clinical   → FHIR resource id (e.g. "obs-her2")
      • policy     → "Aetna CPB 0084 v2024.3 (rev 2024-08) § II.B.3"
      • compendium → "NCCN Drugs & Biologics Compendium v.4.2024 — trastuzumab — Breast"
      • fda_label  → "Trastuzumab HCP § 2.1 Recommended Dosage"
      • guideline  → "NCCN Guidelines Breast Cancer v.4.2024 BINV-K"
                  or "ASCO Guideline 2024 Update — HER2-Positive Breast Cancer"
    """
    kind: CitationKind
    text: str
    pointer: str


class Decision(BaseModel):
    verdict: Literal["APPROVE", "DENY", "REFER"]
    rationale: str               # 3-5 sentences plain English
    citations: list[Citation]
    confidence: float            # equals NecessityAssessment.overall_confidence
    risk_flags: list[str]        # off-label | high-cost | low-evidence | biomarker-mismatch | ...
