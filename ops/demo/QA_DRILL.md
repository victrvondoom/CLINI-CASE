# ClinCase — Q&A Drill (30 questions × 30-second answers)

**Audience:** the 2026 hackathon Health Sciences finalists' panel — assume they include an enterprise architect, a healthcare/payer SME, the partner CTO-org rep, and a sales VP.

**Format:** After your 5-minute pitch + demo, expect **8–12 minutes of Q&A**. Judges typically ask 1–3 hostile questions designed to see if you crack. The list below is over-prepared on purpose; rehearse all 30 so you can't be ambushed.

**Answering rules**
1. **30 seconds, max 90 words.** Anything longer = you sound unprepared.
2. **First sentence answers the question.** Then one sentence of evidence, then bridge to a strength.
3. **No "uhm". No "great question".** Both signal you're stalling.
4. **One person owns each answer.** If a judge asks the wrong teammate, that teammate says *"My colleague <name> owns this — <name>?"* and hands off. Never two voices on one answer.

**Role assignments**
- **TL** = Tech Lead (Preethi) — architecture, AWS, security, compliance plumbing
- **CL** = Clinical Lead — oncology workflow, NCCN, payer behavior, reviewer experience
- **PL** = Product Lead — market, pricing, GTM, ROI, competitive positioning
- **DO** = Demo Operator — operates the laptop, fields "show me X" follow-ups

---

## Section 1 — Architecture & Agentic AI (TL)

**Q1. Why 7 agents and not one big prompt?**
Seven agents — Clinical Extractor, Policy Retriever, Necessity Reasoner, Decision Composer, Denial Forecaster, Appeals Drafter, Patient Communicator. Each has one job, one input contract, one output contract — so we can test, log, and replace any agent independently. A single prompt would couple clinical extraction to legal phrasing to patient communication, and any hallucination would taint the whole chain. With 7 agents we get auditable token boundaries: the Necessity Reasoner literally cannot fabricate a biomarker because it never receives the raw note. Each agent further decomposes into 2–3 named sub-agents — 21 sub-agents in total — for finer-grained contract testing.

**Q1b. What's the difference between an agent and a sub-agent here?**
A parent agent owns a top-level Pydantic input/output contract and a single LLM invocation boundary. A sub-agent is a logical, named decomposition inside that boundary — for example, the Necessity Reasoner's `criterion_splitter`, `evidence_matcher`, and `confidence_calibrator` all run inside one LLM call but the parent prompt walks the model through them in order. Sub-agents make the architecture inspectable for an auditor without inflating token cost. The full 7-by-3 manifest is exposed at `GET /api/v1/agents/manifest`.

**Q2. Why LangGraph instead of LangChain agents or a custom DAG?**
LangGraph gives us conditional edges with first-class state, so the "if DENY → run Appeals Drafter" branch is declarative, not imperative. We get checkpointing for free, which means a stalled case can resume mid-graph after a deploy. Compared to plain LangChain, the graph topology is inspectable — judges, auditors, or reviewers can literally see the DAG. We considered Strands; we'll port to Strands when the AWS-native runtime story matures.

**Q3. What's the latency budget per case end-to-end?**
Target is sub-15 seconds for an APPROVE on a clean case, sub-25 seconds for a DENY-with-appeal. Today we observe a p50 of 11 seconds and p95 of 22 seconds against Claude Sonnet 4.6. The Policy Retriever is the biggest variable — once we're on Bedrock Knowledge Bases with OpenSearch Serverless, retrieval drops from ~700ms to ~120ms. We stream agent traces over SSE so the user sees progress, not a spinner.

**Q4. How do you stop the LLM from hallucinating clinical facts?**
Three layers. One: every agent's system prompt forbids inventing facts not in its input — and we contract-test each prompt against fixtures. Two: the Necessity Reasoner only gets the structured ClinicalSnapshot, never raw text, so it can't "remember" anything beyond extracted fields. Three: every claim in the final decision must point to a citation — clinical evidence pointer or policy section pointer. If a claim has no pointer, the Decision Composer raises a contract violation and the case routes to a human.

**Q5. What's the failure mode if Claude is wrong?**
We default to REFER, not auto-DENY, when confidence is below 0.75 on the Necessity Reasoner — a refer just means "human review", which is the current default state of the world for every payer. Reviewers can override with one click and the override goes back into our cohort analytics so we can detect drift. We never ship a DENY without ≥0.85 confidence and a fully-cited rationale.

---

## Section 2 — Clinical Credibility (CL)

**Q6. NCCN guidelines update every quarter. How do you stay current?**
Two paths. The fast path: every policy is versioned, and our Policy Diff page shows exactly which in-flight cases are affected by a guideline change — that's the killer feature for a clinical operations director. The slow path: we ingest NCCN updates via Bedrock Knowledge Base sync; the embeddings get re-indexed in under 10 minutes. In production we'd subscribe to the NCCN content licensing feed; the architecture is ready for that integration today.

**Q7. Why oncology and not cardiology or rheumatology?**
Oncology has the highest prior-auth volume and the highest denial cost per case. A denied oncology PA delays starting therapy by an average of 11 days — that's measurable harm, not abstract inconvenience. Oncology criteria are also the most structured: HER2 status, ECOG score, biomarker results — all extractable from FHIR. We started where the pain is sharpest. The same architecture extends to immunology, transplant, and specialty rheumatology by swapping the prompt corpus.

**Q8. Wouldn't a board-certified oncologist disagree with the AI half the time?**
Our Reviewer page is built for exactly that disagreement — overrides are first-class, we capture the override reason, and we surface override patterns in the Cohorts page so administrators can see where the AI systematically mismatches a particular oncologist's preferences. ClinCase is decision-support, not decision-replacement. The agent gives a starting point with citations; the oncologist owns the final call. The data we collect makes the next version of the AI better.

**Q9. How do you handle the case where the policy is ambiguous?**
The Necessity Reasoner emits a confidence score per criterion, not just per case. Ambiguous criteria — the kind where the policy says "consider on a case-by-case basis" — score below 0.6, which auto-routes to REFER. The reviewer sees exactly which criterion was ambiguous, the full policy excerpt, and the patient's relevant evidence. They make the human call, and that judgment becomes a few-shot example for the next pass through the same policy.

**Q10. What if the patient's payer hasn't been seen before?**
Today we've trained against four — Aetna, UHC, BCBS, Anthem — covering ~73% of the US commercial market. New payers ingest in under an hour: drop their CPB PDFs into the S3 KB bucket, sync the data source, run the contract tests against a 5-case fixture pack to confirm criteria extraction quality. Cohorts page tracks per-payer accuracy so we know which payers need more training data versus which are stable.

---

## Section 3 — Compliance, HIPAA, CMS-0057-F (TL/CL)

**Q11. Where exactly does PHI flow?** *(TL)*
PHI enters the FHIR bundle, lives encrypted in Postgres or RDS Aurora at rest. Before any LLM call, the Bedrock Guardrail with PII detection masks names, DOBs, MRNs, SSNs, and addresses — verified by the redaction trace in the SSE event. The agents reason on initials plus structured medical context only. Final outputs to the user de-mask back to initials. The original PHI never leaves the VPC; the LLM never sees it.

**Q12. Are you HIPAA-compliant?** *(TL)*
Architecturally, yes — at-rest encryption, in-transit TLS, audit logs, role-based access control, BAA-eligible AWS services only (Bedrock, RDS, ECS, S3, KMS). We're not yet HIPAA-certified because that requires a full SOC-2 audit and a Business Associate Agreement signed with the customer; both happen at deal-close, not at hackathon stage. The point is we won't have to refactor anything to hit HIPAA — the patterns are already in place.

**Q13. CMS-0057-F mandates 7-day API turnaround on prior auth by Jan 2027. How does ClinCase relate?** *(CL)*
CMS-0057-F is the regulatory tailwind that turns ClinCase from "nice-to-have" into "compliance-or-fines" by January 2027. Payers must respond to PA requests in 7 days for non-urgent and 72 hours for urgent. Without automation, payer staff cost goes up 40% to meet the SLA. ClinCase on the provider side cuts the round-trip time by submitting decision-ready packets with citations the payer can verify in minutes. We're the on-ramp to CMS-0057-F compliance, not the destination.

**Q14. How do you prevent the AI from making protected-class discriminatory decisions?** *(TL)*
We never feed race, ZIP code, language, or insurance type into the reasoning input. The Clinical Extractor's output schema explicitly omits those fields. The Necessity Reasoner can only see clinical facts and policy excerpts. Cohorts page surfaces approval rates by every demographic dimension we have access to via NPI registry data — if we ever see a 5-percentage-point gap, we flag it for human audit. Bias detection is a feature, not an afterthought.

**Q15. What's your audit trail look like for a CMS auditor knocking on our door?** *(TL)*
Every agent invocation writes an immutable `agent_traces` row: case ID, agent name, input tokens, output tokens, model ID, timestamp, full system prompt version hash, full structured input, full structured output. For any case decision, we can reconstruct the exact LLM call chain in under 2 seconds. The Compliance page exports a CSV per case ID for any auditor request. Production ships X-Ray traces and CloudWatch Logs Insights queries pre-built for the top 5 audit scenarios.

---

## Section 4 — AWS-native architecture (TL)

**Q16. Why Bedrock and not OpenAI / Azure / direct Anthropic?** *(TL)*
Three reasons. One: Bedrock keeps every prompt token inside our VPC — we can prove to a compliance officer that no PHI ever transited the public internet. Two: Bedrock Guardrails give us auditable PHI redaction with a single API call instead of writing our own redactor. Three: it's the natural fit for the partner client — they're an AWS Premier Partner, deals close faster when the architecture is on AWS. We use the LLMClient abstraction, so switching is a one-line env var change.

**Q17. What's your fallback if Bedrock is down during the demo?** *(TL)*
We've drilled a sub-60-second rollback to OpenRouter Claude Sonnet via a single `LLM_PROVIDER` env var flip. Documented in `ops/aws/MIGRATION_RUNBOOK.md` §8. We rehearsed the drill yesterday — actual measured time was 47 seconds including uvicorn restart. Production-grade systems must degrade gracefully; ours does.

**Q18. Why OpenSearch Serverless vs pgvector?** *(TL)*
For the demo, pgvector is fine — 21 policies, sub-millisecond retrieval. For a real payer with thousands of CPB pages, OpenSearch Serverless gives us managed ANN indexing, automatic scaling, and direct integration with Bedrock Knowledge Bases — Bedrock literally consumes from OpenSearch as a first-class vector store. That removes ~300 lines of retrieval glue code we'd otherwise own. The trade-off is cost; OpenSearch Serverless is overkill below 10K documents.

**Q19. How do you scale to 100,000 cases per month?** *(TL)*
Bottleneck analysis: Bedrock Sonnet 4.6 in `us-east-1` has 200K TPM provisioned-throughput available. At ~3K tokens per case end-to-end, that's 67 cases per minute, or 100K cases in ~24 hours of wall-clock — well above any realistic single-customer load. Knowledge Base retrieval is sub-200ms at any scale. The bottleneck becomes Postgres writes, which we solve by moving to Aurora Serverless v2 with a write replica. Every layer scales horizontally on its own primitive.

**Q20. Cold start latency on Lambda vs ECS Fargate for the SSE stream?** *(TL)*
SSE on Lambda is awkward — Lambda Function URLs support streaming responses, but the 15-minute timeout caps long-running cases. We use ECS Fargate with always-on tasks behind an ALB; cold starts are zero because the tasks are warm. Fargate gives us a managed VPC for Bedrock PrivateLink without ENI gymnastics. Lambda would save ~$30/month at our hackathon scale; the operational simplicity of Fargate is worth it.

---

## Section 5 — Business / GTM (PL)

**Q21. Who pays for this — providers or payers?** *(PL)*
Providers. Specifically, oncology practices and academic medical center cancer institutes. They lose ~$1,200 per denied PA in re-work and delayed therapy, and their PA backlog is growing 18% YoY. Payers benefit from cleaner submissions, but the buyer is the provider revenue cycle director. Our pricing is a flat $25 per submitted case for the first three years, then a tiered enterprise contract above 5K cases/month.

**Q22. What's your TAM?** *(PL)*
US oncology PA volume is approximately 14 million cases per year. At our pricing, that's a $350M annual TAM in oncology alone. Adjacent specialties — immunology, transplant, rare disease — bring it to $1.2B by 2028. the payer organization already serves 8 of the top 10 US oncology providers; we see ClinCase as a wedge product the partner can attach to existing engagements at the COO level. The buyer relationship the partner already owns is our distribution.

**Q23. What stops Epic or Athenahealth from building this themselves?** *(PL)*
Speed and depth. Epic's PA module is generic across specialties and runs on rules, not LLM reasoning — it can't read free-text physician notes, it can't draft appeals, it can't reason across a multi-payer arbitration scenario. Building agentic AI of the depth we have takes a 3-engineer team 9 months minimum, and Epic's product roadmap doesn't put it on a date. By the time they catch up, ClinCase is the wedge inside their largest customers' workflow. the partner is the only path for them to acquire this capability.

**Q24. How do you handle the change-management problem with skeptical doctors?** *(PL)*
Doctors don't see ClinCase. The end users are revenue cycle coordinators and clinical reviewers — both of whom hate PA paperwork and want this. Our Reviewer queue page is designed so an experienced PA reviewer can clear 4x more cases per shift while feeling more confident, not less. The doctor sees a faster turnaround on PA approvals and one fewer thing to fight with the insurance company about. That's the change-management story: nobody loses; everybody wins something.

**Q25. What's the unit economics?** *(PL)*
Per-case cost: ~$0.18 in LLM tokens (Bedrock Sonnet) plus ~$0.02 in compute and storage. Per-case price: $25. That's a 99% gross margin. Customer acquisition cost via the partner's existing client base: under $5K per oncology practice on a 24-month payback. After year one of 50K-case volume, contribution margin per customer crosses $1.2M annually. The math gets better, not worse, as we scale.

---

## Section 6 — Demo deep-dives (DO)

**Q26. Can you show me how the appeal letter is constructed?** *(DO)*
[Click into a denied case → Decision tab → Drafted appeal section.] The Appeals Drafter only fires on the conditional edge when verdict is DENY. It receives the contested criteria and pulls counter-evidence from the same evidence pointers the Necessity Reasoner used. Every paragraph cites either the patient's clinical record or an NCCN guideline. Notice the structured arguments JSON below the prose — that's what the payer's automation reads if they have an API; the prose is for the human appeal reviewer.

**Q27. Show me the multi-payer arbitration on a real case.** *(DO)*
[Click trastuzumab case → Compare button.] Four cards: Aetna's stricter LVEF rule says REFER; UHC, BCBS, Anthem all approve on the same evidence. Behind each card is the payer's actual policy excerpt retrieved from the Bedrock Knowledge Base — the Aetna excerpt explicitly mentions the 60-day window we just tightened in v3.2. The arbitration recommendation tells the coordinator: "submit to UHC first, your patient meets all four, but Aetna will route to manual review."

**Q28. What happens if the FHIR bundle is malformed?** *(DO)*
[Open Bulk Import → drop a broken bundle.] The Clinical Extractor returns a structured ExtractionError with the exact JSON path that failed validation. The case status is set to `pending` with a coordinator-readable error message. No further agents run, no LLM tokens are billed for that case. We surface the parse error in the Cases list with an inline retry button. CMS-0057-F's 7-day clock pauses on coordinator-actionable errors per the spec.

**Q29. Show me the agent observability.** *(DO)*
[Click into any case → Agents tab.] Each agent's row shows input tokens, output tokens, model ID, latency, system prompt version hash. Click any row → full structured input and output. This is exactly what's persisted to the `agent_traces` table for audit. Production ships this same data to X-Ray; from there we get distributed traces across the entire request chain. A judge from the payer organization could replay any production decision in under 30 seconds.

**Q30. What if I asked you to explain *why* this case got denied to a non-technical executive?** *(DO/CL)*
[Click any DENY case → Decision tab.] The plain-English rationale paragraph at the top is generated by the Decision Composer for exactly this audience. It cites the criterion that failed, the patient's evidence that contradicts it, and the policy section number — three pieces of information any executive can hand to a clinical advisor for verification. Below it, the structured arguments JSON powers the appeal. The same data, two consumers, one source of truth.

---

## Drill protocol

**Day before the demo (May 6 evening):**
- 60-minute mock Q&A. One teammate plays judge, picks 10 random questions, the answer-owner has 30 seconds — buzzer goes off. Anything past 30s = answer fails.
- Repeat until every teammate goes under 30s on every question they own.

**Morning of the demo (May 7 AM):**
- 20-minute warm-up. Each teammate runs through their 10 questions out loud, no notes.
- Final dry-run of the demo paths.

**During Q&A (May 7 actual):**
- Whoever owns the question takes the mic. Others stay silent unless explicitly asked.
- If a question is ambiguous: *"Are you asking about <X> or <Y>? Answer in 30s either way."*
- If a question is hostile (e.g., "Isn't this just a wrapper around Claude?"): acknowledge, reframe, answer. *"It's Claude doing the reasoning; what makes this defensible to a CMS auditor is the agent decomposition, the cited evidence, and the audit trail — none of which Claude alone provides."*
- If you don't know the answer: *"That's exactly the question we want to dig into post-hackathon — let me follow up over email with our reasoning."* Never bluff.

**After Q&A:**
- Within 2 hours: log every question asked + the question's owner + did we hit 30s + did the answer land. This becomes the next drill set.

---

*Drill twice. Demo once.*

---

## Section 7 — Strategic alignment (PL + TL)

These are the questions a the payer organization architect or TriZetto sales VP will ask. Practice cold.

**Q31. How does this fit into the partner's existing TriZetto product line? (PL)**
ClinCase is a specialty agent bundle for **TriZetto AI Gateway** — the partner's Aug 6, 2025 launch. Same Bedrock + Anthropic Claude Sonnet 4.6 + MCP stack the Gateway runs on. We submit determinations through the Gateway's MCP tool surface; it fans them out to Facets PA workflows and QNXT case events. From a sales POV, ClinCase is a Day-1 add-on inside an existing the partner subscription — no new procurement, no new platform.

**Q31b. Show me. (DO)**
*Demo path: Case detail → "Submit to TriZetto" button → /api/v1/integrations/trizetto/submit → mock inbox shows the Facets prior_auth_event v3 + QNXT case_event v2 with SHA-256 tamper-evident decision hash and ClinCase provenance block.*

**Q32. the partner–Anthropic announcement was Nov 4, 2025. How does ClinCase relate? (TL)**
ClinCase's stack matches that announcement verbatim. Claude Sonnet 4.6 reasoning + Claude Haiku for graders + MCP for tool exposure + Anthropic Agent SDK semantics in our framework. the industry just put Claude on 350K employees and made themselves one of Anthropic's three largest customers — ClinCase is what runs *on top of* that infrastructure for the partner's payer customers.

**Q33. Why would a TriZetto customer pay for ClinCase on top of what they already have? (PL)**
Three reasons. First: TriZetto AI Gateway has zero specialty-medicine agent bundles in its catalog today — we're the first oncology-PA bundle. Second: CMS-0057-F has been live since Jan 1, 2026; the March 31 metrics report deadline already passed and most payers are scrambling to defend their numbers. Third: at Humana scale, the Star Ratings math is **$1.26 billion per half-star** — ClinCase's faster, more transparent decisions feed those measures directly.

**Q34. Star Ratings — how do you justify the projection? (PL)**
Lilac Software 2025 publishes the per-member economics: **$2.1M per 10K MA members per 0.5 stars per year**. KFF puts the 2025 quality bonus pool at $13B, projected $18B+ over the next decade. The 2026 average MA Star Rating is 3.98 — barely below the 4-star bonus floor, so movement matters. ClinCase feeds the patient-experience and specific-reason-denial measures with auditable evidence. Conservative lift band: +0.2 to +0.4 stars on PA-influenced composites.

**Q35. CMS-0057-F — what specifically does ClinCase satisfy today? (TL)**
**Six clauses live today.** § IV.A — we expose the Da Vinci PAS endpoint at /fhir/Claim/$submit. § IV.B.1 — every decision under 90 seconds vs the 72-hour expedited / 7-day standard SLA. § IV.B.2 — every denial carries a specific-reason rationale with citations. § IV.C — our case data is reportable for the public PA metrics. § IV.D — every agent run persisted to agent_runs with input/output/model_id/tokens for the 7-year retention requirement. CA SB 1120 — adverse determinations route through the review_gate HITL node before any deny. *Demo path: GET /api/v1/compliance/case/{id} returns the live scorecard.*

**Q36. Why Kiro IDE specs in the repo? (TL)**
Two reasons. First: AWS published Kiro as the spec-driven agentic-IDE workflow late 2025. Their only healthcare reference today is "drug discovery agent in 3 weeks" — life sciences, not payers. ClinCase publishes 85 Kiro spec files for 7 parents + 22 sub-agents — the first comprehensive PA-domain Kiro reference. Second: a new specialty (cardiology, behavioral health) is three markdown files; Kiro Hooks regenerate the agent skeleton. We're showing the partner a multi-vertical scaling story, not a single-vertical demo.

**Q37. Amazon Q Business — why both that AND Bedrock KB? (TL)**
Most TriZetto customers' policy libraries live in Microsoft 365 / SharePoint / Confluence — building yet another vector index is a procurement non-starter. Q Business plugs into their existing knowledge corpus directly. ClinCase's policy_retriever has both backends as plug-in sub-agents with the same input/output schema; flip USE_AMAZON_Q=true and the demo runs through Q Business with zero code change. Availity already documented Q + Bedrock for healthcare payer ops in their 2025 case study; we follow that proven pattern.

**Q38. What's ClinCase's pricing motion in the partner catalog? (PL)**
Per-case fee that's a fraction of the displaced manual cost. Conservative starting point: **$5 per case** versus the AMA-loaded $1,500 manual cost — that's 300× headroom for the customer. At 10K cases/day the customer pays $1.825M/year for $5.475B/year of avoided manual cost. Bundled into the existing TriZetto subscription as a "specialty agent bundle" SKU, standard the partner rev-share. Day 0 → Day 90 commercialization plan is in **`ops/demo/GO_TO_MARKET.md`**.

**Q39. What's the actual ask of the partner if you win? (PL)**
Four things. One: TriZetto product team review of our Facets v3 + QNXT v2 event schemas (we built ours from public docs). Two: one Facets/QNXT customer for a 30-day pilot — Aerofyta supplies engineering, the partner supplies the relationship. Three: AWS marketplace listing under the partner's Bedrock Healthcare seller account. Four: joint AWS blog post — same model as the re:Invent 2025 IND210 collaboration.

**Q40. AHIP pledged 80% real-time PA by 2027. Where does ClinCase fit? (PL)**
The pledge covers 60+ insurers and 257M lives. Six months in, only ~11% of PAs have actually been eliminated. The gap is enormous — payers signed the pledge but couldn't deliver. ClinCase's 90-second decision time, audit-grade trail, and specific-reason denials are precisely what closes the gap on oncology PA. We're not the whole answer for AHIP's pledge, but for the highest-cost-per-case specialty (oncology), we're the path.

**Q41. What's stopping a payer from just building this themselves? (PL)**
Time. CMS-0057-F is in force; March 31 already passed; the FHIR PARDA mandate hits January 1, 2027 — eight months away. Building 7 production-grade agents with HITL gating, Bedrock guardrails, audit-grade trace, multi-region active/active, Star-Ratings-aware metrics, AND TriZetto/Facets/QNXT integration is a 12-18 month project. ClinCase ships today. The buy decision is the regulatory clock, not the build effort.

**Q42. The pitch is oncology — but the partner cares about scale. Will this generalize? (CL+TL)**
Yes — and the architecture proves it. Add a specialty by editing three Kiro spec files (`requirements.md`, `design.md`, `tasks.md`) for the new agent; the manifest auto-discovers it; the same DAG handles cardiology, behavioral health, transplant. The clinical extractor's specialty-aware prompt slot is already there. Day 60 of our GTM plan is "second specialty live." We picked oncology because it has the highest pain (36% of oncologists report a patient death linked to PA delay, ASCO 2024) — not because the architecture is oncology-only.
