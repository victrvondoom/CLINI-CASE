# Tasks — `clinical_extractor`

> Generated from ClinCase `AGENT_MANIFEST` at 2026-05-02T13:05:55.317048+00:00.

## Implementation tasks

- [ ] Define `ClinicalExtractorInput` (input) and `ClinicalExtractorOutput` (output) in the package's `schemas.py`.
- [ ] Subclass `Agent[InputSchema, OutputSchema]`, declaring required ClassVars (`name`, `parent`, `role`, `description`).
- [ ] Place implementation in `backend/app/agents/clinical_extractor/orchestrator.py`.

- [ ] Implement `_execute_deterministic(input, ctx) -> output` in `backend/app/agents/clinical_extractor/orchestrator.py`.
- [ ] Set `primary_model = None` so the framework knows to skip the LLM path.


## Test tasks

- [ ] Add a contract test under `backend/tests/agents/test_clinical_extractor.py`.
- [ ] Use `tests/fixtures/` cases that exercise APPROVE / DENY / REFER paths.
- [ ] Assert: schema validity, citations populated, budget consumed, span persisted.
- [ ] Assert HITL routing where `confidence < 0.75`.

## Ops tasks

- [ ] No K8s changes required — auto-discovered by `app/agents/manifest.py`.
- [ ] No metrics wiring required — `Agent.invoke()` emits Prometheus counters automatically.
