"""patient_communicator — parent agent package."""
# node.py is imported for its side effects + legacy shims
from app.agents.patient_communicator import node as _node

# Re-export the LangGraph node and key shims
from app.agents.patient_communicator.node import (
    communicate_to_patient,
    patient_communicator_node,
)
from app.agents.patient_communicator.orchestrator import (
    SUB_AGENTS,
    PatientCommunicatorAgent,
    patient_communicator,
)
from app.agents.patient_communicator.schemas import *  # noqa: F401,F403
from app.agents.patient_communicator.sub_agents import *  # noqa: F401,F403

__all__ = [
    "communicate_to_patient",
    "patient_communicator_node",
    "SUB_AGENTS",
    "PatientCommunicatorAgent",
    "patient_communicator",
    "AppealDraft",
    "ClinicalSnapshot",
    "Decision",
    "PatientCommunication",
    "PatientNextStep",
    "PatientCommunicatorInput",
    "PatientCommunicatorOutput",
    "EmpathyLayerInput",
    "EmpathyLayerOutput",
    "ReadingLevelTunerInput",
    "ReadingLevelTunerOutput",
    "ActionStepWriterInput",
    "ActionStepWriterOutput",
    "EmpathyLayerAgent",
    "ReadingLevelTunerAgent",
    "ActionStepWriterAgent",
    "empathy_layer",
    "reading_level_tuner",
    "action_step_writer",
]
