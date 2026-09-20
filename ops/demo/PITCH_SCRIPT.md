# ClinCase — Verbatim 5-Minute Pitch Script

**For:** the 2026 hackathon finals · May 7, 2026 · Pune
**Format:** 5-min pitch + ~5-min live demo + 8-12 min Q&A
**Print this. Bring it to stage. Read it cold once before; from memory on stage.**

---

## Pre-stage 30 seconds

Stand still. Breathe. Open the laptop. Tab on `/dashboard`. Click into a fixture case so the page is *primed*. **Don't run the case yet** — that's the demo.

When the moderator says "ClinCase":

---

## Minute 0:00 — open ✦ 30 seconds ✦ 70 words

> *"Good morning. I'm Preethi, captain of Team AeroFyta.*
>
> *In December last year, a major systems-integrator CEO named the AI velocity gap — five hundred billion dollars of AI infrastructure spent in 2025, with most of the enterprise value still missing.*
>
> *Today we're going to show you ClinCase — the first oncology specialty agent bundle for TriZetto AI Gateway, that closes that gap in ninety seconds per case."*

**Transition:** point at the screen. Tab on `/dashboard`. Let the live KPI tiles show $X saved MTD.

---

## Minute 0:30 — the problem ✦ 45 seconds ✦ 100 words

> *"In US oncology, eighteen minutes of clinician time are spent on every prior authorization. Seven days is the regulatory SLA. Cancer can't wait.*
>
> *Thirty-six percent of oncologists report a patient death linked to a PA delay. The American Medical Association puts the loaded cost of a single oncology PA at fifteen hundred dollars.*
>
> *CMS-0057-F went live January first. AHIP and the Blues Association just signed fifty insurers to a 2027 FHIR PA mandate. Six months in, only eleven percent of PAs have been eliminated.*
>
> *That's the velocity gap. That's the adaptation gap. That's what ClinCase closes."*

**Transition:** open `/cases`. Click the trastuzumab fixture. Land on Case Detail with **Run ClinCase** button visible.

---

## Minute 1:15 — the solution + live demo start ✦ 90 seconds ✦ 175 words

> *"ClinCase is a seven-agent LangGraph DAG, twenty-two sub-agents, on AWS Bedrock with Claude Sonnet four-point-six.*
>
> *Same Bedrock plus Claude plus MCP stack the industry standardized on for the Anthropic partnership announced November fourth, twenty-twenty-five.*
>
> *Watch the right panel."*

**Click Run ClinCase.** The 7-agent SSE trace lights up. Don't talk over it. Coffee-cup test: **silence for 8 seconds while it runs**, then —

> *"Forty seconds in. The clinical extractor pulled HER2-positive from the FHIR bundle. The policy retriever surfaced Aetna oncology section four-point-two. The necessity reasoner ran five atomic criteria, calibrated confidence at point-nine-two, and now the decision composer is writing the rationale with citations."*

When the 7-agent trace completes (~50-90s):

> *"Done. Ninety seconds. APPROVE. Confidence ninety-two percent. Five citations, every one pointing to a specific Aetna oncology policy section."*

**Point at the BusinessValuePanel that just rendered:**

> *"Fifteen hundred dollars of manual cost displaced. Eighteen minutes returned to the clinic. Twenty times faster than the AMA median."*

---

## Minute 2:45 — the industry-alignment moment ✦ 45 seconds ✦ 100 words

**Click TriZetto Submit.**

> *"This decision is now in TriZetto Facets and QNXT — the partner claims platforms running eighty million Facets lives plus twenty million QNXT lives, a hundred million addressable from the first sale.*
>
> *Same MCP envelope the TriZetto AI Gateway has been speaking since August sixth, twenty-twenty-five. Each event carries a SHA-256 hash over the verdict and rationale and citations and model ID — tamper-evident.*
>
> *No new platform. No new procurement. We're a Day-1 add-on inside the customer's existing TriZetto subscription."*

---

## Minute 3:30 — the proof ✦ 45 seconds ✦ 100 words

**Click Download Evidence Pack.** A JSON file lands.

> *"This is what a CMS auditor gets. Case plus decision plus every agent invocation plus every reviewer action plus the live CMS-0057-F scorecard plus the live business value plus the TriZetto envelope. SHA-256 over the entire bundle.*
>
> *A regulator can rehash the bundle and verify nothing was edited. CMS-0057-F section IV.D auditability — twelve-second turnaround.*
>
> *That's not a slide. That's an endpoint. Anyone in the room can curl it."*

**Tab to `/architecture`.** Scroll past the five layer cards.

---

## Minute 4:15 — the architecture ✦ 30 seconds ✦ 70 words

> *"Five named layers, live introspectable. AI velocity gap addressed. AI adaptation gap addressed. Agent Foundry stage Build, graduating to Scale on the first pilot. Neuro-SAN compatible. TriZetto AI Gateway native. Anthropic Agent SDK semantics.*
>
> *Eight ADRs in canonical Nygard format. Four Terraform modules apply-ready. Twenty-eight named edge cases."*

**Tab to `/roi`.** Slider on Humana 6M.

---

## Minute 4:45 — the ROI close ✦ 15 seconds ✦ 30 words

> *"At Humana scale — six million Medicare Advantage enrollees — half a star is one-point-two-six billion dollars a year. ClinCase's lift band is plus point-two to plus point-four stars."*

---

## Minute 5:00 — the ask ✦ 15 seconds ✦ 35 words

> *"One Facets customer. Thirty days. We bring the engineering. You bring the relationship. We close the AI velocity gap together — eight months before the FHIR PARDA mandate hits.*
>
> *Thank you."*

**Stop. Stand still. Wait for Q&A.**

---

## Q&A handling rules

- **First sentence answers the question.** Then evidence. Then bridge.
- **30 seconds max.** Anything longer = unprepared.
- **Owner table:**
  - Architecture / AWS / scale → **Tech Lead (TL)**
  - Clinical / oncology / NCCN → **Clinical Lead (CL)**
  - Market / ROI / GTM / the partner channel → **Product Lead (PL)**
  - "Show me X" follow-ups → **Demo Operator (DO)** drives the laptop
- If a teammate is asked the wrong question: *"My colleague <name> owns this — <name>?"* No two voices on one answer.
- **If you don't know the answer:** *"That's exactly the question we want to dig into post-hackathon — let me follow up over email."* Never bluff.

Top 12 Q&A answers in [`QA_DRILL.md`](./QA_DRILL.md). Additional 20 Qs in [`ANTICIPATED_QUESTIONS.md`](./ANTICIPATED_QUESTIONS.md).

---

## Word counts (so you can pace yourself)

| Section | Time | Words | WPM equiv |
|---|---:|---:|---:|
| Open | 0:30 | 70 | 140 |
| Problem | 0:45 | 100 | 133 |
| Solution + live demo open | 1:30 | 175 | 117 |
| the partner moment | 0:45 | 100 | 133 |
| Proof (Evidence Pack) | 0:45 | 100 | 133 |
| Architecture | 0:30 | 70 | 140 |
| ROI close | 0:15 | 30 | 120 |
| Ask | 0:15 | 35 | 140 |
| **Total** | **5:00** | **680** | **136 avg** |

130-140 WPM is the right "confident-but-not-rushing" pace. Practice at 120-130 to leave room for breath.

---

## What you must NOT say

- "Sort of" / "kind of" / "basically" — eliminates conviction
- "Hopefully" — sounds uncertain
- "We tried to" — say "we did" or "we will"
- "Like" as a filler — death on stage
- Any technical jargon a non-engineer wouldn't know in the first 60 seconds

---

## What you MUST say verbatim

These exact phrases need to come out of your mouth at least once:

1. **"AI velocity gap"** (the partner CEO's phrase)
2. **"TriZetto AI Gateway-native"** (the partner Aug 6, 2025 platform)
3. **"$1.26 billion per half-star at Humana scale"** (Lilac 2025-anchored)
4. **"CMS-0057-F"** (the regulation; says you've done your homework)
5. **"Anthropic Agent SDK"** OR **"Claude Sonnet 4.6"** (the partner Nov 4 2025 partnership)
6. **"SHA-256 tamper-evident"** OR **"Evidence Pack"** (proof of audit-grade)
7. **"the Agent Foundry — Discover, Design, Build, Scale"** (stages)
8. **"Eighty million Facets lives plus twenty million QNXT lives"** (market)

If you remember nothing else, remember those 8 phrases.

---

*Drill twice. Demo once.*
