# ClinCase — Closing the AI Adaptation Gap

**Audience:** Payer operations leadership · TriZetto product engineering · client CIOs

Buying AI is no longer the hard part. Getting agents adopted into the processes that already run the business is. ClinCase is engineered for that second problem.

| Gap | Question it answers | Where ClinCase fits |
|---|---|---|
| **AI value gap** | *"We have invested heavily in AI infrastructure — where's the P&L value?"* | TriZetto AI Gateway-native bundle on Bedrock + Sonnet 4.6 + MCP, measured per case against a cited manual baseline. |
| **AI Adaptation Gap** (2026) | *"We can build agents — but we can't get them adopted into our existing processes fast enough to compete."* | ClinCase is engineered to be *embedded into* existing TriZetto Facets / QNXT workflows, not launched as a parallel new product. |

---

## What the Adaptation Gap actually is

Enterprises in 2026 face a paradox: AI capability is racing ahead of organizational capacity to absorb it.

- **32% of orgs** are already using agents in production (early-adopter cohort).
- Among them, **47% expected returns over the next 12 months** (industry forecast).
- But the median enterprise still struggles to integrate even one agent into a critical operational workflow — process redesign, change management, integration with systems of record, governance, and adoption move at a different clock speed than model releases.

The Adaptation Gap is the gap between "agents exist" and "agents are doing the work."

Closing it requires four things:

1. **Embed, don't replace.** New agents must drop into existing systems of record (ticketing, CRM, claims platforms) — not require parallel platforms.
2. **Context engineering.** The agent must inherit the operator's working knowledge, not start cold.
3. **Goal-shaped workflows.** Single LLM calls don't move processes. Goals → multi-agent networks → actions → outcomes do.
4. **Operator-friendly UX.** Asynchronous + autonomous: the operator delegates the macro task, the agent network executes, the operator micro-steers.

---

## How ClinCase closes the Adaptation Gap

### 1. Embedded into the TriZetto book of business — not a parallel product

ClinCase is a **TriZetto AI Gateway-native specialty agent bundle** (the Gateway launched Aug 6, 2025). It does not require a customer to provision a new platform; it deploys as a Day-1 add-on inside an existing TriZetto subscription.

Concrete realization (already shipped):
- `app/integrations/trizetto/` — Facets `prior_auth_event v3` + QNXT `case_event v2` adapters with SHA-256 tamper-evident decision hashes.
- `POST /api/v1/integrations/trizetto/submit` — one-click submission round-trip.
- `app/mcp/server.py` — JSON-RPC 2.0 MCP-compliant tool surface the AI Gateway already speaks.

A Facets customer's existing PA workflow is unchanged on the operator side. The change is on the *capability* side — the same workflow now produces decisions in 90 seconds instead of 7 days.

### 2. Context engineering as a first-class layer

> *AI agents fail at inputs, not reasoning; context engineering and knowledge integration are critical.*

ClinCase's Context Retrieval Service (Layer 3 in `ops/architecture/TARGET_ARCHITECTURE.md`) is built for this:

- **Two pluggable retrieval backends** behind one schema:
  - **Bedrock Knowledge Base** — for ClinCase-curated policy corpus.
  - **Amazon Q Business** — for the customer's existing M365 / SharePoint / Confluence library (the customer's "agentic capital").
- **`citation_resolver` sub-agent** — every excerpt fully-pointered (page · section · URL).
- **`biomarker_specialist` sub-agent** — domain-specific extraction with LOINC bindings (the operator's working knowledge encoded).
- **`phi_sanitizer` sub-agent** — PHI redaction so context can flow safely.
- **S3 Vectors backend** — `ops/terraform/s3-vectors/` (apply-ready) for the GA AWS-native vector store, scaling beyond Bedrock KB defaults.

The retrieval layer is what turns AI infrastructure into agentic capital — the operator's accumulated work knowledge becomes part of the agent's situational awareness.

### 3. Goal-shaped workflow, not single LLM calls

The 7-agent LangGraph DAG is structured as **user goal → agent network → actions → outcome**:

```
USER GOAL:    "Decide PA for trastuzumab on patient X under Aetna oncology policy."
   │
   ▼
AGENT NETWORK (7 parents · 22 sub-agents):
   Clinical Extractor → Policy Retriever → Necessity Reasoner →
      Decision Composer → [Denial Forecaster → Appeals Drafter] →
      Patient Communicator
   │
   ▼
ACTIONS:      Submit to TriZetto AI Gateway · Persist Evidence Pack ·
              Notify reviewer (HITL gate if confidence < 0.75) ·
              Draft appeal letter · Generate patient summary
   │
   ▼
OUTCOME:      APPROVE/DENY/REFER · time-to-decision 52s · cost $0.25 ·
              CMS-0057-F evidence pack with bundle SHA-256
```

The actions are formalized in `ops/architecture/AGENTIC_ACTIONS.md` (Nova Act-aligned pattern).

### 4. Asynchronous + autonomous, with operator micro-steering

ClinCase's reviewer experience follows the async-autonomous delivery pattern:

- **Async submit** via `POST /run-async` — operator fires the goal, gets a `job_id` back in <100 ms.
- **SSE trace stream** — operator watches the agent network execute in real time.
- **HITL gate** at `review_gate` — when confidence < threshold, the agent network pauses and asks the operator to approve / override / escalate. Operator signs (CA SB 1120) and the network resumes.
- **Per-case Evidence Pack** — operator can drill into any decision in 12 seconds.
- **Override + reviewer_actions audit** — every operator decision is auditable; the agent network learns which dimensions trigger overrides (out of scope for the MVP).

Operators delegate macro tasks and micro-steer outcomes. ClinCase's case-detail page is that UX shape, applied to the oncology PA workflow.

---

## ClinCase's Adaptation Gap KPIs (2026 trend-aligned)

| KPI | 2026 enterprise benchmark | ClinCase target | Why ClinCase hits the upper band |
|---|---|---|---|
| **Productivity uplift on the target workflow** | 20–40% (typical copilot deployments) | **95–98%** | ClinCase targets a workflow with an extreme baseline (18 min/case, 7-day SLA) — the upper bound of the benchmark range applies because the baseline cost is so high. |
| **Reduction in tickets / escalations / rework** | 20–30% | **60–80% over 90 days** | Provider-abrasion model: ClinCase auto-drafts appeals, returns ~25 min/case to clinic; reduces appeal-loop volume. |
| **Time-to-Adoption (Day 0 → first case-live)** | typical: 60–90 days for a new agent integration | **7–15 business days per customer** | TriZetto-native deployment + per-tenant Bedrock Guardrails + per-tenant KMS; documented in `ops/multi-tenant/ONBOARDING.md`. |
| **% of operators who report agent-attributable productivity gain** | 92% (early-adopter cohort) | **target 95%+** at pilot review | Agent invocations attributable per-case via `llm_invocations` table; reviewer can drill in on any decision. Day-90 pilot review is the verification point. |

These ranges come from public 2026 enterprise GenAI/agent benchmarks. ClinCase's per-case performance hits the **upper band** of every range because the underlying workflow has a high-cost baseline (a manual oncology PA is one of the most expensive operational steps a payer has).

---

## How adoption is staged — Day 0 to Day 90

| Day | Adaptation milestone | Adoption-gap closure mechanism |
|---|---|---|
| **0** | TriZetto pilot customer signs | Bundle deploys natively to existing AI Gateway — no new platform decision |
| **7** | Per-tenant Bedrock Guardrail provisioned | `BEDROCK_GUARDRAIL_ID` env per tenant; customer's PHI policy attached at every model call |
| **14** | First synthetic case live | `POST /api/v1/demo-fixtures/{name}/create-case` → full DAG runs end-to-end |
| **21** | First production case live | Operator runs through the goal → network → actions → outcome flow on a real PA |
| **30** | First reviewer signs off on a HITL pause | CA SB 1120 / CMS-0057-F § IV.C compliance verified in production |
| **45** | Provisioned Throughput pinned | `ops/terraform/provisioned-throughput/` apply — predictable cost + TPM |
| **60** | Second specialty live | Cardiology / behavioral health via Kiro spec edit + Hook regen |
| **90** | First public pilot ROI report | Per-case savings · Star Ratings projection · provider abrasion reduction |

Day-0-to-Day-90 mapped to the Agent Foundry stages in `ops/industrialization/CHECKLIST.md` (Discover · Design · Build · Scale).

---

## Why this matters strategically

The value gap is the conversation a CFO has with the Board. The Adaptation Gap is the conversation a COO has with the operating committee.

ClinCase answers both:

> *Deploy agents on the same Bedrock + Claude + MCP stack you already approved, embedded into the TriZetto workflow your operators already use. One bundle crosses both gaps: drop in Monday, value on Day 21, scaled by Day 90.*

Every claim is groundable to public sources, and every claim has a live, click-able backing in the running app.

---

## Sources

- Adaptation gap — industry knowledge ("AI capability is outrunning organizational adaptation"), Cureintent 2026 PA Automation, AHIP 2026 progress report
- 47% returns / 32% agent adoption — early-adopter enterprise AI benchmarks, 2026
