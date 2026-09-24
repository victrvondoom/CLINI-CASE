# Security policy

## Reporting a vulnerability

ClinCase is a healthcare-adjacent system that handles synthetic PHI in development and may handle real PHI in pilot deployments. We treat security disclosures with the urgency that implies.

**Do NOT** open a public GitHub issue for vulnerabilities. Instead:

- Report it privately through GitHub: [open a security advisory](https://github.com/victrvondoom/CLINI-CASE/security/advisories/new)
- For PHI-related concerns specifically, **stop production traffic immediately** and follow [`ops/sre/RUNBOOK.md`](ops/sre/RUNBOOK.md) § INC-003.

We will acknowledge within 24 hours and aim to confirm the issue + provide a remediation timeline within 72 hours.

## Scope

In scope:

- The ClinCase application code (`backend/`, `frontend/`)
- The agent framework and lifecycle (`backend/app/agents/framework/`)
- The GenAI Gateway and its enforcement layers (`backend/app/llm/gateway.py`)
- The TriZetto AI Gateway adapter (`backend/app/integrations/trizetto/`)
- All published `ops/terraform/` modules
- All `.kiro/hooks/` scripts

Out of scope:

- Third-party dependencies (file with the upstream project)
- The TriZetto AI Gateway itself
- Bedrock / Anthropic models
- Demo-only fixtures and synthetic data

## What we look for

- **PHI leakage** — any path where unredacted PHI flows to a non-Bedrock LLM, an external service, or persistent storage outside the encrypted boundary
- **Bedrock invocation bypass** — any path that calls a Bedrock model_id NOT in the configured tenant policy, or calls without the GenAI Gateway audit row
- **Cross-tenant access** — any query path that returns data from one organization to a user in a different organization (we expect 404, not 403, to avoid existence leaks)
- **HITL gate bypass** — any path that produces a DENY decision row without a corresponding `reviewer_actions` row when SB 1120 / CMS § IV.C apply
- **Tampering with Evidence Pack** — any way to mutate the canonical bundle JSON and have its `bundle_sha256` verify as unchanged
- **Idempotency bypass** — any way to enqueue duplicate `case_jobs` for the same `(organization_id, case_id, idempotency_key)`
- **Authorization escalation** — any way to assume a higher role (admin / reviewer) without a fresh JWT for that role

## What we don't consider a vulnerability

- The development-default `JWT_SECRET` (we expect customers to rotate via AWS Secrets Manager)
- Demo-mode `LLM_PROVIDER=openrouter` with shared credentials (only used in dev)
- The in-process TriZetto mock receiver (`/_mock/inbox`) returning to all org users — it's intentionally accessible for the demo
- Missing rate limiting on `/api/v1/healthz` (intentional — it's the K8s liveness probe)

## Defensive layers (so you know what to bypass)

1. **In-process GenAI Gateway** — per-tenant model allowlist, 24h rolling token + USD quota, content-safety pre-check, `llm_invocations` audit row
2. **AWS API Gateway** (production) — IAM, quotas, network controls
3. **AWS PrivateLink VPC endpoint** for Bedrock — endpoint policy with per-model-id condition
4. **IAM role** `clincase-bedrock-invoke-role` — IRSA-bound to specific K8s ServiceAccounts only
5. **Per-tenant Bedrock Guardrail** — PHI redaction policy applied at the Bedrock API
6. **Per-tenant KMS multi-region key** — envelope encryption at rest + cross-region replica

A successful vulnerability typically requires bypassing layers 1+ AND 4+ AND 5.

## .well-known/security.txt

A live version is served at `/.well-known/security.txt` once the production deploy is up. Static fallback in this repo at `frontend/public/.well-known/security.txt`.

## Scope of synthetic PHI in this repo

The fixture cases under `backend/tests/fixtures/` and `backend/app/synthea/seeds/` use Synthea-generated synthetic patient data. These are NOT real PHI but should still be handled with the same code paths as real PHI to avoid two-mode bugs.
