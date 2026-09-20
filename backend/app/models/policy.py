"""Policy excerpt - one chunk retrieved from the payer policy corpus.

Source of truth: PROPOSAL.md §9.2.
"""
from __future__ import annotations

from pydantic import BaseModel


class PolicyExcerpt(BaseModel):
    payer_id: str           # e.g. "aetna"
    policy_id: str          # e.g. "0048"
    policy_title: str       # e.g. "Trastuzumab (Herceptin)"
    section_heading: str    # e.g. "Medical Necessity Criteria"
    excerpt_text: str       # raw policy text chunk (~500 tokens)
    source_url: str | None = None
    page_number: int | None = None
    relevance_score: float  # 0..1 from pgvector cosine similarity OR Bedrock KB score
