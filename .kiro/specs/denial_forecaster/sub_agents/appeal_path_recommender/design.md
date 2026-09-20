# Design — `appeal_path_recommender`

> Generated from ClinCase `AGENT_MANIFEST` at 2026-05-02T13:05:55.339949+00:00.

## Architecture

This agent is a **sub-agent** of `denial_forecaster`. It shares the parent's
`AgentContext`, including:
  - `BudgetTracker` — per-case $5 / 600K-token ceiling
  - `TraceSink` — `PostgresTraceSink` in production, `InMemoryTraceSink` in tests
  - `WorkingMemory` — case-scoped scratch
  - `parent_span_id` — wires this span under the parent in the AgentTrace tree


## Input schema (`AppealPathRecommenderInput`)

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

## Output schema (`AppealPathRecommenderOutput`)

```json
{
  "$defs": {
    "AppealStrategy": {
      "description": "Recommended appeal angle if the case ends up denied.",
      "properties": {
        "primary_angle": {
          "description": "Highest-probability angle for an appeal to overturn.",
          "enum": [
            "biomarker_evidence",
            "guideline_alignment",
            "prior_therapy_failure",
            "step_therapy_completed",
            "medical_necessity_letter",
            "documentation_gap_resolved"
          ],
          "title": "Primary Angle",
          "type": "string"
        },
        "rationale": {
          "default": "",
          "description": "Why this angle is strongest for this case.",
          "title": "Rationale",
          "type": "string"
        },
        "expected_overturn_probability": {
          "description": "Expected probability the appeal succeeds, calibrated against KFF 2024 (80.7% baseline).",
          "maximum": 1.0,
          "minimum": 0.0,
          "title": "Expected Overturn Probability",
          "type": "number"
        }
      },
      "required": [
        "primary_angle",
        "expected_overturn_probability"
      ],
      "title": "AppealStrategy",
      "type": "object"
    }
  },
  "properties": {
    "strategy": {
      "anyOf": [
        {
          "$ref": "#/$defs/AppealStrategy"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "skipped_reason": {
      "anyOf": [
        {
          "t
```

## Guardrails

### Input

- _(none configured)_

### Output

- `schema`: 

## Lifecycle (inherited from `Agent[I, O]`)

1. Validate input against `AppealPathRecommenderInput` (Pydantic).
2. Cache lookup (sha256 of input + schema version + organization_id).
3. Input guardrails (PHI mask · token budget · custom).
4. Budget reservation against case-level `BudgetTracker`.
5. Act — LLM call OR `_execute_deterministic`.
6. Parse output into `AppealPathRecommenderOutput` with retry-on-failure (Haiku→Sonnet escalation).
7. Output guardrails (citation completeness · custom).
8. Reflection (if `quality_threshold > 0`): grader scores; below-threshold retries.
9. Cache store on success.
10. Emit `AgentTrace` span; persist `agent_runs` row.

## Models

- **Primary:** `haiku` (lightweight_extraction)
- **Fallback:** `auto-escalate`

## Telemetry

Every invocation emits to `app/api/metrics.py` Prometheus counters:
- `clincase_agent_invocations_total{agent="appeal_path_recommender",status=...}`
- `clincase_agent_latency_ms_p99`
- `clincase_llm_tokens_total{model_id=...}`
- `clincase_llm_cost_usd_total`

## Failure modes

- `BudgetExceeded` — caller's case-level budget exhausted before this agent ran.
- `InputBlocked` / `OutputBlocked` — a guardrail rejected the payload.
- `AgentExhausted` — schema parse failed after `max_iterations` retries.
- Bedrock 5xx — `ModelRouter.escalate(...)` switches to fallback on retry.
