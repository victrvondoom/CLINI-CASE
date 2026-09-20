"""Grader — self-evaluation sub-pattern for production agents.

A Grader is a small LLM agent that scores another agent's output on the
quality dimensions that matter for that role:
  • schema_correctness     (cheap; usually deterministic)
  • clinical_faithfulness  (no hallucinated facts)
  • citation_completeness  (every claim has a pointer)
  • policy_alignment       (output references the actual policy text)
  • clarity                (especially for patient-facing output)

If the score is below `quality_threshold`, the parent agent retries with
the grader's feedback embedded in the user message. Bounded by
`max_iterations` so we don't loop forever.

This is the difference between a "prompt with structured output" and a
real agent. The grader is what closes the loop.
"""
from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, Field

from app.agents.framework.models import HAIKU_GRADER, ModelSpec, resolve_model_id
from app.llm import get_llm_client

# =============================================================================
# Schemas
# =============================================================================


class GraderScore(BaseModel):
    """Numerical + textual quality score for an agent's output."""

    score: float = Field(..., ge=0.0, le=1.0)
    schema_correctness: float = Field(..., ge=0.0, le=1.0)
    clinical_faithfulness: float = Field(..., ge=0.0, le=1.0)
    citation_completeness: float = Field(..., ge=0.0, le=1.0)
    feedback: str = Field(
        ...,
        description="One paragraph in the model's voice: what's wrong + how to fix.",
    )


@dataclass
class GraderInput:
    agent_name: str
    purpose: str
    expected_schema_name: str
    output_payload_json: str  # the candidate output JSON


# =============================================================================
# Default LLM grader
# =============================================================================


_GRADER_SYSTEM_PROMPT = """You are the Grader — a senior clinical reasoning evaluator embedded in the ClinCase
prior-authorization pipeline.

Your job is to grade an agent's output on three dimensions, each ∈ [0.0, 1.0]:

  1. schema_correctness     — does the JSON parse cleanly and conform to the expected schema?
  2. clinical_faithfulness  — does every clinical claim derive from inputs the agent could see?
                              Penalize hallucinated biomarkers, invented dates, fabricated guidelines.
  3. citation_completeness  — for outputs that contain a rationale + citations: every factual claim
                              must point to a clinical evidence reference or a policy excerpt.

Compute `score` as the MIN of the three sub-scores (one weak link drags it down).
Provide one paragraph of `feedback` in the agent's voice — concrete, actionable.
If score >= 0.85, feedback is "OK".

Output strict JSON matching the GraderScore schema. No prose outside JSON. No code fences.
"""


class LLMGrader:
    """Cheap Haiku-grade evaluator that returns a GraderScore for any agent output."""

    name = "default_grader"
    model: ModelSpec = HAIKU_GRADER

    async def grade(
        self,
        candidate: GraderInput,
    ) -> tuple[GraderScore, dict[str, int]]:
        user_msg = (
            f"AGENT_NAME: {candidate.agent_name}\n"
            f"AGENT_PURPOSE: {candidate.purpose}\n"
            f"EXPECTED_OUTPUT_SCHEMA: {candidate.expected_schema_name}\n"
            f"\nCANDIDATE_OUTPUT_JSON:\n{candidate.output_payload_json}\n"
            f"\nOutput the GraderScore JSON now."
        )
        client = get_llm_client()
        response = await client.complete(
            system=_GRADER_SYSTEM_PROMPT,
            user=user_msg,
            max_tokens=self.model.max_tokens,
            temperature=self.model.temperature,
            model_id=resolve_model_id(self.model),
        )
        text = response.text.strip()
        if text.startswith("```"):
            text = "\n".join(text.split("\n")[1:-1])
        score = GraderScore.model_validate_json(text.strip())
        usage = {
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
            "model_id": response.model_id,
        }
        return score, usage


# Singleton — agents access via cls.grader
_default_grader: LLMGrader | None = None


def get_default_grader() -> LLMGrader:
    global _default_grader
    if _default_grader is None:
        _default_grader = LLMGrader()
    return _default_grader
