# Design — `criterion_splitter`

> Generated from ClinCase `AGENT_MANIFEST` at 2026-05-02T13:05:55.343848+00:00.

## Architecture

This agent is a **sub-agent** of `necessity_reasoner`. It shares the parent's
`AgentContext`, including:
  - `BudgetTracker` — per-case $5 / 600K-token ceiling
  - `TraceSink` — `PostgresTraceSink` in production, `InMemoryTraceSink` in tests
  - `WorkingMemory` — case-scoped scratch
  - `parent_span_id` — wires this span under the parent in the AgentTrace tree


## Input schema (`CriterionSplitterInput`)

```json
{
  "$defs": {
    "PolicyExcerpt": {
      "properties": {
        "payer_id": {
          "title": "Payer Id",
          "type": "string"
        },
        "policy_id": {
          "title": "Policy Id",
          "type": "string"
        },
        "policy_title": {
          "title": "Policy Title",
          "type": "string"
        },
        "section_heading": {
          "title": "Section Heading",
          "type": "string"
        },
        "excerpt_text": {
          "title": "Excerpt Text",
          "type": "string"
        },
        "source_url": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Source Url"
        },
        "page_number": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Page Number"
        },
        "relevance_score": {
          "title": "Relevance Score",
          "type": "number"
        }
      },
      "required": [
        "payer_id",
        "policy_id",
        "policy_title",
        "section_heading",
        "excerpt_text",
        "relevance_score"
      ],
      "title": "PolicyExcerpt",
      "type": "object"
    }
  },
  "properties": {
    "excerpts": {
      "items": {
        "$ref": "#/$defs/PolicyExcerpt"
      },
      "t
```

## Output schema (`CriterionSplitterOutput`)

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
  "properties": {
    "atomic_criteria": {
      "items": {
        "$ref": "#/$defs/AtomicCriterion"
      },
      "maxItems": 20,
      "minItems": 1,
      "title": "Atomic Criteria",
      "type": "array"
    }
  },
  "required": [
    "atomic_criteria"
  ],
  "title": "CriterionSplitterOutput",
  "type": "object"
}
```

## Guardrails

### Input

- `token_budget`: 

### Output

- `schema`: 

## Lifecycle (inherited from `Agent[I, O]`)

1. Validate input against `CriterionSplitterInput` (Pydantic).
2. Cache lookup (sha256 of input + schema version + organization_id).
3. Input guardrails (PHI mask · token budget · custom).
4. Budget reservation against case-level `BudgetTracker`.
5. Act — LLM call OR `_execute_deterministic`.
6. Parse output into `CriterionSplitterOutput` with retry-on-failure (Haiku→Sonnet escalation).
7. Output guardrails (citation completeness · custom).
8. Reflection (if `quality_threshold > 0`): grader scores; below-threshold retries.
9. Cache store on success.
10. Emit `AgentTrace` span; persist `agent_runs` row.

## Models

- **Primary:** `sonnet` (reasoning)
- **Fallback:** `auto-escalate`

## Telemetry

Every invocation emits to `app/api/metrics.py` Prometheus counters:
- `clincase_agent_invocations_total{agent="criterion_splitter",status=...}`
- `clincase_agent_latency_ms_p99`
- `clincase_llm_tokens_total{model_id=...}`
- `clincase_llm_cost_usd_total`

## Failure modes

- `BudgetExceeded` — caller's case-level budget exhausted before this agent ran.
- `InputBlocked` / `OutputBlocked` — a guardrail rejected the payload.
- `AgentExhausted` — schema parse failed after `max_iterations` retries.
- Bedrock 5xx — `ModelRouter.escalate(...)` switches to fallback on retry.
