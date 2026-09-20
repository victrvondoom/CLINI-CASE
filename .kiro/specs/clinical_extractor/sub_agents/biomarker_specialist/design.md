# Design — `biomarker_specialist`

> Generated from ClinCase `AGENT_MANIFEST` at 2026-05-02T13:05:55.322846+00:00.

## Architecture

This agent is a **sub-agent** of `clinical_extractor`. It shares the parent's
`AgentContext`, including:
  - `BudgetTracker` — per-case $5 / 600K-token ceiling
  - `TraceSink` — `PostgresTraceSink` in production, `InMemoryTraceSink` in tests
  - `WorkingMemory` — case-scoped scratch
  - `parent_span_id` — wires this span under the parent in the AgentTrace tree


## Input schema (`BiomarkerSpecialistInput`)

```json
{
  "properties": {
    "fhir_bundle": {
      "title": "Fhir Bundle",
      "type": "object"
    },
    "physician_note_redacted": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Physician Note Redacted"
    },
    "requested_treatment_name": {
      "title": "Requested Treatment Name",
      "type": "string"
    }
  },
  "required": [
    "fhir_bundle",
    "requested_treatment_name"
  ],
  "title": "BiomarkerSpecialistInput",
  "type": "object"
}
```

## Output schema (`BiomarkerSpecialistOutput`)

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
    }
  },
  "properties": {
    "biomarkers": {
      "items": {
        "$ref": "#/$defs/Biomarker"
      },
      "title": "Biomarkers",
      "type": "array"
    }
  },
  "title": "BiomarkerSpecialistOutput",
  "type": "object"
}
```

## Guardrails

### Input

- `token_budget`: 

### Output

- `schema`: 

## Lifecycle (inherited from `Agent[I, O]`)

1. Validate input against `BiomarkerSpecialistInput` (Pydantic).
2. Cache lookup (sha256 of input + schema version + organization_id).
3. Input guardrails (PHI mask · token budget · custom).
4. Budget reservation against case-level `BudgetTracker`.
5. Act — LLM call OR `_execute_deterministic`.
6. Parse output into `BiomarkerSpecialistOutput` with retry-on-failure (Haiku→Sonnet escalation).
7. Output guardrails (citation completeness · custom).
8. Reflection (if `quality_threshold > 0`): grader scores; below-threshold retries.
9. Cache store on success.
10. Emit `AgentTrace` span; persist `agent_runs` row.

## Models

- **Primary:** `haiku` (lightweight_extraction)
- **Fallback:** `auto-escalate`

## Telemetry

Every invocation emits to `app/api/metrics.py` Prometheus counters:
- `clincase_agent_invocations_total{agent="biomarker_specialist",status=...}`
- `clincase_agent_latency_ms_p99`
- `clincase_llm_tokens_total{model_id=...}`
- `clincase_llm_cost_usd_total`

## Failure modes

- `BudgetExceeded` — caller's case-level budget exhausted before this agent ran.
- `InputBlocked` / `OutputBlocked` — a guardrail rejected the payload.
- `AgentExhausted` — schema parse failed after `max_iterations` retries.
- Bedrock 5xx — `ModelRouter.escalate(...)` switches to fallback on retry.
