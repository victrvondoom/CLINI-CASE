# Design — `letter_composer`

> Generated from ClinCase `AGENT_MANIFEST` at 2026-05-02T13:05:55.315306+00:00.

## Architecture

This agent is a **sub-agent** of `appeals_drafter`. It shares the parent's
`AgentContext`, including:
  - `BudgetTracker` — per-case $5 / 600K-token ceiling
  - `TraceSink` — `PostgresTraceSink` in production, `InMemoryTraceSink` in tests
  - `WorkingMemory` — case-scoped scratch
  - `parent_span_id` — wires this span under the parent in the AgentTrace tree


## Input schema (`LetterComposerInput`)

```json
{
  "$defs": {
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
          "default": null,
          "title": "Source Resource Id"
        }
      },
      "required": [
        "name",
        "value"
      ],
      "title": "Biomarker",
      "type": "object"
    },
    "Citation": {
      "properties": {
        "kind": {
          "enum": [
            "clinical",
            "policy"
          ],
          "title": "Kind",
          "type": "string"
        },
        "text": {
          "title": "Text",
          "type": "string"
        },
        "pointer": {
          "title": "Pointer",
          "type": "string"
        }
      },
      "required": [
        "kind",
        "text",
        "pointer"
      ],
      "title": "Citation",
      "type": "object"
    },
    "ClinicalSnapshot": {
      "description": "The structured clinical record consumed by every downstream agent.",
      "prop
```

## Output schema (`LetterComposerOutput`)

```json
{
  "$defs": {
    "AppealArgument": {
      "properties": {
        "contested_criterion": {
          "title": "Contested Criterion",
          "type": "string"
        },
        "payer_position": {
          "title": "Payer Position",
          "type": "string"
        },
        "counter_position": {
          "title": "Counter Position",
          "type": "string"
        },
        "cited_evidence": {
          "items": {
            "type": "string"
          },
          "title": "Cited Evidence",
          "type": "array"
        },
        "cited_policy_text": {
          "title": "Cited Policy Text",
          "type": "string"
        },
        "cited_guideline": {
          "title": "Cited Guideline",
          "type": "string"
        }
      },
      "required": [
        "contested_criterion",
        "payer_position",
        "counter_position",
        "cited_evidence",
        "cited_policy_text",
        "cited_guideline"
      ],
      "title": "AppealArgument",
      "type": "object"
    }
  },
  "properties": {
    "appeal_body": {
      "description": "Formal letter prose, ~600 words.",
      "title": "Appeal Body",
      "type": "string"
    },
    "structured_arguments": {
      "items": {
        "$ref": "#/$defs/AppealArgument"
      },
      "title": "Structured Arguments",
      "type": "array"
    },
    "requested_action": {
      "title": "Requested Action",
      "type": "string"
    },
    "attachments_referenced": {
      "items": {
      
```

## Guardrails

### Input

- `token_budget`: 

### Output

- `schema`: 

## Lifecycle (inherited from `Agent[I, O]`)

1. Validate input against `LetterComposerInput` (Pydantic).
2. Cache lookup (sha256 of input + schema version + organization_id).
3. Input guardrails (PHI mask · token budget · custom).
4. Budget reservation against case-level `BudgetTracker`.
5. Act — LLM call OR `_execute_deterministic`.
6. Parse output into `LetterComposerOutput` with retry-on-failure (Haiku→Sonnet escalation).
7. Output guardrails (citation completeness · custom).
8. Reflection (if `quality_threshold > 0`): grader scores; below-threshold retries.
9. Cache store on success.
10. Emit `AgentTrace` span; persist `agent_runs` row.

## Models

- **Primary:** `sonnet` (reasoning)
- **Fallback:** `auto-escalate`

## Telemetry

Every invocation emits to `app/api/metrics.py` Prometheus counters:
- `clincase_agent_invocations_total{agent="letter_composer",status=...}`
- `clincase_agent_latency_ms_p99`
- `clincase_llm_tokens_total{model_id=...}`
- `clincase_llm_cost_usd_total`

## Failure modes

- `BudgetExceeded` — caller's case-level budget exhausted before this agent ran.
- `InputBlocked` / `OutputBlocked` — a guardrail rejected the payload.
- `AgentExhausted` — schema parse failed after `max_iterations` retries.
- Bedrock 5xx — `ModelRouter.escalate(...)` switches to fallback on retry.
