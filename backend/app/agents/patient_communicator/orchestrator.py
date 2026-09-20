"""PatientCommunicator — parent agent (7 of 7).

Orchestrator on the production framework. Composes 3 sub-agents:

  1. empathy_layer        (LLM, Sonnet)   — verdict-tuned headline + body
  2. reading_level_tuner  (deterministic) — Flesch-Kincaid + banned-phrase strip
  3. action_step_writer   (LLM, Haiku)    — concrete next-step list

empathy_layer + action_step_writer fire concurrently; reading_level_tuner
runs after empathy_layer to apply Flesch-Kincaid grade enforcement.
"""
from __future__ import annotations

import asyncio
from typing import ClassVar

from app.agents.framework import (
    Agent,
    AgentContext,
    SchemaGuardrail,
)
from app.agents.patient_communicator.schemas import (
    ActionStepWriterInput,
    EmpathyLayerInput,
    PatientCommunicatorInput,
    PatientCommunicatorOutput,
    ReadingLevelTunerInput,
)
from app.agents.patient_communicator.sub_agents.action_step_writer import action_step_writer
from app.agents.patient_communicator.sub_agents.empathy_layer import empathy_layer
from app.agents.patient_communicator.sub_agents.reading_level_tuner import reading_level_tuner
from app.models.communication import PatientCommunication

SUB_AGENTS = [empathy_layer, reading_level_tuner, action_step_writer]


class PatientCommunicatorAgent(Agent[PatientCommunicatorInput, PatientCommunicatorOutput]):
    name: ClassVar[str] = "patient_communicator"
    parent: ClassVar = None
    role: ClassVar[str] = "patient_communication_orchestration"
    description: ClassVar[str] = (
        "Produces a 6th-grade-reading-level patient-facing summary + concrete "
        "next-step actions, calibrated to verdict tone."
    )

    input_schema: ClassVar[type] = PatientCommunicatorInput
    output_schema: ClassVar[type] = PatientCommunicatorOutput

    primary_model: ClassVar = None
    estimated_input_tokens: ClassVar[int] = 0
    estimated_output_tokens: ClassVar[int] = 0

    output_guardrails: ClassVar = [SchemaGuardrail(PatientCommunicatorOutput)]

    async def _execute_deterministic(
        self,
        input: PatientCommunicatorInput,
        ctx: AgentContext,
    ) -> PatientCommunicatorOutput:
        # 1 + 3 in parallel
        empathy_task = empathy_layer.invoke(
            EmpathyLayerInput(
                decision=input.decision,
                snapshot=input.snapshot,
                appeal=input.appeal,
                payer_id=input.payer_id,
            ),
            ctx=ctx,
        )
        steps_task = action_step_writer.invoke(
            ActionStepWriterInput(decision=input.decision, appeal=input.appeal),
            ctx=ctx,
        )
        empathy_result, steps_result = await asyncio.gather(empathy_task, steps_task)

        # 2 — deterministic reading-level tune
        tune_result = await reading_level_tuner.invoke(
            ReadingLevelTunerInput(
                headline=empathy_result.output.headline,
                body=empathy_result.output.body,
                target_grade=7.0,
            ),
            ctx=ctx,
        )

        comm = PatientCommunication(
            headline=empathy_result.output.headline,
            body=tune_result.output.body_with_substitutions,
            next_steps=steps_result.output.next_steps,
            tone=empathy_result.output.tone,
            reading_level_grade=tune_result.output.grade,
            contains_phi=False,
        )

        return PatientCommunicatorOutput(
            communication=comm,
            grade_meets_target=tune_result.output.meets_target,
            n_next_steps=len(comm.next_steps),
        )


patient_communicator = PatientCommunicatorAgent()



