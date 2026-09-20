# Design — `necessity_reasoner`

> Generated from ClinCase `AGENT_MANIFEST` at 2026-05-02T13:05:55.342163+00:00.

## Architecture

This agent is a **top-level orchestrator**. Its output is one of the
seven nodes in the LangGraph DAG (`app/graph/build.py`).


## Input schema (`NecessityReasonerInput`)

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

## Output schema (`NecessityReasonerOutput`)

```json
{
  "$defs": {
    "CriterionAssessment": {
      "properties": {
        "criterion_text": {
          "title": "Criterion Text",
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
          "title": "Policy Excerpt Index",
          "type": "integer"
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
        "supporting_evidence": {
          "items": {
            "type": "string"
          },
          "title": "Supporting Evidence",
          "type": "array"
        },
        "missing_evidence": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Missing Evidence"
        },
        "confidence": {
          "title": "Confidence",
          "type": "number"
        },
        "rationale": {
          "title": "Rationale",
          "type": "string"
        }
      },
      "required": [
        "criterion_text",
        "policy_excerpt_index",
        "status",
        "supporting_evidence",
        "confidence",
        "rationale"
      ],
    
```

## Guardrails

### Input

- _(none configured)_

### Output

- `schema`: 

## Lifecycle (inherited from `Agent[I, O]`)

1. Validate input against `NecessityReasonerInput` (Pydantic).
2. Cache lookup (sha256 of input + schema version + organization_id).
3. Input guardrails (PHI mask · token budget · custom).
4. Budget reservation against case-level `BudgetTracker`.
5. Act — LLM call OR `_execute_deterministic`.
6. Parse output into `NecessityReasonerOutput` with retry-on-failure (Haiku→Sonnet escalation).
7. Output guardrails (citation completeness · custom).
8. Reflection (if `quality_threshold > 0`): grader scores; below-threshold retries.
9. Cache store on success.
10. Emit `AgentTrace` span; persist `agent_runs` row.

## Models

- **Primary:** `deterministic` (n/a)
- **Fallback:** `auto-escalate`

## Telemetry

Every invocation emits to `app/api/metrics.py` Prometheus counters:
- `clincase_agent_invocations_total{agent="necessity_reasoner",status=...}`
- `clincase_agent_latency_ms_p99`
- `clincase_llm_tokens_total{model_id=...}`
- `clincase_llm_cost_usd_total`

## Failure modes

- `BudgetExceeded` — caller's case-level budget exhausted before this agent ran.
- `InputBlocked` / `OutputBlocked` — a guardrail rejected the payload.
- `AgentExhausted` — schema parse failed after `max_iterations` retries.
- Bedrock 5xx — `ModelRouter.escalate(...)` switches to fallback on retry.
