"""Necessity Reasoner sub-agents — public surface.

  • criterion_splitter      (LLM, Sonnet)              — atomicizes criteria
  • evidence_matcher        (LLM, Sonnet, REFLECTION)  — per-criterion judgement
  • confidence_calibrator   (LLM, Haiku)               — min-aggregation
"""
from app.agents.necessity_reasoner.sub_agents.confidence_calibrator import (
    ConfidenceCalibratorAgent,
    confidence_calibrator,
)
from app.agents.necessity_reasoner.sub_agents.criterion_splitter import (
    CriterionSplitterAgent,
    criterion_splitter,
)
from app.agents.necessity_reasoner.sub_agents.evidence_matcher import (
    EvidenceMatcherAgent,
    evidence_matcher,
)

__all__ = [
    "ConfidenceCalibratorAgent",
    "CriterionSplitterAgent",
    "EvidenceMatcherAgent",
    "confidence_calibrator",
    "criterion_splitter",
    "evidence_matcher",
]
