"""Contract tests for phi_sanitizer DeterministicSubAgent."""
from __future__ import annotations

from app.agents.clinical_extractor.schemas import PHISanitizerInput
from app.agents.clinical_extractor.sub_agents.phi_sanitizer import phi_sanitizer


def test_masks_ssn():
    out = phi_sanitizer._execute(  # noqa: SLF001
        PHISanitizerInput(text="Patient SSN 123-45-6789, requesting therapy.")
    )
    assert "{US_SOCIAL_SECURITY_NUMBER}" in out.sanitized_text
    assert "123-45-6789" not in out.sanitized_text
    assert any(m.type == "SSN" for m in out.masks)


def test_masks_mrn():
    out = phi_sanitizer._execute(  # noqa: SLF001
        PHISanitizerInput(text="MRN 1234567 admitted yesterday.")
    )
    assert "{MRN}" in out.sanitized_text
    assert any(m.type == "MRN" for m in out.masks)


def test_masks_phone_and_email():
    out = phi_sanitizer._execute(  # noqa: SLF001
        PHISanitizerInput(text="Reach the patient at john@example.com or 555-123-4567.")
    )
    assert "{EMAIL}" in out.sanitized_text
    assert "{PHONE}" in out.sanitized_text
    assert "john@example.com" not in out.sanitized_text


def test_masks_full_name():
    out = phi_sanitizer._execute(  # noqa: SLF001
        PHISanitizerInput(text="John Smith presented for follow-up.")
    )
    assert "{NAME}" in out.sanitized_text
    assert "John Smith" not in out.sanitized_text


def test_clean_text_passes_through():
    text = "Stage IIIA HER2-positive invasive ductal carcinoma."
    out = phi_sanitizer._execute(PHISanitizerInput(text=text))  # noqa: SLF001
    assert out.sanitized_text == text
    assert out.masks == []


def test_bedrock_compatibility_flag():
    """The sub-agent's output shape must match Bedrock Guardrails' PII filter."""
    out = phi_sanitizer._execute(  # noqa: SLF001
        PHISanitizerInput(text="Patient SSN 123-45-6789.")
    )
    assert out.bedrock_guardrail_compatible is True
