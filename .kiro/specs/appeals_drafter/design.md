# Design — `appeals_drafter`

> Generated from ClinCase `AGENT_MANIFEST` at 2026-05-02T13:05:55.309646+00:00.

## Architecture

This agent is a **top-level orchestrator**. Its output is one of the
seven nodes in the LangGraph DAG (`app/graph/build.py`).


## Input schema (`AppealsDrafterInput`)

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

## Output schema (`AppealsDrafterOutput`)

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
    },
    "AppealDraft": {
      "properties": {
        "patient_initials": {
          "title": "Patient Initials",
          "type": "string"
        },
        "payer_id": {
          "title": "Payer Id",
          "type": "string"
        },
        "requested_treatment": {
          "title": "Requested Treatment",
          "type": "string"
        },
        "denial_date": {
          "title": "Denial Date",
          "type": "string"
        },
        "appeal_body
```

## Guardrails

### Input

- _(none configured)_

### Output

- `schema`: 

## Lifecycle (inherited from `Agent[I, O]`)

1. Validate input against `AppealsDrafterInput` (Pydantic).
2. Cache lookup (sha256 of input + schema version + organization_id).
3. Input guardrails (PHI mask · token budget · custom).
4. Budget reservation against case-level `BudgetTracker`.
5. Act — LLM call OR `_execute_deterministic`.
6. Parse output into `AppealsDrafterOutput` with retry-on-failure (Haiku→Sonnet escalation).
7. Output guardrails (citation completeness · custom).
8. Reflection (if `quality_threshold > 0`): grader scores; below-threshold retries.
9. Cache store on success.
10. Emit `AgentTrace` span; persist `agent_runs` row.

## Models

- **Primary:** `deterministic` (n/a)
- **Fallback:** `auto-escalate`

## Telemetry

Every invocation emits to `app/api/metrics.py` Prometheus counters:
- `clincase_agent_invocations_total{agent="appeals_drafter",status=...}`
- `clincase_agent_latency_ms_p99`
- `clincase_llm_tokens_total{model_id=...}`
- `clincase_llm_cost_usd_total`

## Failure modes

- `BudgetExceeded` — caller's case-level budget exhausted before this agent ran.
- `InputBlocked` / `OutputBlocked` — a guardrail rejected the payload.
- `AgentExhausted` — schema parse failed after `max_iterations` retries.
- Bedrock 5xx — `ModelRouter.escalate(...)` switches to fallback on retry.
