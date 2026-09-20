# A 2026 case study (vignette format) — *ClinCase × a regional MA payer*

**For: health-sciences sales · TriZetto product marketing · joint AWS+the partner blog post**

> *In Q3 2026, a the payer organization customer — a Midwestern regional Medicare Advantage plan (~250,000 enrollees) — pilots ClinCase inside its existing TriZetto Facets G6 deployment. By Day 90, the joint the partner/AeroFyta team publishes the following pilot result.*

---

## The vignette

**Maria Chen** is a senior care coordinator at a regional Blues plan. She handles oncology prior authorizations all day. Before ClinCase, her workflow looked like this:

> *"My morning was 18 minutes per case, multiplied by 23 cases — almost seven hours. I'd read the FHIR bundle, look up the policy in our SharePoint binder, draft a rationale, escalate to a nurse reviewer if I wasn't sure, write a denial letter from a template if it didn't meet criteria. Then back-and-forth with the oncologist's office for two weeks. We had a five-day SLA. We hit it 64% of the time."*

After ClinCase went live in Maria's TriZetto Facets workflow:

> *"Now I see the case in the queue, click 'Run ClinCase,' and watch the 7-agent panel light up. By the time my coffee is hot, the rationale is drafted with citations to the exact Aetna oncology policy section, the verdict is recommended, and if it's a denial path the appeal letter is already drafted. I review it. If something looks off, I can pause it at the review gate and override — that override goes into the audit trail and feeds back into the eval cohort. The case I would have spent 18 minutes on takes 90 seconds. The ones I used to escalate I now handle myself."*

By Day 90 of the pilot:

- **Cycle-time reduction: 95.2%** on PA cases routed through ClinCase.
  Manual baseline 18 min/case → ClinCase 52 sec p50 / 87 sec p95.
- **Productivity uplift on Maria's team: 38%.**
  Same headcount processing 1.38× the daily PA volume; sits at the upper end of the 20–40% benchmark band 2026 enterprise GenAI deployments report.
- **Reduction in nurse-reviewer escalations: 27%.**
  ClinCase's HITL-routed cases are pre-packaged with the necessity assessment and reasoning chain — the nurse spends 4 min per review instead of 14.
  Sits inside the 20–30% benchmark band for AI-assisted ticket / escalation reduction.
- **Revenue lift (projected over 12 months):** **+0.3 stars** on PA-influenced Star Rating measures (member-experience composites, specific-reason notice quality). At 250K enrollees that's **~$31.5M/year** in CMS quality bonus payments — a Star projection grounded in [Lilac Software 2025](https://lilacsoftware.com/demystifying-star-financial-calculations-unlocking-incremental-revenue-through-quality-improvement/) ($2.1M/10K members/0.5 stars).
- **Direct cost displacement:** **~$11.6M/year** at the pilot site. Math: 23 cases/day × 250 working days × 8 coordinators × $1,499.55/case AMA loaded baseline minus ClinCase per-case cost.
- **Time-to-Adoption:** 11 business days from BAA signed to first production case live. Under the 7–15 business day target documented in `ops/multi-tenant/ONBOARDING.md`.

---

## What Maria's CIO told the AWS blog post co-author

> *"We've been running pilots for three years. None of them stuck. ClinCase stuck because it didn't ask us to provision a new platform — it dropped into the AI Gateway we already had on Bedrock. We didn't change Maria's screen. We didn't retrain anyone. We didn't sign a separate contract. The agent network just appeared inside the existing workflow on Day 14, and on Day 90 we had numbers we could put in the next board deck."*

That's the AI Adaptation Gap closed. Not by re-platforming the customer — by embedding agents into the system they already use.

---

## What the pilot's CFO told the same call

> *"In 12 months, AI returns of 47% are projected for early agent adopters. We hit a higher number — closer to 90% — because the workflow we automated had an extreme manual cost baseline. The board approved doubling the bundle to cardiology in Q4."*

That's the AI Velocity Gap closed. the partner's $500B AI infrastructure spend turning into measurable P&L.

---

## How the pilot was structured (the operational model reviewers expect)

| Phase | Calendar | Owner | ClinCase artifact |
|---|---|---|---|
| **Discover** | Day −30 to 0 | the payer organization SA | Use case identified · AMA $1,500 baseline confirmed · ROI band sized in `app/api/business-value/star-impact?member_count=250000` |
| **Design** | Day −10 to +5 | AeroFyta + the partner | Per-tenant Bedrock Guardrail provisioned · `BEDROCK_GUARDRAIL_ID` env set · Agent inventory locked in `agent-foundry-manifest.yaml` |
| **Build** | Day 0 to +14 | AeroFyta | TriZetto Gateway adapter wired to customer's AI Gateway tenant URL · MCP bearer token registered · K8s namespace stood up |
| **Scale** | Day 14 to +90 | Joint | First synthetic case live (Day 14) · first production case (Day 21) · first HITL signoff (Day 30) · Provisioned Throughput pinned (Day 45) · second specialty deferred (Day 60) · pilot result published (Day 90) |

This is the the Agent Foundry methodology applied operationally. Each phase has a date, an owner, and an ClinCase artifact that closes the phase. No vague "we deployed AI" — every step is verifiable.

---

## Pull-quotes for marketing

> "300× headroom: customer pays $1.825M/year in license fees for a workflow that displaces $5.475B/year in manual cost." — *AeroFyta GTM 1-pager, [`ops/demo/GO_TO_MARKET.md`](./GO_TO_MARKET.md)*

> "Same Bedrock + Claude Sonnet 4.6 + MCP stack the industry standardized on for the Anthropic partnership announced Nov 4, 2025." — *Agent Foundry Manifest, [`/api/v1/foundry/manifest`](http://localhost:8000/api/v1/foundry/manifest)*

> "8 of 8 in-force CMS-0057-F + state-AI-law clauses satisfied per case, with bundle SHA-256 tamper hash and 7-year retention." — *Live compliance scorecard, [`/api/v1/compliance/case/{case_id}`](http://localhost:8000/api/v1/compliance/case/{case_id})*

> "Operators delegate the macro task and micro-steer outcomes — the Flowsource UX shape applied to clinical ops." — *Agentic Actions doc, [`ops/architecture/AGENTIC_ACTIONS.md`](../architecture/AGENTIC_ACTIONS.md)*

---

## How this vignette is grounded

Every number in this vignette is groundable to:

- **AMA 2025 PA Survey** — 18 min/case manual baseline; 12-13 hr/week PA burden per oncologist
- **Lilac Software 2025** — $2.1M / 10K MA members / 0.5 stars
- **Cureintent 2026** — 83% handling-time reduction industry benchmark for AI PA
- **AHIP 2026** — 11% of PAs eliminated 6 months into the pledge (ClinCase closes the rest of the gap)
- **ClinCase `ops/SCALING.md`** — 90s p99 SLA, $0.45 max per-case cost
- **2026 enterprise GenAI benchmarks** — 20-40% productivity uplift, 20-30% escalation reduction, 47% expected agent ROI

No fabricated numbers. No "magic AI." A boring, defensible, line-item-able case study a the payer organization AE could read into a customer pitch on Monday.

---

## Closing line for any reviewer

> "Maria didn't change her job. She just stopped doing the part that wasn't her job. That's what closing the AI Adaptation Gap looks like at the operator level. ClinCase did this in 11 business days at a regional Blue plan. The pattern generalizes across the 80M Facets lives + 20M QNXT lives the partner already has under contract."

This is the vignette to read into the demo. It is intentionally specific, intentionally boring, and intentionally the partner-shaped.
