# Design — `confidence_calibrator`

> Generated from ClinCase `AGENT_MANIFEST` at 2026-05-02T13:05:55.347903+00:00.

## Architecture

This agent is a **sub-agent** of `necessity_reasoner`. It shares the parent's
`AgentContext`, including:
  - `BudgetTracker` — per-case $5 / 600K-token ceiling
  - `TraceSink` — `PostgresTraceSink` in production, `InMemoryTraceSink` in tests
  - `WorkingMemory` — case-scoped scratch
  - `parent_span_id` — wires this span under the parent in the AgentTrace tree


## Input schema (`ConfidenceCalibratorInput`)

```json
{
  "$defs": {
    "AtomicCriterion": {
      "description": "One indivisible inclusion/exclusion criterion.",
      "properties": {
        "text": {
          "title": "Text",
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
          "minimum": 0,
          "title": "Policy Excerpt Index",
          "type": "integer"
        },
        "section_pointer": {
          "default": "",
          "title": "Section Pointer",
          "type": "string"
        }
      },
      "required": [
        "text",
        "policy_excerpt_index"
      ],
      "title": "AtomicCriterion",
      "type": "object"
    },
    "EvidenceMatch": {
      "description": "Output schema for the evidence_matcher sub-agent.\n\nThe `criterion` field is optional on the LLM's output \u2014 it's set by the\norchestrator post-call (the parent already knows which criterion it\nsent) so we don't waste tokens making the LLM echo it back.",
      "properties": {
        "criterion": {
          "anyOf": [
            {
              "$ref": "#/$defs/AtomicCriterion"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "status": {
          "enum": [
            "MET",
            "NOT_MET",
        
```

## Output schema (`ConfidenceCalibratorOutput`)

```json
{
  "description": "Output schema for confidence_calibrator.\n\nReturns just the per-criterion confidences (in the SAME ORDER as the\ninput matches) plus the aggregate. The orchestrator zips these with the\ninput matches to assemble the full NecessityAssessment \u2014 keeping the\ncalibrator's output small and the LLM's job focused (numeric calibration,\nnot echoing back all the match content).",
  "properties": {
    "confidences": {
      "description": "One confidence \u2208 [0,1] per input match, in input order.",
      "items": {
        "type": "number"
      },
      "minItems": 1,
      "title": "Confidences",
      "type": "array"
    },
    "overall_confidence": {
      "maximum": 1.0,
      "minimum": 0.0,
      "title": "Overall Confidence",
      "type": "number"
    },
    "summary": {
      "title": "Summary",
      "type": "string"
    }
  },
  "required": [
    "confidences",
    "overall_confidence",
    "summary"
  ],
  "title": "ConfidenceCalibratorOutput",
  "type": "object"
}
```

## Guardrails

### Input

- _(none configured)_

### Output

- `schema`: 

## Lifecycle (inherited from `Agent[I, O]`)

1. Validate input against `ConfidenceCalibratorInput` (Pydantic).
2. Cache lookup (sha256 of input + schema version + organization_id).
3. Input guardrails (PHI mask · token budget · custom).
4. Budget reservation against case-level `BudgetTracker`.
5. Act — LLM call OR `_execute_deterministic`.
6. Parse output into `ConfidenceCalibratorOutput` with retry-on-failure (Haiku→Sonnet escalation).
7. Output guardrails (citation completeness · custom).
8. Reflection (if `quality_threshold > 0`): grader scores; below-threshold retries.
9. Cache store on success.
10. Emit `AgentTrace` span; persist `agent_runs` row.

## Models

- **Primary:** `haiku` (lightweight_extraction)
- **Fallback:** `auto-escalate`

## Telemetry

Every invocation emits to `app/api/metrics.py` Prometheus counters:
- `clincase_agent_invocations_total{agent="confidence_calibrator",status=...}`
- `clincase_agent_latency_ms_p99`
- `clincase_llm_tokens_total{model_id=...}`
- `clincase_llm_cost_usd_total`

## Failure modes

- `BudgetExceeded` — caller's case-level budget exhausted before this agent ran.
- `InputBlocked` / `OutputBlocked` — a guardrail rejected the payload.
- `AgentExhausted` — schema parse failed after `max_iterations` retries.
- Bedrock 5xx — `ModelRouter.escalate(...)` switches to fallback on retry.
