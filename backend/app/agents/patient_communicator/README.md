# Patient Communicator

Parent agent #7 of 7. Produces a 6th-grade-reading-level patient-facing summary + concrete next-step actions, calibrated to verdict tone.

## Package layout

```
patient_communicator/
├── __init__.py        public exports
├── orchestrator.py    Patient CommunicatorAgent (the parent class)
├── node.py            LangGraph wrapper + legacy compat shims
├── schemas.py         orchestrator + sub-agent I/O contracts
└── sub_agents/        3 sub-agents (one file each)
```

## Sub-agents

| Name | Kind | Reflection | What it does |
|------|------|-----------|--------------|
| `empathy_layer` | LLM (sonnet) | — | Picks tone (reassuring/neutral/urgent) by verdict and writes a patient-facing headline + 2–4 paragraph body in plain language. |
| `reading_level_tuner` | deterministic | — | Pure-Python Flesch-Kincaid grade calculator + banned-phrase substitution. Enforces ≤7th-grade reading level on patient-facing copy. |
| `action_step_writer` | LLM (haiku) | — | Generates up to 5 concrete next-step imperatives with timing tags (today/this_week/this_month/after_decision). |

## Lifecycle

This parent inherits the production lifecycle from `app.agents.framework.Agent`:
input validation → input guardrails → budget reservation → orchestrate sub-agents
through `AgentContext.child_for(span)` → output guardrails → reflection → trace
emit → return `AgentResult[PatientCommunicatorOutput]`.

The parent's `_execute_deterministic` body is the orchestration logic; it
never calls the LLM directly — every LLM call is owned by a sub-agent.

## Public exports

```python
from app.agents.patient_communicator import (
    patient_communicator,                      # the parent agent instance
    patient_communicator_node,                 # LangGraph node wrapper
    SUB_AGENTS,                 # list of 3 sub-agent instances
    # plus all schemas and sub-agent instances
)
```

## Trace shape

Running this parent produces one `agent_runs` row for the orchestrator
(`patient_communicator`) plus one row per sub-agent invocation (`patient_communicator.<sub_name>`).
Hierarchy is reflected in the `AgentTrace.parent_span_id` chain.
