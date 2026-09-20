"""NecessityReasonerAgent — parent orchestrator (3 of 7).

Composes 3 sub-agents through a shared `AgentContext`:

  1. criterion_splitter      (LLM, Sonnet)             — atomicize criteria
  2. evidence_matcher        (LLM, Sonnet, reflection) — fan-out per criterion
  3. confidence_calibrator   (LLM, Haiku)              — min-aggregation

Sub-agent #2 is parallelised via `asyncio.gather`. The parent's case-level
budget bounds the entire fan-out — a runaway parallel call still respects
the per-case ceiling because all sub-agents draw from the same
BudgetTracker on the shared AgentContext.
"""
from __future__ import annotations

import asyncio
from typing import ClassVar

from app.agents.framework import (
    Agent,
    AgentContext,
    SchemaGuardrail,
)
from app.agents.necessity_reasoner.schemas import (
    ConfidenceCalibratorInput,
    CriterionSplitterInput,
    EvidenceMatcherInput,
    NecessityReasonerInput,
    NecessityReasonerOutput,
)
from app.agents.necessity_reasoner.sub_agents import (
    confidence_calibrator,
    criterion_splitter,
    evidence_matcher,
)
from app.config import settings

# Public sub-agent registry — discovered by `app.agents.registry`.
SUB_AGENTS = [criterion_splitter, evidence_matcher, confidence_calibrator]

HITL_THRESHOLD = getattr(settings, "HITL_CONFIDENCE_THRESHOLD", 0.75)


class NecessityReasonerAgent(Agent[NecessityReasonerInput, NecessityReasonerOutput]):
    """Per-criterion necessity evaluator with parallel fan-out + HITL gate."""

    name: ClassVar[str] = "necessity_reasoner"
    parent: ClassVar = None
    role: ClassVar[str] = "necessity_orchestration"
    description: ClassVar[str] = (
        "Per-criterion MET/NOT_MET/AMBIGUOUS evaluation with calibrated confidence. "
        "Parallel fan-out across atomic criteria. Drives the HITL gate."
    )

    input_schema: ClassVar[type] = NecessityReasonerInput
    output_schema: ClassVar[type] = NecessityReasonerOutput

    primary_model: ClassVar = None
    estimated_input_tokens: ClassVar[int] = 0
    estimated_output_tokens: ClassVar[int] = 0

    output_guardrails: ClassVar = [SchemaGuardrail(NecessityReasonerOutput)]

    async def _execute_deterministic(
        self,
        input: NecessityReasonerInput,
        ctx: AgentContext,
    ) -> NecessityReasonerOutput:
        # Phase 1 — atomicize criteria (Sonnet)
        split_result = await criterion_splitter.invoke(
            CriterionSplitterInput(
                excerpts=input.excerpts,
                requested_treatment_name=input.snapshot.requested_treatment.name,
            ),
            ctx=ctx,
        )
        atomic = split_result.output.atomic_criteria

        # Phase 2 — evidence matching, parallel fan-out (REFLECTION enabled)
        match_results = await asyncio.gather(*[
            evidence_matcher.invoke(
                EvidenceMatcherInput(criterion=c, snapshot=input.snapshot),
                ctx=ctx,
            )
            for c in atomic
        ])
        # Backfill `criterion` onto each EvidenceMatch — the LLM doesn't
        # echo it back; the parent owns the (criterion, match) pairing.
        matches = [
            r.output.model_copy(update={"criterion": c})
            for r, c in zip(match_results, atomic, strict=False)
        ]

        # Phase 3 — confidence calibration + min-aggregation (Haiku)
        # Calibrator returns just the per-criterion confidences; the
        # orchestrator zips them with the matches it sent to assemble the
        # final NecessityAssessment. Keeps calibrator output small.
        cal_result = await confidence_calibrator.invoke(
            ConfidenceCalibratorInput(matches=matches),
            ctx=ctx,
        )
        assessment = cal_result.output.to_assessment(matches)

        return NecessityReasonerOutput(
            assessment=assessment,
            n_atomic_criteria=len(atomic),
            n_evidence_matches=len(matches),
            overall_confidence=assessment.overall_confidence,
            triggered_hitl=assessment.overall_confidence < HITL_THRESHOLD,
        )


necessity_reasoner = NecessityReasonerAgent()
