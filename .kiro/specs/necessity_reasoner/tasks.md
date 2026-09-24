# Tasks — `necessity_reasoner`

> Generated from ClinCase `AGENT_MANIFEST` at 2026-05-02T13:05:55.342180+00:00.

## Implementation tasks

- [ ] Define `NecessityReasonerInput` (input) and `NecessityReasonerOutput` (output) in the package's `schemas.py`.
- [ ] Subclass `Agent[InputSchema, OutputSchema]`, declaring required ClassVars (`name`, `parent`, `role`, `description`).
- [ ] Place implementation in `backend/app/agents/necessity_reasoner/orchestrator.py`.

- [ ] Implement `_execute_deterministic(input, ctx) -> output` in `backend/app/agents/necessity_reasoner/orchestrator.py`.
- [ ] Set `primary_model = None` so the framework knows to skip the LLM path.


## Test tasks

- [ ] Add a contract test under `backend/tests/agents/test_necessity_reasoner.py`.
- [ ] Use `tests/fixtures/` cases that exercise APPROVE / DENY / REFER paths.
- [ ] Assert: schema validity, citations populated, budget consumed, span persisted.
- [ ] Assert HITL routing where `confidence < 0.75`.

## Ops tasks

- [ ] No K8s changes required — auto-discovered by `app/agents/manifest.py`.
- [ ] No metrics wiring required — `Agent.invoke()` emits Prometheus counters automatically.
