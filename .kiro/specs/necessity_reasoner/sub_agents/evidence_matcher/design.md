# Design — `evidence_matcher`

> Generated from ClinCase `AGENT_MANIFEST` at 2026-05-02T13:05:55.346072+00:00.

## Architecture

This agent is a **sub-agent** of `necessity_reasoner`. It shares the parent's
`AgentContext`, including:
  - `BudgetTracker` — per-case $5 / 600K-token ceiling
  - `TraceSink` — `PostgresTraceSink` in production, `InMemoryTraceSink` in tests
  - `WorkingMemory` — case-scoped scratch
  - `parent_span_id` — wires this span under the parent in the AgentTrace tree


## Input schema (`EvidenceMatcherInput`)

```json
{
  "$defs": {
    "AtomicCriterion": {
      "description": "One indivisible inclusion/exclusion criterion.",
      "properties": {
        "text": {
          "title": "Text",
          "type": "string"
        },
        "criterion_type": {
          "default": "inclusion",
          "enum": [
            "inclusion",
            "exclusion"
          ],
          "title": "Criterion Type",
          "type": "string"
        },
        "policy_excerpt_index": {
          "minimum": 0,
          "title": "Policy Excerpt Index",
          "type": "integer"
        },
        "section_pointer": {
          "default": "",
          "title": "Section Pointer",
          "type": "string"
        }
      },
      "required": [
        "text",
        "policy_excerpt_index"
      ],
      "title": "AtomicCriterion",
      "type": "object"
    },
    "Biomarker": {
      "properties": {
        "name": {
          "title": "Name",
          "type": "string"
        },
        "value": {
          "title": "Value",
          "type": "string"
        },
        "test_date": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Test Date"
        },
        "source_resource_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "d
```

## Output schema (`EvidenceMatch`)

```json
{
  "$defs": {
    "AtomicCriterion": {
      "description": "One indivisible inclusion/exclusion criterion.",
      "properties": {
        "text": {
          "title": "Text",
          "type": "string"
        },
        "criterion_type": {
          "default": "inclusion",
          "enum": [
            "inclusion",
            "exclusion"
          ],
          "title": "Criterion Type",
          "type": "string"
        },
        "policy_excerpt_index": {
          "minimum": 0,
          "title": "Policy Excerpt Index",
          "type": "integer"
        },
        "section_pointer": {
          "default": "",
          "title": "Section Pointer",
          "type": "string"
        }
      },
      "required": [
        "text",
        "policy_excerpt_index"
      ],
      "title": "AtomicCriterion",
      "type": "object"
    }
  },
  "description": "Output schema for the evidence_matcher sub-agent.\n\nThe `criterion` field is optional on the LLM's output \u2014 it's set by the\norchestrator post-call (the parent already knows which criterion it\nsent) so we don't waste tokens making the LLM echo it back.",
  "properties": {
    "criterion": {
      "anyOf": [
        {
          "$ref": "#/$defs/AtomicCriterion"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "status": {
      "enum": [
        "MET",
        "NOT_MET",
        "AMBIGUOUS"
      ],
      "title": "Status",
      "type": "string"
    },
    "suppor
```

## Guardrails

### Input

- `token_budget`: 

### Output

- `schema`: 

## Lifecycle (inherited from `Agent[I, O]`)

1. Validate input against `EvidenceMatcherInput` (Pydantic).
2. Cache lookup (sha256 of input + schema version + organization_id).
3. Input guardrails (PHI mask · token budget · custom).
4. Budget reservation against case-level `BudgetTracker`.
5. Act — LLM call OR `_execute_deterministic`.
6. Parse output into `EvidenceMatch` with retry-on-failure (Haiku→Sonnet escalation).
7. Output guardrails (citation completeness · custom).
8. Reflection (if `quality_threshold > 0`): grader scores; below-threshold retries.
9. Cache store on success.
10. Emit `AgentTrace` span; persist `agent_runs` row.

## Models

- **Primary:** `sonnet` (reasoning)
- **Fallback:** `auto-escalate`

## Telemetry

Every invocation emits to `app/api/metrics.py` Prometheus counters:
- `clincase_agent_invocations_total{agent="evidence_matcher",status=...}`
- `clincase_agent_latency_ms_p99`
- `clincase_llm_tokens_total{model_id=...}`
- `clincase_llm_cost_usd_total`

## Failure modes

- `BudgetExceeded` — caller's case-level budget exhausted before this agent ran.
- `InputBlocked` / `OutputBlocked` — a guardrail rejected the payload.
- `AgentExhausted` — schema parse failed after `max_iterations` retries.
- Bedrock 5xx — `ModelRouter.escalate(...)` switches to fallback on retry.
