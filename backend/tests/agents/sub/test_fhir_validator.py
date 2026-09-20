"""Contract tests for fhir_resource_validator DeterministicSubAgent."""
from __future__ import annotations

from app.agents.clinical_extractor.schemas import FHIRResourceValidatorInput
from app.agents.clinical_extractor.sub_agents.fhir_resource_validator import fhir_resource_validator


def test_valid_minimal_bundle():
    bundle = {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [
            {"resource": {"resourceType": "Patient", "id": "p1"}},
            {"resource": {"resourceType": "Condition", "id": "c1"}},
        ],
    }
    out = fhir_resource_validator._execute(  # noqa: SLF001
        FHIRResourceValidatorInput(fhir_bundle=bundle)
    )
    assert out.is_valid is True
    assert out.resource_counts["Patient"] == 1
    assert out.resource_counts["Condition"] == 1
    assert all(i.severity != "error" for i in out.issues)


def test_rejects_non_bundle():
    out = fhir_resource_validator._execute(  # noqa: SLF001
        FHIRResourceValidatorInput(fhir_bundle={"resourceType": "Patient"})
    )
    assert out.is_valid is False
    assert any(i.severity == "error" for i in out.issues)


def test_requires_patient_and_condition():
    """Missing required resources → invalid."""
    bundle = {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [
            {"resource": {"resourceType": "Observation", "id": "o1"}},
        ],
    }
    out = fhir_resource_validator._execute(  # noqa: SLF001
        FHIRResourceValidatorInput(fhir_bundle=bundle)
    )
    assert out.is_valid is False
    error_msgs = " ".join(i.message for i in out.issues if i.severity == "error")
    assert "Patient" in error_msgs
    assert "Condition" in error_msgs


def test_counts_observation_and_medication_request():
    bundle = {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [
            {"resource": {"resourceType": "Patient", "id": "p1"}},
            {"resource": {"resourceType": "Condition", "id": "c1"}},
            {"resource": {"resourceType": "Observation", "id": "o1"}},
            {"resource": {"resourceType": "Observation", "id": "o2"}},
            {"resource": {"resourceType": "MedicationRequest", "id": "m1"}},
        ],
    }
    out = fhir_resource_validator._execute(  # noqa: SLF001
        FHIRResourceValidatorInput(fhir_bundle=bundle)
    )
    assert out.is_valid is True
    assert out.resource_counts["Observation"] == 2
    assert out.resource_counts["MedicationRequest"] == 1
