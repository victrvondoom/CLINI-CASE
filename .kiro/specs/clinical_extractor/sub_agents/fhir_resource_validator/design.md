# Design — `fhir_resource_validator`

> Generated from ClinCase `AGENT_MANIFEST` at 2026-05-02T13:05:55.319759+00:00.

## Architecture

This agent is a **sub-agent** of `clinical_extractor`. It shares the parent's
`AgentContext`, including:
  - `BudgetTracker` — per-case $5 / 600K-token ceiling
  - `TraceSink` — `PostgresTraceSink` in production, `InMemoryTraceSink` in tests
  - `WorkingMemory` — case-scoped scratch
  - `parent_span_id` — wires this span under the parent in the AgentTrace tree


## Input schema (`FHIRResourceValidatorInput`)

```json
{
  "properties": {
    "fhir_bundle": {
      "title": "Fhir Bundle",
      "type": "object"
    }
  },
  "required": [
    "fhir_bundle"
  ],
  "title": "FHIRResourceValidatorInput",
  "type": "object"
}
```

## Output schema (`FHIRResourceValidatorOutput`)

```json
{
  "$defs": {
    "FHIRResourceIssue": {
      "properties": {
        "severity": {
          "enum": [
            "error",
            "warning"
          ],
          "title": "Severity",
          "type": "string"
        },
        "path": {
          "title": "Path",
          "type": "string"
        },
        "message": {
          "title": "Message",
          "type": "string"
        }
      },
      "required": [
        "severity",
        "path",
        "message"
      ],
      "title": "FHIRResourceIssue",
      "type": "object"
    }
  },
  "properties": {
    "is_valid": {
      "title": "Is Valid",
      "type": "boolean"
    },
    "resource_counts": {
      "additionalProperties": {
        "type": "integer"
      },
      "title": "Resource Counts",
      "type": "object"
    },
    "issues": {
      "items": {
        "$ref": "#/$defs/FHIRResourceIssue"
      },
      "title": "Issues",
      "type": "array"
    }
  },
  "required": [
    "is_valid"
  ],
  "title": "FHIRResourceValidatorOutput",
  "type": "object"
}
```

## Guardrails

### Input

- _(none configured)_

### Output

- _(none configured)_

## Lifecycle (inherited from `Agent[I, O]`)

1. Validate input against `FHIRResourceValidatorInput` (Pydantic).
2. Cache lookup (sha256 of input + schema version + organization_id).
3. Input guardrails (PHI mask · token budget · custom).
4. Budget reservation against case-level `BudgetTracker`.
5. Act — LLM call OR `_execute_deterministic`.
6. Parse output into `FHIRResourceValidatorOutput` with retry-on-failure (Haiku→Sonnet escalation).
7. Output guardrails (citation completeness · custom).
8. Reflection (if `quality_threshold > 0`): grader scores; below-threshold retries.
9. Cache store on success.
10. Emit `AgentTrace` span; persist `agent_runs` row.

## Models

- **Primary:** `deterministic` (n/a)
- **Fallback:** `auto-escalate`

## Telemetry

Every invocation emits to `app/api/metrics.py` Prometheus counters:
- `clincase_agent_invocations_total{agent="fhir_resource_validator",status=...}`
- `clincase_agent_latency_ms_p99`
- `clincase_llm_tokens_total{model_id=...}`
- `clincase_llm_cost_usd_total`

## Failure modes

- `BudgetExceeded` — caller's case-level budget exhausted before this agent ran.
- `InputBlocked` / `OutputBlocked` — a guardrail rejected the payload.
- `AgentExhausted` — schema parse failed after `max_iterations` retries.
- Bedrock 5xx — `ModelRouter.escalate(...)` switches to fallback on retry.
