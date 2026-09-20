"""AppealsDrafter — parent agent (6 of 7).

Orchestrator on the production framework. Composes 3 sub-agents:

  1. counter_evidence_finder    (LLM, Sonnet, REFLECTION) — evidence vs denial
  2. nccn_reference_specialist  (LLM, Haiku)              — NCCN guideline citations
  3. letter_composer            (LLM, Sonnet, REFLECTION) — formal appeal letter

Activated on DENY verdicts via the LangGraph conditional edge after the
Denial Forecaster.
"""
from __future__ import annotations

from datetime import date
from typing import ClassVar

from app.agents.appeals_drafter.schemas import (
    AppealsDrafterInput,
    AppealsDrafterOutput,
    CounterEvidenceFinderInput,
    LetterComposerInput,
    NCCNReferenceSpecialistInput,
)
from app.agents.appeals_drafter.sub_agents.counter_evidence_finder import counter_evidence_finder
from app.agents.appeals_drafter.sub_agents.letter_composer import letter_composer
from app.agents.appeals_drafter.sub_agents.nccn_reference_specialist import (
    nccn_reference_specialist,
)
from app.agents.framework import (
    Agent,
    AgentContext,
    SchemaGuardrail,
)
from app.models import AppealDraft

SUB_AGENTS = [counter_evidence_finder, nccn_reference_specialist, letter_composer]


class AppealsDrafterAgent(Agent[AppealsDrafterInput, AppealsDrafterOutput]):
    name: ClassVar[str] = "appeals_drafter"
    parent: ClassVar = None
    role: ClassVar[str] = "appeals_orchestration"
    description: ClassVar[str] = (
        "On DENY: drafts a NCCN-citing formal appeal letter + structured arguments "
        "JSON for payer-API submission."
    )

    input_schema: ClassVar[type] = AppealsDrafterInput
    output_schema: ClassVar[type] = AppealsDrafterOutput

    primary_model: ClassVar = None
    estimated_input_tokens: ClassVar[int] = 0
    estimated_output_tokens: ClassVar[int] = 0

    output_guardrails: ClassVar = [SchemaGuardrail(AppealsDrafterOutput)]

    async def _execute_deterministic(
        self,
        input: AppealsDrafterInput,
        ctx: AgentContext,
    ) -> AppealsDrafterOutput:
        # 1) Counter-evidence (Sonnet, with reflection)
        cef_result = await counter_evidence_finder.invoke(
            CounterEvidenceFinderInput(
                decision=input.decision,
                assessment=input.assessment,
                snapshot=input.snapshot,
                excerpts=input.excerpts,
            ),
            ctx=ctx,
        )

        # 2) NCCN references (Haiku)
        ncc_result = await nccn_reference_specialist.invoke(
            NCCNReferenceSpecialistInput(
                treatment_name=input.snapshot.requested_treatment.name,
                diagnosis_icd10=input.snapshot.primary_diagnosis.icd10_code,
                counter_items=cef_result.output.items,
            ),
            ctx=ctx,
        )

        # 3) Letter (Sonnet, with reflection)
        let_result = await letter_composer.invoke(
            LetterComposerInput(
                counter_items=cef_result.output.items,
                nccn_references=ncc_result.output.nccn_references,
                decision=input.decision,
                snapshot=input.snapshot,
                payer_id=input.payer_id,
            ),
            ctx=ctx,
        )

        appeal = AppealDraft(
            patient_initials=input.patient_initials,
            payer_id=input.payer_id,
            requested_treatment=input.snapshot.requested_treatment.name,
            denial_date=date.today().isoformat(),
            appeal_body=let_result.output.appeal_body,
            structured_arguments=let_result.output.structured_arguments,
            attachments_referenced=let_result.output.attachments_referenced,
            requested_action=let_result.output.requested_action,
        )

        return AppealsDrafterOutput(
            appeal=appeal,
            n_counter_items=len(cef_result.output.items),
            n_nccn_refs=len(ncc_result.output.nccn_references),
            letter_length_chars=len(let_result.output.appeal_body),
        )


appeals_drafter = AppealsDrafterAgent()



