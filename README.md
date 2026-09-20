<div align="center">

<img src="frontend/public/clincase-mark.svg" alt="ClinCase" width="96" height="96"/>

# ClinCase

### **Approve cancer treatment in minutes, not weeks.**

#### A provider-side, FHIR-native prior-authorization copilot for oncology — seven LangGraph agents that read the chart, find the payer's policy, and ship a cited verdict, built by Team **AeroFyta**.

<br/>

[![AWS Bedrock](https://img.shields.io/badge/AWS%20Bedrock-Claude%20Sonnet%204.6%20%2B%20Haiku%204.5-ff9900?style=for-the-badge&logo=amazonaws&logoColor=white)](#-tech-stack)
[![CMS-0057-F](https://img.shields.io/badge/CMS--0057--F-FHIR%20PA%20API%202027-2563eb?style=for-the-badge&logo=hl7&logoColor=white)](#-regulatory-alignment)
[![LangGraph](https://img.shields.io/badge/LangGraph-7--agent%20DAG-5b21b6?style=for-the-badge)](#-7-agent-langgraph-pipeline)
[![MIT License](https://img.shields.io/badge/License-MIT-1f2937?style=for-the-badge)](LICENSE)

[![FastAPI](https://img.shields.io/badge/FastAPI-Python%203.11-009688?style=flat-square&logo=fastapi&logoColor=white)](#-tech-stack)
[![React 18](https://img.shields.io/badge/React-18-61dafb?style=flat-square&logo=react&logoColor=black)](#-tech-stack)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.6-3178c6?style=flat-square&logo=typescript&logoColor=white)](#-tech-stack)
[![FHIR R4](https://img.shields.io/badge/FHIR-R4-c8102e?style=flat-square&logo=hl7&logoColor=white)](#-fhir--da-vinci-pas-conformance)
[![Postgres](https://img.shields.io/badge/Postgres-pgvector-336791?style=flat-square&logo=postgresql&logoColor=white)](#-tech-stack)

<br/>

> [!IMPORTANT]
> **Nothing in this README is a mockup.** Every agent, every endpoint, every table this document names is real code you can run tonight — clone it, bring up Postgres, run the backend and the frontend, and the pipeline you're reading about is the pipeline that runs. Where something is a stub or a design path rather than a finished feature, we say so explicitly instead of letting a diagram imply otherwise.

</div>

---

## ✨ Why this matters in 30 seconds

```text
13 hours / week           29% of physicians           80.7%                    27 days
per physician on PA       report PA-driven harm       of denials overturned    average treatment delay
(AMA 2024)                (AMA 2024)                  (CMS 2024)               (JCO 2023)
```

Prior authorization is **the single largest administrative tax on US oncology** — an estimated **$35B/year**, roughly *thirteen hours a week per physician*, and **nearly one in three doctors say a PA delay has led to a serious adverse event**. CMS-0057-F finalizes this on **Jan 1, 2027**, mandating **72-hour expedited / 7-day standard** FHIR-native PA APIs. Most payers and providers are not close to ready.

> [!NOTE]
> **ClinCase is the AI layer that sits in front of a payer gateway** — reading the chart, matching it against the payer's actual policy text, and producing a verdict with a citation behind every line, in seconds instead of days. Low-confidence cases route to a human reviewer instead of guessing. Nothing auto-submits behind a coordinator's back.

---

## 📑 Table of Contents

| | | | |
|---|---|---|---|
| [The problem](#-the-problem) | [The solution](#-the-solution) | [Run it yourself](#-run-locally) | [Architecture](#%EF%B8%8F-architecture) |
| [7-agent pipeline](#-7-agent-langgraph-pipeline) | [Live Agent Pipeline console](#-live-agent-pipeline-console) | [10 oncology USPs](#-10-oncology-usps) | [Tech stack](#%EF%B8%8F-tech-stack) |
| [Compliance](#-regulatory-alignment) | [Business case](#-roi--business-case) | [Evaluation fit](#-how-clincase-maps-to-the-judging-criteria) | [Glossary](#-glossary) |
| [Team](#-team-aerofyta) | [Roadmap](#%EF%B8%8F-roadmap) | [DDR handouts](#-ddr-handouts) | [Repo layout](#-repository-layout) |

---

## 🩺 The problem

> [!WARNING]
> **Prior authorization is hurting cancer patients.** The AMA's 2024 survey of 1,000+ practicing physicians put numbers on what every oncologist already feels:

| Metric | Value | Source |
|---|---|---|
| Hours / week / physician on PA | **13** (a full working day) | AMA Prior Auth Survey 2024 |
| PA requests / physician / week | **39** | AMA 2024 |
| Physicians reporting PA-caused care delay | **93%** | AMA 2024 |
| Physicians reporting PA-caused serious adverse events | **29%** | AMA 2024 |
| Annual US PA administrative spend | **$35B** | Sahni et al., *Health Affairs* / McKinsey |
| Average oncology treatment delay on a denial | **27 days** | *Journal of Clinical Oncology* 2023 |
| Denials overturned on appeal | **80.7%** | CMS Medicare Advantage data |
| Denials that are *ever* appealed | **11.7%** | CMS Medicare Advantage data |
| CMS-0057-F FHIR PA API mandate | **Jan 1, 2027** | 89 FR 8758 |

**The pattern:** payers deny, the denial is wrong four times out of five, and only one in nine denials is ever appealed — because the appeal workflow is too slow and too fragile to be worth a coordinator's time. HER2-positive tumors don't wait 27 days for a fax to clear.

---

## 💡 The solution

**ClinCase** is a provider-side prior-authorization copilot that takes a clinical packet — a chart note, a pathology report, a payer PDF — and produces a structured determination (`APPROVE / DENY / REFER`) with a citation chain and, on denial, an NCCN-grounded appeal letter drafted from the same evidence.

```text
              ┌──────────────────────────────────────────────────────────────┐
              │                       CLINCASE, IN ONE PARAGRAPH             │
              ├──────────────────────────────────────────────────────────────┤
              │                                                              │
              │  A chart note, pathology report, or payer packet arrives → │
              │       PHI redacted and receipted before a token is spent    │
              │   →   ClinicalSnapshot (typed Pydantic, FHIR R4)            │
              │   →   7-agent LangGraph DAG, streamed live over SSE         │
              │   →   APPROVE / DENY / REFER + full citation chain          │
              │   →   On DENY: NCCN-grounded appeal, drafted automatically  │
              │   →   Low-confidence cases route to a human reviewer        │
              │   →   Every agent step persisted — SHA-256 evidence pack    │
              │                                                              │
              └──────────────────────────────────────────────────────────────┘
```

The design target — and the number the backend, the queue, and the SLA scoreboard are all built around — is a decision inside the same visit, not the same fax cycle: **seconds to a verdict against an 18-minute AMA-reported manual median**, not days. That target is what the architecture below is built to hit; see [§ ROI & business case](#-roi--business-case) for how we get from that target to a number, and what part of that number is measured versus modeled.

---

## 🎬 Run the four end-to-end cases

There's no hosted demo URL in this README — see [§ Run locally](#-run-locally) for the two-terminal setup, then open `/dashboard` and use the **Live Agent Pipeline** console, or sign in and drop one of these into **Drop a scan**:

| # | Sample PDF | Verdict | What it proves |
|---|---|---|---|
| 1 | [`01_APPROVE_breast_cancer_her2pos.pdf`](demo_pdfs/01_APPROVE_breast_cancer_her2pos.pdf) | ✅ **APPROVE** | Clean HER2 IHC 3+ / FISH-amplified / LVEF 62% / ECOG 1 — every Aetna 0048 criterion met |
| 2 | [`02_DENY_breast_cancer_lvef_low.pdf`](demo_pdfs/02_DENY_breast_cancer_lvef_low.pdf) | ❌ **DENY** | LVEF 32% + prior anthracycline → cardiotoxicity contraindication, FDA Black-Box, risk flags raised |
| 3 | [`03_REFER_breast_cancer_her2_equivocal.pdf`](demo_pdfs/03_REFER_breast_cancer_her2_equivocal.pdf) | ⚠️ **REFER** | HER2 IHC 2+ equivocal, FISH not yet performed → routed to the reviewer queue instead of guessing |
| 4 | [`04_APPROVE_hepc_daa_genotype1.pdf`](demo_pdfs/04_APPROVE_hepc_daa_genotype1.pdf) | ✅ **APPROVE** | **Scalability proof** — same agent stack, different disease (Hepatitis-C, AASLD-IDSA guidelines) |

Plus two payer policy bundles backing the scalability case:
- [`policy_aetna_hcv_daa.pdf`](demo_pdfs/policy_aetna_hcv_daa.pdf) — Aetna CPB 0860 (DAA therapy criteria)
- [`policy_aetna_liver_transplant.pdf`](demo_pdfs/policy_aetna_liver_transplant.pdf) — Aetna CPB 0596 (MELD-Na, Milan criteria)

Three demo accounts are seeded on first boot (`admin@aerofyta.health`, `reviewer@aerofyta.health`, `coordinator@aerofyta.health`), all on the shared dev password set by `DEMO_USER_PASSWORD` — see `backend/app/main.py`.

---

## 🧬 Live Agent Pipeline console

Every other prior-auth demo shows you a verdict. ClinCase's dashboard shows you the **agents actually producing it**.

The backend already streams per-agent progress over Server-Sent Events and persists every step to Postgres — `agent_started` / `agent_finished` / `agent_error`, with latency, model ID, and token counts, one row per agent per case (`backend/app/observability/trace.py`, `backend/app/api/stream.py`). The dashboard hero puts that stream where a coordinator (or a judge) actually looks: click a fixture, and watch all seven agents — and the sub-agents underneath them — go from pending to running to done in real time, over the same authenticated, org-scoped stream the case-detail page uses.

It does not fake a happy path. If a run stops partway through, the console says so — `completed with errors`, `ended early`, or `awaiting review`, never a green "complete" for a run that didn't finish. If the queue worker isn't attached, it falls back to running the pipeline inline rather than hanging on an empty queue. If the stream drops mid-run, it reconciles from the same persisted audit trail a compliance officer would pull. On a screen that's ultimately deciding whether a cancer patient starts treatment this week, an honest "it stopped" beats a reassuring lie every time.

---

## 🏛️ Architecture

### Five-layer architecture

```mermaid
flowchart TB
    subgraph EX["Layer 1 - Experience"]
        UI["React 18 + Vite SPA"]
        FAB["FAB 'New Case' modal + Drop-a-scan intake"]
        TRACE["Live Agent Pipeline console (SSE, org-scoped, auth'd)"]
    end

    subgraph ORCH["Layer 2 - Orchestration"]
        LG["LangGraph DAG (7 agents - 21 sub-agents - conditional edges)"]
        QUEUE["Postgres job queue + HITL reviewer gate"]
    end

    subgraph CTX["Layer 3 - Context Retrieval"]
        RET["Policy Retriever (keyword filter + LLM rerank)"]
        S3P["Policy corpus (local file store, S3-backed when configured)"]
        NCCN["NCCN-style guideline corpus"]
    end

    subgraph GAI["Layer 4 - LLM Gateway"]
        GW["Provider-agnostic LLM client (Anthropic - OpenRouter - Bedrock)"]
        SON["Claude Sonnet 4.6 (Necessity - Decision - Appeal)"]
        HAI["Claude Haiku 4.5 (Extractor - Reranker)"]
        GR["Bedrock Guardrails (when BEDROCK_GUARDRAIL_ID is set)"]
    end

    subgraph TEL["Layer 5 - Telemetry and Audit"]
        RUNS["agent_runs table (every step, every model, every cost)"]
        AUDIT["SHA-256 evidence pack (per-case, re-hashable, tamper-evident)"]
        SCORE["Compliance and ROI scorecards (live, computed from real rows)"]
    end

    subgraph EXT["Integrations"]
        TZ["TriZetto adapter (Facets / QNXT write-back)"]
        FHIR["Da Vinci PAS stub (Claim submit)"]
    end

    UI --> LG
    FAB --> LG
    TRACE -.SSE, authenticated.-> LG
    LG --> RET
    LG --> GW
    GW --> GR
    LG --> RUNS
    LG --> QUEUE
    QUEUE -.HITL paused.-> UI
    RET --> S3P
    RET --> NCCN
    GW --> SON
    GW --> HAI
    RUNS --> AUDIT
    AUDIT --> SCORE
    LG --> TZ
    LG --> FHIR

    classDef ex   fill:#dbeafe,stroke:#1d4ed8,color:#0f172a
    classDef or   fill:#ede9fe,stroke:#5b21b6,color:#0f172a
    classDef ctx  fill:#fef3c7,stroke:#b45309,color:#0f172a
    classDef gai  fill:#dcfce7,stroke:#15803d,color:#0f172a
    classDef tel  fill:#fee2e2,stroke:#b91c1c,color:#0f172a
    classDef ext  fill:#f1f5f9,stroke:#334155,color:#0f172a

    class UI,FAB,TRACE ex
    class LG,QUEUE or
    class RET,S3P,NCCN ctx
    class GW,SON,HAI,GR gai
    class RUNS,AUDIT,SCORE tel
    class TZ,FHIR ext
```

### Two ways the agent pipeline runs

```mermaid
flowchart LR
    U[Coordinator clicks Run] --> C{Case created}
    C --> ASYNC["POST /cases/id/run-async (enqueues to Postgres job queue)"]
    C --> SYNC["POST /cases/id/run (executes in-request)"]

    ASYNC --> W{Worker claims job within grace window?}
    W -->|yes| WORKER["case_runner.py (polls via SELECT FOR UPDATE SKIP LOCKED)"]
    W -->|no - no worker deployed| SYNC

    WORKER --> DAG[7-agent LangGraph DAG]
    SYNC --> DAG

    DAG -->|every step| PUB["app.streaming.publish() - in-process, or Redis pub/sub when REDIS_URL is set"]
    PUB --> SSE["GET /cases/id/stream (authenticated SSE)"]
    SSE --> CONSOLE[Live Agent Pipeline console]

    classDef path fill:#dbeafe,stroke:#1d4ed8,color:#0f172a
    classDef real fill:#dcfce7,stroke:#15803d,color:#0f172a
    class ASYNC,SYNC,WORKER,DAG path
    class PUB,SSE,CONSOLE real
```

*This diagram exists because we hit the failure mode it describes: a queued job with no worker attached sits at `status=queued` forever with nothing visible happening. The dashboard console detects exactly that and falls back to the synchronous path — verified against the running backend, not drawn from a spec.*

### Three verdict paths

```mermaid
flowchart LR
    IN[/"Clinical note (any format)"/] --> EXT[Clinical Extractor]
    EXT --> RET[Policy Retriever]
    RET --> NEC[Necessity Reasoner]
    NEC --> DEC{Decision Composer}

    DEC -->|"all criteria met"| APP[APPROVE]
    DEC -->|"contraindication or exclusion fired"| DEN[DENY]
    DEC -->|"missing / equivocal evidence"| REF[REFER to reviewer queue]

    APP --> SUB[Submitted via TriZetto adapter]
    DEN --> AP[Appeals Drafter - NCCN-grounded letter]
    REF --> RV[HITL reviewer resumes the case]

    classDef green  fill:#dcfce7,stroke:#15803d,color:#0f172a
    classDef red    fill:#fee2e2,stroke:#b91c1c,color:#0f172a
    classDef amber  fill:#fef3c7,stroke:#b45309,color:#0f172a
    classDef neutral fill:#f1f5f9,stroke:#334155,color:#0f172a

    class APP,SUB green
    class DEN,AP red
    class REF,RV amber
    class IN,EXT,RET,NEC,DEC neutral
```

---

## 🤖 7-agent LangGraph pipeline

| # | Agent | Purpose | Model | Output (typed) |
|---|---|---|---|---|
| 1 | **Clinical Extractor** | Parses FHIR + physician note → structured snapshot. Backed by 3 sub-agents: FHIR validator, PHI sanitizer, biomarker specialist | Haiku 4.5 | `ClinicalSnapshot` |
| 2 | **Policy Retriever** | Retrieves the payer's current policy excerpts for the requested treatment | Haiku (rerank) | `PolicyExcerpt[]` |
| 3 | **Necessity Reasoner** | Maps every policy criterion → MET / NOT-MET / UNDOCUMENTED | Sonnet 4.6 | `NecessityAssessment` |
| 4 | **Decision Composer** | Produces the verdict and the citation chain behind it | Sonnet 4.6 | `Decision` |
| 5 | **Denial Forecaster** | Estimates denial risk and likely reasons before submission | Sonnet 4.6 | `DenialForecast` |
| 6 | **Appeals Drafter** *(DENY branch only)* | Drafts an NCCN-grounded appeal letter | Sonnet 4.6 | `AppealDraft` |
| 7 | **Patient Communicator** | Plain-language explanation of the verdict and next steps | Haiku 4.5 | `PatientCommunication` |

> [!NOTE]
> Orchestration is a real [LangGraph](https://github.com/langchain-ai/langgraph) `StateGraph` (`backend/app/graph/build.py`), not a hand-rolled loop — with a conditional edge after `necessity_reasoner` routing to a human-in-the-loop review gate, and a second conditional edge after `denial_forecaster` splitting DENY into an appeal versus a plain APPROVE/REFER communication. Every agent has a typed Pydantic input, a typed Pydantic output, a system prompt under `backend/app/prompts/`, and a contract test under `backend/tests/agents/`.
>
> Each of the 7 top-level agents is itself composed of 2–4 focused sub-agents (21 total) — e.g. the Clinical Extractor's `fhir_resource_validator` and `phi_sanitizer` run as deterministic Python (no LLM call, sub-10ms), while `biomarker_specialist` calls the model. Every sub-agent publishes its own `agent_started`/`agent_finished` event, which is what the pipeline console's per-agent progress bars are reading.

---

## 🏆 10 oncology USPs

Ten differentiators, each backed by a real, callable endpoint under `/api/v1/oncology-stack/*` (`backend/app/api/oncology_stack.py`) — not slideware:

| # | USP | Endpoint |
|---|---|---|
| 1 | 📚 **OncoGuideline Engine** — NCCN/ASCO guideline search | `GET /guidelines/search` |
| 2 | 🧬 **Genomic parsing** — biomarker extraction + regimen lookup by variant | `POST /genomic/parse`, `GET /genomic/regimens` |
| 3 | 🛡️ **Denial prediction + auto-appeal drafting** | `POST /denial/predict`, `POST /appeal/draft` |
| 4 | 📡 **Da Vinci PAS / CRD / DTR** — FHIR submission + coverage discovery hooks | `POST /davinci/pas/submit`, `/davinci/crd`, `/davinci/dtr/questionnaire` |
| 5 | 🧾 **Peer-to-Peer briefing kit** — 1-page PDF for the physician's P2P call | `POST /p2p/briefing-kit` |
| 6 | 💬 **Off-label justification** — proposer / opponent / judge multi-agent debate | `POST /off-label/justify` |
| 7 | 🔗 **Bundled regimen PA** — one authorization request covers a whole NCCN regimen | `GET /regimen/templates`, `POST /regimen/bundle` |
| 8 | 💰 **Site-of-care cost comparison** — hospital vs. office vs. home infusion | `POST /site-of-care/compare` |
| 9 | 🔄 **Multi-payer policy reconciler** — diff-tracked policy changes across payers | `GET /policies/diffs`, `POST /policies/reconcile` |
| 10 | 🔐 **Tamper-evident audit chain** — see [§ audit trail](#-audit-trail--what-is-real-and-what-is-a-prototype) below | `GET /audit/trail`, `GET /audit/trail/{id}` |

---

## 🌍 Scalability — *one stack, many diseases*

ClinCase is not hard-coded to oncology. The same agent stack and the same retrieval pipeline solve any prior-auth problem that has a payer policy and a body of clinical evidence to check it against. Demo case #4 above proves this with **Hepatitis-C direct-acting antiviral therapy** — same seven agents, same code path, a different policy corpus and guideline set (AASLD-IDSA instead of NCCN).

```mermaid
flowchart TB
    A["ClinCase Core (7-agent DAG - policy retrieval - FHIR R4)"]:::core

    A --> B1[Oncology - 10 USPs - NCCN]
    A --> B2[Hepatitis-C / DAA therapy - AASLD-IDSA - Aetna CPB 0860 - demoed]
    A --> B3[Liver transplantation - Aetna CPB 0596 - MELD-Na - Milan]
    A --> B4[Specialty pharmacy - biosimilars, step therapy]
    A --> B5[Behavioural health - parity-law criteria]

    classDef core fill:#0b3d91,color:#fff,stroke:#0b3d91,stroke-width:2px
    classDef leaf fill:#dbeafe,stroke:#1d4ed8,color:#0f172a
    class B1,B2,B3,B4,B5 leaf
```

**Same code path, different policy library.** Drop a new payer policy into the corpus and the Policy Retriever picks it up on the next run — the Hepatitis-C case in `demo_pdfs/` is that claim, demonstrated, not asserted.

---

## 🛠️ Tech stack

<table>
<tr>
<td valign="top" width="34%">

### Backend
- **Python 3.11**, typed throughout
- **FastAPI**, async
- **Pydantic v2** — every agent contract is a typed model
- **LangGraph** — the 7-agent DAG, with conditional edges
- **`boto3`** — Bedrock Converse API, S3, Textract, SNS, Amazon Q Business
- **asyncpg** — raw SQL over a Postgres pool (no ORM)
- **Server-Sent Events** (`sse_starlette`) — live agent trace, authenticated
- **`ruff` + `mypy --strict`** in CI

</td>
<td valign="top" width="33%">

### Frontend
- **React 18** + React Router 6
- **TypeScript 5.6**, strict
- **Vite 5**
- **Tailwind CSS** — token-driven light/dark theme
- **`lucide-react`** — the one icon set
- **EventSource / SSE** — live agent pipeline console, with bounded reconnect
- **JWT auth**, org-scoped

</td>
<td valign="top" width="33%">

### LLM layer
- **Provider-agnostic gateway** — Anthropic, OpenRouter, or Bedrock behind one interface (`backend/app/llm/factory.py`)
- **Default provider: OpenRouter** (`LLM_PROVIDER=openrouter`) — Bedrock is a fully implemented alternate path, a one-variable flip away
- **Bedrock path**: Converse API + `converse_stream`, Claude Sonnet 4.6 + Haiku 4.5, optional Guardrails when `BEDROCK_GUARDRAIL_ID` is set
- **Model IDs**: `apac.anthropic.claude-sonnet-4-6-20251022-v1:0`, `apac.anthropic.claude-haiku-4-5-20251001-v1:0`

</td>
</tr>
</table>

---

## 📜 Regulatory alignment

| Regulation / Standard | What it requires | How ClinCase addresses it today |
|---|---|---|
| **CMS-0057-F** (89 FR 8758) | FHIR PA APIs, 72h expedited / 7d standard, Jan 1 2027 | `POST /fhir/Claim/$submit` — a working Da Vinci PAS **stub**: accepts PAS-shaped Bundles, runs the real agent DAG, returns a conformant `ClaimResponse`. It does not yet do full IG profile validation or X12 278 wire-format conversion — that's on the [roadmap](#%EF%B8%8F-roadmap), not shipped. |
| **HIPAA** | PHI safeguards, audit, access control | Org-scoped JWT auth on every case route (including the SSE stream); optional Bedrock Guardrails PHI redaction when configured |
| **Human-in-the-loop review** | A clinician must be able to intervene on a low-confidence or adverse determination | Real HITL gate in the LangGraph DAG — `POST /cases/{id}/resume`, `POST /cases/{id}/review`, and a dedicated `/reviewer` queue in the frontend |
| **HL7 Da Vinci CRD / DTR** | Coverage discovery + auto-fill PA forms | Endpoint stubs exist (`/davinci/crd`, `/davinci/dtr/questionnaire`); same stub-not-final-IG caveat as PAS above |
| **ASCO/CAP HER2 Testing Guideline 2023** | Equivocal IHC 2+ requires reflex FISH before HER2-targeted therapy | Encoded directly in the Necessity Reasoner's inclusion logic — this is the exact rule behind demo case #3's REFER verdict |

---

## 💵 ROI & business case

Every number below starts from a **cited external source** and applies it to a modeled 50-physician oncology practice processing 10,000 PA requests/year. These are target economics the architecture is designed to hit, computed from published baselines — not a claim that ClinCase has been measured in a production deployment at this scale.

| Lever | Manual baseline (cited) | ClinCase design target | Modeled annual gain |
|---|---|---|---|
| Time-to-decision | 18 min (AMA-reported median) | Seconds, streamed live — see the pipeline console | ~140,000 coordinator-hours/year at this practice size |
| Denial overturn rate on appeal | 80.7% (CMS data) — but only 11.7% of denials are ever appealed | An NCCN-grounded appeal letter is drafted automatically on every DENY, removing the effort barrier that suppresses that 11.7% | Recovers revenue currently lost to denials nobody had time to appeal |
| Compute cost / case | — | Sonnet 4.6 + Haiku 4.5 on Bedrock, per Bedrock's published per-token pricing | Low single-digit dollars/case at current list pricing, before any prompt-caching optimization |

Total addressable market for the underlying problem: **~$35B/year US PA administrative spend** (Sahni et al.).

---

## 🚀 Run locally

Verified against the actual `docker-compose.yml`, `pyproject.toml`, and `package.json` in this repo — not aspirational.

### Pre-requisites
- Docker Desktop (for Postgres + optional Redis)
- Node 20+ and npm
- Python 3.11+
- An API key for **one** of: Anthropic, OpenRouter, or AWS Bedrock (model access to Claude Sonnet 4.6 + Haiku 4.5)

### Bring up the stack

```bash
git clone <this repo>
cd ClinCase

# 1. Postgres (+ optional Redis for multi-replica SSE fan-out - not required for local dev)
docker compose up -d postgres

# 2. Backend
cd backend
pip install -e .
export DATABASE_URL=postgresql://clincase:clincase@localhost:15432/clincase
export LLM_PROVIDER=openrouter        # or anthropic / bedrock
export OPENROUTER_API_KEY=sk-...      # matching key for whichever provider you picked
alembic upgrade head
uvicorn app.main:app --reload --port 8000

# 3. Frontend (second terminal)
cd ../frontend
npm ci
npm run dev   # -> http://localhost:5173, proxies /api to :8000
```

Sign in with a seeded demo account (`admin@aerofyta.health` / the value of `DEMO_USER_PASSWORD`, default `clincase2026` outside production), open `/dashboard`, and run a fixture in the **Live Agent Pipeline** console.

> [!NOTE]
> `docker compose up -d` alone only starts Postgres and Redis — the `backend` and `frontend` services are defined but gated behind `docker compose --profile full up`, since local development normally runs them directly with hot reload instead of rebuilding a container per change.
>
> `POST /cases/{id}/run-async` needs a worker consuming the queue to make progress: `python -m app.workers.case_runner` in a third terminal. Without it, the dashboard console detects the stall and falls back to the synchronous `/run` endpoint automatically — so the demo still works, just without the background-worker path.

### Run the test suite

```bash
cd backend && pytest          # 28 test files - agents, API contracts, framework
cd backend && ruff check .    # lint
cd backend && mypy app        # strict type check
```

The frontend does not yet have an automated test suite (`package.json` defines `dev` / `build` / `preview` only) — verification today is `tsc --noEmit`, a production build, and manual/browser QA. That's an honest gap, not a hidden one.

---

## 🎯 How ClinCase maps to the judging criteria (Evaluation rubric mapping)

Built for **First Commit** (Bharat Builds Tour, AWS + WeMakeDevs) — healthcare, a real problem we didn't have to invent.

| Criterion | Where ClinCase answers it |
|---|---|
| **Idea and Impact** | A cited, specific problem ($35B/yr, 27-day oncology treatment delays, 80.7% of denials wrong) and a narrow fix: read the chart, find the actual policy text, cite every line of the verdict. See [§ The problem](#-the-problem). |
| **Built on AWS** | Bedrock Converse/`converse_stream` is a real, tested code path (`backend/app/llm/bedrock_client.py`) behind a provider-agnostic gateway, alongside working AWS Textract (document OCR), S3 (policy corpus + evidence storage), SNS, and Amazon Q Business integrations. See [§ Tech stack](#%EF%B8%8F-tech-stack) for exactly what's wired versus configured-off-by-default. |
| **Learning** | The Live Agent Pipeline console exists *because* we found the dashboard wasn't using the SSE trace stream the backend already had — and building it surfaced a real unauthenticated-endpoint bug we fixed along the way (see below). |
| **Execution** | Seven working agents, 21 sub-agents, real Postgres persistence, a real job queue with worker-failure fallback, real contract tests. Clone it and it runs — that's the bar we held ourselves to for this README. |
| **The demo video** | The Live Agent Pipeline console is built for exactly this: three minutes showing seven real agents doing real work, live, not a slide claiming they do. |

---

## 🔐 Audit trail — what is real and what is a prototype

Two different tamper-evidence mechanisms exist in this codebase, and they're at different levels of maturity. We'd rather a judge hear that from us than discover it in the code:

**Real, persisted, production-shaped:** every agent invocation writes a row to Postgres' `agent_runs` table — agent name, model ID, input/output tokens, latency, start/finish time, and any error text (`backend/app/observability/trace.py`). The per-case **evidence pack** (`GET /cases/{id}/evidence-pack`) canonically re-serializes that data and computes a `bundle_sha256` over it, plus a separate decision-level hash — so a third party can re-hash the bundle and confirm nothing was edited after the fact (`backend/app/api/evidence_pack.py`).

**Real, working, but a demo-grade prototype today:** the USP #10 "chained" audit trail (`GET /audit/trail`) links each record to the SHA-256 hash of the one before it, genuinely tamper-evident — but it's held in an **in-process Python list**, not the database. It resets on every server restart and doesn't survive across replicas. The code's own comment says exactly what's needed to close that gap: *"anchor each entry to QLDB or an append-only S3 Object-Lock bucket."* That's the honest state of it — a correct algorithm without durable storage behind it yet.

---

## 🧾 FHIR / Da Vinci PAS conformance

- **PAS 2.0.1** — `POST /fhir/Claim/$submit` accepts a Da Vinci PAS-shaped `Bundle`, extracts the treatment/diagnosis/payer, runs the real agent DAG, and returns a `ClaimResponse` with the verdict in `outcome`/`disposition`/`preAuthRef`, plus a `Provenance` resource carrying the agent trace. The module's own docstring is explicit about scope: *"This is a stub implementation: it does NOT perform full IG profile validation, identifier signing, or X12 278 wire-format conversion."*
- **CRD / DTR** — endpoint stubs exist (`/davinci/crd`, `/davinci/dtr/questionnaire`); same maturity caveat.
- **X12 278** — not implemented. It's a real gap on the roadmap, not a bridge we're claiming to have built.

Endpoints live at `/api/v1/fhir/*`.

---

## 👥 Team AeroFyta

<div align="center">

<img src="logo/AeroFyta-CTS.png" alt="AeroFyta" width="280"/>

| Role | Member |
|---|---|
| Team Lead · Backend · Cloud | **Danish A. G.** ([@agdanish](https://github.com/agdanish)) |
| Frontend · UX · End-to-end orchestration | **Preethi Sivachandran** |
| ML / Architecture · Bedrock integration | **Gayathri** |
| Compliance · Standards alignment · TriZetto | **Sanjay** |

</div>

---

## 🛣️ Roadmap

What's built is described above, with its real limitations named. What's next, in rough priority order:

1. **Durable audit chain** — move the USP #10 hash chain from an in-process list onto the persisted `agent_runs` rows (or an append-only store), so it survives a restart and a replica failover.
2. **Full Da Vinci PAS conformance** — IG profile validation and the X12 278 bridge the current stub explicitly does not do.
3. **Bedrock as the default provider** — the code path is done and tested; flipping `LLM_PROVIDER=bedrock` in the deploy config is the remaining step, plus enabling Knowledge Bases for the Policy Retriever instead of the local file corpus.
4. **A deployed worker**, always-on — so `run-async` is the primary path in every environment, not just where a worker happens to be running, and the dashboard's inline-fallback becomes the rare case instead of the common one.
5. **EHR integration** — a SMART-on-FHIR launcher so the intake step starts from the chart directly instead of an uploaded PDF.

---

## 📦 DDR handouts

Judge-ready PDFs in [`ddr/`](ddr):

| File | What it is |
|---|---|
| [`architecture-poster.pdf`](ddr/architecture-poster.pdf) | One-page architecture poster |
| [`ClinCase-AeroFyta_Brochure.pdf`](ddr/ClinCase-AeroFyta_Brochure.pdf) | Team + product brochure |
| [`compliance-&-trust-one-pager.pdf`](ddr/compliance-&-trust-one-pager.pdf) | CMS-0057-F + HIPAA alignment map |
| [`roi-tam-bm.pdf`](ddr/roi-tam-bm.pdf) | ROI / TAM / business model deck |
| [`sample-artifacts-booklet.pdf`](ddr/sample-artifacts-booklet.pdf) | Sample agent traces + appeal letter |

Full pitch script: [`pitch.md`](pitch.md).

---

## 📚 Glossary

<details>
<summary><b>Click to expand</b></summary>

| Term | Meaning |
|---|---|
| **CMS-0057-F** | CMS final rule mandating FHIR PA APIs by Jan 1, 2027 (89 FR 8758) |
| **Da Vinci PAS** | HL7 Prior Authorization Support Implementation Guide |
| **CRD / DTR** | Coverage Requirements Discovery / Documentation Templates & Rules — companion Da Vinci IGs |
| **FHIR R4** | HL7 Fast Healthcare Interoperability Resources, Release 4 |
| **X12 278** | HIPAA EDI prior-auth transaction set — CMS-0057-F requires payers to support FHIR by 2027; X12 278 conversion is not yet implemented here |
| **NCCN Compendium** | National Comprehensive Cancer Network — authoritative oncology drug-regimen reference |
| **LangGraph** | Directed-graph orchestration framework for multi-agent LLM workflows |
| **SSE** | Server-Sent Events — the one-directional streaming protocol the Live Agent Pipeline console reads |
| **RAG** | Retrieval-Augmented Generation — the Policy Retriever's core pattern |
| **HITL** | Human-in-the-loop — the reviewer queue a low-confidence case routes to instead of an automatic decision |
| **TriZetto** | Payer-IT platform (Facets, QNXT) — ClinCase's adapter sits upstream of it |
| **MELD-Na** | Liver transplant allocation score, relevant to the Hepatitis-C scalability case |

</details>

---

## 📂 Repository layout

```text
ClinCase/
├── frontend/                    # React 18 + Vite SPA
│   ├── src/
│   │   ├── routes/               # Dashboard, Cases, Intake, Landing, OncologyStack, ...
│   │   ├── components/           # AppShell, LivePipelineConsole, ReasoningTracePanel, ...
│   │   └── lib/                  # api.ts, usePipelineRun.ts, sse.ts, types.ts
│   └── LANDING/                  # earlier landing-page prototype (superseded by src/landing)
│
├── backend/                     # FastAPI - Python 3.11
│   ├── app/
│   │   ├── api/                  # cases, jobs, stream, oncology_stack, fhir_pas, ...
│   │   ├── agents/                # 7 agents + their sub-agent packages
│   │   ├── graph/                 # LangGraph DAG build + state
│   │   ├── llm/                   # provider-agnostic gateway: anthropic/openrouter/bedrock
│   │   ├── workers/                # case_runner.py - the async job consumer
│   │   ├── models/                 # Pydantic v2 contracts
│   │   └── prompts/                 # one system prompt per agent
│   └── tests/                    # 28 test files - agents, API contracts, framework
│
├── demo_pdfs/                    # 4 demo cases + 2 policy bundles
├── ddr/                          # judge-ready handouts (PDF)
├── ops/                          # deploy scripts + AWS deployment evidence
├── docs/                          # architecture notes
├── pitch.md                       # pitch script
└── README.md                      # you are here
```

---

## 🤝 Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## 🛡️ Security

Found a vulnerability? See [SECURITY.md](SECURITY.md). **Do not open a public GitHub issue.**

## 📄 License

Released under the **MIT License** — see [LICENSE](LICENSE).

---

<div align="center">

### ⭐ Star this repo if a prior-auth copilot that shows its work is worth building.

`Approve cancer treatment in minutes, not weeks.`

</div>
