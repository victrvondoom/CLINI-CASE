# Design — `nccn_reference_specialist`

> Generated from ClinCase `AGENT_MANIFEST` at 2026-05-02T13:05:55.313689+00:00.

## Architecture

This agent is a **sub-agent** of `appeals_drafter`. It shares the parent's
`AgentContext`, including:
  - `BudgetTracker` — per-case $5 / 600K-token ceiling
  - `TraceSink` — `PostgresTraceSink` in production, `InMemoryTraceSink` in tests
  - `WorkingMemory` — case-scoped scratch
  - `parent_span_id` — wires this span under the parent in the AgentTrace tree


## Input schema (`NCCNReferenceSpecialistInput`)

```json
{
  "$defs": {
    "CounterEvidenceItem": {
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
          "maxItems": 4,
          "title": "Cited Evidence",
          "type": "array"
        }
      },
      "required": [
        "contested_criterion",
        "payer_position",
        "counter_position"
      ],
      "title": "CounterEvidenceItem",
      "type": "object"
    }
  },
  "properties": {
    "treatment_name": {
      "title": "Treatment Name",
      "type": "string"
    },
    "diagnosis_icd10": {
      "title": "Diagnosis Icd10",
      "type": "string"
    },
    "counter_items": {
      "items": {
        "$ref": "#/$defs/CounterEvidenceItem"
      },
      "title": "Counter Items",
      "type": "array"
    }
  },
  "required": [
    "treatment_name",
    "diagnosis_icd10",
    "counter_items"
  ],
  "title": "NCCNReferenceSpecialistInput",
  "type": "object"
}
```

## Output schema (`NCCNReferenceSpecialistOutput`)

```json
{
  "properties": {
    "nccn_references": {
      "description": "Precise NCCN guideline references (e.g. 'NCCN Breast 4.2025 \u00a7 BINV-J').",
      "items": {
        "type": "string"
      },
      "maxItems": 5,
      "minItems": 1,
      "title": "Nccn References",
      "type": "array"
    }
  },
  "required": [
    "nccn_references"
  ],
  "title": "NCCNReferenceSpecialistOutput",
  "type": "object"
}
```

## Guardrails

### Input

- _(none configured)_

### Output

- `schema`: 

## Lifecycle (inherited from `Agent[I, O]`)

1. Validate input against `NCCNReferenceSpecialistInput` (Pydantic).
2. Cache lookup (sha256 of input + schema version + organization_id).
3. Input guardrails (PHI mask · token budget · custom).
4. Budget reservation against case-level `BudgetTracker`.
5. Act — LLM call OR `_execute_deterministic`.
6. Parse output into `NCCNReferenceSpecialistOutput` with retry-on-failure (Haiku→Sonnet escalation).
7. Output guardrails (citation completeness · custom).
8. Reflection (if `quality_threshold > 0`): grader scores; below-threshold retries.
9. Cache store on success.
10. Emit `AgentTrace` span; persist `agent_runs` row.

## Models

- **Primary:** `haiku` (lightweight_extraction)
- **Fallback:** `auto-escalate`

## Telemetry

Every invocation emits to `app/api/metrics.py` Prometheus counters:
- `clincase_agent_invocations_total{agent="nccn_reference_specialist",status=...}`
- `clincase_agent_latency_ms_p99`
- `clincase_llm_tokens_total{model_id=...}`
- `clincase_llm_cost_usd_total`

## Failure modes

- `BudgetExceeded` — caller's case-level budget exhausted before this agent ran.
- `InputBlocked` / `OutputBlocked` — a guardrail rejected the payload.
- `AgentExhausted` — schema parse failed after `max_iterations` retries.
- Bedrock 5xx — `ModelRouter.escalate(...)` switches to fallback on retry.
