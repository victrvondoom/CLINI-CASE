"""DecisionComposer — parent agent (4 of 7).

Orchestrator on the production framework. Composes 3 sub-agents:

  1. verdict_synthesizer  (deterministic) — APPROVE/DENY/REFER + audit trace
  2. rationale_writer     (LLM, Sonnet)   — executive rationale paragraph
  3. citation_linker      (LLM, Haiku)    — every claim has a pointer

Each emits its own row in `agent_runs` named `decision_composer.<sub_name>`.
"""
from __future__ import annotations

from typing import ClassVar

from app.agents.decision_composer.schemas import (
    CitationLinkerInput,
    DecisionComposerInput,
    DecisionComposerOutput,
    RationaleWriterInput,
    VerdictSynthesizerInput,
)
from app.agents.decision_composer.sub_agents.citation_linker import citation_linker
from app.agents.decision_composer.sub_agents.rationale_writer import rationale_writer
from app.agents.decision_composer.sub_agents.verdict_synthesizer import verdict_synthesizer
from app.agents.framework import (
    Agent,
    AgentContext,
    SchemaGuardrail,
)
from app.models import Decision

SUB_AGENTS = [verdict_synthesizer, rationale_writer, citation_linker]


class DecisionComposerAgent(Agent[DecisionComposerInput, DecisionComposerOutput]):
    name: ClassVar[str] = "decision_composer"
    parent: ClassVar = None
    role: ClassVar[str] = "decision_orchestration"
    description: ClassVar[str] = (
        "Deterministic verdict + LLM-written rationale + LLM-validated citation chain."
    )

    input_schema: ClassVar[type] = DecisionComposerInput
    output_schema: ClassVar[type] = DecisionComposerOutput

    primary_model: ClassVar = None
    estimated_input_tokens: ClassVar[int] = 0
    estimated_output_tokens: ClassVar[int] = 0

    output_guardrails: ClassVar = [SchemaGuardrail(DecisionComposerOutput)]

    async def _execute_deterministic(
        self,
        input: DecisionComposerInput,
        ctx: AgentContext,
    ) -> DecisionComposerOutput:
        # 1) Deterministic verdict
        verdict_result = await verdict_synthesizer.invoke(
            VerdictSynthesizerInput(assessment=input.assessment),
            ctx=ctx,
        )
        verdict_out = verdict_result.output

        # 2) LLM rationale
        rat_result = await rationale_writer.invoke(
            RationaleWriterInput(
                verdict=verdict_out.verdict,
                assessment=input.assessment,
                snapshot=input.snapshot,
                excerpts=input.excerpts,
            ),
            ctx=ctx,
        )

        # 3) LLM citation chain
        cit_result = await citation_linker.invoke(
            CitationLinkerInput(
                rationale=rat_result.output.rationale,
                assessment=input.assessment,
                excerpts=input.excerpts,
                snapshot=input.snapshot,
            ),
            ctx=ctx,
        )

        decision = Decision(
            verdict=verdict_out.verdict,
            rationale=rat_result.output.rationale,
            citations=cit_result.output.citations,
            confidence=input.assessment.overall_confidence,
            risk_flags=rat_result.output.risk_flags,
        )

        return DecisionComposerOutput(
            decision=decision,
            verdict_rule=verdict_out.trace.triggered_rule,
            n_citations=len(decision.citations),
        )


decision_composer = DecisionComposerAgent()



