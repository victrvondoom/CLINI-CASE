# Clinical Extractor

Parent agent #1 of 7. Parses FHIR R4 bundle + physician note into a strictly-typed ClinicalSnapshot. PHI sanitised at the prompt boundary.

## Package layout

```
clinical_extractor/
├── __init__.py        public exports
├── orchestrator.py    Clinical ExtractorAgent (the parent class)
├── node.py            LangGraph wrapper + legacy compat shims
├── schemas.py         orchestrator + sub-agent I/O contracts
└── sub_agents/        3 sub-agents (one file each)
```

## Sub-agents

| Name | Kind | Reflection | What it does |
|------|------|-----------|--------------|
| `fhir_resource_validator` | deterministic | — | Validates FHIR R4 Bundle structure (Patient + Condition required; counts Observation / MedicationRequest / DiagnosticReport). Errors short-circuit the parent before any LLM call is made. |
| `phi_sanitizer` | deterministic | — | Pattern-based PII mask emitting Bedrock-Guardrails-compatible output shape. On Bedrock deployment this is replaced 1-for-1 by the Guardrail's PII filter. |
| `biomarker_specialist` | LLM (haiku) | — | Extracts a focused, treatment-relevant set of high-stakes oncology biomarkers (HER2, EGFR, BRCA1/2, MSI, PD-L1, ALK, ROS1, BRAF, ECOG, LVEF) from FHIR + note. |

## Lifecycle

This parent inherits the production lifecycle from `app.agents.framework.Agent`:
input validation → input guardrails → budget reservation → orchestrate sub-agents
through `AgentContext.child_for(span)` → output guardrails → reflection → trace
emit → return `AgentResult[ClinicalExtractorOutput]`.

The parent's `_execute_deterministic` body is the orchestration logic; it
never calls the LLM directly — every LLM call is owned by a sub-agent.

## Public exports

```python
from app.agents.clinical_extractor import (
    clinical_extractor,                      # the parent agent instance
    clinical_extractor_node,                 # LangGraph node wrapper
    SUB_AGENTS,                 # list of 3 sub-agent instances
    # plus all schemas and sub-agent instances
)
```

## Trace shape

Running this parent produces one `agent_runs` row for the orchestrator
(`clinical_extractor`) plus one row per sub-agent invocation (`clinical_extractor.<sub_name>`).
Hierarchy is reflected in the `AgentTrace.parent_span_id` chain.
