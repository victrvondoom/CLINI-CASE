# ClinCase agent layer

Production-grade 7-agent / 21-sub-agent architecture organized as **self-contained
packages**. Each parent is a Python package with the same 5-file shape; each
sub-agent is a single file. Drop one in or out without touching anything else.

```
backend/app/agents/
├── README.md                          ← you are here
├── ARCHITECTURE.md                    ← invariants, lifecycle, diagrams
├── __init__.py                        ← public exports
├── manifest.py                        ← AGENT_MANIFEST (single source of truth)
│
├── framework/                         ← LAYER 1: production runtime primitives
│   ├── agent.py                       Agent[I, O] — the canonical base class
│   ├── budget.py                      BudgetTracker (reservation pattern)
│   ├── context.py                     AgentContext (threaded everywhere)
│   ├── grader.py                      LLMGrader (self-evaluation pattern)
│   ├── guardrails.py                  Guardrail ABC + 4 concrete impls
│   ├── memory.py                      3-tier memory store
│   ├── models.py                      ModelSpec + ModelRouter (Haiku → Sonnet)
│   ├── tools.py                       Tool[I, O] + ToolRegistry (idempotent)
│   └── types.py                       AgentResult, AgentMetadata, AgentTrace
│
├── clinical_extractor/                ← LAYER 2: parent package #1 (one of seven)
│   ├── __init__.py                    public exports — orchestrator + node + schemas + sub_agents
│   ├── README.md                      what this parent does, lifecycle, sub-agents
│   ├── orchestrator.py                ClinicalExtractorAgent (the parent class)
│   ├── node.py                        LangGraph wrapper + legacy compat shims
│   ├── schemas.py                     all I/O contracts (orch + sub-agents)
│   └── sub_agents/                    LAYER 3: 3 sub-agents
│       ├── __init__.py
│       ├── fhir_resource_validator.py (deterministic)
│       ├── phi_sanitizer.py           (deterministic)
│       └── biomarker_specialist.py    (LLM, Haiku)
│
├── policy_retriever/                  ← same 5-file shape × 7 parents
├── necessity_reasoner/
├── decision_composer/
├── denial_forecaster/
├── appeals_drafter/
└── patient_communicator/
```

The mirror layout lives at `backend/app/prompts/`:

```
backend/app/prompts/
├── clinical_extractor/
│   ├── orchestrator.txt               (parent prompt, when applicable)
│   └── sub_agents/
│       └── biomarker_specialist.txt   (one .txt per LLM-backed sub-agent)
├── necessity_reasoner/
├── ... (one directory per parent)
```

## The contract every agent satisfies

Every parent and sub-agent inherits from `app.agents.framework.Agent[I, O]`.
Subclasses declare identity (name, parent, role, description), schemas,
model, guardrails, and one hook:

  - LLM agents: `system_prompt` (loaded from a `.txt` file) + optional `_build_user_message`
  - Deterministic agents: `_execute_deterministic`

The lifecycle is fixed in the framework and runs the same for every
invocation:

```
Agent.invoke(input, ctx) →
  1. validate input schema                       (Pydantic boundary)
  2. run input_guardrails                        (PASS / MASK / BLOCK)
  3. reserve budget                              (BudgetExceeded raises before any LLM call)
  4. act                                         — LLM completion OR _execute_deterministic
  5. parse output                                (retry-with-feedback on schema fail; Haiku → Sonnet escalation)
  6. run output_guardrails                       (PASS / RETRY / BLOCK)
  7. reflect                                     (LLMGrader scores; below quality_threshold → retry)
  8. commit / cancel budget
  9. emit hierarchical AgentTrace span           (parent_span_id chain)
 10. persist agent_runs row + SSE event
 11. return AgentResult[O] with cost / tokens / retries / grader_score
```

## The 21 sub-agents at a glance

| # | Parent | Sub-agent | Kind | Model | Reflection |
|---|---|---|---|---|---|
| 1 | clinical_extractor | fhir_resource_validator | det | — | — |
| 2 | clinical_extractor | phi_sanitizer | det | — | — |
| 3 | clinical_extractor | biomarker_specialist | LLM | haiku | — |
| 4 | policy_retriever | keyword_filter | det | — | — |
| 5 | policy_retriever | llm_reranker | LLM | sonnet | — |
| 6 | policy_retriever | citation_resolver | det | — | — |
| 7 | necessity_reasoner | criterion_splitter | LLM | sonnet | — |
| 8 | necessity_reasoner | evidence_matcher | LLM | sonnet | **0.80 / 3** |
| 9 | necessity_reasoner | confidence_calibrator | LLM | haiku | — |
| 10 | decision_composer | verdict_synthesizer | det | — | — |
| 11 | decision_composer | rationale_writer | LLM | sonnet | — |
| 12 | decision_composer | citation_linker | LLM | haiku | — |
| 13 | denial_forecaster | probability_estimator | LLM | sonnet | — |
| 14 | denial_forecaster | reason_predictor | LLM | haiku | — |
| 15 | denial_forecaster | appeal_path_recommender | LLM | haiku | — |
| 16 | appeals_drafter | counter_evidence_finder | LLM | sonnet | **0.80 / 3** |
| 17 | appeals_drafter | nccn_reference_specialist | LLM | haiku | — |
| 18 | appeals_drafter | letter_composer | LLM | sonnet | **0.80 / 3** |
| 19 | patient_communicator | empathy_layer | LLM | sonnet | — |
| 20 | patient_communicator | reading_level_tuner | det | — | — |
| 21 | patient_communicator | action_step_writer | LLM | haiku | — |

**Counts:** 15 LLM-backed · 6 deterministic · 3 with reflection enabled.

## Invariants

These hold across every agent in the system. Violating any of them is a
production bug.

1. **Schemas are pinned.** Every input and output crosses a Pydantic boundary
   that's reflected in the manifest (`input_schema_json`, `output_schema_json`).
2. **One trace per invocation.** Parent and sub-agent invocations write
   independent rows into `agent_runs` named `<parent>` or `<parent>.<sub>`.
3. **Budget cannot be exceeded.** The reservation step raises before any LLM
   token is spent if the case ceiling would be breached.
4. **Sub-agents share their parent's context.** Same case_id, same
   organization_id, same budget tracker, same tool cache. `ctx.child_for(span)`
   forks `parent_span_id` only.
5. **Deterministic sub-agents are still traced.** Zero token cost; an
   `agent_runs` row is still produced so the audit trail is complete.
6. **PHI never reaches an LLM.** The Clinical Extractor's `phi_sanitizer`
   sub-agent runs (deterministically; Bedrock-Guardrails-compatible shape)
   before any prompt is built.
7. **Verdict is deterministic.** The LLM `rationale_writer` justifies the
   verdict; it never overrides it. The verdict comes from the
   `verdict_synthesizer` deterministic rule.
8. **Min-aggregation on confidence.** `overall_confidence` is enforced as
   `min(per_criterion_confidence)` post-LLM in `confidence_calibrator`.
9. **HITL gate triggers below 0.75.** Below the threshold, the LangGraph
   conditional edge routes to `review_gate` (terminal) and a clinician's
   verdict is required to resume.

## How to add a new sub-agent

Each parent's package gives you exactly one place to look. Adding a new
sub-agent to (say) `decision_composer`:

```python
# 1. Schemas — append to app/agents/decision_composer/schemas.py
class MyNewSubAgentInput(BaseModel): ...
class MyNewSubAgentOutput(BaseModel): ...

# 2. Prompt (LLM agents only)
# app/prompts/decision_composer/sub_agents/my_new_sub_agent.txt

# 3. Class — new file at app/agents/decision_composer/sub_agents/my_new_sub_agent.py
from app.agents.framework import Agent, SONNET_REASONING, SchemaGuardrail
from app.agents.decision_composer.schemas import MyNewSubAgentInput, MyNewSubAgentOutput

_PROMPT_PATH = (
    Path(__file__).resolve().parents[3]
    / "prompts" / "decision_composer" / "sub_agents" / "my_new_sub_agent.txt"
)

class MyNewSubAgent(Agent[MyNewSubAgentInput, MyNewSubAgentOutput]):
    name = "my_new_sub_agent"
    parent = "decision_composer"
    role = "<role>"
    description = "..."
    input_schema = MyNewSubAgentInput
    output_schema = MyNewSubAgentOutput
    primary_model = SONNET_REASONING       # or None for deterministic
    system_prompt = _PROMPT_PATH.read_text(encoding="utf-8")
    estimated_input_tokens = 1500
    estimated_output_tokens = 500
    output_guardrails = [SchemaGuardrail(MyNewSubAgentOutput)]

my_new_sub_agent = MyNewSubAgent()

# 4. Wire into parent's SUB_AGENTS list in orchestrator.py
# 5. Re-export from sub_agents/__init__.py
# 6. Write contract test in tests/agents/sub/test_my_new_sub_agent.py
```

`AGENT_MANIFEST` auto-discovers from `SUB_AGENTS`, so no manual registry
update is needed.

## How to read a case's full trace

```sql
SELECT id, agent_name, model_id, input_tokens, output_tokens,
       latency_ms, status, started_at
FROM agent_runs
WHERE case_id = '<case_id>'
ORDER BY started_at;
```

Rows named `<parent>` are the orchestrator's own row; rows named
`<parent>.<sub_name>` are sub-agent invocations interleaved in start-time
order. The `parent_span_id` column (when populated by the framework) makes
the tree explicit.

## Files NOT to edit

- `app/agents/framework/types.py` — schema changes ripple through every agent.
- `app/agents/framework/agent.py` — invoke() lifecycle is the single contract.

If you need new behavior, add a guardrail / tool / grader rather than mutating
the lifecycle.
