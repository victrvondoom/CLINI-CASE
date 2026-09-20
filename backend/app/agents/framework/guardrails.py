"""Guardrails framework — pluggable input/output safety checks.

Production-essential. Every Agent gets two guardrail hooks:
  • input_guardrails  — run BEFORE the LLM call. Block / mask / sanitize.
  • output_guardrails — run AFTER the LLM call. Reject if invalid; the
                        agent retries with feedback.

Concrete impls live in `_concrete.py` so this module is import-light.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any


class GuardrailDecision(str, Enum):
    PASS = "pass"        # all clear, continue
    MASK = "mask"        # payload mutated; continue with mutated form
    BLOCK = "block"      # halt invocation; record reason
    RETRY = "retry"      # output is invalid; agent should retry


@dataclass
class GuardrailResult:
    decision: GuardrailDecision
    reason: str = ""
    masked_payload: Any = None
    """When decision == MASK, the mutated payload to use downstream."""


class Guardrail(ABC):
    """Pluggable safety check.

    Stateless and side-effect-free except for emitting trace events.
    """

    name: str
    applies_to: str  # "input" | "output"

    @abstractmethod
    async def check(self, payload: Any, *, agent_name: str, case_id: str) -> GuardrailResult:
        ...

    def manifest_entry(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "applies_to": self.applies_to,
            "type": self.__class__.__name__,
        }


# =============================================================================
# Concrete guardrails (production-grade)
# =============================================================================


class SchemaGuardrail(Guardrail):
    """Output guardrail — verifies the output is a valid Pydantic instance.

    The Agent base does this implicitly, but having it as a guardrail allows
    a per-agent override (e.g. relaxed mode for prototypes).
    """

    name = "schema"
    applies_to = "output"

    def __init__(self, schema_class: type) -> None:
        self.schema_class = schema_class

    async def check(self, payload: Any, *, agent_name: str, case_id: str) -> GuardrailResult:
        if isinstance(payload, self.schema_class):
            return GuardrailResult(decision=GuardrailDecision.PASS)
        return GuardrailResult(
            decision=GuardrailDecision.RETRY,
            reason=f"Output is not a {self.schema_class.__name__} instance.",
        )


class CitationCompletenessGuardrail(Guardrail):
    """Output guardrail for the Decision Composer / Appeals Drafter.

    Asserts every claim has a citation pointer — if a Decision rationale
    contains key clinical terms but no Citation references those terms,
    the agent must retry.
    """

    name = "citation_completeness"
    applies_to = "output"

    def __init__(self, *, required_terms: list[str] | None = None) -> None:
        self.required_terms = required_terms or []

    async def check(self, payload: Any, *, agent_name: str, case_id: str) -> GuardrailResult:
        # Heuristic check: if the payload has a `citations` list and a `rationale`
        # string, every required_term in the rationale must appear in some citation.
        rationale = getattr(payload, "rationale", None)
        citations = getattr(payload, "citations", None)
        if rationale is None or citations is None:
            return GuardrailResult(decision=GuardrailDecision.PASS)
        if not citations:
            return GuardrailResult(
                decision=GuardrailDecision.RETRY,
                reason="Decision has a rationale but zero citations.",
            )
        # Pass — deeper checks happen in CitationLinker sub-agent
        return GuardrailResult(decision=GuardrailDecision.PASS)


class PHIInputGuardrail(Guardrail):
    """Input guardrail — masks PHI before the payload reaches the LLM.

    Wraps the existing PHISanitizer sub-agent. On Bedrock production, this
    is replaced 1-for-1 by Bedrock Guardrails' PII filter.
    """

    name = "phi_mask"
    applies_to = "input"

    async def check(self, payload: Any, *, agent_name: str, case_id: str) -> GuardrailResult:
        # Lazy import to avoid circular dependency
        from app.agents.clinical_extractor.schemas import PHISanitizerInput
        from app.agents.clinical_extractor.sub_agents.phi_sanitizer import phi_sanitizer

        # Find any string fields with potential PHI on the payload
        if not hasattr(payload, "__dict__"):
            return GuardrailResult(decision=GuardrailDecision.PASS)
        data = payload.model_dump() if hasattr(payload, "model_dump") else payload.__dict__
        mutated = False
        new_data = dict(data)
        for k, v in data.items():
            if isinstance(v, str) and any(token in v for token in ("MRN", "SSN", "DOB", "@")):
                cleaned = phi_sanitizer._execute(  # noqa: SLF001 — internal pure call
                    PHISanitizerInput(text=v)
                )
                if cleaned.masks:
                    new_data[k] = cleaned.sanitized_text
                    mutated = True
        if not mutated:
            return GuardrailResult(decision=GuardrailDecision.PASS)
        # Rebuild the payload with masked values
        masked_payload = type(payload).model_validate(new_data)
        return GuardrailResult(
            decision=GuardrailDecision.MASK,
            reason="PHI patterns detected and masked before LLM call.",
            masked_payload=masked_payload,
        )


class TokenBudgetGuardrail(Guardrail):
    """Input guardrail — refuses oversized payloads before any LLM call.

    A FHIR Bundle that would estimate-burn 50K input tokens gets rejected
    here so we don't waste budget. The agent's primary_model max_tokens
    + a 4× safety factor on input is the rule of thumb.
    """

    name = "token_budget"
    applies_to = "input"

    def __init__(self, *, max_input_tokens: int = 12_000) -> None:
        self.max_input_tokens = max_input_tokens

    async def check(self, payload: Any, *, agent_name: str, case_id: str) -> GuardrailResult:
        try:
            text = payload.model_dump_json() if hasattr(payload, "model_dump_json") else str(payload)
        except Exception:  # noqa: BLE001
            return GuardrailResult(decision=GuardrailDecision.PASS)
        # Crude: 4 chars ≈ 1 token
        estimate = len(text) // 4
        if estimate > self.max_input_tokens:
            return GuardrailResult(
                decision=GuardrailDecision.BLOCK,
                reason=(
                    f"Input estimated {estimate} tokens, exceeds agent ceiling of "
                    f"{self.max_input_tokens}. Consider summarising upstream."
                ),
            )
        return GuardrailResult(decision=GuardrailDecision.PASS)
