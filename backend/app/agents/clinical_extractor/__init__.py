"""clinical_extractor — parent agent package."""

# node.py is imported for its side effects + legacy shims
from app.agents.clinical_extractor import node as _node

# Re-export the LangGraph node and key shims
from app.agents.clinical_extractor.node import (
    SYSTEM_PROMPT,
    _build_user_message,
    _strip_code_fence,
    clinical_extractor_node,
    extract_clinical_snapshot,
)
from app.agents.clinical_extractor.orchestrator import (
    SUB_AGENTS,
    ClinicalExtractorAgent,
    clinical_extractor,
)
from app.agents.clinical_extractor.schemas import *  # noqa: F401,F403
from app.agents.clinical_extractor.sub_agents import *  # noqa: F401,F403

__all__ = [
    "SYSTEM_PROMPT",
    "_build_user_message",
    "_strip_code_fence",
    "clinical_extractor_node",
    "extract_clinical_snapshot",
    "SUB_AGENTS",
    "ClinicalExtractorAgent",
    "clinical_extractor",
    "Biomarker",
    "ClinicalSnapshot",
    "ClinicalExtractorInput",
    "ClinicalExtractorOutput",
    "FHIRResourceValidatorInput",
    "FHIRResourceIssue",
    "FHIRResourceValidatorOutput",
    "BiomarkerSpecialistInput",
    "BiomarkerSpecialistOutput",
    "PHISanitizerInput",
    "PHIMask",
    "PHISanitizerOutput",
    "FHIRResourceValidatorAgent",
    "PHISanitizerAgent",
    "BiomarkerSpecialistAgent",
    "fhir_resource_validator",
    "phi_sanitizer",
    "biomarker_specialist",
]
