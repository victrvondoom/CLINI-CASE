"""Contract test for the Clinical Extractor agent.

Bypasses trace_agent (no DB needed) - validates the LLM contract directly:
prompt + FHIR bundle -> valid ClinicalSnapshot with the right key fields.
"""
from __future__ import annotations

import pytest

from app.agents.clinical_extractor import (
    SYSTEM_PROMPT,
    _build_user_message,
    _strip_code_fence,
)
from app.graph.state import ClinCaseState
from app.llm import get_llm_client
from app.models import ClinicalSnapshot


@pytest.mark.asyncio
async def test_extracts_stage_iiia_her2pos_breast_cancer(fhir_bundle_factory):
    """Per PROPOSAL.md §9.1: must extract diagnosis, stage, biomarkers, treatment."""
    bundle = fhir_bundle_factory("stage3_her2pos_breast")
    state = ClinCaseState(
        case_id="contract-test",
        fhir_bundle=bundle,
        physician_note=(
            "Patient is a 53-year-old female with newly diagnosed stage IIIA "
            "invasive ductal carcinoma of the right breast, HER2-positive, "
            "ER and PR negative. Performance status ECOG 1. No prior systemic therapy."
        ),
        requested_treatment={"name": "trastuzumab", "j_code": "J9355"},
        payer_id="aetna",
    )

    # Direct LLM call - bypasses trace_agent / DB
    response = await get_llm_client().complete(
        system=SYSTEM_PROMPT,
        user=_build_user_message(state),
        max_tokens=2000,
        temperature=0.0,
    )
    snap = ClinicalSnapshot.model_validate_json(_strip_code_fence(response.text))

    # Diagnosis: malignant neoplasm of breast (ICD-10 C50.x)
    assert snap.primary_diagnosis.icd10_code.startswith("C50"), (
        f"Expected ICD-10 starting C50, got {snap.primary_diagnosis.icd10_code}"
    )

    # Stage: IIIA (AJCC notation)
    assert snap.primary_diagnosis.stage == "IIIA", (
        f"Expected stage IIIA, got {snap.primary_diagnosis.stage}"
    )

    # HER2 biomarker: positive
    assert any(
        b.name.upper() == "HER2"
        and b.value.lower() in ("positive", "3+", "high", "positive (3+)")
        for b in snap.biomarkers
    ), f"HER2-positive should be in biomarkers; got {[b.model_dump() for b in snap.biomarkers]}"

    # Requested treatment: trastuzumab
    assert snap.requested_treatment.name.lower() == "trastuzumab"

    # ECOG performance status: 1
    assert snap.performance_status == "1", (
        f"Expected ECOG '1', got {snap.performance_status}"
    )

    # Source resource id traceability
    assert snap.primary_diagnosis.source_resource_id == "condition-primary"

    # Free text summary: a short clinical paragraph. We allow up to 10 sentences
    # because LLM verbosity varies even at temperature 0; the contract is
    # "concise human-readable summary", not "exact sentence count".
    sentences = [s for s in snap.free_text_summary.split(".") if s.strip()]
    assert 3 <= len(sentences) <= 10, (
        f"Expected 3-10 sentence summary, got {len(sentences)} sentences"
    )
