# ClinCase — Master Proposal & Engineering Specification

**Team:** AeroFyta
**Product:** ClinCase
**Program:** National-level engineering innovation challenge, India, 2026
**Domain:** Healthcare
**Theme:** Prior Authorisation Automation
**Wedge:** Oncology prior authorisation + auto-drafted appeals
**Document version:** v1.0
**Document purpose:** Single source of truth for Team AeroFyta and for every Claude Code session. The April 12 Superset form submission, the April 23 Agent Builder Challenge, the May 6 Pune MVP build, the pitch deck, the demo script, and every line of code derive from this file. If anything contradicts this file, this file wins. If something needs to change, change it here first and bump the version in Section 28.

---

## TABLE OF CONTENTS

**PART A — STRATEGY (the Why / How / What)**
1. Elevator pitch
2. WHY — Problem, scope, stakeholders
3. HOW — Solution overview, technical details, innovation, market potential
4. WHAT — Value proposition with quantified targets
5. Locked facts and statistics (single source of truth)
6. Glossary

**PART B — ARCHITECTURE**
7. The 7-agent system overview (with 21 sub-agents)
8. LangGraph orchestration and state schema
9. Per-agent specifications (contracts, prompts, tools, tests)
10. Data models (Pydantic / TypeScript)
11. Database schema (PostgreSQL DDL)
12. REST API contract (FastAPI)
13. Frontend architecture (React component tree)
14. Observability, audit logging, and the reasoning-trace stream

**PART C — IMPLEMENTATION**
15. Repository structure (monorepo layout)
16. Dependencies (exact versions)
17. Local development setup
18. Docker, Docker Compose, and AWS deployment
19. Environment variables and secrets
20. Testing strategy
21. Sample data, seed scripts, and demo fixtures
22. Error handling, retry, and graceful degradation

**PART D — EXECUTION**
23. CLAUDE.md conventions for Claude Code sessions
24. 23-day prep plan (April 13 → May 5)
25. Pitch script (5 minutes for May 7)
26. Demo script (3 minutes, second-by-second)
27. Risk register
28. Change log

---

# PART A — STRATEGY

## 1. Elevator pitch (memorize this)

In March 2024, a stage-3 breast cancer patient in the United States waited 27 days for her insurer to approve the chemotherapy her oncologist had already prescribed. The drug was eventually approved on appeal. She started treatment six weeks late.

**ClinCase is an agentic AI system that would have approved her on Day 1 — and if denied, would have filed her appeal in four minutes instead of four weeks.** It is a provider-side prior authorisation copilot for oncology that ingests clinical documentation, retrieves the relevant payer medical policy, reasons about medical necessity against that policy, produces an explainable approve/deny/refer decision with a full citation chain, and — when a payer denies — automatically drafts an evidence-grounded appeal letter using the same clinical record the denial ignored.

It is built as five named LangGraph agents on a recommended AWS stack, and is designed for the regulatory tailwind that goes federal in months: CMS-0057-F operational provisions begin January 1, 2026, and the Prior Authorization API requirements go live January 1, 2027.

---

## 2. WHY — Problem, scope, stakeholders

### 2.1 Problem description and business scenario (full)

Prior authorisation (PA) is the process by which a healthcare provider must obtain approval from a patient's insurer before delivering a treatment, medication, or procedure. It exists to control cost and enforce clinical guidelines, but in practice it has become the single most-cited administrative pain point in modern healthcare.

The American Medical Association's 2024 prior authorisation survey reports that **94% of physicians say prior authorisation delays patient care**, **24% report that prior authorisation has led to a serious adverse event for a patient in their care**, and physicians handle approximately **39 prior authorisation requests per week** per practice. The Kaiser Family Foundation's 2024 Medicare Advantage analysis found that **80.7% of appealed prior authorisation denials were partially or fully overturned** in 2024 — yet only a small fraction of denials are ever appealed, because the appeals process is so manually burdensome that most providers simply give up.

This creates a documented, quantifiable harm pattern: insurers issue denials that would not survive review four out of five times, and the only thing standing between a patient and their care is whether a human being has the time to file an appeal. In oncology, where treatment delays of even two weeks can change survival outcomes, this is not an administrative inconvenience — it is a patient-safety failure with a paper trail.

The regulatory environment is also moving. The CMS Interoperability and Prior Authorization Final Rule (CMS-0057-F) mandates that impacted payers (Medicare Advantage organisations, state Medicaid and CHIP agencies, and QHP issuers on the Federally-Facilitated Exchanges) implement specific operational and process requirements beginning **January 1, 2026**, and implement the Prior Authorization API (along with other API requirements) beginning **January 1, 2027**. Every impacted payer in the United States must comply. The technical infrastructure to do this at scale does not yet exist for most providers, creating a multi-billion-dollar greenfield opportunity for FHIR-native, AI-powered prior authorisation tooling.

The health sciences IT services market is large and active, with established client relationships across US payers and providers. This is not a hypothetical market — it is a market enterprise health IT vendors already sell into, where the buying decision is being forced by federal rule, and where no incumbent has yet shipped a satisfactory agentic solution.

### 2.2 Problem scope

ClinCase focuses on **provider-side prior authorisation for oncology**, with built-in **automated appeals drafting** for denied requests. We deliberately do *not* build a payer-side denial engine — that would be ethically and commercially misaligned. We deliberately do *not* attempt to cover every specialty in version one — oncology gives us the highest-stakes, highest-emotional-impact, and most-evidence-rich use case, and the lessons generalise to other specialties in subsequent versions.

We assume FHIR R4 clinical data inputs (Synthea-generated synthetic patient records for the demo), public payer medical policy PDFs as the policy corpus (Aetna, Anthem, BCBS, and UnitedHealthcare publish these openly), and a human-in-the-loop reviewer console for any decision the system flags as low-confidence or high-risk.

### 2.3 Target users and stakeholders

- **Primary users:** Oncology practice administrators, prior authorisation coordinators, and revenue-cycle teams at provider organisations. These are the people who today spend hours per case manually compiling PA packets and writing appeal letters.
- **Beneficiaries:** Oncology patients, who experience faster time-to-treatment and a higher rate of appeal success on denied requests.
- **Buying stakeholders:** Provider CFOs, CMIOs, and revenue-cycle directors, who measure success in PA approval rate, time-to-decision, denial-overturn rate, and FTE hours saved per case.
- **Regulatory stakeholder:** CMS, whose 2026/2027 rule effectively mandates the kind of FHIR-native, programmatic prior authorisation infrastructure ClinCase is built around.
- **Enterprise health IT channel:** ClinCase is built to be the kind of system a systems integrator could put in front of an existing client on Monday morning.

### 2.4 Compressed Why (~600 chars, for Superset form)

> Prior authorisation delays cancer treatment for millions of patients each year. The AMA's 2024 survey reports 94% of physicians say PA delays care and 24% report a serious adverse event from PA. KFF reports 80.7% of *appealed* Medicare Advantage denials are overturned — yet most are never appealed because the manual workload is crushing. The CMS Interoperability and Prior Authorization Final Rule (CMS-0057-F) mandates electronic PA infrastructure with operational provisions from Jan 1, 2026 and Prior Authorization API requirements from Jan 1, 2027. Every impacted US payer must comply, and enterprise health IT vendors sell into this market today.

---

## 3. HOW — Solution, technical details, innovation, market potential

### 3.1 Solution overview (full)

**ClinCase is a provider-side, agentic prior authorisation copilot for oncology.** A practice administrator uploads (or, in production, FHIR-streams) a patient's clinical record and the requested treatment. ClinCase's five agents then work in sequence and in parallel:

1. **Clinical Extractor Agent** parses the FHIR bundle and any unstructured physician notes to extract the structured clinical facts that matter for PA: diagnosis with ICD-10 codes, staging, prior therapies, biomarkers, comorbidities, performance status, and the specific treatment being requested with HCPCS/J-codes.
2. **Policy Retriever Agent** runs a RAG retrieval over an indexed corpus of payer medical policies (the demo ships with 4–5 real, publicly-available oncology policies from major US payers) and surfaces the policy sections that govern the requested treatment for the patient's specific diagnosis and stage.
3. **Necessity Reasoner Agent** matches the extracted clinical evidence against the retrieved policy criteria, line by line, and produces a structured assessment: which criteria are met, which are not met, which are ambiguous, and what additional documentation would resolve each ambiguity.
4. **Decision Composer Agent** consumes the necessity assessment and produces one of three outputs — APPROVE, DENY, or REFER (low confidence, escalate to human reviewer) — with a full citation chain back to the specific clinical evidence and the specific policy section supporting each conclusion.
5. **Appeals Drafter Agent** activates whenever a real or simulated payer denial is received. It re-reads the denial language, identifies the specific policy criteria the denial cites, finds the clinical evidence in the patient record that contradicts the denial's reasoning, and drafts a complete appeal letter with structured argumentation and inline citations to both the clinical record and the medical literature.

A **human-in-the-loop reviewer console** lets a PA coordinator see every agent's reasoning trace in real time, approve or override the system's decision, and contribute corrections that flow back as feedback. An **audit trail** logs every agent input, output, tool call, and decision to a structured store, producing a compliance view that can be reproduced and defended in any payer dispute.

### 3.2 Technical details (full stack)

- **Languages:** Python 3.11 (backend, agents), TypeScript 5.x (frontend)
- **Backend framework:** FastAPI 0.115+, Uvicorn, async-by-default
- **Frontend framework:** React 18 + Vite, TanStack Query for data fetching, Tailwind CSS for styling
- **Database:** PostgreSQL 16 with the `pgvector` extension for the policy RAG index (no separate vector DB)
- **AI / ML:** LangChain 0.3+, LangGraph 0.2+, Anthropic Claude (via Anthropic API or AWS Bedrock as fallback), `sentence-transformers` for embeddings, `pypdf` for policy ingestion
- **FHIR handling:** `fhir.resources` Python library for typed FHIR R4 parsing
- **Containerisation:** Docker + Docker Compose for local; ECS Fargate or App Runner for AWS
- **Streaming:** Server-Sent Events (SSE) from FastAPI for the live reasoning-trace UI
- **Testing:** `pytest`, `pytest-asyncio`, `httpx` for API tests, `vitest` for frontend
- **Observability:** Structured JSON logging via `structlog`, every agent call recorded to the `agent_runs` table with inputs/outputs/tool calls/latency

### 3.3 Innovation

ClinCase is innovative on three axes that, together, no existing product combines:

1. **Genuine multi-agent decomposition, not a single LLM call dressed as agents.** Each of the five agents has a defined contract, a specific toolset, a single-axis quality metric, and a contract test. The LangGraph DAG is observable, replayable, and audit-logged.
2. **Appeals as a first-class workflow, not an afterthought.** Most PA tools focus only on the initial submission. ClinCase treats the appeal as an equally important agent path, because the KFF data shows that's where the highest-leverage patient outcomes hide.
3. **A streaming reasoning-trace UI that turns the agents' thinking into visible, citable, defensible artefacts.** Every conclusion the system reaches is traceable back to a specific piece of clinical evidence and a specific policy clause. This is what makes the system "audit-ready" in a way that black-box ML PA tools are not — and it's what makes it sellable into a regulated environment where every denial can become a legal dispute.

### 3.4 Market potential

The US prior authorisation automation market sits inside a broader healthcare administrative-spend problem estimated at over **$30 billion per year** in waste attributable to PA-related administrative friction. The CMS-0057-F rule creates a federally-mandated buying cycle: every impacted payer must implement operational provisions starting January 1, 2026 and the Prior Authorization API starting January 1, 2027. Provider-side tooling that can speak to those APIs and automate the provider half of the workflow is the natural counterpart to the payer-side mandate.

The health sciences segment includes deep, existing relationships with both payer and provider clients across the US.

### 3.5 Compressed How (~800 chars, for Superset form)

> ClinCase is a provider-side, agentic prior authorisation copilot for oncology, built as a LangGraph DAG of five named agents: Clinical Extractor (parses FHIR + physician notes), Policy Retriever (RAG over real payer medical policies), Necessity Reasoner (matches evidence to policy criteria line-by-line), Decision Composer (produces APPROVE/DENY/REFER with full citation chain), and Appeals Drafter (auto-drafts evidence-grounded appeal letters on denial). Built on Python/FastAPI/React/PostgreSQL with pgvector, deployed on AWS, using LangChain + LangGraph + Anthropic Claude. Synthea-generated FHIR data and publicly-available payer policies make the demo real, not toy. A streaming reasoning-trace UI and a structured audit log make every decision reproducible and defensible. The appeals workflow is the differentiator — KFF reports 80.7% of appealed Medicare Advantage denials are overturned, yet most denials are never appealed.

---

## 4. WHAT — Value proposition

### 4.1 Quantified targets

**For oncology patients:**
- Time-to-decision on straightforward PA requests: **from days to under 5 minutes**
- Time to draft an appeal letter on a denied case: **from 2–4 hours to under 5 minutes**
- Survival-relevant treatment delay on appealed cases: **collapsed from weeks to a single day**

**For oncology practices:**
- PA coordinator FTE hours saved per case: **70–85% on straightforward cases**
- Appeal-success rate uplift on denied cases: **target 60%+**, anchored on KFF's 80.7% baseline
- Documentation completeness at first submission: **+40%** (because the Necessity Reasoner flags missing evidence pre-submission)

**For provider CFOs:**
- Direct labour-cost savings on PA workflow
- Direct revenue capture on previously-abandoned denials
- Reduced patient leakage to competing providers due to PA friction

**For payers:**
- Lower volume of low-quality submissions
- Faster turnaround on the requests that do come through
- Defensible audit trail for every decision

**For enterprise health IT vendors:**
- A production-grade, agentic, FHIR-native PA solution that fits directly into an existing sales motion
- Built on a recommended AI/AWS stack
- Addresses a federally-mandated 2026/2027 buying cycle
- Audit-trail completeness: **100%** — every agent decision is logged with inputs, outputs, tool calls, and citations

### 4.2 Compressed What (~700 chars, for Superset form)

> ClinCase delivers measurable value across every stakeholder. For patients: time-to-treatment in oncology drops from days to minutes on straightforward cases, and appeal cycles drop from weeks to minutes on denied cases — directly improving survival-relevant treatment timelines. For providers: 70–85% reduction in PA coordinator hours per case, dramatically higher appeal-success rate (anchored on KFF's 80.7% overturn-on-appeal baseline), and direct revenue capture from previously-abandoned denials. For payers: cleaner submissions, faster decisions, and a defensible audit trail aligned with CMS-0057-F. For enterprise health IT vendors: a production-grade, FHIR-native, agentic solution built on the recommended stack, ready for the health sciences segment.

---

## 5. Locked facts and statistics (single source of truth)

> Use these exact numbers everywhere — the form, the deck, the demo, Q&A. Do not paraphrase, do not round, do not improvise. If a teammate cites a different number, correct them against this section.

- **CMS Interoperability and Prior Authorization Final Rule (CMS-0057-F):** Operational and process provisions generally begin **January 1, 2026**. Prior Authorization API requirements (and other API requirements) generally due **January 1, 2027**. Applies to Medicare Advantage organisations, state Medicaid and CHIP agencies, and QHP issuers on the Federally-Facilitated Exchanges.
- **AMA 2024 prior authorization survey:** **94%** of physicians report PA delays patient care. **24%** of physicians report PA has led to a serious adverse event for a patient in their care. Physicians handle approximately **39** PAs per week per practice.
- **KFF 2024 Medicare Advantage analysis:** **80.7%** of appealed prior authorisation denials in Medicare Advantage in 2024 were partially or fully overturned. The rate of denials that are appealed at all is small.
- **Program framing:** This is a national-level innovation platform for 2027 engineering graduates across India. Never call it international.
- **Tech stack to name in the submission:** Python, TypeScript, FastAPI, React, PostgreSQL with pgvector, LangChain, LangGraph, Anthropic Claude, AWS, Docker.
- **Heuristics, not facts (do not cite):** pick-rate estimates for other themes, probability-of-top-3 percentages, any speculative claim about competitor teams.

---

## 6. Glossary (non-healthcare teammates ramp in 20 minutes)

- **Prior Authorisation (PA):** The process by which a provider must get approval from an insurer before delivering a treatment. Without it, the insurer will not pay.
- **Payer:** The insurance company. In the US: Aetna, Anthem, BCBS, UnitedHealthcare, Cigna, Humana, Medicare Advantage organisations, Medicaid agencies.
- **Provider:** The doctor, hospital, or clinic delivering care.
- **Medical necessity:** The clinical justification that a treatment is appropriate for a specific patient. Insurers approve PAs when medical necessity is demonstrated against their policy.
- **Medical policy:** A payer-specific document describing the criteria a patient must meet for a treatment to be approved. Real and publicly published.
- **FHIR (Fast Healthcare Interoperability Resources):** The HL7 standard for exchanging clinical data. R4 is the current production version. CMS-0057-F requires FHIR-based APIs.
- **CMS-0057-F:** The CMS Interoperability and Prior Authorization Final Rule. Operational provisions in 2026; API requirements in 2027.
- **ICD-10 / HCPCS / J-codes:** Standard code systems for diagnoses (ICD-10), procedures (HCPCS), and injectable drugs (J-codes).
- **NCCN:** National Comprehensive Cancer Network. Publishes the de facto US oncology treatment guidelines.
- **Adverse event:** A negative patient outcome. "Serious" includes hospitalisation, life-threatening events, disability, and death.
- **Appeal:** The process of contesting a payer's denial. KFF: 80.7% succeed in MA, but most denials are never appealed.
- **Synthea:** Open-source synthetic patient generator. Produces FHIR-shaped data with no real patients.
- **RAG (Retrieval-Augmented Generation):** LLM technique where the model retrieves relevant documents and generates an answer grounded in them.
- **LangGraph:** Library for building stateful, multi-agent LLM workflows as directed graphs.
- **Human-in-the-loop:** Workflow pattern where the AI proposes and a human approves, especially for high-risk or low-confidence decisions.
- **HITL Reviewer Console:** ClinCase's UI for human reviewers to see agent reasoning, approve/override, and submit corrections.

---

# PART B — ARCHITECTURE

## 7. The 7-agent system overview (with 21 sub-agents)

The ClinCase DAG is composed of **7 parent agents** (orchestrators) and
**21 sub-agents** (3 per parent). All 28 agents — parent and sub —
inherit from a single canonical `Agent[I, O]` base class in
`app/agents/framework/agent.py`. The base class implements the full
production lifecycle (input validation → guardrails → budget reservation →
LLM call or deterministic execution → schema parse → output guardrails →
optional reflection-and-retry → budget commit → hierarchical trace emit),
so subclasses only declare identity, schemas, model, guardrails, and one
hook. **There is no second class of "helpers" — every named agent in this
list is a real Agent[I, O] instance with its own Pydantic input/output
schema, its own prompt (LLM agents) or pure-Python `_execute_deterministic`
(deterministic agents), its own trace event in `agent_runs`, and its own
contract test surface.**

| # | Parent agent          | Sub-agents (kind · model)                                                                                              |
|---|----------------------|------------------------------------------------------------------------------------------------------------------------|
| 1 | Clinical Extractor   | fhir_resource_validator (det) · phi_sanitizer (det) · biomarker_specialist (LLM, Haiku)                                |
| 2 | Policy Retriever     | keyword_filter (det) · llm_reranker (LLM, Sonnet) · citation_resolver (det)                                            |
| 3 | Necessity Reasoner   | criterion_splitter (LLM, Sonnet) · evidence_matcher (LLM, Sonnet · reflection 0.80/3) · confidence_calibrator (LLM, Haiku) |
| 4 | Decision Composer    | verdict_synthesizer (det) · rationale_writer (LLM, Sonnet) · citation_linker (LLM, Haiku)                              |
| 5 | Denial Forecaster    | probability_estimator (LLM, Sonnet) · reason_predictor (LLM, Haiku) · appeal_path_recommender (LLM, Haiku)             |
| 6 | Appeals Drafter      | counter_evidence_finder (LLM, Sonnet · reflection 0.80/3) · nccn_reference_specialist (LLM, Haiku) · letter_composer (LLM, Sonnet · reflection 0.80/3) |
| 7 | Patient Communicator | empathy_layer (LLM, Sonnet) · reading_level_tuner (det) · action_step_writer (LLM, Haiku)                              |

**Counts:** 15 LLM-backed sub-agents (10 Sonnet, 5 Haiku) · 6 deterministic
sub-agents · 3 sub-agents with reflection enabled (LLMGrader-driven self-
correction with `quality_threshold=0.80`, `max_iterations=3`).

The architecture is surfaced via:
  - `GET /api/v1/agents/manifest` — full nested manifest with input/output JSON schemas, model size, guardrails, reflection threshold per agent
  - `GET /api/v1/agents/sub-agents` — flat list for analytics
  - The `/agents` UI page rendering each parent card with its sub-agents inline
  - `backend/app/agents/README.md` — file-tree map and lifecycle invariants
  - Live SQL: `SELECT * FROM agent_runs WHERE case_id = '...' ORDER BY started_at` returns parent + sub-agent rows interleaved (rows named `<parent>` or `<parent>.<sub_name>`)

### The framework's contract — what every Agent satisfies

Every `Agent[I, O]` invocation runs the same lifecycle, in this order, and
emits one `agent_runs` row at completion:

```
1.  validate input schema                       (Pydantic boundary)
2.  run input_guardrails                        (PASS / MASK / BLOCK)
3.  reserve budget                              (raises BudgetExceeded before any LLM call)
4.  act                                         — LLM call OR _execute_deterministic
5.  parse output                                (retry-with-feedback on schema fail; Haiku → Sonnet escalation)
6.  run output_guardrails                       (PASS / RETRY / BLOCK)
7.  reflect                                     (LLMGrader scores; below quality_threshold → retry with feedback)
8.  commit / cancel budget
9.  emit hierarchical AgentTrace span           (parent_span_id chain)
10. persist agent_runs row + SSE event
11. return AgentResult[O] with cost / tokens / retries / grader_score
```

Sub-agents share their parent's `AgentContext` (case_id, organization_id,
budget tracker, tool cache, memory store, trace tree). The
`ctx.child_for(span)` helper forks `parent_span_id` only — everything else
is shared so a single case-level budget bounds the entire fan-out.



```
                         FHIR bundle + treatment request
                                       │
                                       ▼
                         ┌─────────────────────────────┐
                         │  Agent 1: Clinical          │
                         │           Extractor         │
                         └──────────────┬──────────────┘
                                        │ ClinicalSnapshot
                                        ▼
                         ┌─────────────────────────────┐
                         │  Agent 2: Policy            │
                         │           Retriever         │
                         └──────────────┬──────────────┘
                                        │ + PolicyExcerpts[]
                                        ▼
                         ┌─────────────────────────────┐
                         │  Agent 3: Necessity         │
                         │           Reasoner          │
                         └──────────────┬──────────────┘
                                        │ NecessityAssessment
                                        ▼
                         ┌─────────────────────────────┐
                         │  Agent 4: Decision          │
                         │           Composer          │
                         └──────────────┬──────────────┘
                                        │ Decision
                  ┌─────────────────────┼─────────────────────┐
                  ▼                     ▼                     ▼
              APPROVE                 REFER                 DENY
                  │                     │                     │
                  │                     │                     ▼
                  │                     │   ┌─────────────────────────────┐
                  │                     │   │  Agent 5: Appeals           │
                  │                     │   │           Drafter           │
                  │                     │   └──────────────┬──────────────┘
                  │                     │                  │ AppealDraft
                  ▼                     ▼                  ▼
            ─────── HITL Reviewer Console + Audit Log Stream ───────
```

## 7B. Document Intake — pre-DAG layer for real-world inputs

Indian hospital reality is that prior-auth submissions almost never arrive
as clean FHIR R4 bundles. They arrive as:

- Handwritten oncology prescriptions on practice letterhead, often with
  brand names (Herceptin, Remdovac), shorthand doses (6 mg/kg q3w), and
  scribbled signatures.
- Phone-camera photos of pathology slips, echo reports, lab results — often
  skewed, with variable lighting and visible camera glare.
- Faxed payer denial letters with stamped headers and signatures.
- Mixed-format PDFs: typed letterhead + handwritten margins.

The 7-agent DAG above only runs on a typed `ClinicalSnapshot`. The
**Document Intake** layer is a pre-DAG pipeline that converts those messy
inputs into the typed payload the rest of the system expects. It lives at
`app/agents/intake/`. Per AAOSA bounded responsibility, this layer ONLY
produces an `IntakeResult` (classification + OCR + partial snapshot +
audit) — it never reasons about coverage.

### 7B.1 Pipeline

| # | Stage              | Implementation                                                       | LLM tokens?       |
|---|--------------------|----------------------------------------------------------------------|-------------------|
| 1 | Classifier         | `app/agents/intake/classifier.py` (PIL stats; edge density, stroke variance, paper texture) | none — deterministic |
| 2 | Vision Extractor   | Claude Sonnet 4.6 vision via `LLMClient.complete_with_image()` (Bedrock multimodal Converse) | yes — one call    |
| 3 | FHIR Shaper        | embedded in (2) — vision prompt emits the partial ClinicalSnapshot in the same structured-JSON output | none — same call  |

Stage 1 is cheap and deterministic — every upload runs through it before any
LLM is invoked. Its output is fed into stage 2's user prompt as a routing
hint ("this is a handwritten Rx; expect drug name + dose"), which materially
improves the vision model's extraction accuracy on poor-quality inputs.

### 7B.2 Confidence and HITL routing

The vision extractor emits per-field confidence ∈ [0, 1] plus an
`overall_confidence` (the MIN over critical fields). Routing rules:

- `overall_confidence ≥ 0.7` AND no binding field missing → autonomous flow
  into the Clinical Extractor.
- `overall_confidence < 0.7` OR `requested_treatment.name` /
  `primary_diagnosis.description` missing → `requires_human_review = True`
  and the case is dispatched to the Reviewer queue with the
  `low-evidence-from-intake` risk_flag pre-attached.

This preserves the **safety-first** posture the rest of ClinCase stands on —
the model never silently APPROVES on a smudged biomarker.

### 7B.3 CMS-0057-F § IV.A audit anchor

Every uploaded document is hashed (SHA-256) and persisted to
`intake_documents` alongside the IntakeResult. Every downstream
`agent_runs` row that consumes a field traceable to the upload references
the document via `source_resource_id = "intake-doc-{sha8}"`. A scanned-fax
verdict is as auditable as a clean-FHIR verdict — both reconstructible from
the audit ledger alone.

### 7B.4 API surface

```
POST /api/v1/intake/parse-document
       multipart/form-data with `file` field (image/png · image/jpeg ·
       image/webp · application/pdf)
       8 MB cap.
   →   IntakeResult { classification, ocr, clinical_snapshot_partial,
                      risk_flags, requires_human_review, audit }
```

Frontend: the **Drop a scan** route at `/intake` renders the result with
per-field confidence colors (≥ 85% green, 70–85% amber, < 70% rose) and a
"Create case" CTA gated on `requires_human_review = false`.

### 7B.5 Why not AWS Textract?

Textract is excellent for printed text + structured tables (and is a
documented option in the architecture). For the demo, Claude Sonnet 4.6
vision via Bedrock is preferred because:

- One model handles printed AND handwritten content (no router needed)
- Same `LLMClient` abstraction the rest of the system uses
- Per-field confidence scoring is native to the Bedrock JSON output
- Bounded-competency story is cleaner ("vision extractor is one sub-agent")

Textract remains a documented fallback for tenants that need cheaper bulk
OCR on typed-only documents — see `app/integrations/textract/` (planned).

## 8. LangGraph orchestration and state schema

The orchestration is a LangGraph `StateGraph` with named nodes (one per agent) and conditional edges. State is a typed Pydantic model that flows through the graph and accumulates each agent's output.

```python
# backend/app/graph/state.py
from typing import Optional, Literal
from pydantic import BaseModel, Field
from app.models.clinical import ClinicalSnapshot
from app.models.policy import PolicyExcerpt
from app.models.necessity import NecessityAssessment
from app.models.decision import Decision
from app.models.appeal import AppealDraft

class ClinCaseState(BaseModel):
    # Input
    case_id: str
    fhir_bundle: dict
    physician_note: Optional[str] = None
    requested_treatment: dict  # {hcpcs_code, j_code, name, dose, frequency}
    payer_id: str

    # Accumulated agent outputs
    clinical_snapshot: Optional[ClinicalSnapshot] = None
    policy_excerpts: list[PolicyExcerpt] = Field(default_factory=list)
    necessity_assessment: Optional[NecessityAssessment] = None
    decision: Optional[Decision] = None
    appeal_draft: Optional[AppealDraft] = None

    # External denial input (for appeals-only flow)
    external_denial_letter: Optional[str] = None

    # Routing flag
    next_route: Optional[Literal["approve_done", "refer_done", "denial_path"]] = None

    # Trace events for the streaming UI
    trace_events: list[dict] = Field(default_factory=list)
```

```python
# backend/app/graph/build.py
from langgraph.graph import StateGraph, END
from app.graph.state import ClinCaseState
from app.agents import (
    clinical_extractor_node,
    policy_retriever_node,
    necessity_reasoner_node,
    decision_composer_node,
    appeals_drafter_node,
)

def route_after_decision(state: ClinCaseState) -> str:
    if state.decision is None:
        return END
    if state.decision.verdict == "DENY":
        return "appeals_drafter"
    return END

def build_clincase_graph():
    g = StateGraph(ClinCaseState)
    g.add_node("clinical_extractor", clinical_extractor_node)
    g.add_node("policy_retriever", policy_retriever_node)
    g.add_node("necessity_reasoner", necessity_reasoner_node)
    g.add_node("decision_composer", decision_composer_node)
    g.add_node("appeals_drafter", appeals_drafter_node)

    g.set_entry_point("clinical_extractor")
    g.add_edge("clinical_extractor", "policy_retriever")
    g.add_edge("policy_retriever", "necessity_reasoner")
    g.add_edge("necessity_reasoner", "decision_composer")
    g.add_conditional_edges("decision_composer", route_after_decision, {
        "appeals_drafter": "appeals_drafter",
        END: END,
    })
    g.add_edge("appeals_drafter", END)
    return g.compile()
```

## 9. Per-agent specifications

### 9.1 Agent 1 — Clinical Extractor

**Responsibility:** Convert a FHIR bundle (and optional unstructured physician note) into a structured `ClinicalSnapshot`.

**Inputs:** `fhir_bundle: dict`, `physician_note: Optional[str]`, `requested_treatment: dict`

**Output schema:**

```python
# backend/app/models/clinical.py
from pydantic import BaseModel, Field
from typing import Optional

class Diagnosis(BaseModel):
    icd10_code: str
    description: str
    stage: Optional[str] = None  # e.g. "IIIA"
    onset_date: Optional[str] = None
    source_resource_id: str  # FHIR Condition.id

class PriorTherapy(BaseModel):
    therapy_name: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    response: Optional[str] = None  # complete/partial/progression/intolerance
    source_resource_id: Optional[str] = None

class Biomarker(BaseModel):
    name: str  # e.g. "HER2", "ER", "PR", "PD-L1"
    value: str  # e.g. "positive", "negative", "3+", "high"
    test_date: Optional[str] = None
    source_resource_id: Optional[str] = None

class Comorbidity(BaseModel):
    icd10_code: str
    description: str

class RequestedTreatment(BaseModel):
    name: str
    hcpcs_code: Optional[str] = None
    j_code: Optional[str] = None
    dose: Optional[str] = None
    frequency: Optional[str] = None
    intent: Optional[str] = None  # curative/palliative/adjuvant/neoadjuvant

class ClinicalSnapshot(BaseModel):
    patient_age: Optional[int] = None
    patient_sex: Optional[str] = None
    primary_diagnosis: Diagnosis
    additional_diagnoses: list[Diagnosis] = Field(default_factory=list)
    prior_therapies: list[PriorTherapy] = Field(default_factory=list)
    biomarkers: list[Biomarker] = Field(default_factory=list)
    comorbidities: list[Comorbidity] = Field(default_factory=list)
    performance_status: Optional[str] = None  # ECOG 0–4
    requested_treatment: RequestedTreatment
    free_text_summary: str  # 3–5 sentence narrative for the trace UI
```

**System prompt:**

```text
You are the Clinical Extractor agent for ClinCase, a prior authorisation
system for oncology. Your job is to read a FHIR R4 bundle and an optional
physician note and produce a strictly-typed ClinicalSnapshot JSON object.

Rules:
1. Output ONLY a single JSON object matching the ClinicalSnapshot schema.
   No prose, no markdown, no comments.
2. Every field in the snapshot that comes from a FHIR resource MUST include
   the source resource id in source_resource_id.
3. If a field is genuinely unknown, use null. Do not fabricate values.
4. The free_text_summary must be 3–5 sentences and must mention diagnosis,
   stage, key prior therapies, key biomarkers, and the requested treatment.
5. ICD-10 codes, HCPCS codes, and J-codes must be returned exactly as found.
   Do not invent codes.
6. For oncology stage, use AJCC notation (e.g. "IIIA", "IV").
7. For ECOG performance status, use the integer 0–4 as a string.
```

**Tools:** none for the demo (the FHIR bundle is parsed in-process by `fhir.resources` and passed to the LLM as text). In production this agent could be given a `lookup_icd10` tool and a `parse_fhir_resource` tool.

**Quality metric:** Field-level extraction accuracy on a held-out set of 10 hand-labelled Synthea oncology cases. Target: ≥90% on diagnosis, stage, biomarkers, and requested treatment.

**Contract test:**

```python
# tests/agents/test_clinical_extractor.py
import pytest
from app.agents.clinical_extractor import clinical_extractor_node
from app.graph.state import ClinCaseState
from tests.fixtures import load_fhir_bundle

@pytest.mark.asyncio
async def test_extracts_stage_iiia_breast_cancer():
    bundle = load_fhir_bundle("stage3_her2pos_breast.json")
    state = ClinCaseState(
        case_id="test-001",
        fhir_bundle=bundle,
        requested_treatment={"name": "trastuzumab", "j_code": "J9355"},
        payer_id="aetna",
    )
    out = await clinical_extractor_node(state)
    snap = out.clinical_snapshot
    assert snap is not None
    assert snap.primary_diagnosis.icd10_code.startswith("C50")
    assert snap.primary_diagnosis.stage == "IIIA"
    assert any(b.name == "HER2" and b.value.lower() in ("positive", "3+") for b in snap.biomarkers)
    assert snap.requested_treatment.name.lower() == "trastuzumab"
```

### 9.2 Agent 2 — Policy Retriever

**Responsibility:** Retrieve the payer policy sections relevant to the patient's diagnosis and requested treatment.

**Inputs:** `clinical_snapshot: ClinicalSnapshot`, `payer_id: str`

**Output schema:**

```python
# backend/app/models/policy.py
from pydantic import BaseModel
from typing import Optional

class PolicyExcerpt(BaseModel):
    payer_id: str           # e.g. "aetna"
    policy_id: str          # e.g. "0048"
    policy_title: str       # e.g. "Trastuzumab (Herceptin)"
    section_heading: str    # e.g. "Medical Necessity Criteria"
    excerpt_text: str       # raw policy text chunk
    source_url: Optional[str] = None
    page_number: Optional[int] = None
    relevance_score: float  # 0..1 from pgvector
```

**Retrieval method (hybrid search):**
1. Filter the policy corpus by `payer_id` AND a treatment-name keyword match.
2. Within the filtered set, run pgvector cosine similarity over an embedding of a query string built from `{requested_treatment.name} for {primary_diagnosis.description} stage {stage} with biomarkers {biomarkers}`.
3. Take top 10 candidates, then LLM re-rank to top 5.

**Re-rank prompt:**

```text
You are the Policy Retriever re-ranker for ClinCase. You have a clinical
snapshot and 10 candidate policy excerpts. Return a JSON array of exactly
5 excerpt indices (0-9), ordered from most to least relevant for deciding
medical necessity for THIS patient and THIS treatment. Output ONLY the
JSON array, e.g. [3, 1, 7, 0, 5]. No prose.
```

**Tools:** `pgvector_search(query_embedding, payer_id, top_k)`, `keyword_filter(treatment_name)`.

**Quality metric:** Recall@5 against a hand-labelled set of (clinical case → relevant policy section) pairs. Target: ≥80%.

### 9.3 Agent 3 — Necessity Reasoner

**Responsibility:** Match the clinical evidence against the policy criteria, criterion by criterion.

**Inputs:** `clinical_snapshot: ClinicalSnapshot`, `policy_excerpts: list[PolicyExcerpt]`

**Output schema:**

```python
# backend/app/models/necessity.py
from pydantic import BaseModel
from typing import Literal, Optional

class CriterionAssessment(BaseModel):
    criterion_text: str           # the policy criterion verbatim
    policy_excerpt_index: int     # which PolicyExcerpt it came from
    status: Literal["MET", "NOT_MET", "AMBIGUOUS"]
    supporting_evidence: list[str]  # excerpts from ClinicalSnapshot
    missing_evidence: Optional[str] = None  # what would resolve an ambiguity
    confidence: float             # 0..1
    rationale: str                # one or two sentences

class NecessityAssessment(BaseModel):
    criteria: list[CriterionAssessment]
    overall_confidence: float
    summary: str  # 2–3 sentences, plain English
```

**System prompt:**

```text
You are the Necessity Reasoner agent for ClinCase. You receive a structured
clinical snapshot and a list of payer policy excerpts. Your job is to extract
every distinct medical-necessity criterion from the policy excerpts and
assess each one against the clinical evidence.

Rules:
1. Output ONLY a JSON object matching the NecessityAssessment schema.
2. For each criterion, status must be exactly one of MET, NOT_MET, AMBIGUOUS.
3. supporting_evidence must quote or paraphrase from the clinical snapshot
   and must point to facts that are actually present. Never fabricate.
4. If a criterion is AMBIGUOUS, missing_evidence must state the specific
   document or fact that would resolve it (e.g. "ECHO showing LVEF >=50%").
5. confidence is your subjective certainty in the status assignment, 0..1.
6. Be conservative. When in doubt, mark AMBIGUOUS rather than MET.
7. overall_confidence is the minimum confidence across all criteria.
8. summary is a 2–3 sentence plain-English explanation a clinician would
   accept as accurate.
```

**Tools:** none. Pure reasoning over the inputs.

**Quality metric:** Per-criterion agreement with a clinician-reviewed ground truth on 10 cases. Target: ≥85% agreement.

### 9.4 Agent 4 — Decision Composer

**Responsibility:** Convert the necessity assessment into a final verdict with a citation chain.

**Inputs:** `necessity_assessment: NecessityAssessment`, `clinical_snapshot: ClinicalSnapshot`, `policy_excerpts: list[PolicyExcerpt]`

**Output schema:**

```python
# backend/app/models/decision.py
from pydantic import BaseModel
from typing import Literal

class Citation(BaseModel):
    kind: Literal["clinical", "policy"]
    text: str
    pointer: str  # FHIR resource id, or "policy:{policy_id}#section"

class Decision(BaseModel):
    verdict: Literal["APPROVE", "DENY", "REFER"]
    rationale: str  # 3–5 sentences plain English
    citations: list[Citation]
    confidence: float
    risk_flags: list[str]  # off-label / high-cost / low-evidence / etc.
```

**Deterministic verdict rule (applied before the LLM):**

```python
# backend/app/agents/decision_composer.py (excerpt)
def derive_verdict(assessment: NecessityAssessment) -> str:
    statuses = [c.status for c in assessment.criteria]
    if any(s == "NOT_MET" for s in statuses):
        return "DENY"
    if all(s == "MET" for s in statuses) and assessment.overall_confidence >= 0.75:
        return "APPROVE"
    return "REFER"
```

The LLM call then *justifies* the deterministic verdict in natural language and produces the citation chain.

**System prompt:**

```text
You are the Decision Composer agent for ClinCase. You have been given a
necessity assessment, a clinical snapshot, and the policy excerpts that
were considered. The verdict has already been deterministically derived as
{verdict}. Your job is to write a 3–5 sentence rationale and produce a
complete citation chain.

Rules:
1. Output ONLY a JSON object matching the Decision schema, with verdict
   set to "{verdict}".
2. Every claim in the rationale must be supported by at least one citation.
3. Citations must include both clinical citations (from the ClinicalSnapshot)
   and policy citations (from the PolicyExcerpts).
4. risk_flags should include any of: off-label, high-cost, low-evidence,
   biomarker-mismatch, contraindication, low-performance-status.
5. confidence equals overall_confidence from the necessity assessment.
6. Never contradict the deterministic verdict.
```

**Quality metric:** Citation-coverage rate (every claim in the rationale traceable to a citation). Target: 100%.

### 9.5 Agent 5 — Appeals Drafter

**Responsibility:** When a denial is issued (either by ClinCase's own Decision Composer or by an external payer letter), draft a complete appeal letter grounded in the clinical evidence.

**Inputs:** `decision: Decision` (verdict=DENY) OR `external_denial_letter: str`, plus `clinical_snapshot`, `policy_excerpts`.

**Output schema:**

```python
# backend/app/models/appeal.py
from pydantic import BaseModel

class AppealArgument(BaseModel):
    contested_criterion: str
    payer_position: str
    counter_position: str
    cited_evidence: list[str]
    cited_policy_text: str
    cited_guideline: str  # e.g. "NCCN Breast Cancer v.4.2024 BINV-K"

class AppealDraft(BaseModel):
    patient_initials: str
    payer_id: str
    requested_treatment: str
    denial_date: str
    appeal_body: str           # full letter text, ~500–800 words
    structured_arguments: list[AppealArgument]
    attachments_referenced: list[str]
    requested_action: str      # e.g. "Overturn the denial and authorise..."
```

**System prompt:**

```text
You are the Appeals Drafter agent for ClinCase. You receive a denial (either
an ClinCase-generated Decision with verdict=DENY, or an external payer denial
letter), the clinical snapshot, and the policy excerpts. Your job is to draft
a formal, persuasive, evidence-grounded appeal letter to the payer.

Rules:
1. Output ONLY a JSON object matching the AppealDraft schema.
2. The appeal_body must be a complete formal letter, 500–800 words, with:
   - opening identifying the patient (initials only), the denied treatment,
     the denial date, and a clear statement that this is an appeal
   - a clinical background paragraph
   - one paragraph per contested criterion, citing the specific clinical
     evidence and the specific policy or guideline language that supports
     overturning the denial
   - a closing requesting the specific action (overturn + authorise)
3. structured_arguments must mirror the contested criteria from the
   appeal_body, with each argument's cited_evidence drawn ONLY from the
   ClinicalSnapshot. Never fabricate clinical facts.
4. cited_guideline should reference NCCN, ASCO, or FDA labelling where
   applicable. If you cannot identify a specific guideline citation, leave
   it empty rather than fabricate one.
5. The tone is firm, professional, evidence-first. No emotional language.
```

**Quality metric:** Letter completeness score (presence of all required sections) + a human-rater quality score on a 1–5 scale. Target: completeness 100%, quality ≥4.

### 9.6 Per-agent timing budget

| Agent | Target latency |
|---|---|
| Clinical Extractor | <8s |
| Policy Retriever | <3s |
| Necessity Reasoner | <12s |
| Decision Composer | <5s |
| Appeals Drafter | <15s |
| **Total (happy path)** | **<30s** |
| **Total (denial → appeal)** | **<45s** |

## 10. Data models

All data models live in `backend/app/models/` as Pydantic v2 classes (defined above) and are mirrored in `frontend/src/lib/types.ts` as TypeScript interfaces. The TypeScript mirrors are generated from the OpenAPI schema FastAPI emits, via `openapi-typescript`.

## 11. Database schema (PostgreSQL DDL)

```sql
-- backend/db/schema.sql

CREATE EXTENSION IF NOT EXISTS vector;

-- Cases (a single PA request)
CREATE TABLE cases (
    id              TEXT PRIMARY KEY,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    payer_id        TEXT NOT NULL,
    patient_initials TEXT NOT NULL,
    requested_treatment_name TEXT NOT NULL,
    requested_j_code TEXT,
    fhir_bundle     JSONB NOT NULL,
    physician_note  TEXT,
    status          TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending','running','approved','denied','referred','appealed','overturned'))
);

-- Agent runs (one row per agent invocation per case)
CREATE TABLE agent_runs (
    id              BIGSERIAL PRIMARY KEY,
    case_id         TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    agent_name      TEXT NOT NULL,
    started_at      TIMESTAMPTZ NOT NULL,
    finished_at     TIMESTAMPTZ,
    input_json      JSONB NOT NULL,
    output_json     JSONB,
    tool_calls      JSONB,
    latency_ms      INTEGER,
    error_text      TEXT
);
CREATE INDEX ON agent_runs(case_id);
CREATE INDEX ON agent_runs(agent_name);

-- Decisions
CREATE TABLE decisions (
    id              BIGSERIAL PRIMARY KEY,
    case_id         TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    verdict         TEXT NOT NULL CHECK (verdict IN ('APPROVE','DENY','REFER')),
    rationale       TEXT NOT NULL,
    citations_json  JSONB NOT NULL,
    confidence      REAL NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Appeals
CREATE TABLE appeals (
    id              BIGSERIAL PRIMARY KEY,
    case_id         TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    appeal_body     TEXT NOT NULL,
    structured_arguments_json JSONB NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Reviewer overrides (HITL)
CREATE TABLE reviewer_actions (
    id              BIGSERIAL PRIMARY KEY,
    case_id         TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    reviewer_id     TEXT NOT NULL,
    action          TEXT NOT NULL CHECK (action IN ('approve','override_to_approve','override_to_deny','escalate','add_note')),
    note            TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Policy corpus (RAG)
CREATE TABLE policy_chunks (
    id              BIGSERIAL PRIMARY KEY,
    payer_id        TEXT NOT NULL,
    policy_id       TEXT NOT NULL,
    policy_title    TEXT NOT NULL,
    section_heading TEXT,
    chunk_text      TEXT NOT NULL,
    page_number     INTEGER,
    source_url      TEXT,
    embedding       VECTOR(384) NOT NULL  -- sentence-transformers/all-MiniLM-L6-v2
);
CREATE INDEX ON policy_chunks(payer_id);
CREATE INDEX ON policy_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```

## 12. REST API contract (FastAPI)

```
POST /api/v1/cases
  Body: { payer_id, patient_initials, fhir_bundle, physician_note?, requested_treatment }
  Returns: { case_id }

POST /api/v1/cases/{case_id}/run
  Triggers the LangGraph for this case.
  Returns: { run_id }

GET  /api/v1/cases/{case_id}/stream         (Server-Sent Events)
  Streams trace events as the agents run.
  Event types:
    - "agent_started":  { agent_name, ts }
    - "agent_thinking": { agent_name, partial_text, ts }
    - "agent_finished": { agent_name, output, latency_ms, ts }
    - "decision":       { verdict, rationale, citations, confidence, ts }
    - "appeal_started": { ts }
    - "appeal_finished":{ appeal_id, ts }
    - "agent_error":    { agent_name, error, ts }
    - "done":           { ts }

GET  /api/v1/cases/{case_id}                      → Case + Decision + Appeal (if any)
GET  /api/v1/cases/{case_id}/audit                → Full agent_runs trail
POST /api/v1/cases/{case_id}/appeal/regenerate    → Re-runs Appeals Drafter with reviewer notes
POST /api/v1/cases/{case_id}/review               → Reviewer action (approve/override/escalate)

POST /api/v1/cases/{case_id}/external_denial
  Body: { denial_letter_text }
  Triggers the Appeals Drafter directly on an external denial.

GET  /api/v1/policies                             → List ingested policies
GET  /api/v1/healthz                              → Health check
```

## 13. Frontend architecture (React component tree)

```
frontend/src/
├── main.tsx
├── App.tsx
├── routes/
│   ├── Home.tsx                  (case list + "New PA request")
│   ├── NewCase.tsx               (form: upload FHIR, treatment, payer)
│   ├── CaseDetail.tsx            (the main demo screen)
│   └── PolicyLibrary.tsx
├── components/
│   ├── ReasoningTracePanel.tsx   ★ THE KEY COMPONENT — streams agent cards
│   ├── AgentCard.tsx             (one card per agent, colour-coded, with citations)
│   ├── DecisionBadge.tsx         (APPROVE green / DENY red / REFER amber)
│   ├── CitationPopover.tsx       (click any citation, see the source)
│   ├── AppealLetterEditor.tsx    (read-only by default, edit on reviewer override)
│   ├── AuditLogViewer.tsx        (table of every agent_runs row)
│   ├── ReviewerConsole.tsx       (approve / override / escalate buttons)
│   └── ui/ (button, input, card, badge — Tailwind primitives)
├── lib/
│   ├── api.ts                    (typed fetch client)
│   ├── sse.ts                    (EventSource wrapper for the stream)
│   └── types.ts                  (generated from OpenAPI)
└── styles/index.css
```

The single most-important component is `ReasoningTracePanel.tsx`. It opens an `EventSource` to `/api/v1/cases/{case_id}/stream`, renders one `AgentCard` per agent as the events arrive, and animates each card in with a subtle slide. Each card shows the agent name, a coloured status pill, the latency, and a collapsible "thinking" section. Citations inside the card are clickable.

## 14. Observability, audit logging, and the trace stream

Every agent invocation is wrapped in a context manager that:
1. Inserts an `agent_runs` row at start with `started_at` and `input_json`.
2. Records every tool call into `tool_calls`.
3. On finish, updates the row with `output_json`, `finished_at`, and `latency_ms`.
4. Emits an SSE event to any open stream for that case.
5. On exception, records `error_text` and emits an `agent_error` SSE event.

```python
# backend/app/observability/trace.py
import time, json, structlog
from contextlib import asynccontextmanager
from app.db import db
from app.streaming import publish

logger = structlog.get_logger()

@asynccontextmanager
async def trace_agent(case_id: str, agent_name: str, input_payload: dict):
    started = time.time()
    row_id = await db.fetchval(
        "INSERT INTO agent_runs (case_id, agent_name, started_at, input_json) "
        "VALUES ($1, $2, NOW(), $3) RETURNING id",
        case_id, agent_name, json.dumps(input_payload)
    )
    await publish(case_id, {"type": "agent_started", "agent_name": agent_name})
    try:
        result = {}
        yield result
        latency_ms = int((time.time() - started) * 1000)
        await db.execute(
            "UPDATE agent_runs SET finished_at=NOW(), output_json=$1, latency_ms=$2 WHERE id=$3",
            json.dumps(result.get("output", {})), latency_ms, row_id
        )
        await publish(case_id, {
            "type": "agent_finished",
            "agent_name": agent_name,
            "output": result.get("output", {}),
            "latency_ms": latency_ms,
        })
    except Exception as e:
        await db.execute(
            "UPDATE agent_runs SET finished_at=NOW(), error_text=$1 WHERE id=$2",
            str(e), row_id
        )
        await publish(case_id, {"type": "agent_error", "agent_name": agent_name, "error": str(e)})
        raise
```

---

# PART C — IMPLEMENTATION

## 15. Repository structure

```
clincase/
├── README.md
├── CLAUDE.md                     ← project conventions for Claude Code
├── PROPOSAL.md                   ← this file
├── docker-compose.yml
├── .env.example
├── Makefile
│
├── backend/
│   ├── pyproject.toml
│   ├── Dockerfile
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py               (FastAPI app)
│   │   ├── config.py
│   │   ├── db.py                 (asyncpg pool)
│   │   ├── streaming.py          (SSE pub/sub)
│   │   ├── observability/
│   │   │   └── trace.py
│   │   ├── models/
│   │   │   ├── clinical.py
│   │   │   ├── policy.py
│   │   │   ├── necessity.py
│   │   │   ├── decision.py
│   │   │   └── appeal.py
│   │   ├── agents/
│   │   │   ├── __init__.py
│   │   │   ├── clinical_extractor.py
│   │   │   ├── policy_retriever.py
│   │   │   ├── necessity_reasoner.py
│   │   │   ├── decision_composer.py
│   │   │   └── appeals_drafter.py
│   │   ├── graph/
│   │   │   ├── state.py
│   │   │   └── build.py
│   │   ├── prompts/
│   │   │   ├── clinical_extractor.txt
│   │   │   ├── policy_retriever_rerank.txt
│   │   │   ├── necessity_reasoner.txt
│   │   │   ├── decision_composer.txt
│   │   │   └── appeals_drafter.txt
│   │   ├── ingestion/
│   │   │   ├── ingest_policies.py     (PDF → chunks → embeddings → DB)
│   │   │   └── policies/              (the actual PDFs)
│   │   ├── synthea/
│   │   │   ├── generate.py            (wrapper around Synthea)
│   │   │   └── seeds/                 (10 hand-picked oncology cases)
│   │   └── api/
│   │       ├── cases.py
│   │       ├── stream.py
│   │       ├── audit.py
│   │       └── policies.py
│   ├── db/
│   │   └── schema.sql
│   └── tests/
│       ├── agents/
│       ├── api/
│       ├── fixtures/
│       └── e2e/
│
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.ts
│   ├── Dockerfile
│   ├── index.html
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── routes/
│       ├── components/
│       ├── lib/
│       └── styles/
│
└── ops/
    ├── aws/
    │   ├── ecs-task-definition.json
    │   └── infra-notes.md
    └── scripts/
        ├── seed_demo.sh
        └── reset_db.sh
```

## 16. Dependencies (exact versions)

**`backend/pyproject.toml`** (key deps):

```toml
[project]
name = "clincase-backend"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "fastapi==0.115.0",
  "uvicorn[standard]==0.32.0",
  "pydantic==2.9.2",
  "asyncpg==0.30.0",
  "pgvector==0.3.6",
  "sse-starlette==2.1.3",
  "structlog==24.4.0",
  "anthropic==0.39.0",
  "langchain==0.3.7",
  "langchain-anthropic==0.2.4",
  "langgraph==0.2.45",
  "sentence-transformers==3.2.1",
  "pypdf==5.0.1",
  "fhir.resources==7.1.0",
  "python-dotenv==1.0.1",
  "httpx==0.27.2",
]

[project.optional-dependencies]
dev = [
  "pytest==8.3.3",
  "pytest-asyncio==0.24.0",
  "pytest-cov==5.0.0",
  "ruff==0.7.1",
  "mypy==1.13.0",
]
```

**`frontend/package.json`** (key deps):

```json
{
  "name": "clincase-frontend",
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "test": "vitest",
    "gen:types": "openapi-typescript http://localhost:8000/openapi.json -o src/lib/types.ts"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.27.0",
    "@tanstack/react-query": "^5.59.0",
    "lucide-react": "^0.453.0",
    "clsx": "^2.1.1"
  },
  "devDependencies": {
    "vite": "^5.4.10",
    "@vitejs/plugin-react": "^4.3.3",
    "typescript": "^5.6.3",
    "tailwindcss": "^3.4.14",
    "postcss": "^8.4.47",
    "autoprefixer": "^10.4.20",
    "openapi-typescript": "^7.4.2",
    "vitest": "^2.1.3"
  }
}
```

## 17. Local development setup

```bash
# one-time
git clone <repo> && cd clincase
cp .env.example .env       # fill in ANTHROPIC_API_KEY
docker compose up -d postgres
make db.init               # runs schema.sql
make ingest.policies       # ingests the bundled payer PDFs
make seed.demo             # seeds 10 demo cases

# every dev session
docker compose up -d postgres
make backend.dev           # uvicorn with reload
make frontend.dev          # vite dev server
# open http://localhost:5173
```

## 18. Docker Compose & AWS deployment

```yaml
# docker-compose.yml
services:
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: clincase
      POSTGRES_PASSWORD: clincase
      POSTGRES_DB: clincase
    ports: ["5432:5432"]
    volumes: ["pgdata:/var/lib/postgresql/data"]

  backend:
    build: ./backend
    env_file: .env
    depends_on: [postgres]
    ports: ["8000:8000"]

  frontend:
    build: ./frontend
    depends_on: [backend]
    ports: ["5173:5173"]

volumes:
  pgdata:
```

**AWS deployment plan (for the provided AWS environment):**
- Postgres: RDS for PostgreSQL 16 with the `pgvector` extension
- Backend: ECS Fargate, behind an ALB with sticky sessions for SSE
- Frontend: S3 static hosting + CloudFront
- Secrets: AWS Secrets Manager for `ANTHROPIC_API_KEY` (or AWS Bedrock IAM role as fallback)
- Logs: CloudWatch Logs

## 19. Environment variables

```bash
# .env.example
DATABASE_URL=postgresql://clincase:clincase@localhost:5432/clincase
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-sonnet-4-5
USE_BEDROCK_FALLBACK=false
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
LOG_LEVEL=INFO
CORS_ORIGINS=http://localhost:5173
```

## 20. Testing strategy

| Layer | Tool | What we test |
|---|---|---|
| Unit (models) | pytest | Pydantic validation, edge cases |
| Unit (agents) | pytest + mocked LLM | Each agent on a fixed input → asserts on output schema |
| Contract (agents) | pytest + real LLM (small set) | Each agent on 3 real cases → asserts on key fields |
| API | pytest + httpx | Each endpoint, happy + error paths |
| Integration (graph) | pytest + real LLM (3 cases) | Full LangGraph end-to-end |
| End-to-end (UI) | manual + recorded video | The demo script, exactly |

Target: ≥80% line coverage on `backend/app/models/`, `backend/app/graph/`, `backend/app/api/`. Agents are tested via contract tests, not coverage.

## 21. Sample data, seed scripts, and demo fixtures

**Demo cohort (10 cases, hand-picked from Synthea output):**
1. Stage IIIA HER2+ breast cancer, requesting trastuzumab → APPROVE (clean happy path)
2. Stage IV NSCLC, EGFR+, requesting osimertinib → APPROVE
3. Stage IV melanoma, BRAF V600E, requesting dabrafenib + trametinib → APPROVE
4. Stage II colon cancer, MSI-high, requesting pembrolizumab → REFER (off-label nuance)
5. Stage IIIB breast cancer, HER2-, requesting trastuzumab → DENY (biomarker mismatch) → APPEAL path
6. Stage IV NSCLC, no biomarker testing documented → REFER (missing evidence)
7. Stage I prostate cancer, requesting abiraterone → DENY → APPEAL path
8. Stage IV breast cancer, HER2+, prior trastuzumab progression, requesting T-DXd → APPROVE
9. Stage III ovarian cancer, BRCA1+, requesting olaparib → APPROVE
10. Stage IV pancreatic cancer, requesting FOLFIRINOX → APPROVE

**Seed script:**

```python
# backend/app/synthea/seed.py
import asyncio, json
from pathlib import Path
from app.db import db

async def seed():
    seeds = Path(__file__).parent / "seeds"
    for f in sorted(seeds.glob("*.json")):
        case = json.loads(f.read_text())
        await db.execute(
            "INSERT INTO cases (id, payer_id, patient_initials, requested_treatment_name, "
            "requested_j_code, fhir_bundle, physician_note) VALUES ($1,$2,$3,$4,$5,$6,$7) "
            "ON CONFLICT (id) DO NOTHING",
            case["id"], case["payer_id"], case["patient_initials"],
            case["requested_treatment"]["name"], case["requested_treatment"].get("j_code"),
            json.dumps(case["fhir_bundle"]), case.get("physician_note"),
        )

if __name__ == "__main__":
    asyncio.run(seed())
```

**Policy ingestion script:** Reads PDFs from `backend/app/ingestion/policies/`, splits each into ~500-token chunks with 50-token overlap, computes embeddings via `sentence-transformers/all-MiniLM-L6-v2`, inserts into `policy_chunks`. One-time run before the demo.

## 22. Error handling, retry, and graceful degradation

- **LLM call failures:** Retry up to 3 times with exponential backoff. On final failure, the agent returns a `REFER` outcome with an explicit "system unable to complete reasoning" rationale, never a fabricated answer.
- **Schema validation failures:** If the LLM returns malformed JSON, retry once with a "your previous output was invalid JSON, here is the schema again" follow-up. If still invalid, return REFER.
- **Policy retrieval returns empty:** Return REFER with rationale "no applicable policy found for this payer/treatment combination."
- **Database failures:** Surface 503 to the API client; do not silently lose data.
- **Bedrock fallback:** If `USE_BEDROCK_FALLBACK=true` and the Anthropic API call fails, retry once via Bedrock with the same prompt. This is the venue-network insurance for May 6.

---

# PART D — EXECUTION

## 23. CLAUDE.md conventions (for Claude Code sessions)

The repo will contain a `CLAUDE.md` at the root that Claude Code reads at the start of every session. Its core contents:

```markdown
# ClinCase — Project Conventions for Claude Code

## Read first
- `PROPOSAL.md` is the single source of truth. Do not contradict it.
- This is an early-stage project but the code must look production-grade.
  The reviewing judges are enterprise architects.

## Coding conventions
- Python: 3.11, type hints everywhere, Pydantic v2 models for every contract,
  `ruff` formatting, `mypy --strict` on `app/models/` and `app/graph/`.
- TypeScript: strict mode, no `any`, generated types from OpenAPI.
- Async by default in the backend. Never block the event loop.
- No global state. Inject the db pool and the LLM client.
- Prompts live in `backend/app/prompts/` as `.txt` files. Never inline a
  multi-line prompt in code.

## Agent conventions
- Every agent has: a Pydantic input model, a Pydantic output model, a system
  prompt file, a `*_node` function for LangGraph, and a contract test.
- Every agent call is wrapped in `trace_agent(case_id, agent_name, input)`.
- Every agent emits SSE trace events.
- Agents NEVER fabricate clinical facts. If the data isn't there, say so.

## Testing
- Run `make test` before any commit.
- New agents require a contract test on at least one fixture.

## Things never to do
- Never hard-code secrets.
- Never call the LLM without trace_agent.
- Never return free-form prose from an agent — always structured JSON.
- Never log PHI even in synthetic mode (use patient initials only).
- Never delete from the cases table — use `status` instead.

## Demo discipline
- The demo cohort is the 10 cases in `backend/app/synthea/seeds/`. Do not
  add new cases without updating PROPOSAL.md Section 21.
- The demo script in PROPOSAL.md Section 26 is the authoritative path.
```

## 24. 23-day prep plan (April 13 → May 5)

### Week 1 — Foundation (April 13–19)
- **Day 1 (Apr 13):** Lock PROPOSAL.md v1.0. All four teammates read it end-to-end. Set up GitHub repo with this file at root.
- **Day 1:** One teammate begins reading 2 real Aetna oncology medical policies in full and writes a 1-page summary into PROPOSAL.md as a new appendix.
- **Day 2 (Apr 14):** Initialise the monorepo per Section 15. Create empty packages, `pyproject.toml`, `package.json`, `docker-compose.yml`, `Makefile`, `.env.example`.
- **Day 2:** Stand up Postgres via Docker Compose. Apply `schema.sql`. Verify `pgvector` extension loads.
- **Day 3 (Apr 15):** Implement `backend/app/models/*` (all five Pydantic schemas). Implement `backend/app/graph/state.py`. Write unit tests for the models.
- **Day 4 (Apr 16):** Implement `backend/app/observability/trace.py` and `backend/app/streaming.py`. Write a stub agent that uses `trace_agent` and verify SSE events flow.
- **Day 5 (Apr 17):** Implement Agent 1 (Clinical Extractor) with its prompt file and contract test. Use a Synthea-generated stage IIIA HER2+ breast cancer bundle as the first fixture.
- **Day 6 (Apr 18):** Generate 10 Synthea oncology cases and hand-label them. Place in `backend/app/synthea/seeds/`. Implement `seed.py` and verify all 10 land in the DB.
- **Day 7 (Apr 19):** Implement `backend/app/ingestion/ingest_policies.py`. Download 4–5 real public oncology policies (Aetna trastuzumab, Aetna pembrolizumab, BCBS osimertinib, etc.). Ingest them. Verify pgvector retrieval returns sensible results on 5 manual queries.

### Week 2 — Core agents + Agent Builder Challenge (April 20–23)
- **Day 8 (Apr 20):** Implement Agent 2 (Policy Retriever) with re-rank prompt and contract test.
- **Day 9 (Apr 21):** Implement Agent 3 (Necessity Reasoner) with prompt and contract test. End-of-day milestone: Agents 1+2+3 wired through LangGraph end-to-end on at least one demo case.
- **Day 10 (Apr 22):** Rehearse the 60-second decomposition pitch ten times as a team. Build a one-page printable cheat-sheet with the agent diagram and the locked facts. Pre-build the LangGraph skeleton with placeholder nodes that you can fill in live on April 23.
- **Day 11 (Apr 23): AGENT BUILDER CHALLENGE.** Walk in with the rehearsed decomposition, the pre-built skeleton, and the contract tests. Fill in the agents live. Defend the architecture verbally.

### Week 3 — Depth + the appeals wedge (April 24–30)
- **Day 12 (Apr 24):** Implement Agent 4 (Decision Composer) with the deterministic verdict rule and the LLM justification step. Contract test.
- **Day 13 (Apr 25):** Begin Agent 5 (Appeals Drafter). This is the differentiator — give it the most attention. Draft the prompt, test on case 5 (HER2- breast cancer requesting trastuzumab → DENY → APPEAL).
- **Day 14 (Apr 26):** Finish Agent 5. Add the conditional edge in LangGraph. End-to-end test on cases 5 and 7 (the two denial → appeal cases).
- **Day 15 (Apr 27):** Build `ReasoningTracePanel.tsx`. This is the second most-important UI element after the decision verdict itself. SSE wiring, animated card insertion, citation popovers.
- **Day 16 (Apr 28):** Build `AuditLogViewer.tsx` and `ReviewerConsole.tsx`. Wire up the reviewer override path through the API.
- **Day 17 (Apr 29):** Build `AppealLetterEditor.tsx`. Render the appeal as a formatted letter with inline citation chips. Allow the reviewer to edit and re-submit.
- **Day 18 (Apr 30):** End-to-end integration test on all 10 demo cases. Fix everything that breaks. Tag `v0.9.0`.

### Week 4 — Polish, rehearse, package (May 1–5)
- **Day 19 (May 1):** Write the three demo scripts (happy, denial→appeal, audit view). Time them. Cut anything over budget. Practice transitions.
- **Day 20 (May 2):** Dry-run the full pitch in front of two strangers (not teammates, not family — strangers). Take notes on every confused face.
- **Day 21 (May 3):** Fix the demo and the deck based on dry-run feedback. Re-time. Re-rehearse.
- **Day 22 (May 4):** Final dry-run. Record a video backup of each demo path (in case the live demo fails). Verify the Docker image runs on a clean machine that has never seen the repo. Vendor all dependencies offline.
- **Day 23 (May 5):** Pack the USB. Verify ANTHROPIC_API_KEY works AND the Bedrock fallback works AND a local-cached prompt path works. Sleep early. Tag `v1.0.0`.

### May 6 in Pune (24-hour MVP build)
- **Hour 0:** Arrive with the scaffold. Smoke-test on the venue network.
- **Hours 1–6:** Integrate any last polish. Re-seed the demo data. Re-verify the streaming UI on the venue's actual hardware/projector resolution.
- **Hours 6–18:** Add one or two tasteful enhancements that are obviously fresh-built (a new policy from a new payer, a new edge-case demo case, an improvement to one agent's prompt). This is what you point at when asked "what did you build today?"
- **Hours 18–24:** Final dry-runs. Sleep at least 4 hours.

### May 7 in Pune
- Pitch. Win.

## 25. Pitch script (5 minutes for May 7)

**[0:00–0:15] Cold open. No slides.**
> "In March 2024, a stage-3 breast cancer patient in Ohio waited 27 days for her insurer to approve the chemotherapy her oncologist had already prescribed. The drug was eventually approved on appeal. She started treatment six weeks late."
>
> *[pause two seconds]*

**[0:15–0:30] Name the system.**
> "We built ClinCase. ClinCase is an agentic AI system that would have approved her on Day 1 — and if denied, would have filed her appeal in four minutes instead of four weeks."

**[0:30–0:55] The numbers.**
> "Prior authorisation wastes over thirty billion dollars a year in US healthcare administration. The AMA's 2024 survey says 94% of physicians report PA delays patient care, and 24% report PA has led to a serious adverse event for a patient in their care. KFF reports that 80.7% of appealed Medicare Advantage denials are overturned in 2024 — but most denials are never appealed, because the manual workload is crushing. And the CMS Interoperability and Prior Authorization Final Rule mandates electronic PA infrastructure with operational provisions starting January 2026 and Prior Authorization API requirements starting January 2027. Every impacted US payer must comply."

**[0:55–3:55] Live demo (3 minutes — see Section 26).**

**[3:55–4:35] Architecture slide.**
> "ClinCase is built as five LangGraph agents — Clinical Extractor, Policy Retriever, Necessity Reasoner, Decision Composer, and Appeals Drafter — running on Python, FastAPI, React, PostgreSQL with pgvector, deployed on AWS. We use Synthea for synthetic FHIR data and real, publicly-available payer medical policies for the RAG corpus, so the demo isn't a toy. Every decision is logged and defensible."

**[4:35–5:00] The ask.**
> "ClinCase is built for the federal mandate that goes live in months, on the exact stack that's recommended, in the health sciences segment. We'd like to pilot this with an enterprise health sciences client. Thank you."

## 26. Demo script (the live three minutes, second by second)

| Time | Action | What the audience sees | What you say |
|---|---|---|---|
| 0:00 | Click "New PA request" | Empty form | "Let's start with a real oncology case." |
| 0:05 | Load the stage IIIA HER2+ breast cancer fixture | Patient summary appears | "Stage 3 breast cancer, HER2-positive. Oncologist requesting trastuzumab." |
| 0:15 | Click "Run ClinCase" | Trace panel begins streaming | "Watch the agents think." |
| 0:20–0:50 | Cards stream in: Clinical Extractor → Policy Retriever → Necessity Reasoner | Coloured cards with timestamps and citations | "Each card is one agent. Each citation is clickable — clinical evidence in blue, policy text in purple." |
| 0:55 | Decision Composer returns APPROVE | Green APPROVE badge, full citation chain | "Under one minute. Fully cited. Defensible." |
| 1:00 | Reset, load the HER2- denial case | New case loads | "Now the harder one. This patient is HER2-negative — the same drug shouldn't be approved." |
| 1:10–2:00 | Same flow, Decision Composer returns DENY | Red DENY badge with clear reasoning | "ClinCase correctly denies. Watch what happens next." |
| 2:05 | Appeals Drafter activates automatically | New panel slides in, drafting in real time | "Now imagine a real payer denied a case that *should* have been approved. The Appeals Drafter re-reads the denial, finds the clinical evidence the denial missed, and writes a complete appeal letter." |
| 2:30 | Switch to a real overturn-eligible case (the KFF 80.7% wedge) | Full appeal letter renders | "Four minutes of wall-clock time, compressed for the demo. Every claim cited to the patient record and the policy." |
| 2:45 | Click "Audit view" | Audit log of every agent action | "And every step is reproducible. Every input, every output, every tool call. This is what audit-ready looks like for a regulated environment." |
| 3:00 | End demo | Return to architecture slide | — |

## 27. Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| April 23 Agent Builder Challenge has unexpected format | Medium | High | Pre-built LangGraph skeleton, memorised decomposition, practised live-fill |
| Pune venue has no internet | Medium | High | Vendor all deps; ship Docker image on USB; pre-cache embeddings |
| Pune venue has no Anthropic API access | Low | Critical | AWS Bedrock fallback wired and tested in week 2 |
| Demo crashes on stage | Medium | Critical | Three rehearsed paths; recorded video backup; hard-coded happy-path fallback |
| One judge doesn't understand prior auth | High | Medium | Cold open is the mitigation — anyone hears "stage-3 cancer patient waited 27 days" and instantly understands |
| Team member drops out | Low | High | Cross-train every member on at least one other member's domain; everything documented in this file |
| Synthetic data looks fake to a clinically-trained judge | Medium | Medium | Use Synthea's most-realistic config; reference real public policies; one teammate reads 2 real policies in week 1 |
| Scope creep eats the prep window | High | High | The wedge is locked: oncology only, appeals as differentiator. Reject every "what if we also..." |
| Pre-built code is challenged on May 6 | Medium | Medium | Honest framing: "We arrived with a scaffold and used the 24 hours to integrate, validate, extend, and polish." Don't lie, don't volunteer |
| LLM returns malformed JSON mid-demo | Medium | High | Schema-retry logic + REFER fallback + happy-path fixture as last resort |
| pgvector retrieval returns garbage on a fresh case | Low | Medium | Hand-tune the query template in week 2; fall back to keyword filter if vector recall < threshold |

## 28. Change log

- **v1.0** (this version) — initial master spec. Theme, wedge, agent design, schemas, prompts, repo layout, dependencies, 23-day plan, pitch, demo, risk register. All future changes versioned and logged here.

---

*End of PROPOSAL.md v1.0. Anything not in this file is not in scope. Anything in this file is binding until a v1.1 is published with a logged change reason.*
