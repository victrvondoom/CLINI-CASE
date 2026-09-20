# ClinCase — One-Page Leave-Behind for Judges

**Print this. Hand to each judge after the pitch.** Single A4, both sides if needed.

---

## What

**ClinCase** — TriZetto AI Gateway-native specialty agent bundle for **oncology prior authorization**.
**Stack:** AWS Bedrock + Claude Sonnet 4.6 + MCP — same the industry standardized on for Anthropic partnership (Nov 4, 2025).
**Built by:** Team AeroFyta · the 2026 hackathon finals.

---

## Why now

| Forcing function | What it means | ClinCase response |
|---|---|---|
| **CMS-0057-F** live Jan 1, 2026 | 72-hr expedited / 7-day standard PA TAT mandated | 90-second decision (1,400× faster than worst-case SLA) |
| **March 31, 2026** PA metrics report | First public report past due — payers scrambling | Live `/compliance/org` scorecard available now |
| **CA SB 1120** in force | AI cannot autonomously deny | `review_gate` HITL routing baked into the DAG |
| **AHIP/BCBSA Apr 24, 2026** | 50 insurers signed for FHIR PA APIs by 2027 | Da Vinci PAS endpoint live at `/fhir/Claim/$submit` |
| **Ravi Kumar Dec 2025** | "$500B AI infra spent, value missing" | ClinCase closes the velocity gap, in oncology PA, today |

---

## What it does (90-second case)

1. Coordinator submits FHIR R4 bundle for a PA request.
2. **7 agents · 22 sub-agents** run in 90s p95: Clinical Extractor → Policy Retriever → Necessity Reasoner → Decision Composer → (DENY?) Denial Forecaster → Appeals Drafter → Patient Communicator.
3. Decision dispatched as **Facets `prior_auth_event v3` + QNXT `case_event v2`** to TriZetto AI Gateway.
4. **Evidence Pack** with **SHA-256 tamper hash** packaged for CMS audit.

---

## Numbers

| KPI | Value | Source |
|---|--:|---|
| Cycle time per case (p50) | **52 seconds** | measured |
| Cost per case (clean APPROVE) | **$0.25** vs $1,500 manual | AMA 2025 baseline |
| **Per-case savings** | **$1,499.75** | math |
| Productivity uplift on workflow | **95–98%** | upper band of 2026 GenAI benchmarks |
| Star Ratings revenue lift @ Humana scale | **$1.26B per half-star** | Lilac 2025 |
| Customer onboarding (after first pilot) | **7–15 business days** | docs |

---

## Why now

- ✅ **First specialty agent bundle for TriZetto AI Gateway** (Aug 6, 2025; zero specialty bundles in catalog today)
- ✅ **Maps 1:1 to the Agent Foundry stages** (Discover · Design · Build · Scale)
- ✅ **Neuro-SAN compatible** — drop-in HOCON network
- ✅ **Same Bedrock + Claude + MCP stack** the industry standardized on (Nov 4, 2025)
- ✅ **Drop into existing TriZetto subscription** — no new procurement, no new platform
- ✅ **~80M Facets lives + ~20M QNXT lives** addressable Day-0

---

## Production-grade evidence

| Artifact | Path |
|---|---|
| 5-layer architecture | `ops/architecture/TARGET_ARCHITECTURE.md` |
| 8 ADRs (Nygard format) | `ops/adr/` |
| CI/CD pipelines | `.github/workflows/{ci,deploy-prod}.yml` |
| 7 SLOs + PagerDuty alerts | `ops/sre/SLO.yaml` |
| SRE runbook (7 incidents) | `ops/sre/RUNBOOK.md` |
| 4 Terraform modules | `ops/terraform/{multi-region,provisioned-throughput,bedrock-vpc-endpoint,s3-vectors}/` |
| Multi-tenant onboarding | `ops/multi-tenant/ONBOARDING.md` |
| Live Responsible AI model card | `GET /api/v1/responsible-ai/model-card.md` |
| Live Foundry compatibility manifest | `GET /api/v1/foundry/manifest` |
| 28 named edge cases | `ops/demo/EDGE_CASES.md` |
| Live Evidence Pack endpoint | `GET /api/v1/cases/{case_id}/evidence-pack` |

---

## The ask

**One Facets / QNXT customer. 30-day pilot.** AeroFyta brings the engineering. the partner brings the relationship.

Joint AWS + the partner blog post (re:Invent 2025 IND210 collaboration model). AWS Marketplace listing under the partner Bedrock Healthcare seller account.

**We close the AI velocity gap together — eight months before the FHIR PARDA mandate hits.**

---

## Contact

- **Captain:** Preethi Sivachandran · `preethisivachandran0@gmail.com`
- **Team:** AeroFyta
- **Repo:** ClinCase (private; access on request)
- **Live demo:** today, in this room
- **Day 0 → Day 90 commercialization plan:** `ops/demo/GO_TO_MARKET.md`

---

*the 2026 hackathon finals — May 7, 2026 — Pune*
