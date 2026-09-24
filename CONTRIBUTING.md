# Contributing to ClinCase

Thank you for considering contributing. ClinCase is the kind of system where small misalignments become production incidents — every change should land here knowing why it landed.

## Read first

- [`README.md`](README.md) — what ClinCase is and how to run it
- [`ops/architecture/TARGET_ARCHITECTURE.md`](ops/architecture/TARGET_ARCHITECTURE.md) — the 5-layer model
- [`ops/adr/`](ops/adr/) — 8 Architecture Decision Records (read at least the ones whose layer you're touching)
- [`CLAUDE.md`](CLAUDE.md) — coding conventions

## Before you change anything

```bash
make smoke                # 5-layer self-check passes (round-7 baseline)
make frontend.typecheck   # tsc --noEmit returns 0
```

If either fails on a clean checkout, **don't start your work** — open an issue. The baseline must be green.

## How to add a new agent

1. Drop a package under `backend/app/agents/<your_agent>/`. The auto-discovery in `app/agents/manifest.py` walks `app.agents.*` via `pkgutil` — your agent appears in the manifest on the next process restart, no hand-edits required.
2. Each agent ships:
   - `__init__.py` (re-exports your `Agent[I,O]` instance)
   - `orchestrator.py` (your `Agent[I,O]` subclass)
   - `node.py` (LangGraph node entry point)
   - `schemas.py` (Pydantic v2 input + output models)
   - `sub_agents/` (optional — if your agent decomposes further)
3. Subclass `app.agents.framework.agent.Agent[I, O]`. Declare:
   - `name`, `parent`, `role`, `description` (ClassVars)
   - `input_schema`, `output_schema`
   - `primary_model = SONNET_REASONING` *or* `_execute_deterministic(self, input, ctx)`
   - `quality_threshold` (if reflection-enabled)
4. Drop the prompt in `backend/app/prompts/<your_agent>/<your_agent>.txt`. **Never inline a multi-line prompt in code.**
5. Write a contract test in `backend/tests/agents/test_<your_agent>.py` against at least one fixture in `backend/tests/fixtures/`.
6. Run `make smoke && make backend.test` — should pass on your branch.
7. Run `make kiro.export` to refresh `.kiro/specs/`.

## How to add a new backend retrieval source

See ADR-0004 ([`ops/adr/0004-pluggable-retrieval-behind-one-schema.md`](ops/adr/0004-pluggable-retrieval-behind-one-schema.md)). Implement a sub-agent under `backend/app/agents/policy_retriever/sub_agents/` that consumes `KeywordFilterInput` and produces `KeywordFilterOutput`. Add a config flag and wire the orchestrator's per-call selection.

## How to add a new compliance clause

`backend/app/compliance/cms_0057f.py` — append to `CLAUSES`. Add a `case` branch in `case_scorecard()` with the check logic. The frontend at `/compliance` picks it up automatically.

## Architecture boundary rules (enforced by Kiro Hook)

The Kiro Hook `architecture-boundary-check.sh` enforces:

- `app/api/*` MUST NOT import from `app/llm/*` directly (must go via `get_llm_client()` / Gateway).
- `app/agents/*` MUST NOT import from `app/api/*`.
- Only `app/llm/gateway.py` + `app/llm/factory.py` may call `BedrockClient` directly.
- `app/integrations/trizetto/**` MUST NOT import from `app/agents/**`.

If your change crosses any of these, **you're probably doing the wrong thing** — open an architecture discussion first.

## Commit conventions

```
feat(agents): add cardiology necessity reasoner sub-agent
fix(gateway): respect per-tenant model allowlist on retry
docs(adr): ADR-0009 — switch to AgentCore Runtime in prod
chore(deps): bump python-pptx to 1.0.2
```

## PR checklist

- [ ] `make smoke` passes
- [ ] `make frontend.typecheck` passes
- [ ] If you touched a Pydantic schema: ran `make kiro.export` so `.kiro/specs/` matches
- [ ] If you touched a model_id: confirmed it's in the per-tenant allowlist (`tenant_policies` table)
- [ ] If you added a new agent: contract test + `agent-foundry-manifest.yaml` updated (Hook will catch this)
- [ ] If you touched a regulatory boundary (HITL gate, PHI guardrail, audit trail): noted in PR description with the regulation name
- [ ] No new `.env` file staged (CI catches this)
- [ ] No prompts inlined in code (must live in `backend/app/prompts/`)

## Things never to do

(From [`CLAUDE.md`](CLAUDE.md):)

- Hard-code secrets
- Call the LLM without the Gateway's `LLMClient` interface
- Return free-form prose from an agent — always structured Pydantic JSON
- Log PHI even in synthetic mode (use patient initials only)
- Delete from the `cases` table — use `status` instead
- Skip the HITL gate for adverse determinations (CA SB 1120 / CMS § IV.C)

## Getting help

- Architecture questions → read the ADRs first
- Strategic alignment questions → [`ops/architecture/BUSINESS_USE_CASE.md`](ops/architecture/BUSINESS_USE_CASE.md)
- "How do I onboard a new customer?" → [`ops/multi-tenant/ONBOARDING.md`](ops/multi-tenant/ONBOARDING.md)
- Production incidents → [`ops/sre/RUNBOOK.md`](ops/sre/RUNBOOK.md)
