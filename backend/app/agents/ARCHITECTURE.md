# ClinCase agent architecture — deep dive

This document is the single source of truth for the **structure**, **lifecycle**,
**invariants**, and **trace contract** of the ClinCase agent layer. It complements
`README.md` (file-tree map) and the per-parent READMEs (parent-specific docs).

If anything in this file conflicts with code, the code wins — and this document
is wrong. File a fix.

## 1. The 3-layer architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Layer 1: framework/                                                        │
│  Production runtime primitives. Stable.                                     │
│  • Agent[I, O]                  the canonical base class                    │
│  • AgentContext                 threaded through every invocation           │
│  • BudgetTracker                cost / token / latency ceilings             │
│  • Tool[I, O] + ToolRegistry    schema-validated, idempotent capabilities   │
│  • MemoryStore                  3-tier memory (working / episodic / semantic)│
│  • Guardrail + concrete impls   PII / schema / citation / token-budget      │
│  • LLMGrader                    self-evaluation pattern                     │
│  • ModelSpec + ModelRouter      cost-aware Haiku → Sonnet escalation        │
│  • AgentResult / AgentMetadata  per-invocation telemetry                    │
│  • AgentTrace                   hierarchical span (parent_span_id chain)    │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  Layer 2: 7 parent-agent packages (self-contained)                          │
│                                                                             │
│  Each parent is a Python PACKAGE with the same 5-file shape:                │
│    parent/                                                                  │
│    ├── __init__.py        public exports                                    │
│    ├── README.md          parent-specific docs                              │
│    ├── orchestrator.py    Agent[OrchestratorInput, OrchestratorOutput]      │
│    ├── node.py            LangGraph wrapper + legacy compat shims           │
│    ├── schemas.py         orch + sub-agent I/O contracts                    │
│    └── sub_agents/        layer-3 child agents (3 per parent)               │
│                                                                             │
│  The 7 parents in DAG order:                                                │
│    1. clinical_extractor       FHIR + note → ClinicalSnapshot              │
│    2. policy_retriever         payer + treatment → top-5 PolicyExcerpts    │
│    3. necessity_reasoner       criteria evaluation + HITL gate              │
│    4. decision_composer        APPROVE/DENY/REFER + cited rationale         │
│    5. denial_forecaster        probability + reasons + appeal angle         │
│    6. appeals_drafter          formal appeal letter (on DENY only)          │
│    7. patient_communicator     6th-grade-reading-level summary              │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  Layer 3: 21 sub-agents (3 per parent)                                      │
│                                                                             │
│  Each sub-agent is a single file at parent/sub_agents/<name>.py.            │
│  Each declares: name, parent, role, description, input_schema,              │
│  output_schema, primary_model (or None for deterministic), and either       │
│  system_prompt (LLM) or _execute_deterministic (deterministic).             │
│                                                                             │
│  Counts: 15 LLM-backed (10 Sonnet, 5 Haiku) · 6 deterministic ·             │
│          3 with reflection (evidence_matcher, counter_evidence_finder,      │
│          letter_composer — each quality_threshold=0.80, max_iterations=3)   │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 2. The Agent.invoke() lifecycle

The `Agent[I, O]` base class implements one method: `invoke(input, ctx)`. Every
parent and every sub-agent runs exactly the same lifecycle. Subclasses don't
override `invoke` — they declare metadata + ONE hook (`system_prompt` for LLM
agents or `_execute_deterministic` for deterministic agents).

```
invoke(input: I, ctx: AgentContext) → AgentResult[O]
─────────────────────────────────────────────────────
  ┌─ 1. validate input schema ──────────────────────────────────────┐
  │     Pydantic boundary; bad input rejected before any side-effect│
  └─────────────────────────────────────────────────────────────────┘
  ┌─ 2. run input_guardrails ───────────────────────────────────────┐
  │     PASS    → continue                                          │
  │     MASK    → continue with mutated payload (e.g. PHI redacted) │
  │     BLOCK   → InputBlocked raised; trace recorded; abort        │
  └─────────────────────────────────────────────────────────────────┘
  ┌─ 3. reserve budget ─────────────────────────────────────────────┐
  │     BudgetTracker.reserve(estimated_usd, est_in, est_out)       │
  │     BudgetExceeded raised BEFORE any LLM token spent if over    │
  └─────────────────────────────────────────────────────────────────┘
  ┌─ 4. ACT ────────────────────────────────────────────────────────┐
  │     LLM agent:           get_llm_client().complete(system_prompt│
  │                          + _build_user_message(input))          │
  │     Deterministic agent: _execute_deterministic(input, ctx)     │
  └─────────────────────────────────────────────────────────────────┘
  ┌─ 5. parse output schema ────────────────────────────────────────┐
  │     On schema fail: retry with feedback embedded in user message│
  │     ModelRouter.escalate() bumps Haiku → Sonnet on retry        │
  │     Bounded by max_iterations                                   │
  └─────────────────────────────────────────────────────────────────┘
  ┌─ 6. run output_guardrails ──────────────────────────────────────┐
  │     SchemaGuardrail / CitationCompletenessGuardrail / custom    │
  │     RETRY → loop back to step 4 with feedback                   │
  │     BLOCK → OutputBlocked raised                                │
  └─────────────────────────────────────────────────────────────────┘
  ┌─ 7. reflect (when quality_threshold > 0) ───────────────────────┐
  │     LLMGrader scores schema_correctness × clinical_faithfulness │
  │     × citation_completeness                                     │
  │     score < quality_threshold → loop back to step 4 with feedback│
  │     Bounded by max_iterations                                   │
  └─────────────────────────────────────────────────────────────────┘
  ┌─ 8. commit / cancel budget ─────────────────────────────────────┐
  │     Reconciles actual cost against the reservation              │
  └─────────────────────────────────────────────────────────────────┘
  ┌─ 9. emit AgentTrace span ───────────────────────────────────────┐
  │     parent_span_id chain → hierarchical execution tree          │
  │     attributes: model_id, retries, cost_usd, grader_score, ...  │
  └─────────────────────────────────────────────────────────────────┘
  ┌─ 10. persist agent_runs row + SSE event ────────────────────────┐
  │     Audit trail row keyed by case_id; SSE for live UI           │
  └─────────────────────────────────────────────────────────────────┘
  ┌─ 11. return AgentResult[O] ─────────────────────────────────────┐
  │     output: O                                                   │
  │     metadata: AgentMetadata (cost, tokens, retries, score)      │
  │     trace: AgentTrace (hierarchical span tree)                  │
  └─────────────────────────────────────────────────────────────────┘
```

## 3. Invariants

These hold across every agent in the system. Violating any of them is a
production bug, not a quirk.

| # | Invariant | Where enforced |
|---|---|---|
| 1 | Schemas are pinned via Pydantic | `Agent.invoke` step 1 + 5 |
| 2 | One trace row per invocation | `Agent.invoke` step 9 + 10 |
| 3 | Budget cannot be exceeded | `BudgetTracker.reserve` step 3 |
| 4 | Sub-agents share parent's context | `AgentContext.child_for(span)` |
| 5 | Deterministic agents are still traced | `_execute_deterministic` wrapped by `Agent.invoke` |
| 6 | PHI never reaches an LLM | `phi_sanitizer` runs before any LLM call in `clinical_extractor` |
| 7 | Verdict is deterministic | `verdict_synthesizer` is the rule; LLM only justifies |
| 8 | Min-aggregation on confidence | enforced post-LLM in `confidence_calibrator._parse_response` |
| 9 | HITL gate triggers below 0.75 | LangGraph conditional edge → `review_gate` (terminal) |

## 4. Hierarchical trace contract

Every invocation writes ONE row to `agent_runs`. Sub-agent rows are named
`<parent>.<sub_name>` so a query like:

```sql
SELECT id, agent_name, model_id, input_tokens, output_tokens,
       latency_ms, status, started_at
FROM agent_runs
WHERE case_id = 'xyz'
ORDER BY started_at;
```

returns the orchestrator's row first, then each sub-agent in start-time
order. Combined with `AgentResult.trace.parent_span_id` chain, you can
render the full hierarchical execution tree.

## 5. The 7-by-3 manifest

The manifest is built at module import time by aggregating each parent's
`SUB_AGENTS` list. There is no manually-maintained dict.

```
clinical_extractor       (3 sub-agents)
  ├ fhir_resource_validator       det
  ├ phi_sanitizer                 det
  └ biomarker_specialist          LLM (haiku)

policy_retriever         (3 sub-agents)
  ├ keyword_filter                det
  ├ llm_reranker                  LLM (sonnet)
  └ citation_resolver             det

necessity_reasoner       (3 sub-agents)
  ├ criterion_splitter            LLM (sonnet)
  ├ evidence_matcher              LLM (sonnet) · reflection 0.80 / 3
  └ confidence_calibrator         LLM (haiku)

decision_composer        (3 sub-agents)
  ├ verdict_synthesizer           det (rule-based)
  ├ rationale_writer              LLM (sonnet)
  └ citation_linker               LLM (haiku)

denial_forecaster        (3 sub-agents)
  ├ probability_estimator         LLM (sonnet)
  ├ reason_predictor              LLM (haiku)
  └ appeal_path_recommender       LLM (haiku)

appeals_drafter          (3 sub-agents)
  ├ counter_evidence_finder       LLM (sonnet) · reflection 0.80 / 3
  ├ nccn_reference_specialist     LLM (haiku)
  └ letter_composer               LLM (sonnet) · reflection 0.80 / 3

patient_communicator     (3 sub-agents)
  ├ empathy_layer                 LLM (sonnet)
  ├ reading_level_tuner           det (Flesch-Kincaid)
  └ action_step_writer            LLM (haiku)
```

## 6. The DAG flow

```
   FHIR bundle + treatment
         │
         ▼
   ┌─────────────────────┐
   │ clinical_extractor  │── snapshot ──┐
   └─────────────────────┘              │
                                        ▼
                              ┌─────────────────────┐
                              │   policy_retriever  │── excerpts ──┐
                              └─────────────────────┘              │
                                                                   ▼
                                                        ┌─────────────────────┐
                                                        │ necessity_reasoner  │
                                                        └──────────┬──────────┘
                                          confidence < 0.75 ?      │
                                              ┌────────────────────┴────────────────┐
                                              ▼                                     ▼
                                       ┌──────────────┐                   ┌─────────────────────┐
                                       │ review_gate  │ (HITL)            │  decision_composer  │
                                       │   (END)      │                   └──────────┬──────────┘
                                       └──────────────┘                              │
                                                                                     ▼
                                                                          ┌─────────────────────┐
                                                                          │ denial_forecaster   │
                                                                          └──────────┬──────────┘
                                                                              verdict == DENY ?
                                                              ┌──────────────────┴──────────────┐
                                                              ▼                                 ▼
                                                       ┌──────────────┐                ┌─────────────────────┐
                                                       │ appeals_drafter│              │patient_communicator │
                                                       └──────┬─────────┘              └──────────┬──────────┘
                                                              ▼                                   ▼
                                                       ┌─────────────────────┐                  END
                                                       │patient_communicator │
                                                       └──────────┬──────────┘
                                                                  ▼
                                                                 END
```

## 7. Files NOT to edit

- `framework/types.py` — schema changes ripple through every agent
- `framework/agent.py` — invoke() lifecycle is the single contract

If you need new behavior, add a guardrail / tool / grader rather than
mutating the lifecycle.

## 8. Where to start (new engineer)

1. Read this file (`ARCHITECTURE.md`) for the big picture
2. Read `framework/agent.py` for the canonical Agent base class (~350 LOC)
3. Pick any parent — say `necessity_reasoner/` — and read its 5 files
4. Pick any sub-agent — say `necessity_reasoner/sub_agents/evidence_matcher.py` — and read it (under 60 lines)
5. Run `pytest tests/framework/ tests/agents/sub/` — 48 contract tests pass in 2 seconds
