"""ClinCase agents — 7 parent orchestrators × 21 sub-agents.

Canonical architecture (everything is `Agent[I, O]` from app.agents.framework):

  Layer 1: framework           (lifecycle, budget, tools, memory, guardrails, grader)
  Layer 2: parents (7)         each is an Agent[OrchestratorInput, OrchestratorOutput]
                                 - clinical_extractor    (sub-agents: 3)
                                 - policy_retriever      (sub-agents: 3)
                                 - necessity_reasoner    (sub-agents: 3)
                                 - decision_composer     (sub-agents: 3)
                                 - denial_forecaster     (sub-agents: 3)
                                 - appeals_drafter       (sub-agents: 3)
                                 - patient_communicator  (sub-agents: 3)
  Layer 3: sub-agents (21)     each is an Agent[Input, Output] with its own
                                 prompt (LLM) or pure-Python execute (deterministic)

Public exports:
  - 7 parent agent INSTANCES (e.g. `clinical_extractor`)
  - 7 LangGraph node functions (e.g. `clinical_extractor_node`)
  - 7 backwards-compat shim functions (e.g. `extract_clinical_snapshot`)
  - the full AGENT_MANIFEST from .manifest

Importing this package is side-effect-free except for the canonical
agent instances being instantiated at module load time.
"""
from app.agents.appeals_drafter import (
    appeals_drafter,
    appeals_drafter_node,
    draft_appeal,
)
from app.agents.clinical_extractor import (
    clinical_extractor,
    clinical_extractor_node,
    extract_clinical_snapshot,
)
from app.agents.decision_composer import (
    compose_decision,
    decision_composer,
    decision_composer_node,
    derive_verdict,
)
from app.agents.denial_forecaster import (
    denial_forecaster,
    denial_forecaster_node,
    forecast_denial,
)
from app.agents.necessity_reasoner import (
    necessity_reasoner,
    necessity_reasoner_node,
    reason_necessity,
)
from app.agents.patient_communicator import (
    communicate_to_patient,
    patient_communicator,
    patient_communicator_node,
)
from app.agents.policy_retriever import (
    policy_retriever,
    policy_retriever_node,
    retrieve_policies,
)

__all__ = [
    # Parent agent instances
    "appeals_drafter",
    "clinical_extractor",
    "decision_composer",
    "denial_forecaster",
    "necessity_reasoner",
    "patient_communicator",
    "policy_retriever",
    # LangGraph node wrappers
    "appeals_drafter_node",
    "clinical_extractor_node",
    "decision_composer_node",
    "denial_forecaster_node",
    "necessity_reasoner_node",
    "patient_communicator_node",
    "policy_retriever_node",
    # Backwards-compat shims
    "communicate_to_patient",
    "compose_decision",
    "derive_verdict",
    "draft_appeal",
    "extract_clinical_snapshot",
    "forecast_denial",
    "reason_necessity",
    "retrieve_policies",
]
