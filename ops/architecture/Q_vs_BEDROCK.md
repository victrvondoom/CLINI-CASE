# ClinCase — Amazon Q vs Amazon Bedrock — Division of Roles

**Audience:** Health-sciences solution architect · AWS account team · ClinCase engineering

This is the canonical answer to *"why both? where does each one go?"* in the ClinCase deployment. Backed by AWS's published guidance, two services with different jobs:

> **Amazon Bedrock** — *"foundation-model platform underpinning GenAI features (LLMs, RAG, customization, monitoring and governance capabilities for enterprise AI)"*
> ([Avasant 2026](https://avasant.com/report/aws-charts-a-bold-path-in-generative-ai-with-amazon-q-nova-models-and-bedrock-innovations/))
>
> **Amazon Q** — *"enterprise assistant or developer / knowledge copilot, leveraging AWS-specific and enterprise knowledge"*
> ([CloudThat 2025](https://www.cloudthat.com/resources/blog/amazon-q-vs-amazon-bedrock-choosing-the-right-ai-solution-for-your-enterprise/))

Both have a place in ClinCase. They do different things.

---

## TL;DR — the one-line decision

| If the job is… | Use… |
|---|---|
| Reason over patient data + payer policy + emit a structured Decision | **Bedrock** (Sonnet 4.6 via `LLMClient` / GenAI Gateway) |
| Retrieve passages from the *customer's* policy library (M365 / SharePoint / Confluence) | **Amazon Q Business** (drop-in for Bedrock KB) |
| Help a ClinCase developer / partner SA navigate the codebase / write a new agent | **Amazon Q Developer** (deferred — see below) |
| Run a managed Bedrock Knowledge Base directly off our policy S3 | **Bedrock KB** |

---

## Where each is used in ClinCase today

### Amazon Bedrock — the LLM platform

Bedrock is the **reasoning engine** for every agent that produces structured output:

| ClinCase component | Bedrock role | Code reference |
|---|---|---|
| 7-agent LangGraph DAG (parents) | Sonnet 4.6 InvokeModel for all 7 reasoning passes | `app/agents/<parent>/orchestrator.py` |
| 22 sub-agents (15 LLM-backed) | Sonnet primary, Haiku for graders, ModelRouter escalation | `app/agents/<parent>/sub_agents/*.py` |
| `LLMGrader` (reflection) | Haiku 4.5 self-evaluation; quality_threshold gates | `app/agents/framework/grader.py` |
| Per-tenant Bedrock Guardrail | PHI redaction policy attached at InvokeModel | `BEDROCK_GUARDRAIL_ID` env per tenant |
| Bedrock Knowledge Base | Optional retrieval backend over ClinCase-curated policy corpus | `app/agents/policy_retriever/sub_agents/keyword_filter.py` (Path A) |
| Provisioned Throughput | 1 MU Sonnet + 1 MU Haiku, OneMonth commitment | `ops/terraform/provisioned-throughput/` |
| AgentCore Runtime (apply-ready) | Per-parent Runtime + Memory + Gateway + Identity | `ops/aws/agentcore/deployment.yaml` |

**Network and access pattern.** Every Bedrock InvokeModel goes through:

1. **GenAI Gateway in-process** (`app/llm/gateway.py`) — per-tenant model allowlist, per-tenant 24h quota, content-safety pre-check, audit log to `llm_invocations`.
2. **AWS PrivateLink VPC endpoint** (`ops/terraform/bedrock-vpc-endpoint/`) — endpoint policy with per-model-id condition; SG locked to EKS node SG only.
3. **IRSA role** `clincase-bedrock-invoke-role` — only the configured `clincase-api` and `clincase-worker` ServiceAccounts can assume; per-model-id IAM condition.
4. **Bedrock Guardrails** — per-tenant PHI policy, applied at the API.
5. **CloudWatch Bedrock model-invocation logging** — 7-year retention for CMS-0057-F § IV.D.

Five enforcement layers; defense in depth from the AWS-published architectural guidance.

### Amazon Q Business — the customer-knowledge copilot

Q Business is the **enterprise-knowledge bridge** for retrieval over the customer's existing M365 / SharePoint / Confluence library. The customer typically already has a Q Business app provisioned; ClinCase flips one env var to use it.

| ClinCase component | Q Business role | Code reference |
|---|---|---|
| `q_business_retriever` sub-agent | Drop-in alternative to `keyword_filter` (Bedrock KB path) | `app/agents/policy_retriever/sub_agents/q_business_retriever.py` |
| Toggle | `USE_AMAZON_Q=true` + `AMAZON_Q_APPLICATION_ID` + `AMAZON_Q_INDEX_ID` | `app/config.py` |
| Demo mock | Deterministic fixture so the demo works offline | `app/integrations/amazon_q/client.py` `_mock_retrieve` |
| Production wire | `qbusiness.retrieve` boto3 call with attribute filter (per `payer_id`) | `app/integrations/amazon_q/client.py` `_real_retrieve` |

**Why Q Business and not just Bedrock KB?** The customer's policy library lives in their existing knowledge stack — Microsoft 365 / SharePoint / Confluence — not in S3. Q Business has first-party connectors for those. Building yet another vector index is a procurement non-starter; Q Business plugs into what's already there.

This pattern follows the publicly-documented Availity case study ([AWS case study](https://aws.amazon.com/solutions/case-studies/availity-q-case-study/)) — Q + Bedrock is the proven combination for healthcare payer ops in 2025–2026.

### Amazon Q Developer — deferred (intentional)

Amazon Q Developer is the **AI-assisted IDE** for engineers writing ClinCase itself.

**Status:** new Q Developer signups blocked after May 15, 2026; teams who already have Q Pro retain access through Apr 30, 2027 ([AWS EOS notice](https://aws.amazon.com/blogs/devops/amazon-q-developer-end-of-support-announcement/)).

**ClinCase's posture:** we use **Kiro IDE** instead — AWS's spec-driven agentic IDE that's the strategic successor. Spec-format detail in `.kiro/specs/` and Hooks documented in `ops/kiro/HOOKS.md`. Q Developer would be redundant; Kiro is the AWS-blessed forward path.

---

## Decision matrix — when adding a new feature

| Need | First choice | Why |
|---|---|---|
| Reason over PHI-bearing FHIR + payer policy → structured output | **Bedrock** (Sonnet via Gateway) | Foundation-model platform; per-tenant Guardrails; provisioned-throughput-pinned; in our `Agent[I, O]` lifecycle. |
| Retrieve from a customer's knowledge corpus already in M365/SharePoint/Confluence | **Q Business** | First-party connectors; no new vector index; matches Availity reference. |
| Retrieve from a corpus we curate ourselves (ClinCase-owned policy PDFs) | **Bedrock KB** | Tighter integration with our agent lifecycle; managed by us. |
| Cross-document Q&A surface for a clinical reviewer | **Q Business** with the customer's connectors | Built for that exact pattern; reviewer sees a chat over their corpus. |
| Anything mutating clinical data | **Neither autonomously** | HITL gate routes to qualified clinician (CA SB 1120). The LLM is decision-support; the human signs. |
| Code generation / refactoring for ClinCase engineering | **Kiro IDE** (not Q Developer) | AWS's strategic IDE for agentic-spec workflows; future-proof past May 15, 2026. |

---

## Cross-ClinCase view — at a glance

```
                         ┌──────────────────┐
                         │  CUSTOMER's KM   │      ← M365 / SharePoint / Confluence
                         └────────┬─────────┘
                                  │
                                  ▼
                         ┌──────────────────┐
                         │  AMAZON Q BUSINESS │      ← retrieval (Path B; USE_AMAZON_Q=true)
                         │  (customer's app)  │
                         └────────┬─────────┘
                                  │
                                  ▼
   ┌─────────────────────────────────────────────────────────────────┐
   │             policy_retriever orchestrator                       │
   │   (chooses keyword_filter vs q_business_retriever per env)      │
   └─────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
                         ┌──────────────────┐
                         │  ClinCase 7-agent │      ← reasoning
                         │   LangGraph DAG  │
                         └────────┬─────────┘
                                  │ every LLM call
                                  ▼
   ┌─────────────────────────────────────────────────────────────────┐
   │       app/llm/gateway.py — GenAI Gateway (in-process)            │
   │  authz scope · model allowlist · 24h quota · content safety ·    │
   │  audit row → llm_invocations                                     │
   └─────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
                         ┌──────────────────┐
                         │ Bedrock VPC      │      ← AWS PrivateLink
                         │  endpoint policy │
                         └────────┬─────────┘
                                  │
                                  ▼
                         ┌──────────────────┐
                         │  AMAZON BEDROCK  │      ← reasoning
                         │  Sonnet 4.6      │
                         │  Haiku 4.5       │
                         │  Guardrails      │
                         │  KB (Path A)     │
                         └──────────────────┘
```

**Two services, two distinct jobs, one decision lifecycle.**

---

## Sources

- [Amazon Q vs Amazon Bedrock — CloudThat 2025](https://www.cloudthat.com/resources/blog/amazon-q-vs-amazon-bedrock-choosing-the-right-ai-solution-for-your-enterprise/)
- [Avasant — AWS GenAI: Q, Nova, Bedrock 2026](https://avasant.com/report/aws-charts-a-bold-path-in-generative-ai-with-amazon-q-nova-models-and-bedrock-innovations/)
- [Availity case study — Q + Bedrock for healthcare](https://aws.amazon.com/solutions/case-studies/availity-q-case-study/)
- [AWS Architecture blog — Bedrock category (governed access patterns)](https://aws.amazon.com/blogs/architecture/category/artificial-intelligence/amazon-machine-learning/amazon-bedrock/)
- [Q Developer EOS notice](https://aws.amazon.com/blogs/devops/amazon-q-developer-end-of-support-announcement/)
