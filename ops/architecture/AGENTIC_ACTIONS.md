# ClinCase — Agentic Actions ("user goal → agent network → actions → outcome")

**The 2026 multi-agent shape, applied to oncology PA.**

> *"Enterprises are moving from single copilots to multi-agent ecosystems orchestrated around goals and workflows."*
> — 2026 trend, sourced in `ops/architecture/AI_ADAPTATION_GAP.md`

This document formalizes ClinCase's existing 7-agent DAG as the canonical
*goal → agent network → actions → outcome* pattern, aligned with **AWS Bedrock
AgentCore + Nova Act-style agentic workloads** (the AWS-published primitive
for UI automation + policy-enforced actions).

---

## The four phases

```
┌──────────────┐  ┌────────────────────────────┐  ┌─────────────────┐  ┌──────────────┐
│  USER GOAL   │→ │      AGENT NETWORK         │→ │     ACTIONS     │→ │   OUTCOME    │
│              │  │   (7 parents · 22 subs)    │  │  (typed,        │  │ (auditable,  │
│ Issued by    │  │   under the GenAI Gateway  │  │   policy-gated, │  │  measurable, │
│ a coordinator│  │   under the BudgetTracker  │  │   reversible)   │  │  reproducible)│
│ via /run-async│ │   under the review_gate    │  │                 │  │              │
└──────────────┘  └────────────────────────────┘  └─────────────────┘  └──────────────┘
```

---

## Phase 1 — User goal

A coordinator submits the goal:

```http
POST /api/v1/cases/{case_id}/run-async
Idempotency-Key: <sha256-of-payload>
Authorization: Bearer <jwt>
```

Goal shape (declarative):
- **What**: decide PA for a specific (member, drug, payer)
- **Why**: clinical request from physician
- **By when**: implicit CMS-0057-F § IV.B.1 standard 7-day SLA (ClinCase p95 90s)
- **Success criteria**: APPROVE/DENY/REFER with cited rationale, persisted decision row, TriZetto-Gateway-acceptable envelope

The coordinator does NOT specify *how*. That's the agent network's job.

---

## Phase 2 — Agent network

The 7-parent LangGraph DAG, with conditional edges for HITL routing and DENY-path:

```
clinical_extractor (Sonnet · 3 sub-agents: phi_sanitizer, fhir_resource_validator, biomarker_specialist)
       │
       ▼
policy_retriever (orchestrator · 4 sub-agents: keyword_filter / q_business_retriever, llm_reranker, citation_resolver)
       │
       ▼
necessity_reasoner (Sonnet · 3 sub-agents: criterion_splitter, evidence_matcher [reflection], confidence_calibrator)
       │
       ▼
   confidence < 0.75 ──→ review_gate (HITL)
       │ (else)
       ▼
decision_composer (Sonnet · 3 sub-agents: verdict_synthesizer, rationale_writer, citation_linker)
       │
       ▼
denial_forecaster (gated to DENY · 3 sub-agents: probability_estimator, reason_predictor, appeal_path_recommender)
       │ (DENY only)
       ▼
appeals_drafter (Sonnet · 3 sub-agents: nccn_reference_specialist, counter_evidence_finder [reflection], letter_composer [reflection])
       │
       ▼
patient_communicator (Sonnet · 3 sub-agents: empathy_layer, action_step_writer, reading_level_tuner)
```

**Three architectural properties enterprise reviewers look for:**

1. **Goal-shaped, not call-shaped.** The network executes a goal end-to-end; the coordinator never sees an LLM prompt.
2. **Per-agent fault isolation.** A schema regression in `appeals_drafter` doesn't poison `clinical_extractor`'s output.
3. **Operator override at every junction.** HITL gate at confidence < 0.75; reviewer can resume with override; reviewer_actions audit trail.

---

## Phase 3 — Actions (the Nova-Act-aligned formal layer)

Actions are the *side-effecting* steps the network takes once reasoning is done. They are:

- **Typed** — every action has a Pydantic input + output contract.
- **Policy-gated** — every action is filtered by tenant policy (model allowlist + Bedrock Guardrail + per-tenant quota in the GenAI Gateway).
- **Auditable** — every action emits a row to `agent_runs` (read by Evidence Pack) and, for LLM-touching actions, to `llm_invocations`.
- **Reversible where possible** — Decision rows are append-only; corrections create a new row. TriZetto submissions emit a tamper-evident SHA-256 hash so a withdrawal can be cryptographically scoped.

### The 5 ClinCase actions

| # | Action | Trigger | Implementation | Reversible? |
|---|---|---|---|---|
| **A1** | `persist_decision` | All paths | `INSERT INTO decisions ...` from `decision_composer` output | append-only; new decision row supersedes |
| **A2** | `route_to_review` | confidence < HITL_CONFIDENCE_THRESHOLD | LangGraph `review_gate` node + `cases.status='awaiting_review'` | yes — `POST /cases/{id}/resume` |
| **A3** | `submit_to_trizetto_gateway` | After persist_decision | `POST /api/v1/integrations/trizetto/submit` builds `prior_auth_event v3` + `qnxt_case_event v2`; SHA-256 over (verdict, rationale, citations, model_id) | partial — emit a "withdrawal" event referencing the prior hash |
| **A4** | `draft_appeal` | DENY-path only | `appeals_drafter` orchestrator → `appeal_body` + `structured_arguments` → `INSERT INTO appeals` | append-only |
| **A5** | `notify_patient` | All paths (`patient_communicator`) | Grade-8 reading-level summary; (future) email/SMS dispatch through customer's existing notification channel | one-shot; can be resent |

These are the actions — explicit, finite, governed. Not "the agent can do anything"; not "we hope it stays in scope."

### Why this matches the AWS Nova Act / AgentCore pattern

AWS Bedrock AgentCore (GA Oct 2025) ships **Action Groups** — typed action surfaces a foundation model can invoke. Nova Act extends this to UI automation. The ClinCase actions above are AgentCore-Action-Group-shaped:

- Each action has an **input schema** (Pydantic) and **output schema** (Pydantic).
- Each action's invocation is **logged** at the GenAI Gateway layer.
- Each action is **gated by policy** — TriZetto submission requires a persisted decision; appeal drafting requires a DENY verdict; HITL routing requires confidence below threshold.

When we port to AgentCore Runtime (`ops/aws/agentcore/deployment.yaml`), these actions become formal AgentCore Action Groups. The interface stays the same.

---

## Phase 4 — Outcome

The outcome is **auditable, measurable, reproducible**:

| Dimension | Where it shows up |
|---|---|
| **Auditable** | Evidence Pack endpoint (`GET /api/v1/cases/{id}/evidence-pack`) — single JSON bundle with bundle-SHA-256 over case + decision + agent_runs + reviewer_actions + compliance + ROI + TriZetto envelope |
| **Measurable** | `GET /api/v1/business-value/case/{id}` — per-case ROI · `GET /compliance/case/{id}` — per-case CMS-0057-F scorecard · `/llm-gateway/usage` — per-tenant LLM cost rolling 24h |
| **Reproducible** | `agent_runs` rows persisted (CMS-0057-F § IV.D 7-year retention) · Bedrock model invocation logging mirrors to CloudWatch (`ops/terraform/bedrock-vpc-endpoint/logs.tf`) |

---

## How this matches the 2026 agentic delivery pattern

The emerging enterprise pattern:

> *Operators delegate macro tasks to agent networks and "micro-steer" the outcomes.*

| Pattern verb | ClinCase's mechanism |
|---|---|
| *delegate* | `POST /run-async` → `case_jobs` queue → worker picks up |
| *macro tasks* | "Decide PA for trastuzumab on patient X" — one user-comprehensible goal |
| *agent networks* | 7-parent / 22-sub-agent LangGraph DAG with conditional routing |
| *micro-steer* | HITL `review_gate` + reviewer override + Evidence Pack drill-in |
| *async-autonomous* | Async submit + SSE trace + reviewer queue + audit trail — the UX shape used in agentic software engineering, applied to clinical ops |

That alignment is intentional: ClinCase's UX translates the async-autonomous engineering pattern into healthcare prior-auth ops.

---

## What this is NOT

- This is **not generic chat over PHI**. It's a finite agent network with bounded actions.
- This is **not autonomous denial**. Adverse determinations route through `review_gate`; a clinician signs (CA SB 1120).
- This is **not multi-modal UI automation**. We don't drive a browser; we publish typed events to TriZetto's well-known APIs.
- This is **not replacement of the operator**. Operators delegate the macro task and micro-steer outcomes.

---

## Sources

- AWS Bedrock AgentCore — GA Oct 2025 ([whatsnew](https://aws.amazon.com/about-aws/whats-new/2025/10/amazon-bedrock-agentcore-available/))
- Multi-agent goal→network→actions→outcome pattern — 2026 industry trend
- HITL + SB 1120 — [Sheppard Mullin](https://www.sheppardhealthlaw.com/2024/11/articles/state-legislation/california-limits-health-plan-use-of-ai-in-utilization-management/)
