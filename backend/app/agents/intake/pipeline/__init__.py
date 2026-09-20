"""Document Intake pipeline — chain-of-responsibility with named stages.

Each stage:
  - declares its `name` (audit log key)
  - declares its `inputs_required` and `outputs_produced` (introspectable)
  - implements `async run(context)` that mutates the IntakeContext

The orchestrator runs stages in a configured order and captures per-stage
timing + errors so the audit ledger reconstructs every hop.

Public API: only `run_intake_pipeline(IntakeDocument) -> IntakeResult`.
"""
from app.agents.intake.pipeline.orchestrator import run_intake_pipeline

__all__ = ["run_intake_pipeline"]
