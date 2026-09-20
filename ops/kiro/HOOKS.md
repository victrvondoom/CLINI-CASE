# ClinCase — Kiro IDE Hooks (GenAI in the SDLC)

**Audience:** AeroFyta engineering · Cognizant TriZetto delivery engineering

> *"GenAI in the SDLC, not just GenAI in the app."*
> — the Cognizant "AI builder" narrative

Kiro Hooks are the AWS-blessed primitive that fires AI-assisted automation
on file events / PR events / repo events. We use them to enforce modular
architecture, automate task decomposition, regenerate specs from code, and
keep the codebase clean enough that a 30-day pilot kickoff doesn't burn a
week on cleanup. This document is the canonical list.

## Why Hooks (and not just GitHub Actions)

GitHub Actions runs after a developer pushes — it catches mistakes in CI.
Kiro Hooks run **inside the IDE while the developer is still typing** — the
mistake is corrected before it ever reaches the PR. That difference is what
turns "5 specialty bundles per year" into "5 specialty bundles per quarter."

This pairs with `.github/workflows/ci.yml` (the post-push gate) and
`.kiro/specs/` (the agent contracts auto-generated from `AGENT_MANIFEST`).

## The Hooks shipped today

### `.kiro/hooks/regenerate-specs-on-save.sh`

**Trigger:** on file save in `backend/app/agents/**`

Runs `python -m app.integrations.kiro.exporter` to regenerate `.kiro/specs/`
from the live manifest. **Guarantees that every commit's `.kiro/specs/`
mirrors its agents.** No manual sync; no spec drift.

### `.kiro/hooks/verify-foundry-manifest-on-pr.sh`

**Trigger:** on PR opened or updated

Verifies `ops/agent-foundry/agent-foundry-manifest.yaml` agents block
matches `AGENT_MANIFEST` (parents_total, sub_agents_total). If it doesn't,
fail the PR with a one-line explanation. **Closes the manifest-drift gap
that kills enterprise AI deployments.**

### `.kiro/hooks/architecture-boundary-check.sh`

**Trigger:** on file save anywhere in `backend/app/`

Enforces the 5-layer module boundaries from `ops/architecture/TARGET_ARCHITECTURE.md`:

- `app/api/*` MUST NOT import from `app/llm/*` directly (must go via Gateway).
- `app/agents/*` MUST NOT import from `app/api/*` (no circular orchestration).
- `app/llm/gateway.py` is the ONLY module that may call `BedrockClient` directly.
- `app/integrations/trizetto/**` MUST NOT import from `app/agents/**`.

Runs a quick AST walk; if a forbidden import is found, surface the violation
in Kiro's diagnostics panel before the developer hits save.

### `.kiro/hooks/contract-test-on-prompt-edit.sh`

**Trigger:** on file save in `backend/app/prompts/**.txt`

When a prompt file is edited, run the contract test for the corresponding
agent and invalidate the deterministic response cache for that agent's
schema version. **The cache invalidation is the killer feature — without
it, prompt edits silently take 1 hour to propagate.**

### `.kiro/hooks/responsible-ai-card-refresh.sh`

**Trigger:** on file save in `backend/app/llm/*` OR `backend/app/config.py`

Refreshes `ops/responsible-ai/MODEL_CARD_SNAPSHOT.md` from the live
`/api/v1/responsible-ai/model-card.md` so the repo's static copy stays in
sync with what the running app declares. **Saves a procurement/security
team from chasing stale evidence.**

## How to install

```bash
cp .kiro/hooks/*.sh /usr/local/bin/  # OR add to PATH
# Configure Kiro to recognize them as Hooks via the IDE's
# Settings > Hooks > Add Hook flow. Each script is registered as
# `on_save` / `on_pr` / `on_merge` per the trigger noted above.
```

In a Cognizant Agent Foundry deployment, Hooks are installed automatically
via `kiro install --bundle clincase` — see Foundry's published packaging
docs once they ship.

## Coverage of the user's stated discipline goals

| Goal from project conventions | Hook that enforces it |
|---|---|
| "Modularity, separation of concerns, clean layering" | `architecture-boundary-check.sh` |
| "Automate task decomposition, refactoring, test generation" | `contract-test-on-prompt-edit.sh` (test gen on prompt edit) + Kiro's built-in `tasks.md` decomposition |
| "Improve developer productivity and maintainability" | `regenerate-specs-on-save.sh` removes spec-drift drag |
| "Cognizant 'AI builder' narrative — GenAI in the SDLC" | All five Hooks plus `.kiro/specs/` auto-export |

## Cognizant Flowsource alignment

Cognizant Flowsource is the published platform for **async-autonomous software
engineering** — *"associates delegate macro tasks to agent networks and
'micro-steer' outcomes"* ([Constellation 2025](https://www.constellationr.com/insights/news/cognizant-aims-solve-ai-velocity-gap)).
The ClinCase repo is engineered to graft directly onto a Cognizant Flowsource
deployment:

| Flowsource concept | ClinCase realization |
|---|---|
| **Macro task delegation** | Engineer edits `app/agents/<parent>/orchestrator.py`; Hook 1 (`regenerate-specs-on-save.sh`) propagates the change into `.kiro/specs/` automatically. |
| **Agent-network execution** | Hook 4 (`contract-test-on-prompt-edit.sh`) runs the bounded contract test for the affected agent; reflection-enabled agents re-grade themselves. |
| **Operator micro-steering** | Hook 3 (`architecture-boundary-check.sh`) surfaces violations in the IDE's diagnostic panel — engineer sees what to override before the file is committed. |
| **Outcome attribution** | Hook 2 (`verify-foundry-manifest-on-pr.sh`) keeps `agent-foundry-manifest.yaml` synced with the live `AGENT_MANIFEST` so the Foundry Marketplace listing matches what's actually shipping. |

A Cognizant engineering manager evaluating ClinCase for Flowsource ingestion
runs the Hooks and gets a one-paragraph "is this Flowsource-shaped?" yes/no
verdict — without reading the codebase.

## Agentic capital — what these hooks actually preserve

Cognizant's 2026 narrative names the underlying asset *agentic capital*:
the encoded, auditable, replayable knowledge that an agent network draws on
to do work. Each Hook above protects one dimension of that capital:

- **Spec-code coherence** (Hook 1) — the contract a customer's compliance
  officer reads (`.kiro/specs/<agent>/requirements.md`) is always
  identical to the contract the agent enforces at runtime.
- **Cross-layer integrity** (Hook 3) — the architecture published in
  `ops/architecture/TARGET_ARCHITECTURE.md` is enforced at the import
  boundary; a junior engineer can't accidentally couple the `api` layer
  to the `llm` layer.
- **Manifest fidelity** (Hook 2) — the Cognizant Agent Marketplace listing
  matches the running implementation; no drift, no surprise.
- **Test-prompt alignment** (Hook 4) — every prompt edit triggers its
  contract test + invalidates the response cache; an editor sees the
  consequence of their change before it reaches CI.

That's how ClinCase turns "GenAI in the SDLC" from a slogan into operational
discipline.

## Sources

- AWS — Kiro IDE GA + GovCloud regions ([AWS Weekly Roundup Feb 23 2026](https://aws.amazon.com/blogs/aws/aws-weekly-roundup-claude-sonnet-4-6-in-amazon-bedrock-kiro-in-govcloud-regions-new-agent-plugins-and-more-february-23-2026/))
- AWS — "From spec to production: a three-week drug discovery agent using Kiro" ([AWS for Industries](https://aws.amazon.com/blogs/industries/from-spec-to-production-a-three-week-drug-discovery-agent-using-kiro/))
- Cognizant Flowsource — async-autonomous engineering platform ([Constellation 2025](https://www.constellationr.com/insights/news/cognizant-aims-solve-ai-velocity-gap))
- "Agentic capital" framing — Cognizant 2026 narrative
