"""Document Intake — pre-processing layer that converts raw scans, photos,
and handwritten notes into a structured ClinicalSnapshot before the
existing 7-agent DAG fires.

Bounded responsibility (per AAOSA): this module ONLY produces an
IntakeResult. It does NOT reason about coverage, draft appeals, or talk
to the Necessity Reasoner. If a document is too low-quality, it sets
`requires_human_review=True` and lets the case_router dispatch to HITL.

Two-stage pipeline:

  1. classify_document() — rule-based PIL stats: typed vs handwritten vs
     mixed. Cheap, deterministic, no LLM. Always runs first.

  2. vision_extract()    — Claude Sonnet 4.6 vision via Bedrock. Reads the
     document AND emits a partial ClinicalSnapshot in one structured call.
     Handles printed text, handwritten Rx, mixed forms equally.

The two-stage shape preserves the multi-stage architecture story without
double-charging for LLM tokens — the classifier informs the vision prompt
("this is a handwritten Rx, expect drug name + dose") which materially
improves extraction accuracy on poor-quality inputs.
"""
from app.agents.intake.runner import parse_document

__all__ = ["parse_document"]
