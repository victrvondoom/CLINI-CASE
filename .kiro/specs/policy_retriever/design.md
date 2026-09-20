# Design — `policy_retriever`

> Generated from ClinCase `AGENT_MANIFEST` at 2026-05-02T13:05:55.356738+00:00.

## Architecture

This agent is a **top-level orchestrator**. Its output is one of the
seven nodes in the LangGraph DAG (`app/graph/build.py`).


## Input schema (`PolicyRetrieverInput`)

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
    "ClinicalSnapshot": {
      "description": "The structured clinical record consumed by every downstream agent.",
      "properties": {
        "patient_age": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Patient Age"
        },
        "patient_sex": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Patient Sex"
        },
        "pr
```

## Output schema (`PolicyRetrieverOutput`)

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

## Guardrails

### Input

- _(none configured)_

### Output

- `schema`: 

## Lifecycle (inherited from `Agent[I, O]`)

1. Validate input against `PolicyRetrieverInput` (Pydantic).
2. Cache lookup (sha256 of input + schema version + organization_id).
3. Input guardrails (PHI mask · token budget · custom).
4. Budget reservation against case-level `BudgetTracker`.
5. Act — LLM call OR `_execute_deterministic`.
6. Parse output into `PolicyRetrieverOutput` with retry-on-failure (Haiku→Sonnet escalation).
7. Output guardrails (citation completeness · custom).
8. Reflection (if `quality_threshold > 0`): grader scores; below-threshold retries.
9. Cache store on success.
10. Emit `AgentTrace` span; persist `agent_runs` row.

## Models

- **Primary:** `deterministic` (n/a)
- **Fallback:** `auto-escalate`

## Telemetry

Every invocation emits to `app/api/metrics.py` Prometheus counters:
- `clincase_agent_invocations_total{agent="policy_retriever",status=...}`
- `clincase_agent_latency_ms_p99`
- `clincase_llm_tokens_total{model_id=...}`
- `clincase_llm_cost_usd_total`

## Failure modes

- `BudgetExceeded` — caller's case-level budget exhausted before this agent ran.
- `InputBlocked` / `OutputBlocked` — a guardrail rejected the payload.
- `AgentExhausted` — schema parse failed after `max_iterations` retries.
- Bedrock 5xx — `ModelRouter.escalate(...)` switches to fallback on retry.
