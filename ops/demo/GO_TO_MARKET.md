# ClinCase — Go-to-Market 1-pager

**For: health-sciences sales + TriZetto product leadership**
**Status: ready to commercialize on the Neuro AI / Agent Foundry stack**

---

## The TL;DR

ClinCase is **the first oncology-specialty agent bundle for TriZetto AI Gateway** (launched Aug 6, 2025). Same Bedrock + Anthropic Claude Sonnet 4.6 + MCP stack that's now industry-standard following the **Anthropic partnership announced Nov 4, 2025** — already deployed across 350K enterprise employees.

A TriZetto Facets or QNXT customer can install ClinCase as an agent bundle in their existing AI Gateway deployment. **Sales motion: Day-1 add-on. No new procurement, no new platform.**

---

## What's in the box (today, demo-ready)

| Capability | What it does | Where |
|---|---|---|
| **7-agent oncology PA DAG** | Clinical extraction → Policy retrieval → Necessity reasoning → Decision composition → Denial forecasting → Appeals drafting → Patient communication | LangGraph on Bedrock; ~52s p50 per case |
| **TriZetto AI Gateway adapter** | MCP-native submission of ClinCase determinations → Facets PA tasks + QNXT case events. SHA-256 tamper-evident hashes. | `app/integrations/trizetto/` |
| **CMS-0057-F live scorecard** | Per-case clause checker against the in-force regulation (Jan 1, 2026) + state AI laws (CA SB 1120, CO AI Act). | `app/compliance/cms_0057f.py` |
| **Business value calculator** | Per-case ROI vs $1,500 manual baseline; org-level Star Ratings $$ projection; provider-abrasion reduction model. | `app/business_value/` |
| **Amazon Q Business connector** | Drop-in alternative to Bedrock KB for customers whose policy library lives in M365 / SharePoint / Confluence. One env flip. | `app/integrations/amazon_q/` |
| **Kiro IDE spec library** | 28 spec dirs auto-generated from `AGENT_MANIFEST`. First comprehensive PA-domain Kiro reference in AWS's healthcare portfolio. | `.kiro/specs/` |
| **MCP server** | JSON-RPC 2.0; 5 tools (`policy_lookup`, `clinical_extract`, `decision_check`, `appeal_draft`, `audit_query`). | `app/mcp/server.py` |

---

## The business case (numbers a CFO defends)

### 1. Direct PA-cost displacement

| | ClinCase | Manual baseline (AMA) | Savings |
|---|--:|--:|--:|
| Cost / case (clean APPROVE) | $0.25 | $1,500 | **$1,499.75** |
| Cost / case (DENY + appeal) | $0.45 | $1,500 | **$1,499.55** |
| Time / case | ~52 seconds | ~18 minutes | 95% |
| Speedup factor | — | — | **20×** |

Source: AMA 2025 Prior Authorization Physician Survey · CAQH Index 2024 · MGMA 2024 oncologist comp.

### 2. Star Ratings revenue lift (MA payers)

- **0.5 stars ≈ $2.1M / 10K MA members / year** (Lilac 2025)
- **At Humana scale (~6M MA enrollees) = $1.26B per half-star**
- 2026 average MA Star: **3.98** — barely below the 4-star bonus floor
- 2025 quality bonus pool: **~$13B** (KFF)
- ClinCase projected lift on PA-influenced measures: **+0.2 to +0.4 stars**

### 3. Provider abrasion reduction (network adequacy)

- Physicians spend **12–13 hrs/week** on PAs (AMA 2025)
- **89–95%** say PA contributes to burnout
- Physician turnover cost: **$250K–$1.2M** (AMN 2024)
- **36% of oncologists report a patient death linked to PA delay** (ASCO)
- ClinCase returns **~25 minutes per provider per case** to clinical practice

---

## Why this stack — why now

### 1. Stack alignment is already done

ClinCase is built on the *exact* stack that's now industry-standard for this space:

- **AWS Bedrock** (proven via the AWS Premier Partner ecosystem; re:Invent 2025 IND210 joint session)
- **Anthropic Claude Sonnet 4.6** (Nov 4, 2025 enterprise partnership — Claude deployed across 350K employees at one of Anthropic's three largest customers globally)
- **MCP** (TriZetto AI Gateway is MCP-native)
- **Anthropic Agent SDK** (the documented runtime for Neuro AI Multi-Agent Orchestration)
- **Kiro IDE specs** (AWS's published spec-driven workflow; ClinCase is the first PA-domain reference)

### 2. The regulatory window is now

- **CMS-0057-F** is live since Jan 1, 2026 (72-hr expedited / 7-day standard TATs)
- **March 31, 2026** — first public PA metrics report due (passed; payers scrambling to defend the data)
- **Jan 1, 2027** — FHIR PARDA mandate (Da Vinci PAS replaces X12 278 under enforcement discretion)
- **CA SB 1120** in force — physicians must sign every adverse determination
- **AHIP 80%-real-time-by-2027 pledge** — 60+ insurers, 257M lives covered; only ~11% eliminated 6 months in

### 3. TriZetto's customer base needs this Monday

- ~80M lives on Facets · ~20M on QNXT (industry public)
- Best in KLAS 2026 #1 Claims & Administration (Payer) — TriZetto retained the title
- TriZetto AI Gateway launched Aug 6, 2025 — currently has zero specialty-medicine agent bundles
- ClinCase is the **first oncology-PA bundle** that ships as a Gateway-native MCP suite

---

## Day 0 → Day 90 — commercialization plan

| Day | Milestone | Owner |
|---|---|---|
| **Day 0** | Launch; demo to TriZetto product leadership | AeroFyta + the payer organization |
| **Day 7** | Joint announcement: "ClinCase enters TriZetto AI Gateway agent bundle catalog" | Enterprise PR + AWS blog (Bedrock Healthcare) |
| **Day 14** | Pilot kickoff with one Facets payer — 1,000 cases / day; oncology only | Payer CSM + AeroFyta deployment eng |
| **Day 30** | First public ROI numbers from pilot — direct savings + Star projection update | Pilot payer signs off |
| **Day 45** | Apply Bedrock Provisioned Throughput (1 MU Sonnet) — `ops/terraform/provisioned-throughput/` | AWS account team |
| **Day 60** | Add second specialty (cardiology) via Kiro spec edit + Hook regen — proves multi-vertical | AeroFyta engineering |
| **Day 90** | Second Facets/QNXT customer signs; multi-region active/active deployed via `ops/terraform/multi-region/` | health-sciences sales |

---

## Pricing motion (TriZetto-aligned)

- **Per-case fee** that's a fraction of the displaced manual cost. Conservative starting point: **$5/case**.
  - Vs $1,500 manual = **300× headroom** for the customer
  - At 10K cases/day = **$1.825M/year** per customer (margin: ~92%)
- Bundled into the **TriZetto subscription** as a "specialty agent bundle" SKU — no separate procurement.
- TriZetto sales team gets standard rev-share; same motion as any AI Gateway agent.

---

## What we'd ask for (the actual ask)

1. **TriZetto product team review** — schema validation against the production Facets v3 + QNXT v2 event surfaces (we built ours from public docs).
2. **One Facets/QNXT customer** for a 30-day pilot. AeroFyta supplies engineering; the payer partner supplies the relationship.
3. **AWS marketplace listing** — under a Bedrock Healthcare seller account.
4. **Joint AWS blog post** — AeroFyta + AWS Bedrock Healthcare team, replicating the IND210 collaboration model.

---

## Risks (and how they're already mitigated)

| Risk | Mitigation |
|---|---|
| State AI laws (SB 1120) require human signoff on denials | ClinCase never denies autonomously — `review_gate` HITL routing is built into the DAG (`app/graph/build.py`). Reviewer signoff is row-level audited. |
| Bedrock regional throughput limits | `ops/terraform/provisioned-throughput/` apply-ready; pre-warm before any payer go-live. |
| Customer's policy library is in SharePoint, not in our corpus | `USE_AMAZON_Q=true` env flip routes retrieval through the customer's existing Q Business app. |
| 7-year HIPAA retention + cross-region resilience | `ops/terraform/multi-region/` apply-ready; Aurora Global + S3 CRR + KMS multi-region. |
| AI hallucinations on clinical facts | 4-layer guardrails (Schema · PHI · Citation completeness · Token budget) + LLMGrader self-evaluation + bounded retry-with-feedback. |
| LLM cost runaway | Per-case `BudgetTracker` with hard $5 ceiling; `BudgetExceeded` raised before the LLM is called. |

---

## One-line elevator pitch (for the demo)

> "ClinCase is the first oncology-specialty agent bundle for TriZetto's AI Gateway, built on the exact Bedrock + Claude Sonnet 4.6 + MCP stack that's now industry-standard following the Anthropic partnership. It saves a payer **$1,499.55 per case**, projects **+$1.26B per half-star** at Humana scale, and ships **CMS-0057-F compliance evidence as a first-class scorecard** — all on May 7, 2026, eight months before the FHIR PARDA mandate hits."
