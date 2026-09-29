"""PHISanitizer — Clinical Extractor sub-agent.

Deterministic best-effort pattern screening, not complete de-identification.
Output has a Bedrock-Guardrails-compatible PHI mask shape. Pattern-based PII
detection that emits the same shape Bedrock Guardrails returns from its
`assessments[].sensitiveInformationPolicy.piiEntities[]` block. Provider guardrails, when configured, are an additional control; this code
does not verify arbitrary free-text de-identification.
"""
from __future__ import annotations

import re
from typing import ClassVar

from app.agents.clinical_extractor.schemas import (
    PHIMask,
    PHISanitizerInput,
    PHISanitizerOutput,
)
from app.agents.framework import Agent, AgentContext

_PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    ("SSN",     re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),                 "{US_SOCIAL_SECURITY_NUMBER}"),
    ("MRN",     re.compile(r"\bMRN[:\s]?\d{6,10}\b", re.I),           "{MRN}"),
    ("DOB",     re.compile(r"\bDOB[:\s]?\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}\b", re.I), "{DATE_OF_BIRTH}"),
    ("DOB",     re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),                 "{DATE}"),
    ("EMAIL",   re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), "{EMAIL}"),
    ("PHONE",   re.compile(r"\b\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b"), "{PHONE}"),
    ("NAME",    re.compile(r"\b(?:patient(?: name)?|name)\s*:\s*[^\n;,]+", re.I), "{NAME}"),
    # Conservative unlabeled-name context. Avoid masking clinical phrases such
    # as "Malignant neoplasm" merely because both words are capitalized.
    ("NAME",    re.compile(r"\b[A-Z][a-z]{1,20} [A-Z][a-z]{1,20}(?=\s+(?:presented|arrived|reports|was|is|admitted)\b)"), "{NAME}"),
    ("ADDRESS", re.compile(r"\b\d{1,5} [A-Z][a-z]+ (Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd)\b"), "{ADDRESS}"),
]


class PHISanitizerAgent(Agent[PHISanitizerInput, PHISanitizerOutput]):
    name: ClassVar[str] = "phi_sanitizer"
    parent: ClassVar[str] = "clinical_extractor"
    role: ClassVar[str] = "phi_masking"
    description: ClassVar[str] = (
        "Pattern-based PII mask emitting Bedrock-Guardrails-compatible output shape. "
        "Not a guarantee of complete de-identification; provider governance remains required."
    )

    input_schema: ClassVar[type] = PHISanitizerInput
    output_schema: ClassVar[type] = PHISanitizerOutput

    primary_model: ClassVar = None
    estimated_input_tokens: ClassVar[int] = 0
    estimated_output_tokens: ClassVar[int] = 0

    async def _execute_deterministic(
        self,
        input: PHISanitizerInput,
        ctx: AgentContext,
    ) -> PHISanitizerOutput:
        text = input.text
        masks: list[PHIMask] = []
        for entity_type, pat, mask_token in _PATTERNS:
            for m in reversed(list(pat.finditer(text))):
                masks.append(
                    PHIMask(
                        type=entity_type,  # type: ignore[arg-type]
                        masked_value=mask_token,
                        char_offset=m.start(),
                    )
                )
                text = text[: m.start()] + mask_token + text[m.end() :]
        masks.sort(key=lambda m: m.char_offset)
        return PHISanitizerOutput(
            sanitized_text=text,
            masks=masks,
            bedrock_guardrail_compatible=True,
        )


phi_sanitizer = PHISanitizerAgent()
