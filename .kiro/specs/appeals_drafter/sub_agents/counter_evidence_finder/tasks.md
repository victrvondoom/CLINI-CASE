# Tasks — `counter_evidence_finder`

> Generated from ClinCase `AGENT_MANIFEST` at 2026-05-02T13:05:55.311955+00:00.

## Implementation tasks

- [ ] Define `CounterEvidenceFinderInput` (input) and `CounterEvidenceFinderOutput` (output) in the package's `schemas.py`.
- [ ] Subclass `Agent[InputSchema, OutputSchema]`, declaring required ClassVars (`name`, `parent`, `role`, `description`).
- [ ] Place implementation in `backend/app/agents/appeals_drafter/sub_agents/counter_evidence_finder.py`.

- [ ] Author `system_prompt` in `backend/app/prompts/appeals_drafter/sub_agents/counter_evidence_finder.txt` (or `counter_evidence_finder.txt` for orchestrators).
- [ ] Set `primary_model` to the appropriate `ModelSpec` (`SONNET_REASONING`, `HAIKU_LITE`, etc.).
- [ ] If output requires reflection, set `quality_threshold > 0` and reuse `LLMGrader` default.
- [ ] Add a `phi_sanitizer` input guardrail when prompt receives raw FHIR.


## Test tasks

- [ ] Add a contract test under `backend/tests/agents/test_counter_evidence_finder.py`.
- [ ] Use `tests/fixtures/` cases that exercise APPROVE / DENY / REFER paths.
- [ ] Assert: schema validity, citations populated, budget consumed, span persisted.
- [ ] Assert HITL routing where `confidence < 0.75`.

## Ops tasks

- [ ] No K8s changes required — auto-discovered by `app/agents/manifest.py`.
- [ ] No metrics wiring required — `Agent.invoke()` emits Prometheus counters automatically.
- [ ] Update `ops/demo/PITCH_DECK.md` if this agent is part of the headline demo path.
