"""FHIRResourceValidator — Clinical Extractor sub-agent.

Deterministic. Pre-LLM Bundle structural validation. Confirms the Bundle
has resourceType=Bundle, contains entries with valid resource shapes,
counts each resource type, and collects any structural issues. Errors
short-circuit the parent before any LLM token is spent.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, ClassVar

from app.agents.clinical_extractor.schemas import (
    FHIRResourceIssue,
    FHIRResourceValidatorInput,
    FHIRResourceValidatorOutput,
)
from app.agents.framework import Agent, AgentContext

_REQUIRED_RESOURCE_TYPES = {"Patient", "Condition"}


class FHIRResourceValidatorAgent(
    Agent[FHIRResourceValidatorInput, FHIRResourceValidatorOutput]
):
    name: ClassVar[str] = "fhir_resource_validator"
    parent: ClassVar[str] = "clinical_extractor"
    role: ClassVar[str] = "structural_validation"
    description: ClassVar[str] = (
        "Validates FHIR R4 Bundle structure (Patient + Condition required; counts "
        "Observation / MedicationRequest / DiagnosticReport). Errors short-circuit "
        "the parent before any LLM call is made."
    )

    input_schema: ClassVar[type] = FHIRResourceValidatorInput
    output_schema: ClassVar[type] = FHIRResourceValidatorOutput

    primary_model: ClassVar = None
    estimated_input_tokens: ClassVar[int] = 0
    estimated_output_tokens: ClassVar[int] = 0

    async def _execute_deterministic(
        self,
        input: FHIRResourceValidatorInput,
        ctx: AgentContext,
    ) -> FHIRResourceValidatorOutput:
        bundle = input.fhir_bundle
        issues: list[FHIRResourceIssue] = []

        if not isinstance(bundle, dict) or bundle.get("resourceType") != "Bundle":
            issues.append(
                FHIRResourceIssue(
                    severity="error",
                    path="$.resourceType",
                    message="Top-level resourceType must be 'Bundle'.",
                )
            )
            return FHIRResourceValidatorOutput(
                is_valid=False, resource_counts={}, issues=issues
            )

        entries: list[dict[str, Any]] = bundle.get("entry") or []
        if not entries:
            issues.append(
                FHIRResourceIssue(
                    severity="error",
                    path="$.entry",
                    message="Bundle.entry is empty.",
                )
            )

        counts: Counter[str] = Counter()
        for i, e in enumerate(entries):
            r = e.get("resource") or {}
            rt = r.get("resourceType")
            if not rt:
                issues.append(
                    FHIRResourceIssue(
                        severity="error",
                        path=f"$.entry[{i}].resource.resourceType",
                        message="Missing resourceType.",
                    )
                )
                continue
            counts[rt] += 1

        for rt in _REQUIRED_RESOURCE_TYPES:
            if counts.get(rt, 0) == 0:
                issues.append(
                    FHIRResourceIssue(
                        severity="error",
                        path=f"$.entry[*].resource[resourceType={rt}]",
                        message=f"Bundle must contain at least one {rt} resource.",
                    )
                )

        is_valid = not any(i.severity == "error" for i in issues)
        return FHIRResourceValidatorOutput(
            is_valid=is_valid,
            resource_counts=dict(counts),
            issues=issues,
        )


fhir_resource_validator = FHIRResourceValidatorAgent()
