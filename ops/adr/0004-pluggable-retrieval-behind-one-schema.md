# ADR-0004 — Pluggable retrieval (Bedrock KB ↔ Q Business) behind one Pydantic schema

## Status
Accepted · 2026-04-22

## Context

The ClinCase `policy_retriever` parent agent needs to surface the top-K payer-policy excerpts most relevant to a clinical case. The corpus lives in one of two places per customer:

- **Path A — ClinCase-curated corpus.** A small, hand-picked set of payer policy PDFs we ingest into Bedrock Knowledge Base. Used in dev + offline demo.
- **Path B — Customer's existing policy library.** Lives in M365 / SharePoint / Confluence — already accessible via the customer's Amazon Q Business tenant. The pattern Availity validated in 2025.

A new customer must NOT be forced to migrate their corpus to a new system just to onboard.

## Decision

**Pluggable retrieval backend behind one Pydantic schema.**

The `policy_retriever` orchestrator (`app/agents/policy_retriever/orchestrator.py`) picks between two sub-agents at call time based on `settings.USE_AMAZON_Q`:

- `USE_AMAZON_Q=false` → `keyword_filter` sub-agent → curated corpus or Bedrock KB.
- `USE_AMAZON_Q=true` → `q_business_retriever` sub-agent → Amazon Q Business `retrieve` API over the customer's existing connectors.

**Both sub-agents share the same `KeywordFilterInput` → `KeywordFilterOutput` Pydantic schema.** Downstream agents (`llm_reranker`, `citation_resolver`, `necessity_reasoner`) consume the same `CandidateSection` shape regardless of source.

## Consequences

**Positive**
- **Customer-onboarding velocity.** A new customer with their corpus in M365 flips `USE_AMAZON_Q=true` and the policy-retrieval path is live. **Saves ~1 month** of customer-onboarding time vs. building a new Bedrock KB index per customer (`ops/multi-tenant/ONBOARDING.md`).
- **Day-1 add-on** to a TriZetto customer who already has Q Business provisioned — no new platform decision.
- **Identical downstream code.** Reranker, citation resolver, necessity reasoner are all unaware of which backend produced the excerpts. Single test fixture validates both paths.
- **Future backend swap is one sub-agent module** away. (e.g. `s3_vectors_retriever` over the S3 Vectors module in `ops/terraform/s3-vectors/` — same schema.)

**Negative**
- **Two retrieval surfaces to monitor.** Both have `/metrics` cost counters; CloudWatch dashboards show each independently.
- **Q Business per-tenant config** complicates onboarding (`AMAZON_Q_APPLICATION_ID` + `AMAZON_Q_INDEX_ID` per customer). Mitigated by the per-tenant Terraform module roadmap.

**Neutral**
- ClinCase doesn't choose between the two for the customer — the customer (their TriZetto delivery team) does.

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| Bedrock KB only | Forces every customer to migrate their policy corpus into a new S3 bucket + KB index. Procurement-impossible for a customer with M365 already configured. |
| Q Business only | Q Business needs a connected enterprise corpus. ClinCase's curated dev/demo corpus has no M365/SharePoint home. Dev workflow would break. |
| Single hand-rolled retrieval over both | Doubles the code path; exposes the orchestrator to two completely different APIs. The Pydantic-schema boundary is the single right abstraction. |
| Custom embeddings + pgvector | Already had pgvector in `backend/db/schema.sql` for the dev-mode embeddings — kept for that. But customer-side: building per-customer pgvector is back to "Bedrock KB only" with extra steps. |

## References

- Availity Q + Bedrock case study: https://aws.amazon.com/solutions/case-studies/availity-q-case-study/
- Implementation: `backend/app/agents/policy_retriever/orchestrator.py`
- Q Business client: `backend/app/integrations/amazon_q/client.py`
- Per-tenant onboarding: `ops/multi-tenant/ONBOARDING.md`
- Q vs Bedrock division: `ops/architecture/Q_vs_BEDROCK.md`
