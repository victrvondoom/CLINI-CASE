# ClinCase MVP Deck — Speaker Notes (per slide)

**Deck:** [`CLINCASE_MVP_DECK.pptx`](./CLINCASE_MVP_DECK.pptx) — 13 slides
**Companion:** [`PITCH_SCRIPT.md`](./PITCH_SCRIPT.md) — verbatim 5-min speech

These notes belong in PowerPoint's "Speaker Notes" pane (View → Notes Page). 30 seconds of context per slide.

---

## Slide 1 — Cover

**Time:** 10 seconds (just be on screen while moderator introduces).

**What you say (only if asked to introduce yourself):**
> "I'm Preethi, captain of Team AeroFyta. We're presenting ClinCase — an oncology prior-auth copilot for TriZetto AI Gateway."

**What's on screen:** Cover with the team info. **Don't read it aloud.**

---

## Slide 2 — Problem Statement | Solution Description

**Time:** 1 minute combined (0:30 problem + 0:30 solution).

**Anchor numbers (memorize these):**
- 18 minutes per case manual baseline (AMA 2025)
- 7-day SLA (CMS-0057-F § IV.B.1)
- $35B/year US PA admin cost (CAQH)
- 36% of oncologists report a patient death linked to PA delay (ASCO)

**Key transition:** "Cancer can't wait. Prior auth does." — say it slowly, look at the room. Don't undersell it.

**What you say (left side):** *"Eighteen minutes of manual work, seven days of regulatory wait, thirty-five billion dollars a year of US healthcare admin cost on prior auth alone — and thirty-six percent of oncologists have reported a patient death they trace back to a PA delay."*

**What you say (right side):** *"ClinCase — FHIR bundle to TriZetto-native decision in ninety seconds. Seven-agent LangGraph DAG, twenty-two sub-agents, on Bedrock and Claude Sonnet four-six. The exact stack the industry standardized on for the Anthropic partnership announced November fourth."*

---

## Slide 3 — Uniqueness / Innovativeness | Business Impact

**Time:** 1 minute combined.

**Anchor numbers:**
- $1,499.55 saved per case (vs $1,500 AMA baseline; ClinCase per-case $0.45)
- $1.26B per half-star at Humana scale (Lilac 2025: $2.1M/10K members/0.5 stars)
- 95% of GenAI pilots fail to scale (MIT NANDA)

**Killer line:** "Not a chatbot. A CMS-0057-F-evidenced agent bundle." Pause after.

**What you say (left side — uniqueness):** *"the industry launched the TriZetto AI Gateway August sixth, twenty-twenty-five — zero specialty bundles in the catalog today. ClinCase is the first oncology one. Same Bedrock plus Claude plus MCP stack the partner just made standard."*

**What you say (right side — impact):** *"Per case: fifteen hundred dollars displaced. Per half star at Humana scale: one-point-two-six billion dollars. We sit in McKinsey's five percent of GenAI deployments that show transformational ROI."*

---

## Slide 4 — Technical Design and architecture

**Time:** 1 minute (this is the deep slide).

**The five layers — name them out loud:**
1. Experience
2. Orchestration & Policy Engine
3. Context Retrieval Service
4. GenAI Gateway
5. Telemetry & Governance

**Key proof point:** "Live introspectable at `/api/v1/architecture/layers` — anyone in the room can curl it."

**What you say:** *"Five layers. Live introspectable. Experience, orchestration with the seven-agent DAG and HITL gate, context retrieval pluggable between Bedrock KB and Amazon Q Business, GenAI Gateway with per-tenant quotas and audit logs, and telemetry with Prometheus metrics, Evidence Pack, and Responsible AI model card. Every layer is in the code. Every layer is queryable."*

**If asked "why LangGraph?":** ADR-0001 in `ops/adr/`. Conditional edges + checkpointing + AgentCore framework-agnostic.

---

## Slide 5 — Scalable / Reusable | Roadmap

**Time:** 45 seconds.

**Anchor numbers:**
- Capacity model: 1K → 10K → 100K cases/day (`ops/SCALING.md`)
- Customer onboarding: 7-15 business days (`ops/multi-tenant/ONBOARDING.md`)
- 4 Terraform modules apply-ready: multi-region, provisioned-throughput, bedrock-vpc-endpoint, s3-vectors

**What you say (left side):** *"Multi-tenant by construction. Four Terraform modules apply-ready. Customer onboarding seven to fifteen business days. New specialty — cardiology, behavioral health — equals three markdown files plus a Kiro Hook regen."*

**What you say (right side — roadmap):** *"Day zero: pilot signs. Day twenty-one: first production case. Day forty-five: Bedrock Provisioned Throughput pinned. Day ninety: first pilot ROI report — joint AWS plus the partner blog post."*

---

## Slide 6 — Unique Value Proposition

**Time:** 30 seconds.

**Killer line:** "Drop into TriZetto Monday. Audit-grade by Day 21. Star lift by Day 90."

**What you say:** *"We don't ask the customer to provision a new platform. We're a Day-1 add-on inside their existing TriZetto subscription. CMS-0057-F evidence ships as a first-class endpoint, not a slide claim. Live compliance scorecard. Live evidence pack with SHA-256 tamper hash. Twelve seconds to reproduce any decision for an auditor."*

---

## Slide 7 — Business Model & Channel

**Time:** 30 seconds.

**Anchor numbers:**
- $5/case license
- 300× customer headroom (vs $1,500 AMA cost)
- $5.475B/yr displaced cost per 10K-case/day customer
- ~80M Facets lives + ~20M QNXT lives = 100M addressable

**What you say:** *"Five dollars per case. Three-hundred-times headroom for the customer. Sold by TriZetto sales as a Specialty Agent Bundle SKU — bundled into the existing subscription. Standard rev-share. We're not a separate procurement decision. We're an add-on."*

---

## Slide 8 — Market, ROI Calculator & GTM

**Time:** 45 seconds — and **switch to `/roi` page in the browser** for the live demo moment.

**What you say:** *"AHIP and the Blues Association signed fifty insurers in April twenty-twenty-six for FHIR PA APIs. Six months in, only eleven percent of PAs have been eliminated — the gap ClinCase closes."*

**Demo moment:** *"Let me show you our live ROI calculator — drag this Humana six-million slider — at point-three star lift, that's seven hundred and fifty-six million dollars per year in CMS quality bonuses. The math is anchored to Lilac Software twenty-twenty-five."*

---

## Slide 9 — Agentic Workflow & Why This Stack

**Time:** 45 seconds.

**The four-phase pattern:** user goal → agent network → typed actions → outcome.

**What you say:** *"This is the twenty-twenty-six pattern the Flowsource uses for software engineering — applied to clinical ops. User issues a goal: decide PA for trastuzumab. Seven-agent network executes. Five typed actions: persist decision, route to review, submit to TriZetto, draft appeal, notify patient. Auditable outcome with the Evidence Pack we just downloaded. Bedrock AgentCore Action Group-aligned."*

**If asked "why these models?":** Cost-routing — Haiku for graders, Sonnet for reasoning. Per-tenant Bedrock Guardrails. Provisioned Throughput for predictable cost.

---

## Slide 10 — The Pilot Ask

**Time:** 30 seconds (the close).

**What you say:** *"One Facets customer. Thirty-day pilot. We bring the engineering. You bring the relationship. Joint AWS plus the partner blog post. AWS Marketplace listing under your Bedrock Healthcare seller account.*
>
> *We close the AI velocity gap together — eight months before the FHIR PARDA mandate hits.*
>
> *Thank you."*

**Stop. Don't fill silence. Wait for the panel.**

---

## Slide 11 — Additional slides / journey

**Time:** Only show if explicitly asked, OR if you have leftover time.

**What you say:** *"Thirty-three days from idea submission to today. Seven parents, twenty-two sub-agents, fifty-six routes, eighteen architecture documents, eight ADRs. Built around a single thesis: the partner's AI velocity gap is solvable, today, in oncology PA, on the stack the partner just standardized."*

---

## Slide 12 — Thank you

**Time:** Display only.

**What you say:** Nothing. Let the room read it.

---

## Slide 13 — MVP Evaluation Criteria reference

**Time:** Skip in pitch. **Open during Q&A** if a judge asks "how does this map to the rubric?" — then point at our [MVP_COMPLETENESS.md](./MVP_COMPLETENESS.md).

---

## Final speaker note — the most important one

**Don't read the slides.** Speak *to* the room. Slides are visual reinforcement, not your script. The script is in [`PITCH_SCRIPT.md`](./PITCH_SCRIPT.md). The slides are wallpaper.

If you find yourself reading a bullet, **stop, look up, paraphrase, point at the slide, move on.**
