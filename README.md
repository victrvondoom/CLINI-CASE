# CLINI-CASE One Health Interoperability Gateway

CLINI-CASE is a OneAquaHealth Track 7 interoperability gateway.

Environmental, laboratory and health systems often use incompatible schemas and terminology. CLINI-CASE discovers source fields, suggests constrained semantic mappings, and requires an authenticated human reviewer to approve them before generating an OAH/FHIR exchange. Application-level validation can block invalid data before transfer.

An independent System B process receives the Bundle over HTTP, validates and stores it, changes resource IDs and references, then returns it for semantic round-trip verification. The Evidence Passport records mapping decisions, validation, transfer acknowledgement, hashes and round-trip results. The Track 7 journey uses synthetic data and does not infer health causation.

The interoperability workflow has no cloud dependency. Docker and kind files are a small optional deployment showcase; AWS and Bedrock remain optional adapters, not prerequisites. Existing oncology, OncoTwin, CardioTwin and AquaHealth functionality remains available through the same application.

**OneAquaHealth IEEE Global Hackathon — Track 7: Digital Health Standards.** Start at `/onehealth`; use `/interop` for the cross-system demonstration. The previous platform landing page is retained at `/platform`.

[![CI](https://github.com/victrvondoom/CLINI-CASE/actions/workflows/ci.yml/badge.svg)](https://github.com/victrvondoom/CLINI-CASE/actions/workflows/ci.yml)

Citizen observation ? laboratory evidence ? human mapping review ? FHIR/OAH validation ? independent receiver ? consented clinical context ? new retest ? verified return exchange.

The flagship story uses a persisted **Evidence Passport**, a computed **epistemic ceiling** and six evidence gates. These connect the existing capabilities into one evidence journey. A stream photo cannot establish arsenic exposure; imported consent and verification are not automatically trusted. Environmental evidence never changes cancer authorization or OncoTwin/CardioTwin model inputs.

Run `./start-track7.ps1` for the complete synthetic, deterministic reference journey. The launcher starts separate application/receiver processes, generates private demo credentials and records actual runtime metrics. Optional `-AI` uses the existing governed provider; the current credential was rejected, so live AI remains unverified.

- [Demo runbook](docs/DEMO_RUNBOOK.md) and [manual items remaining](docs/TRACK7_MANUAL_CHECKLIST.md)
- [Track 7 architecture and APIs](docs/ONEHEALTH_TRACK7.md)
- [Evidence Passport](docs/EVIDENCE_PASSPORT.md), [epistemic ceiling](docs/EPISTEMIC_CEILING.md) and [conformance statement](docs/OAH_CONFORMANCE.md)
- [Verification](docs/TRACK7_HARDENING_VERIFICATION.md), [build scope / AI assistance](docs/HACKATHON_BUILD_SCOPE.md) and [self-audit](docs/TRACK7_SELF_AUDIT.md)

**Validation scope:** FHIR R4-targeted exchange with selected pinned OAH constraints, local contract checks and semantic round-trip tests. A prior core-only validator result (0 errors, 22 warnings and 7 informational messages) used a different fixture and did not load the OAH package or terminology; it is not evidence for the current generated Bundle. Full OAH validation is currently not run because the local Java/validator and immutable guide package are unavailable. No HL7 certification is claimed. See [the validation record](docs/track7/VALIDATION.md). All demo data is synthetic; no real pilot or clinical-performance claim is made.

**License:** [proprietary terms](LICENSE) are unchanged. The owner is credited by the existing license/history. You confirmed authorization exists; judges' signed run/review rights still need documentary verification. See [judge access](docs/JUDGE_ACCESS.md). Public availability alone grants no license.

The following sections retain the existing platform reference documentation. This hardening phase did not create the entire repository; the dated build-scope document describes reuse and additions accurately.

## Contents

- [ClinCase One Health — primary OneAquaHealth Track 7](docs/ONEHEALTH_TRACK7.md)
- [AquaHealth Sentinel — supporting OneAquaHealth Track 3](docs/AQUAHEALTH_TRACK3.md)
- [Why ClinCase](#-why-clincase)
- [What it does](#-what-it-does)
- [Try the four reference cases](#-try-the-four-reference-cases)
- [Live Agent Pipeline console](#-live-agent-pipeline-console)
- [Architecture](#%EF%B8%8F-architecture)
- [The 7-agent pipeline](#-the-7-agent-pipeline)
- [Oncology capabilities](#-oncology-capabilities)
- [OncoTwin: the patient digital twin](#-oncotwin-the-patient-digital-twin)
- [Beyond oncology](#-beyond-oncology)
- [Tech stack](#%EF%B8%8F-tech-stack)
- [Regulatory alignment](#-regulatory-alignment)
- [FHIR / Da Vinci PAS conformance](#-fhir--da-vinci-pas-conformance)
- [Audit trail](#-audit-trail)
- [Business case](#-business-case)
- [Getting started](#-getting-started)
- [Roadmap](#%EF%B8%8F-roadmap)
- [Repository layout](#-repository-layout)
- [Glossary](#-glossary)

---

## 🩺 Why ClinCase

```text
13 hours / week           29% of physicians           80.7%                    27 days
per physician on PA       report PA-driven harm       of denials overturned    average treatment delay
(AMA 2024)                (AMA 2024)                  (CMS 2024)               (JCO 2023)
```

Prior authorization (PA) is the largest administrative burden in US oncology. It costs an estimated **$35B a year**, takes about **13 hours a week per physician**, and **29% of physicians report that a PA delay led to a serious adverse event**. The CMS-0057-F final rule requires FHIR-native PA APIs from **January 1, 2027**, with **72-hour expedited and 7-day standard** decision windows. Most payers and providers are not ready.

| Metric | Value | Source |
|---|---|---|
| Hours per week per physician on PA | **13** | AMA Prior Auth Survey 2024 |
| PA requests per physician per week | **39** | AMA 2024 |
| Physicians reporting PA-caused care delay | **93%** | AMA 2024 |
| Physicians reporting PA-caused serious adverse events | **29%** | AMA 2024 |
| Annual US PA administrative spend | **$35B** | Sahni et al., *Health Affairs* / McKinsey |
| Average oncology treatment delay on a denial | **27 days** | *Journal of Clinical Oncology* 2023 |
| Denials overturned on appeal | **80.7%** | CMS Medicare Advantage data |
| Denials that are ever appealed | **11.7%** | CMS Medicare Advantage data |
| CMS-0057-F FHIR PA API deadline | **Jan 1, 2027** | 89 FR 8758 |

Payers deny, four out of five of those denials are overturned when appealed, and only about one in nine denials is ever appealed, because the appeal process costs a coordinator too much time.

---

## 💡 What it does

ClinCase takes a clinical packet (a chart note, a pathology report or a payer PDF) and returns a structured determination: **`APPROVE`**, **`DENY`** or **`REFER`**, with a citation for every criterion. When the verdict is DENY, it drafts an NCCN-grounded appeal letter from the same evidence.

```text
  Chart note, pathology report or payer packet arrives
    → identifiers screened and minimized, with a receipt, before model calls
    → ClinicalSnapshot (typed Pydantic, FHIR R4)
    → 7-agent LangGraph DAG, streamed live over SSE
    → APPROVE / DENY / REFER + full citation chain
    → On DENY: NCCN-grounded appeal letter drafted automatically
    → Low-confidence cases go to a human reviewer
    → Every agent step persisted; SHA-256 evidence pack per case
```

The goal is to shorten the work between intake and a reviewable verdict. Production latency depends on the configured models, evidence sources, and workload and must be measured in each deployment. ClinCase does not submit anything on its own. Low-confidence cases wait in a reviewer queue, and a coordinator sees every step.

---

## 🎬 Try the four reference cases

After [getting started](#-getting-started), open `/dashboard` and use the **Live Agent Pipeline** console. Or sign in and upload one of these under **Drop a scan**:

| # | Sample PDF | Verdict | What it shows |
|---|---|---|---|
| 1 | [`01_APPROVE_breast_cancer_her2pos.pdf`](demo_pdfs/01_APPROVE_breast_cancer_her2pos.pdf) | ✅ **APPROVE** | HER2 IHC 3+, FISH-amplified, LVEF 62%, ECOG 1: every Aetna 0048 criterion met |
| 2 | [`02_DENY_breast_cancer_lvef_low.pdf`](demo_pdfs/02_DENY_breast_cancer_lvef_low.pdf) | ❌ **DENY** | LVEF 32% plus prior anthracycline: cardiotoxicity contraindication, FDA Black Box warning, risk flags raised |
| 3 | [`03_REFER_breast_cancer_her2_equivocal.pdf`](demo_pdfs/03_REFER_breast_cancer_her2_equivocal.pdf) | ⚠️ **REFER** | HER2 IHC 2+ equivocal, FISH not yet performed: sent to the reviewer queue instead of guessing |
| 4 | [`04_APPROVE_hepc_daa_genotype1.pdf`](demo_pdfs/04_APPROVE_hepc_daa_genotype1.pdf) | ✅ **APPROVE** | Same agents, different disease: Hepatitis C, AASLD-IDSA guidelines |

Two payer policy bundles support case 4:

- [`policy_aetna_hcv_daa.pdf`](demo_pdfs/policy_aetna_hcv_daa.pdf): Aetna CPB 0860 (DAA therapy criteria)
- [`policy_aetna_liver_transplant.pdf`](demo_pdfs/policy_aetna_liver_transplant.pdf): Aetna CPB 0596 (MELD-Na, Milan criteria)

---

## 🧬 Live Agent Pipeline console

Most prior-auth tools show only the verdict. The ClinCase dashboard also shows the agents working on it.

The backend streams per-agent progress over Server-Sent Events and saves every step to Postgres: `agent_started`, `agent_finished` and `agent_error` events, with latency, model ID and token counts, one row per agent per case (`backend/app/observability/trace.py`, `backend/app/api/stream.py`). The dashboard console shows that stream. Pick a reference case and watch all seven agents, and the sub-agents under them, move from pending to running to done. The console uses the same authenticated, org-scoped stream as the case-detail page.

The console reports failures plainly. A partial run shows as `completed with errors`, `ended early` or `awaiting review`, never as a green "complete". If no queue worker is attached, the console runs the pipeline inline instead of waiting on an empty queue. If the stream drops mid-run, the console rebuilds the run from the saved audit trail.

---

## 🏛️ Architecture

### Five layers

```mermaid
flowchart TB
    subgraph EX["Layer 1 - Experience"]
        UI["React 18 + Vite SPA"]
        FAB["FAB 'New Case' modal + Drop-a-scan intake"]
        TRACE["Live Agent Pipeline console (SSE, org-scoped, auth'd)"]
    end

    subgraph ORCH["Layer 2 - Orchestration"]
        LG["LangGraph DAG (7 agents - 22 sub-agents - conditional edges)"]
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
        SCORE["Compliance and ROI scorecards (computed from real rows)"]
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

### How a run executes

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

A queued job with no worker attached would otherwise sit at `status=queued` indefinitely. The console detects this and falls back to the synchronous path.

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

For a deeper walkthrough, see [ARCHITECTURE.md](ARCHITECTURE.md).

---

## 🤖 The 7-agent pipeline

| # | Agent | Purpose | Model | Output (typed) |
|---|---|---|---|---|
| 1 | **Clinical Extractor** | Parses FHIR and the physician note into a structured snapshot. Uses 3 sub-agents: FHIR validator, PHI sanitizer, biomarker specialist | Haiku 4.5 | `ClinicalSnapshot` |
| 2 | **Policy Retriever** | Retrieves the payer's current policy excerpts for the requested treatment | Haiku (rerank) | `PolicyExcerpt[]` |
| 3 | **Necessity Reasoner** | Marks every policy criterion MET, NOT-MET or UNDOCUMENTED | Sonnet 4.6 | `NecessityAssessment` |
| 4 | **Decision Composer** | Produces the verdict and the citation chain behind it | Sonnet 4.6 | `Decision` |
| 5 | **Denial Forecaster** | Estimates denial risk and likely reasons before submission | Sonnet 4.6 | `DenialForecast` |
| 6 | **Appeals Drafter** *(DENY branch only)* | Drafts an NCCN-grounded appeal letter | Sonnet 4.6 | `AppealDraft` |
| 7 | **Patient Communicator** | Explains the verdict and next steps in plain language | Haiku 4.5 | `PatientCommunication` |

Orchestration is a [LangGraph](https://github.com/langchain-ai/langgraph) `StateGraph` (`backend/app/graph/build.py`), not a hand-rolled loop. A conditional edge after `necessity_reasoner` routes to a human-in-the-loop review gate. A second conditional edge after `denial_forecaster` sends a DENY to the Appeals Drafter and an APPROVE or REFER to patient communication. Every agent has a typed Pydantic input and output, a system prompt under `backend/app/prompts/`, and a contract test under `backend/tests/agents/`.

Each of the 7 agents is built from 2 to 4 focused sub-agents, 21 in total. For example, the Clinical Extractor's `fhir_resource_validator` and `phi_sanitizer` are deterministic Python that run in under 10 ms with no LLM call, while `biomarker_specialist` calls the model. Every sub-agent publishes its own `agent_started` and `agent_finished` events, which drive the console's per-agent progress bars.

---

## 🏆 Oncology capabilities

Each capability is a callable endpoint under `/api/v1/oncology-stack/*` (`backend/app/api/oncology_stack.py`):

| # | Capability | Endpoint |
|---|---|---|
| 1 | 📚 **OncoGuideline Engine**: NCCN/ASCO guideline search | `GET /guidelines/search` |
| 2 | 🧬 **Genomic parsing**: biomarker extraction and regimen lookup by variant | `POST /genomic/parse`, `GET /genomic/regimens` |
| 3 | 🛡️ **Denial prediction and appeal drafting** | `POST /denial/predict`, `POST /appeal/draft` |
| 4 | 📡 **Da Vinci PAS / CRD / DTR**: FHIR submission and coverage discovery hooks | `POST /davinci/pas/submit`, `/davinci/crd`, `/davinci/dtr/questionnaire` |
| 5 | 🧾 **Peer-to-peer briefing kit**: a 1-page PDF for the physician's P2P call | `POST /p2p/briefing-kit` |
| 6 | 💬 **Off-label justification**: a proposer, opponent and judge multi-agent debate | `POST /off-label/justify` |
| 7 | 🔗 **Bundled regimen PA**: one authorization request covers a whole NCCN regimen | `GET /regimen/templates`, `POST /regimen/bundle` |
| 8 | 💰 **Site-of-care cost comparison**: hospital, office or home infusion | `POST /site-of-care/compare` |
| 9 | 🔄 **Multi-payer policy reconciler**: tracks policy changes across payers | `GET /policies/diffs`, `POST /policies/reconcile` |
| 10 | 🔐 **Tamper-evident audit chain**: see [Audit trail](#-audit-trail) | `GET /audit/trail`, `GET /audit/trail/{id}` |

---

## 🫀 OncoTwin: the patient digital twin

ClinCase decides whether a treatment is approved. **OncoTwin** watches the patient between visits. It keeps a per-patient model measured against the patient's own baseline and flags when their trajectory changes. It estimates risk only at horizons the data supports, simulates what-if scenarios, and passes findings a clinician has accepted into the ClinCase prior-auth workflow.

OncoTwin is an **add-on layer**. The 7-agent pipeline, its endpoints, FHIR handling and audit tables are unchanged, and a test pins that (`backend/tests/oncotwin/test_twin.py::test_clincase_seven_agent_architecture_is_unchanged`).

**What it models.** `OT-ACUTE-7`: an unplanned ED visit or admission for one of the 10 CMS OP-35 chemotherapy-related conditions within 7 days, plus 24-hour and 72-hour horizons. It does not offer a 6-hour horizon because its signals are daily aggregates.

**Seven core capabilities**

| Capability | What it does |
|---|---|
| Living Twin State | 19 dimensions tracked daily. Each state is SHA-256 hashed and never overwritten, with a transition ledger and hysteresis to stop flapping |
| Personalised baseline | Robust median ± MAD per signal, so every deviation is expressed in the patient's own standard deviations |
| Multimodal fusion | EHR, pathology, genomics, labs, treatment, wearables, home devices and patient-reported symptoms, feeding a 42-feature store with lineage |
| Trajectory and change points | Bayesian online change-point detection, cross-signal lead/lag, and a multi-horizon survival model |
| What-if and counterfactual | 64 Monte Carlo runs per scenario (antibiotics, hydration, G-CSF, dose changes) and a "nothing changed" counterfactual |
| Twin Memory | Deterioration and recovery per cycle, ANC nadir, and similarity between cycles |
| ClinCase handoff | Explainable alerts, safety gates and clinician review before anything reaches prior auth |

**Measured on synthetic data.** On a held-out set of 200 synthetic patients, the multimodal twin reached **AUROC 0.866 [0.832, 0.902]** and alerted before **39 of 40** events, with a median lead of **4 days**. Population vital-sign thresholds caught 12 of 40 events. All patients, signals and outcomes are simulated and tagged `SYNTHETIC`, so these numbers show that the method works end to end, not that it performs clinically. OncoTwin is clinical decision support: it never diagnoses, orders or submits anything, and a clinician reviews every alert.

Full details, including limitations, are in [docs/ONCOTWIN.md](docs/ONCOTWIN.md). In the app, go to **Digital twin** in the sidebar (`/twin`).

---

## 🫀 CardioTwin: vessel-level cardiovascular risk

CardioTwin estimates the probability of angiographic CAD and of stenosis in the LAD, LCX and RCA from clinical,
ECG, laboratory and echo features, and shows them on an interactive schematic 3D heart at `/cardiotwin`.
It is deliberately honest about what a 303-patient tabular dataset can support: probabilities are calibrated and
drawn with their uncertainty, an out-of-cohort profile triggers a warning instead of false confidence, every
explanation and what-if is an exact re-evaluation of an integrity-checked model, and the view never claims to show
*where* a lesion is. **Decision support / educational only — not a substitute for diagnostic imaging.**
Reproduce with `make cardio.train` and `make cardio.test`; full write-up in [`docs/CARDIOTWIN.md`](docs/CARDIOTWIN.md).

## 🌍 Beyond oncology

ClinCase is not limited to oncology. The same agents and retrieval pipeline work on any prior-auth problem that has a payer policy and a body of clinical evidence. Reference case 4 shows this with **Hepatitis C direct-acting antiviral therapy**: the same seven agents and the same code path, with a different policy corpus and guideline set (AASLD-IDSA instead of NCCN).

```mermaid
flowchart TB
    A["ClinCase Core (7-agent DAG - policy retrieval - FHIR R4)"]:::core

    A --> B1[Oncology - NCCN]
    A --> B2[Hepatitis-C / DAA therapy - AASLD-IDSA - Aetna CPB 0860]
    A --> B3[Liver transplantation - Aetna CPB 0596 - MELD-Na - Milan]
    A --> B4[Specialty pharmacy - biosimilars, step therapy]
    A --> B5[Behavioural health - parity-law criteria]

    classDef core fill:#0b3d91,color:#fff,stroke:#0b3d91,stroke-width:2px
    classDef leaf fill:#dbeafe,stroke:#1d4ed8,color:#0f172a
    class B1,B2,B3,B4,B5 leaf
```

Add a new payer policy to the corpus and the Policy Retriever uses it on the next run.

---

## 🛠️ Tech stack

<table>
<tr>
<td valign="top" width="34%">

### Backend
- **Python 3.11**, typed throughout
- **FastAPI**, async
- **Pydantic v2**: every agent contract is a typed model
- **LangGraph**: the 7-agent DAG with conditional edges
- **`boto3`**: Bedrock Converse API, S3, Textract, SNS, Amazon Q Business
- **asyncpg**: raw SQL over a Postgres pool, no ORM
- **Server-Sent Events** (`sse_starlette`): authenticated live agent trace
- **`ruff` + `mypy --strict`** in CI

</td>
<td valign="top" width="33%">

### Frontend
- **React 18** + React Router 6
- **TypeScript 5.6**, strict
- **Vite 5**
- **Tailwind CSS**: token-driven light and dark themes
- **`lucide-react`** icons
- **EventSource / SSE**: live pipeline console with bounded reconnect
- **JWT auth**, org-scoped

</td>
<td valign="top" width="33%">

### LLM layer
- **Provider-agnostic gateway**: Anthropic, OpenRouter or Bedrock behind one interface (`backend/app/llm/factory.py`)
- **Default provider: OpenRouter** (`LLM_PROVIDER=openrouter`). Bedrock is fully implemented and one variable away
- **Bedrock path**: Converse API and `converse_stream`, Claude Sonnet 4.6 and Haiku 4.5, optional Guardrails when `BEDROCK_GUARDRAIL_ID` is set
- **Model IDs**: `apac.anthropic.claude-sonnet-4-6-20251022-v1:0`, `apac.anthropic.claude-haiku-4-5-20251001-v1:0`

</td>
</tr>
</table>

---

## 📜 Regulatory alignment

| Regulation / standard | What it requires | How ClinCase addresses it today |
|---|---|---|
| **CMS-0057-F** (89 FR 8758) | FHIR PA APIs, 72h expedited / 7d standard, Jan 1 2027 | `POST /fhir/Claim/$submit` is a partial Da Vinci PAS contract. It accepts PAS-shaped Bundles and transactionally queues the agent DAG. Full IG validation, synchronous verdict response, and X12 278 conversion are not built yet. |
| **HIPAA** | PHI safeguards, audit, access control | Org-scoped JWT auth on every case route, including the SSE stream. Optional Bedrock Guardrails PHI redaction when configured |
| **Human-in-the-loop review** | A clinician can intervene on a low-confidence or adverse determination | HITL gate in the LangGraph DAG: `POST /cases/{id}/resume`, `POST /cases/{id}/review`, and a `/reviewer` queue in the frontend |
| **HL7 Da Vinci CRD / DTR** | Coverage discovery and auto-filled PA forms | Endpoint stubs exist (`/davinci/crd`, `/davinci/dtr/questionnaire`), with the same caveat as PAS above |
| **ASCO/CAP HER2 Testing Guideline 2023** | Equivocal IHC 2+ requires reflex FISH before HER2-targeted therapy | Encoded in the Necessity Reasoner's inclusion logic. This rule produces reference case 3's REFER verdict |

---

## 🧾 FHIR / Da Vinci PAS conformance

- **PAS-shaped queue contract**: `POST /fhir/Claim/$submit` accepts a Da Vinci PAS-shaped `Bundle`, extracts treatment, diagnosis and payer, transactionally creates a case and worker job, and returns a queued `ClaimResponse`. It does not synchronously return a verdict and does not yet implement full IG validation, identifier signing, subscriptions, or X12 278 conversion.
- **CRD / DTR**: endpoint stubs, with the same caveat.
- **X12 278**: not implemented yet. It is on the roadmap.

Endpoints are served under `/api/v1/fhir/*`.

---

## 🔐 Audit trail

ClinCase has two tamper-evidence mechanisms at different levels of maturity.

**Persisted and production-shaped.** Every agent call writes a row to the Postgres `agent_runs` table with the agent name, model ID, input and output tokens, latency, start and finish times, and any error text (`backend/app/observability/trace.py`). The per-case **evidence pack** (`GET /cases/{id}/evidence-pack`) re-serializes that data in canonical form and computes a `bundle_sha256` over it, plus a separate decision-level hash. A third party can re-hash the bundle to confirm nothing changed after the fact (`backend/app/api/evidence_pack.py`).

**Working, but a prototype.** The chained audit trail (`GET /audit/trail`) links each record to the SHA-256 hash of the previous one, so edits are detectable. It is held in an **in-process Python list**, not the database, so it resets on restart and is not shared across replicas. The next step is to anchor each entry in QLDB or an append-only S3 Object Lock bucket.

---

## 💵 Business case

The figures below start from **cited external sources** and apply them to a modeled 50-physician oncology practice with 10,000 PA requests a year. They are the economics the product is designed to deliver, not results measured in a production deployment.

| Lever | Manual baseline (cited) | ClinCase target | Modeled annual gain |
|---|---|---|---|
| Time to decision | Establish from the deployment's current workflow | Measure through agent traces and queue telemetry | Calculate only from observed workload data |
| Appeals | 80.7% of appealed denials are overturned (CMS), but only 11.7% of denials are appealed | An NCCN-grounded appeal letter is drafted for every DENY, so appealing takes little extra effort | Recovers revenue now lost to denials nobody had time to appeal |
| Compute cost per case | n/a | Sonnet 4.6 and Haiku 4.5 on Bedrock at published per-token prices | A few dollars per case at list price, before prompt caching |

The underlying problem accounts for about **$35B a year in US PA administrative spend** (Sahni et al.).

---

## 🚀 Getting started

### Prerequisites

- Docker Desktop (for Postgres, and optionally Redis)
- Node 20+ and npm
- Python 3.11+
- An API key for **one** of Anthropic, OpenRouter or AWS Bedrock, with access to Claude Sonnet 4.6 and Haiku 4.5

### Start the stack

```bash
git clone https://github.com/victrvondoom/CLINI-CASE.git
cd CLINI-CASE
cp .env.example .env                  # then fill in your provider key

# 1. Postgres (Redis is optional and only needed for multi-replica SSE fan-out)
docker compose up -d postgres

# 2. Backend
cd backend
pip install -e .
export DATABASE_URL=postgresql://clincase:clincase@localhost:15432/clincase
export LLM_PROVIDER=openrouter        # or anthropic / bedrock
export OPENROUTER_API_KEY=sk-...      # the key for the provider you chose
alembic upgrade head
uvicorn app.main:app --reload --port 8000

# 3. Frontend (second terminal)
cd ../frontend
npm ci
npm run dev   # http://localhost:5173, proxies /api to :8000
```

On first boot, the backend seeds three accounts: an admin, a reviewer and a coordinator. Their addresses are in `backend/app/main.py`. They share the password set by `DEMO_USER_PASSWORD`, which has no default. Seeding requires an explicitly configured nonempty development password. The Track 7 launcher generates a private reviewer account; review existing accounts before exposing the app. Sign in, open `/dashboard`, and run a reference case in the **Live Agent Pipeline** console.

> [!NOTE]
> `docker compose up -d` on its own starts only Postgres and Redis. The `backend` and `frontend` services run with `docker compose --profile full up`. For local development, running them directly gives you hot reload.
>
> `POST /cases/{id}/run-async` needs a worker consuming the queue: run `python -m app.workers.case_runner` in a third terminal. Without a worker, the dashboard console detects the stall and falls back to the synchronous `/run` endpoint.

### OncoTwin

OncoTwin needs no database and no LLM key. From the repository root:

```bash
make twin.test        # OncoTwin unit, integration, API/RBAC and end-to-end tests
make twin.demo        # flagship patient journey in one command (synthetic data)
make twin.stress      # red-team stress test; exits non-zero on any unsafe result
make twin.benchmark   # Research Lab benchmark
```

### Tests and checks

```bash
make backend.test              # deterministic offline core suite (default)
make backend.test.integration  # PostgreSQL-backed API contracts
make backend.test.live         # metered model-provider contracts; requires credentials
make backend.test.all          # every test; requires PostgreSQL and model credentials
make backend.lint              # blocking Ruff + scoped strict mypy
make frontend.build            # TypeScript + production build
```

Plain `pytest` uses the same deterministic offline selection as
`make backend.test`: tests marked `integration` or `live` are excluded. CI runs
that core suite on every change and runs the PostgreSQL integration group in a
separate job with an initialized pgvector database. Live tests remain explicit
because they make metered external model calls. See
[`docs/TESTING.md`](docs/TESTING.md) for marker rules, prerequisites, and exact
commands.

---

## 🛣️ Roadmap

In rough priority order:

1. **Durable audit chain**: move the hash chain from an in-process list to the persisted `agent_runs` rows or an append-only store, so it survives restarts and replica failover.
2. **Full Da Vinci PAS conformance**: IG profile validation and the X12 278 bridge.
3. **Bedrock as the default provider**: the code path is done and tested. The remaining work is setting `LLM_PROVIDER=bedrock` in deployment and moving the Policy Retriever to Bedrock Knowledge Bases.
4. **An always-on worker**: make `run-async` the primary path in every environment, so the inline fallback is rare.
5. **EHR integration**: a SMART on FHIR launcher so intake starts from the chart instead of an uploaded PDF.
6. **OncoTwin on real cohorts**: validation on real longitudinal patient data before any clinical use.

---

## 📂 Repository layout

```text
.
├── frontend/                    # React 18 + Vite SPA
│   └── src/
│       ├── routes/              # Dashboard, Cases, Intake, Twin*, OncologyStack, ...
│       ├── components/          # AppShell, LivePipelineConsole, ReasoningTracePanel, ...
│       ├── oncotwin/            # OncoTwin UI
│       └── lib/                 # api.ts, usePipelineRun.ts, sse.ts, types.ts
│
├── backend/                     # FastAPI, Python 3.11
│   ├── app/
│   │   ├── api/                 # cases, jobs, stream, oncology_stack, fhir_pas, oncotwin, ...
│   │   ├── agents/              # 7 agents and their sub-agent packages
│   │   ├── graph/               # LangGraph DAG build and state
│   │   ├── llm/                 # provider-agnostic gateway: anthropic / openrouter / bedrock
│   │   ├── oncotwin/            # digital twin engine, intelligence, safety gates
│   │   ├── workers/             # case_runner.py, the async job consumer
│   │   ├── models/              # Pydantic v2 contracts
│   │   └── prompts/             # one system prompt per agent
│   └── tests/                   # agents, API contracts, framework, OncoTwin
│
├── demo_pdfs/                   # 4 reference cases + 2 policy bundles
├── docs/                        # product docs, including ONCOTWIN.md
├── ops/                         # deployment scripts, Terraform, Kubernetes, SRE runbooks
├── docker-compose.yml
├── Makefile
└── README.md
```

---

## 📚 Glossary

<details>
<summary><b>Show glossary</b></summary>

| Term | Meaning |
|---|---|
| **CMS-0057-F** | CMS final rule requiring FHIR PA APIs by Jan 1, 2027 (89 FR 8758) |
| **Da Vinci PAS** | HL7 Prior Authorization Support Implementation Guide |
| **CRD / DTR** | Coverage Requirements Discovery / Documentation Templates & Rules, companion Da Vinci IGs |
| **FHIR R4** | HL7 Fast Healthcare Interoperability Resources, Release 4 |
| **X12 278** | HIPAA EDI prior-auth transaction set. X12 278 conversion is not implemented here yet |
| **NCCN Compendium** | National Comprehensive Cancer Network's reference for oncology drug regimens |
| **LangGraph** | Directed-graph orchestration framework for multi-agent LLM workflows |
| **SSE** | Server-Sent Events, the one-way streaming protocol behind the Live Agent Pipeline console |
| **RAG** | Retrieval-Augmented Generation, the Policy Retriever's core pattern |
| **HITL** | Human-in-the-loop: the reviewer queue that low-confidence cases go to |
| **TriZetto** | Payer IT platform (Facets, QNXT). The ClinCase adapter sits upstream of it |
| **OP-35** | CMS measure of ED visits and admissions after outpatient chemotherapy, used as OncoTwin's outcome |
| **MELD-Na** | Liver transplant allocation score, used in the Hepatitis C case |

</details>

---

## 🤝 Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## 🛡️ Security

To report a vulnerability, see [SECURITY.md](SECURITY.md). **Do not open a public GitHub issue.**

## 📄 License

Copyright © 2026 **vsrupeshkumar**. **All rights reserved.** This is proprietary software, not open-source software.
No permission is granted to use, copy, modify, distribute, deploy, host, sublicense, sell, or create derivative works
unless the user has prior written authorization in an agreement signed by vsrupeshkumar and the authorized person or
entity. See [LICENSE](LICENSE) for the complete terms.

---

<div align="center">

**ClinCase** is designed and built by **[vsrupeshkumar](https://github.com/vsrupeshkumar)**.

`Approve cancer treatment in minutes, not weeks.`

</div>


### Track 7: OneAquaHealth interoperability gateway

Fragmented environmental and health systems send data in incompatible schemas. The `/interop`
workbench performs schema discovery, constrained deterministic/optional AI mapping, authenticated
human approval, OAH/FHIR generation, and local validation before transfer. Invalid data is blocked.
An independent System B process exchanges the Bundle over HTTP, reassigns resource IDs and updates
references; CLINI-CASE decodes the returned Bundle and compares normalized semantic fields. The
Evidence Passport records the journey and its evidence.

A generic `arsenic` label never implies chemical speciation. The pinned OAH CI guide supports the
exact dissolved-arsenic term, while other concepts remain text-only unless source evidence and a
verified terminology mapping support them. This is custom, partial contract validation—not full
HL7/OAH profile validation or certification. See the [validation record](docs/track7/VALIDATION.md)
and [conformance note](docs/track7/CONFORMANCE.md). The existing `/onehealth`, oncology, OncoTwin,
CardioTwin and AquaHealth workflows remain intact.

Run `python backend/scripts/track7_network_demo.py` for the separate-process HTTP proof. For the
interactive workbench use `./start-track7.ps1 -SQLite`; the service runs locally with synthetic
data and no cloud dependency. Docker/kind are optional showcase material; AWS and Bedrock remain
optional and are not required. The [4:40 interoperability demo script](docs/track7/DEMO_SCRIPT.md)
reserves only the final 20 seconds for deployment portability.
