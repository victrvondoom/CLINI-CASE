# Design — `reason_predictor`

> Generated from ClinCase `AGENT_MANIFEST` at 2026-05-02T13:05:55.337379+00:00.

## Architecture

This agent is a **sub-agent** of `denial_forecaster`. It shares the parent's
`AgentContext`, including:
  - `BudgetTracker` — per-case $5 / 600K-token ceiling
  - `TraceSink` — `PostgresTraceSink` in production, `InMemoryTraceSink` in tests
  - `WorkingMemory` — case-scoped scratch
  - `parent_span_id` — wires this span under the parent in the AgentTrace tree


## Input schema (`ReasonPredictorInput`)

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
       
```

## Output schema (`ReasonPredictorOutput`)

```json
{
  "$defs": {
    "DenialReason": {
      "description": "One predicted denial rationale, ranked by likelihood.",
      "properties": {
        "rank": {
          "maximum": 10,
          "minimum": 1,
          "title": "Rank",
          "type": "integer"
        },
        "text": {
          "description": "One-sentence reason in payer language.",
          "title": "Text",
          "type": "string"
        },
        "policy_section_pointer": {
          "default": "",
          "description": "Which payer policy section drives this risk (e.g. 'Aetna 0048 \u00a7 Initial Authorization Criteria').",
          "title": "Policy Section Pointer",
          "type": "string"
        },
        "likelihood": {
          "maximum": 1.0,
          "minimum": 0.0,
          "title": "Likelihood",
          "type": "number"
        }
      },
      "required": [
        "rank",
        "text",
        "likelihood"
      ],
      "title": "DenialReason",
      "type": "object"
    }
  },
  "properties": {
    "top_reasons": {
      "items": {
        "$ref": "#/$defs/DenialReason"
      },
      "maxItems": 3,
      "title": "Top Reasons",
      "type": "array"
    }
  },
  "title": "ReasonPredictorOutput",
  "type": "object"
}
```

## Guardrails

### Input

- _(none configured)_

### Output

- `schema`: 

## Lifecycle (inherited from `Agent[I, O]`)

1. Validate input against `ReasonPredictorInput` (Pydantic).
2. Cache lookup (sha256 of input + schema version + organization_id).
3. Input guardrails (PHI mask · token budget · custom).
4. Budget reservation against case-level `BudgetTracker`.
5. Act — LLM call OR `_execute_deterministic`.
6. Parse output into `ReasonPredictorOutput` with retry-on-failure (Haiku→Sonnet escalation).
7. Output guardrails (citation completeness · custom).
8. Reflection (if `quality_threshold > 0`): grader scores; below-threshold retries.
9. Cache store on success.
10. Emit `AgentTrace` span; persist `agent_runs` row.

## Models

- **Primary:** `haiku` (lightweight_extraction)
- **Fallback:** `auto-escalate`

## Telemetry

Every invocation emits to `app/api/metrics.py` Prometheus counters:
- `clincase_agent_invocations_total{agent="reason_predictor",status=...}`
- `clincase_agent_latency_ms_p99`
- `clincase_llm_tokens_total{model_id=...}`
- `clincase_llm_cost_usd_total`

## Failure modes

- `BudgetExceeded` — caller's case-level budget exhausted before this agent ran.
- `InputBlocked` / `OutputBlocked` — a guardrail rejected the payload.
- `AgentExhausted` — schema parse failed after `max_iterations` retries.
- Bedrock 5xx — `ModelRouter.escalate(...)` switches to fallback on retry.
