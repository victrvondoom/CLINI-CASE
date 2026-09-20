# Appeals Drafter

Parent agent #6 of 7. On DENY: drafts a NCCN-citing formal appeal letter + structured arguments JSON for payer-API submission.

## Package layout

```
appeals_drafter/
├── __init__.py        public exports
├── orchestrator.py    Appeals DrafterAgent (the parent class)
├── node.py            LangGraph wrapper + legacy compat shims
├── schemas.py         orchestrator + sub-agent I/O contracts
└── sub_agents/        3 sub-agents (one file each)
```

## Sub-agents

| Name | Kind | Reflection | What it does |
|------|------|-----------|--------------|
| `counter_evidence_finder` | LLM (sonnet) | reflection 0.8 | For each contested criterion, extracts payer position + counter position + supporting evidence quotations from the snapshot. |
| `nccn_reference_specialist` | LLM (haiku) | — | Returns 1–5 precise NCCN Clinical Practice Guidelines references that support the patient's counter-position (e.g. 'NCCN Breast 4.2025 § BINV-J'). |
| `letter_composer` | LLM (sonnet) | reflection 0.8 | Produces a ~600-word formal appeal letter (5-paragraph structure) plus AppealArgument JSON entries for payer-API submission. |

## Lifecycle

This parent inherits the production lifecycle from `app.agents.framework.Agent`:
input validation → input guardrails → budget reservation → orchestrate sub-agents
through `AgentContext.child_for(span)` → output guardrails → reflection → trace
emit → return `AgentResult[AppealsDrafterOutput]`.

The parent's `_execute_deterministic` body is the orchestration logic; it
never calls the LLM directly — every LLM call is owned by a sub-agent.

## Public exports

```python
from app.agents.appeals_drafter import (
    appeals_drafter,                      # the parent agent instance
    appeals_drafter_node,                 # LangGraph node wrapper
    SUB_AGENTS,                 # list of 3 sub-agent instances
    # plus all schemas and sub-agent instances
)
```

## Trace shape

Running this parent produces one `agent_runs` row for the orchestrator
(`appeals_drafter`) plus one row per sub-agent invocation (`appeals_drafter.<sub_name>`).
Hierarchy is reflected in the `AgentTrace.parent_span_id` chain.
