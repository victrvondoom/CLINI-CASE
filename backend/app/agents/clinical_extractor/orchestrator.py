"""ClinicalExtractorAgent — parent orchestrator (1 of 7).

Composes 3 sub-agents:
  1. fhir_resource_validator  (deterministic) — Bundle structural validation
  2. phi_sanitizer            (deterministic) — Bedrock-Guardrail-compatible PHI mask
  3. biomarker_specialist     (LLM, Haiku)    — focused biomarker extraction

After sub-agents run, the parent fires ONE Sonnet LLM call to assemble the
full ClinicalSnapshot, merging the biomarker_specialist's curated list as
the authoritative biomarker block.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import ClassVar

from app.agents.clinical_extractor.schemas import (
    BiomarkerSpecialistInput,
    ClinicalExtractorInput,
    ClinicalExtractorOutput,
    FHIRResourceValidatorInput,
    PHISanitizerInput,
)
from app.agents.clinical_extractor.sub_agents import (
    biomarker_specialist,
    fhir_resource_validator,
    phi_sanitizer,
)
from app.agents.framework import (
    Agent,
    AgentContext,
    SchemaGuardrail,
    TokenBudgetGuardrail,
)
from app.llm import get_llm_client
from app.models import ClinicalSnapshot
from app.privacy.boundary import prepare_fhir, restore_source_ids, screen_text

SUB_AGENTS = [fhir_resource_validator, phi_sanitizer, biomarker_specialist]

_PROMPT_PATH = (
    Path(__file__).resolve().parents[2] / "prompts" / "clinical_extractor" / "orchestrator.txt"
)


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        end = len(lines) - 1 if lines[-1].strip().startswith("```") else len(lines)
        text = "\n".join(lines[1:end])
    return text.strip()


class ClinicalExtractorAgent(Agent[ClinicalExtractorInput, ClinicalExtractorOutput]):
    name: ClassVar[str] = "clinical_extractor"
    parent: ClassVar = None
    role: ClassVar[str] = "fhir_to_snapshot_orchestration"
    description: ClassVar[str] = (
        "Parses FHIR R4 bundle + physician note into a strictly-typed ClinicalSnapshot. "
        "PHI sanitised at the prompt boundary."
    )

    input_schema: ClassVar[type] = ClinicalExtractorInput
    output_schema: ClassVar[type] = ClinicalExtractorOutput

    # This is an ORCHESTRATOR. primary_model = None so the framework runs
    # `_execute_deterministic` (which composes sub-agents). The Sonnet LLM
    # call that assembles the final snapshot is invoked DIRECTLY inside
    # `_execute_deterministic` — not through Agent.invoke — because the
    # parent's job is to coordinate, not to be a single LLM call.
    primary_model: ClassVar = None
    system_prompt: ClassVar[str] = _PROMPT_PATH.read_text(encoding="utf-8")
    estimated_input_tokens: ClassVar[int] = 0
    estimated_output_tokens: ClassVar[int] = 0
    max_iterations: ClassVar[int] = 1

    input_guardrails: ClassVar = [TokenBudgetGuardrail(max_input_tokens=20_000)]
    output_guardrails: ClassVar = [SchemaGuardrail(ClinicalExtractorOutput)]

    async def _execute_deterministic(
        self,
        input: ClinicalExtractorInput,
        ctx: AgentContext,
    ) -> ClinicalExtractorOutput:
        # 1) Validate FHIR Bundle + 2) PHI-sanitize the physician note — run
        # concurrently via asyncio.gather. These two calls read completely
        # disjoint inputs (input.fhir_bundle vs input.physician_note), neither
        # depends on the other's output, and both sub-agents are pure
        # w.r.t. each other (no shared mutable state) — see
        # fhir_resource_validator._execute_deterministic and
        # phi_sanitizer._execute_deterministic. Same fan-out pattern as
        # necessity_reasoner's evidence_matcher parallelization. Both calls
        # complete before either result is inspected below, which is fine
        # here since a validation failure has no side effects contingent on
        # the sanitizer (or vice versa) — the ValueError is still raised,
        # and still raised before the biomarker/Sonnet steps run.
        if input.physician_note:
            validation, phi_result = await asyncio.gather(
                fhir_resource_validator.invoke(
                    FHIRResourceValidatorInput(fhir_bundle=input.fhir_bundle), ctx=ctx
                ),
                phi_sanitizer.invoke(PHISanitizerInput(text=input.physician_note), ctx=ctx),
            )
        else:
            validation = await fhir_resource_validator.invoke(
                FHIRResourceValidatorInput(fhir_bundle=input.fhir_bundle), ctx=ctx
            )
            phi_result = None

        if not validation.output.is_valid:
            errors = [i.message for i in validation.output.issues if i.severity == "error"]
            raise ValueError("FHIR Bundle failed validation: " + "; ".join(errors))

        redacted_note: str | None = None
        n_phi_masked = 0
        if phi_result is not None:
            redacted_note = phi_result.output.sanitized_text
            n_phi_masked = len(phi_result.output.masks)

        # 3) Biomarker Specialist (Haiku)
        bio_result = await biomarker_specialist.invoke(
            BiomarkerSpecialistInput(
                fhir_bundle=input.fhir_bundle,
                physician_note_redacted=redacted_note,
                requested_treatment_name=input.requested_treatment.get("name", ""),
            ),
            ctx=ctx,
        )

        # 4) Final extractor LLM (Sonnet) — assemble the full snapshot
        client = get_llm_client()
        user_msg = self._build_extractor_user_message(input, redacted_note)
        response = await client.complete(
            system=self.system_prompt,
            user=user_msg,
            max_tokens=2000,
            temperature=0.0,
        )
        snapshot = ClinicalSnapshot.model_validate_json(_strip_code_fence(response.text))

        if bio_result.output.biomarkers:
            snapshot = snapshot.model_copy(update={"biomarkers": bio_result.output.biomarkers})

        # Provider-visible aliases preserve evidence linking without exposing raw IDs.
        _, alias_map = prepare_fhir(input.fhir_bundle)
        snapshot = ClinicalSnapshot.model_validate(
            restore_source_ids(snapshot.model_dump(), alias_map)
        )
        return ClinicalExtractorOutput(
            snapshot=snapshot,
            n_resources_validated=sum(validation.output.resource_counts.values()),
            phi_entities_masked=n_phi_masked,
            n_biomarkers_extracted=len(snapshot.biomarkers),
        )

    @staticmethod
    def _build_extractor_user_message(
        input: ClinicalExtractorInput, redacted_note: str | None
    ) -> str:
        parts = [
            "FHIR_BUNDLE:",
            json.dumps(prepare_fhir(input.fhir_bundle)[0], indent=2),
        ]
        if redacted_note:
            parts += ["", "PHYSICIAN_NOTE_REDACTED:", redacted_note]
        parts += [
            "",
            "REQUESTED_TREATMENT:",
            screen_text(json.dumps(input.requested_treatment, indent=2)),
            "",
            "Output the ClinicalSnapshot JSON object now.",
        ]
        return "\n".join(parts)


clinical_extractor = ClinicalExtractorAgent()
