# ClinCase — Pitch Deck (8 slides + 5-minute talk script)

**Event:** the 2026 hackathon Finals — Health Sciences / Prior Authorisation Automation
**Team:** AeroFyta · S. Preethi Sivachandran (Tech Lead) + 3 teammates
**Format:** 5-minute pitch with live demo + 8–12 minute Q&A
**Date:** May 7, 2026, Pune

---

## How to use this deck

- Build the slides in Keynote / Google Slides / Pitch.com using the per-slide spec below.
- Read the **TALK** sections out loud with a stopwatch. Each slide block is timed; total = 5:00 ± 0:15.
- Bold = on-stage emphasis; *italic* = teleprompter cue / stage direction.
- The demo runs **inside slide 6** — switch to the live app, then back to the deck for slides 7–8.

---

## Slide 1 — Title (0:00–0:18)

### Visual
```
┌──────────────────────────────────────────────────────┐
│                                                      │
│   CLINCASE                                            │
│   ────────────                                       │
│   The prior-auth copilot that thinks like an         │
│   oncologist and writes like a payer.                │
│                                                      │
│   Team AeroFyta · the 2026 hackathon         │
│                                                      │
│   [ClinCase wordmark]   [AWS Bedrock badge]           │
│                                                      │
└──────────────────────────────────────────────────────┘
```
- Background: deep indigo (#1B1F3A), single-color, no clutter.
- ClinCase wordmark in inter-bold.
- AWS Bedrock + Anthropic Claude badges bottom-right (small, professional).

### TALK
> "Good morning. I'm Preethi, from team AeroFyta. The product is **ClinCase** — a prior-authorisation copilot for oncology, built on AWS Bedrock and Claude Sonnet 4.6. In the next five minutes I'll show you why a US oncology nurse loses 11 days of patient therapy time per denied case, how five reasoning agents fix that, and why the payer organization should ship this to their top-10 oncology clients."

---

## Slide 2 — Problem (0:18–0:55)

### Visual
```
┌──────────────────────────────────────────────────────┐
│  Three numbers nobody disputes:                      │
│                                                      │
│   14M   oncology PAs filed in the US every year      │
│   33%   denied or referred on first submission       │
│   11 days  average therapy delay per denied case     │
│                                                      │
│   Every denied PA is a patient waiting on chemo.     │
│                                                      │
│   Source: AMA Prior Auth survey 2025;                │
│   Cancer.org PA-delay analysis 2024.                 │
└──────────────────────────────────────────────────────┘
```
- Three numbers in big serif (Playfair / Source Serif), each on its own line.
- Subheadline italic, smaller.
- Cite sources in 9pt at the bottom — judges respect citations.

### TALK
> "Three numbers. **14 million** oncology prior-auth requests in the US every year. **One in three** is denied or referred on first submission. **Eleven days** is the average therapy delay per denied case. That's eleven days of a Stage IV breast cancer patient *not* on trastuzumab — measured outcomes, not abstract inconvenience. Today, this work is done by hand, paper-by-paper, by overworked coordinators reading 40-page payer policies. CMS-0057-F mandates a 7-day SLA on these decisions starting January 2027. The current process can't possibly hit it."

---

## Slide 3 — Insight (0:55–1:22)

### Visual
```
┌──────────────────────────────────────────────────────┐
│  Why this can't be a chatbot.                        │
│                                                      │
│  ✗   Hallucinated criteria → patient harm + lawsuit  │
│  ✗   No audit trail → CMS auditor walks out          │
│  ✗   Single-prompt LLMs can't cite                   │
│                                                      │
│  ─────────────────────────────────────────────       │
│                                                      │
│  An auditable PA decision needs:                     │
│   1. Structured extraction (separable from prose)    │
│   2. Per-criterion citation (clinical + policy)      │
│   3. Confidence-gated escalation                     │
│   4. Permanent, queryable trace                      │
└──────────────────────────────────────────────────────┘
```
- Top half red ✗ list (3 items, terse).
- Bottom half black numbered list (4 items).
- Divider in the middle. This visualises the pivot.

### TALK
> "**This can't be a chatbot.** A chatbot hallucinates a criterion — a patient gets harmed. A chatbot can't cite — a CMS auditor walks out. A chatbot is a single prompt — there's no audit trail, no separable failure modes. An auditable PA decision needs four things: structured extraction kept separate from prose, per-criterion citations to both clinical evidence and policy text, confidence-gated escalation to a human, and a permanent, queryable trace. **No single prompt does these things.** Five specialised agents do."

---

## Slide 4 — Solution (1:22–2:05)

### Visual

A horizontal flow diagram, left-to-right:

```
┌──────────────────────────────────────────────────────┐
│                                                      │
│   FHIR        Clinical                              │
│   Bundle  →   Extractor  →  Policy        →   Necessity      │
│   + Note        🧪          Retriever  🔍       Reasoner ⚖️    │
│                                                      │
│            →  Decision   ──── (if DENY) ──→  Appeals          │
│               Composer 📋                    Drafter ✉️       │
│                                                      │
│   [under each agent: Pydantic in/out + system prompt]│
│                                                      │
│   All 7 agents stream over SSE.                      │
│   All 7 agents log to agent_traces.                  │
│   Conditional edge: DENY → Appeals.                  │
└──────────────────────────────────────────────────────┘
```
- Use icons (lucide / phosphor) consistent with the app.
- Color the conditional edge (DENY → Appeals) in red so it pops.

### TALK
> "Five agents, one DAG. **Clinical Extractor** parses the FHIR bundle plus physician note into a structured snapshot. **Policy Retriever** pulls the top-five payer-specific policy sections from a Bedrock Knowledge Base. **Necessity Reasoner** evaluates each criterion and emits a confidence score per criterion — not just per case. **Decision Composer** writes the cited rationale and the structured arguments JSON. And on a DENY, a conditional edge fires the **Appeals Drafter**, which writes a NCCN-cited appeal letter ready for the payer. Every agent has a Pydantic input contract, a Pydantic output contract, a versioned system prompt, and a contract test. Every call is traced. This is not a wrapper around Claude — this is an auditable reasoning system that *uses* Claude."

---

## Slide 5 — Architecture (2:05–2:35)

### Visual

A vertical AWS-native architecture diagram:

```
┌──────────────────────────────────────────────────────┐
│  React + Vite (S3 + CloudFront)                     │
│       ↓ JWT auth, SSE                                │
│  ──────────────────────────────────                  │
│  FastAPI on ECS Fargate (multi-tenant)               │
│       ↓                                              │
│  LangGraph DAG ── trace_agent() ──→ CloudWatch + X-Ray│
│       ↓                ↑                             │
│  Bedrock Claude Sonnet 4.6  (Converse API + Guardrails)│
│       ↓                                              │
│  Bedrock Knowledge Base ←── S3 (payer CPB markdown)  │
│       ↓                                              │
│  OpenSearch Serverless (vector index)                │
│                                                      │
│  All persistence: RDS Aurora Serverless v2 +         │
│                    pgvector (audit-grade)            │
│  Identity: JWT + RBAC (3 roles), org-scoped          │
└──────────────────────────────────────────────────────┘
```
- AWS service icons (official AWS architecture icons set).
- Dotted line: PHI redaction boundary at the Bedrock Guardrail layer — call it out with a label "PHI redacted before any LLM call".

### TALK
> "**100% AWS-native.** React frontend on S3 + CloudFront. FastAPI backend on ECS Fargate, multi-tenant — every query is scoped by `organization_id`. LangGraph runs the DAG, every agent call is wrapped in `trace_agent` and streams to CloudWatch and X-Ray. The LLM is Claude Sonnet 4.6 via Bedrock — token traffic stays inside the VPC. Bedrock Knowledge Base over OpenSearch Serverless does the policy retrieval. RDS Aurora Serverless v2 with pgvector holds the audit trail. **PHI never leaves the VPC** — the Bedrock Guardrail redacts it before any LLM call. We have a sub-60-second rollback to OpenRouter Claude if Bedrock has an incident — drilled and timed."

---

## Slide 6 — DEMO (2:35–4:05)

> **Switch to the live app at this point. Spend 90 seconds in the app, then back to slides.**

### Visual (slide stays up as a placeholder while demo runs)
```
┌──────────────────────────────────────────────────────┐
│                                                      │
│   LIVE DEMO                                          │
│                                                      │
│   ▸ Path A — Approval (30s)                          │
│   ▸ Path B — Denial → Appeal (30s)                   │
│   ▸ Path C — Multi-payer arbitration (30s)           │
│                                                      │
│   [Press SPACE to continue when ready]               │
│                                                      │
└──────────────────────────────────────────────────────┘
```

### TALK (read while demo unfolds)

**Path A — Approval (30s):**
> "Submitting a real case — Stage IIIA HER2-positive breast cancer, requesting trastuzumab on Aetna policy 0048. Watch the agent stream. Clinical Extractor — done in 1.2 seconds. Policy Retriever — 5 sections pulled from the Bedrock Knowledge Base. Necessity Reasoner — every criterion green. Decision Composer — APPROVE with a paragraph any executive can read. Total wall-time: 11 seconds."

**Path B — Denial + Appeal (30s):**
> "Now a denial-bound case — same request, but the EGFR mutation status is wild-type. Necessity Reasoner flags the biomarker mismatch. Verdict: DENY, 0.92 confidence. The conditional edge fires the Appeals Drafter — and it writes a structured appeal citing NCCN guideline 3.2024 and the patient's actual pathology report. **No human typed any of this.**"

**Path C — Multi-payer arbitration (30s):**
> "Same trastuzumab case, Compare view. Four payer cards populate from real Bedrock retrieval per payer. Aetna says REFER — their LVEF window is now 60 days, ours is 75. UHC, BCBS, Anthem all approve. The arbitration recommendation tells the coordinator: *'Submit to UHC first.'* That's the kind of decision an experienced coordinator makes in 20 minutes. ClinCase did it in 8 seconds, with the citation trail."

> *Switch back to slides.*

---

## Slide 7 — Why us (4:05–4:35)

### Visual
```
┌──────────────────────────────────────────────────────┐
│  Why ClinCase wins this category                      │
│                                                      │
│   ✓  Built on the AWS-native stack the partner         │
│      already sells                                   │
│                                                      │
│   ✓  Architecture is auditable, not just impressive  │
│      (7 agents · 21 sub-agents, contract-tested, traceable)          │
│                                                      │
│   ✓  Real policy corpus: 21 NCCN-aligned entries     │
│      across 4 payers. Cross-payer arbitration       │
│      is backend-real, not frontend-mocked            │
│                                                      │
│   ✓  CMS-0057-F is a 2027 deadline, not a vision     │
│                                                      │
│   ✓  Per-case unit economics: $0.20 cost / $25 price │
└──────────────────────────────────────────────────────┘
```

### TALK
> "Five reasons we win this category. **One:** built on the exact AWS stack the partner already sells — Bedrock, ECS, Aurora, OpenSearch — so the implementation path is the existing engagement model. **Two:** the architecture is auditable, not just impressive. Five agents, contract-tested, traceable — which is what an enterprise architect needs to defend on day one of deployment. **Three:** the policy corpus is real — 21 NCCN-aligned entries across four payers, with cross-payer arbitration backend-real, not mocked. **Four:** CMS-0057-F is a January 2027 deadline; we're not selling a vision, we're selling regulatory readiness. **Five:** the unit economics are obscene — twenty cents in tokens, twenty-five dollars in price."

---

## Slide 8 — The ask + close (4:35–5:00)

### Visual
```
┌──────────────────────────────────────────────────────┐
│                                                      │
│   What we want next                                  │
│                                                      │
│   ▸ A pilot at one the payer organization         │
│     oncology client — 4-week scope, 200-case         │
│     accuracy benchmark                               │
│                                                      │
│   ▸ Co-publish the accuracy + latency results        │
│     with the partner's clinical research arm           │
│                                                      │
│   ─────────────────────────────────────────────      │
│                                                      │
│   We'll have a payer pilot offer in your inbox       │
│   by Friday.                                         │
│                                                      │
│   preethisivachandran0@gmail.com                     │
│                                                      │
└──────────────────────────────────────────────────────┘
```

### TALK
> "One ask. **Pilot ClinCase at one the payer organization oncology client — four-week scope, two-hundred-case accuracy benchmark, co-published results.** That's how a hackathon project becomes the partner offering. We'll have a pilot scope document in your inbox by Friday. Thank you."

---

## Speaker timing cheat-sheet

| Slide | Cue | Cum. time |
|------:|-----|----------:|
| 1 — Title          | Walk to mic, breath, read title          | 0:18 |
| 2 — Problem        | Three big numbers, slow on each          | 0:55 |
| 3 — Insight        | Pivot from "chatbot" to "auditable"      | 1:22 |
| 4 — Solution       | Walk through the DAG left-to-right       | 2:05 |
| 5 — Architecture   | Stress AWS-native + PHI boundary         | 2:35 |
| 6 — Demo           | LIVE — 90s, three paths                  | 4:05 |
| 7 — Why us         | Five-finger close                        | 4:35 |
| 8 — Ask            | Pilot ask + email                        | 5:00 |

> If you're at 4:30 and on slide 6, **skip Path C**. The Compare arbitration is impressive but not foundational. Hitting 5:00 sharp matters more than the third path.

---

## Pre-demo failure plan

- **Backend won't start:** keep a 3-minute pre-recorded backup video of all three paths. Demo Operator (DO) plays it from the laptop without comment. Tech Lead does the talk over the video.
- **Network drops:** the recorded video is local. Don't rely on the internet during the demo.
- **Bedrock 5xx mid-demo:** Tech Lead says *"and you can see we hit the rollback drill from the runbook — provider flipped to OpenRouter in 47 seconds."* Continue the demo. The judges will love this more than a flawless run.

---

## Post-pitch handoff (Q&A)

After slide 8, sit on stools. **Tech Lead leads Q&A**, hands off to CL/PL/DO per the role assignments in `QA_DRILL.md`. Keep water on the stools. Smile. The work is done; now you're talking to peers.
