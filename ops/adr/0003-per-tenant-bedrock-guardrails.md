# ADR-0003 — Per-tenant Bedrock Guardrail attached at InvokeModel

## Status
Accepted · 2026-04-19

## Context

ClinCase is multi-tenant. Different customers have different PHI-redaction policies — e.g. one customer redacts MRNs, DOBs, addresses, and SSNs; another also redacts insurance member numbers + provider NPIs (as PHI under a stricter HIPAA implementation guide). The redaction policy must:

- Apply on **every** Bedrock InvokeModel call across all 22 sub-agents.
- Be **per-tenant configurable** without code change.
- Be **auditable** — a CISO can verify which guardrail was applied to a given decision.
- Co-exist with the in-process `PHIInputGuardrail` (which is a pre-call sanity net, not the policy of record).

## Decision

**Per-tenant Bedrock Guardrail ID, attached at the API call.**

Each tenant has its own `BEDROCK_GUARDRAIL_ID` (and version). The GenAI Gateway (`app/llm/gateway.py`) reads the per-tenant policy via `get_tenant_policy()`, retrieves the configured guardrail ID, and the underlying `BedrockClient` attaches it to every InvokeModel request via the `guardrailIdentifier` parameter. The guardrail ID is recorded on every `llm_invocations` audit row.

Per-tenant onboarding documented in `ops/multi-tenant/ONBOARDING.md`.

## Consequences

**Positive**
- **Customer's PHI policy lives in their account.** They control what's redacted; we don't make policy decisions on their behalf.
- **Audit trail** — `llm_invocations.guardrail_id` (planned) records which guardrail was applied to each call. A CISO can verify policy provenance per case.
- **Zero code change** to onboard a customer with a new guardrail policy — just provision a new `BEDROCK_GUARDRAIL_ID` and set the env. The Bedrock VPC endpoint policy in `ops/terraform/bedrock-vpc-endpoint/vpc-endpoints.tf` allows `bedrock:ApplyGuardrail` on whatever guardrail ARN the customer provides.
- **Defense in depth.** PHI sanity-check pre-flight in `app/llm/gateway.py` + Bedrock Guardrail at the API + per-tenant KMS at storage. Three independent layers; a bug in any one doesn't leak.

**Negative**
- **Two guardrail systems to think about.** App-layer `PHIInputGuardrail` for fast-fail in dev + Bedrock Guardrail for the policy of record. Comment-of-record in `app/agents/framework/guardrails.py` explains which is authoritative.
- **Guardrail provisioning is a per-tenant onboarding step.** Documented + automated in the per-tenant Terraform stub (TODO post-pilot — see `ops/multi-tenant/ONBOARDING.md`).

**Neutral**
- Bedrock Guardrails ApplyGuardrail call adds ~15 ms p95 latency. Acceptable inside our 90 s p95 SLO.

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| Single global Bedrock Guardrail | Forces every customer to accept ClinCase's redaction policy. Procurement non-starter for a customer with stricter HIPAA implementation. |
| App-layer redaction only | Bedrock's native guardrail tooling is the AWS-blessed safety primitive. App-layer redaction can't be enforced if a developer accidentally bypasses it; Bedrock's enforcement is at the API. |
| AWS Macie + post-call redaction | Reactive. PHI would already be in CloudWatch logs / our DB. Pre-call enforcement is the only correct shape. |

## References

- AWS Bedrock Guardrails docs: https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails.html
- Implementation: `app/llm/gateway.py`, `app/llm/bedrock_client.py`
- Per-tenant onboarding: `ops/multi-tenant/ONBOARDING.md`
- VPC endpoint policy allowing per-tenant guardrails: `ops/terraform/bedrock-vpc-endpoint/vpc-endpoints.tf`
