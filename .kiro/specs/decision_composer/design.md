# Design — `decision_composer`

> Generated from ClinCase `AGENT_MANIFEST` at 2026-05-02T13:05:55.326055+00:00.

## Architecture

This agent is a **top-level orchestrator**. Its output is one of the
seven nodes in the LangGraph DAG (`app/graph/build.py`).


## Input schema (`DecisionComposerInput`)

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

## Output schema (`DecisionComposerOutput`)

```json
{
  "$defs": {
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
    "Decision": {
      "properties": {
        "verdict": {
          "enum": [
            "APPROVE",
            "DENY",
            "REFER"
          ],
          "title": "Verdict",
          "type": "string"
        },
        "rationale": {
          "title": "Rationale",
          "type": "string"
        },
        "citations": {
          "items": {
            "$ref": "#/$defs/Citation"
          },
          "title": "Citations",
          "type": "array"
        },
        "confidence": {
          "title": "Confidence",
          "type": "number"
        },
        "risk_flags": {
          "items": {
            "type": "string"
          },
          "title": "Risk Flags",
          "type": "array"
        }
      },
      "required": [
        "verdict",
        "rationale",
        "citations",
        "confidence",
        "risk_flags"
      ],
      "title": "Decision",
      "type": "object"
    }
  },
  "properties": {
    "decision
```

## Guardrails

### Input

- _(none configured)_

### Output

- `schema`: 

## Lifecycle (inherited from `Agent[I, O]`)

1. Validate input against `DecisionComposerInput` (Pydantic).
2. Cache lookup (sha256 of input + schema version + organization_id).
3. Input guardrails (PHI mask · token budget · custom).
4. Budget reservation against case-level `BudgetTracker`.
5. Act — LLM call OR `_execute_deterministic`.
6. Parse output into `DecisionComposerOutput` with retry-on-failure (Haiku→Sonnet escalation).
7. Output guardrails (citation completeness · custom).
8. Reflection (if `quality_threshold > 0`): grader scores; below-threshold retries.
9. Cache store on success.
10. Emit `AgentTrace` span; persist `agent_runs` row.

## Models

- **Primary:** `deterministic` (n/a)
- **Fallback:** `auto-escalate`

## Telemetry

Every invocation emits to `app/api/metrics.py` Prometheus counters:
- `clincase_agent_invocations_total{agent="decision_composer",status=...}`
- `clincase_agent_latency_ms_p99`
- `clincase_llm_tokens_total{model_id=...}`
- `clincase_llm_cost_usd_total`

## Failure modes

- `BudgetExceeded` — caller's case-level budget exhausted before this agent ran.
- `InputBlocked` / `OutputBlocked` — a guardrail rejected the payload.
- `AgentExhausted` — schema parse failed after `max_iterations` retries.
- Bedrock 5xx — `ModelRouter.escalate(...)` switches to fallback on retry.
