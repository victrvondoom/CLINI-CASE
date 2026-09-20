# ClinCase — Anticipated Q&A (beyond QA_DRILL.md)

**Companion to:** [`QA_DRILL.md`](./QA_DRILL.md) — first 30 questions
**Bring this to stage** as Q&A backup. Each answer ≤ 30 seconds. Owner in parentheses.

---

## Strategic alignment (PL)

**Q31. Why should TriZetto put ClinCase into the Agent Marketplace today?**
Three reasons. One: zero specialty bundles in the Gateway catalog right now. We're the first oncology one, ready to plug in. Two: the customer asks the partner doesn't want to do — per-tenant Bedrock Guardrail provisioning, KMS multi-region, Da Vinci PAS schema mapping — ClinCase already shipped them. Three: the AI velocity gap is what the partner is selling against; ClinCase is the proof that the gap closes when you embed agents into existing platforms instead of standing up new ones.

**Q32. What does the partner rev-share look like in practice?**
Standard TriZetto specialty-SKU rev-share — the partner takes the customer relationship and the contract margin; AeroFyta takes the per-case usage fee net of Bedrock costs. We've sized for $5/case at the customer; AWS Bedrock Provisioned Throughput at OneMonth tier on 1 MU Sonnet is ~$45,990/month, which covers ~10,000 cases/day at 18 sub-agent calls per case.

**Q33. Why didn't the partner just build this themselves?**
Time. CMS-0057-F has been live since January 1, 2026. The FHIR PARDA mandate hits January 1, 2027 — eight months. the partner's playbook is to Discover → Design → Build → Scale through Agent Foundry, which we've done. We're at Build/Scale boundary today. Building from Discover takes 9-12 months. ClinCase is "buy" in the build-vs-buy decision.

## Architecture & technical depth (TL)

**Q34. What if a customer's policy library uses a citation format your citation_resolver doesn't know?**
The `citation_resolver` is a deterministic sub-agent — it consumes `CandidateSection` and produces `PolicyExcerpt`. The shape is the same regardless of source. A new format means extending `CandidateSection` parsers in `keyword_filter` or `q_business_retriever`. We've never seen a payer policy that doesn't have page numbers + section headings, so the citation_resolver has zero edge cases in the pilot scope.

**Q35. Show me how a new agent gets added — what's the SDLC?**
Three steps. Drop a package under `app/agents/<name>/` with the standard layout. Subclass `Agent[I, O]` with name + role + schemas + primary_model. Drop the prompt in `app/prompts/<name>/<name>.txt`. The Kiro Hook `regenerate-specs-on-save.sh` materializes `.kiro/specs/<name>/` automatically. Manifest auto-discovers via pkgutil — no hand-edits anywhere. Net: ~half a day for an LLM-backed agent, ~2 hours for a deterministic one.

**Q36. How does the GenAI Gateway interact with Bedrock Provisioned Throughput?**
The Gateway is in-process — it manages per-tenant policy + audit + content safety. Provisioned Throughput is the AWS-side capacity reservation. They're complementary. PT splits TPM across tenants; the Gateway enforces that no one tenant's bursts exhaust shared PT. PT alarms fire at 80% / 95% utilization (configured in the Terraform module).

**Q37. Why don't you use Strands Agents instead of LangGraph?**
Strands is AWS's newer Python agent framework. We considered it. LangGraph has 3x the GitHub mindshare today + checkpointing primitives we use for the HITL pause. Strands' value is a tighter Bedrock integration — exactly what AgentCore Runtime gives us. So our path is: LangGraph for orchestration, AgentCore Runtime for production deployment. ADR-0001 has the full reasoning.

**Q38. What's the actual cost of a single ClinCase case to the partner customer?**
$0.25 for clean APPROVE, $0.45 for DENY+appeal. Sonnet input tokens around 24K per case at $3/MTok = $0.072. Sonnet output around 4.5K at $15/MTok = $0.067. Plus Haiku for the graders, ~$0.02 each, three of them. Plus retrieval, ~$0.05. Total = ~$0.20-$0.30 amortized. The $1,499.55-per-case savings number is vs the $1,500 AMA-loaded manual baseline.

**Q39. How do you ensure the LLM isn't hallucinating clinical facts?**
Four layers. Schema guardrail enforces Pydantic v2 output. Citation completeness guardrail requires every claim in the rationale to point to a `PolicyExcerpt` or clinical evidence. PHI input guardrail redacts before any model invocation. LLMGrader runs reflection on three sub-agents (evidence_matcher, counter_evidence_finder, letter_composer) — quality_threshold 0.80, retry-with-feedback escalates Haiku → Sonnet. Plus per-tenant Bedrock Guardrails at the API. Five layers total.

**Q40. What's the failure mode if a Bedrock model_id is deprecated?**
Per-tenant `tenant_policies.allowed_model_ids` is the gate. A deprecated model_id removed from the allowlist immediately blocks new calls (`GatewayPolicyViolation`). New model_id added → flip the env + restart workers; the cache key includes the schema_version so cached entries from the old model invalidate correctly. ADR-0006 covers the cache invalidation reasoning.

## Compliance & regulatory (CL/TL)

**Q41. CA SB 1120 says "physicians must make decisions" — is your HITL gate enough?**
Yes. SB 1120 doesn't say AI can't *suggest* a decision — it says AI can't be the *final adverse-determination signature*. ClinCase never produces a DENY that bypasses `review_gate`. The reviewer's signoff is on the `decisions` row attributed to them with `confidence=1.0` (human override). Provenance text on every reviewer override reads "HUMAN REVIEWER OVERRIDE — clinician {email} ..." — auditable.

**Q42. EU AI Act high-risk effective August 2, 2026 — what's your readiness?**
Annex III high-risk classification: healthcare access decisions support. Live model card at `/api/v1/responsible-ai/model-card.md` declares all 12 required fields. NIST AI RMF + ISO 42001 + EU AI Act all mapped. Risk register in the model card § failure_modes. Post-market monitoring via `/metrics` Prometheus + SLO breaches → PagerDuty.

**Q43. The CMS-0057-F § IV.A FHIR PARDA mandate hits January 2027. ClinCase doesn't expose that endpoint yet — is that a gap?**
We do — `/fhir/Claim/$submit` is live in `app/api/fhir_pas.py`. Da Vinci PAS Implementation Guide URL convention. The endpoint is up; what's not yet in is the X12 278 ↔ FHIR translation layer (CMS allows FHIR PARDA as a complete substitute under enforcement discretion). That's a Day-30 milestone in the pilot plan.

**Q44. What about HIPAA business associate agreements?**
ClinCase itself is the BA. AWS is sub-BA via the Bedrock + RDS BAA; Anthropic is sub-BA via Bedrock. The customer signs a BAA with AeroFyta. PHI never leaves the VPC (NetworkPolicy locks egress to RDS + Bedrock VPC endpoints only). Multi-tenant Bedrock Guardrail with PHI redaction at every InvokeModel.

## Business model & GTM (PL)

**Q45. the payer organization vertical revenue is ~$5B/year. What's the total addressable market for ClinCase?**
~80M Facets lives + ~20M QNXT lives = 100M lives addressable Day-0 inside the partner's existing book. Conservative oncology PA volume: 0.5% of lives generate an oncology PA event annually = 500K cases/year. At $5/case that's $2.5M/year revenue ceiling on oncology alone, inside the partner. Multi-specialty: cardiology + behavioral health + transplant push the ceiling to ~$15M/year. Outside the partner (other claims platforms) is 4× larger but slower to capture.

**Q46. How does ClinCase price vs Innovaccer Flow Auth or XiFin Empower Appeals?**
Innovaccer and XiFin are point solutions priced per-customer subscription at ~$300K-$1M/year. ClinCase prices per-case at ~$5, which for a 10K-case/day customer is $1.825M/year. We're more expensive at high volumes — but our embedded-into-TriZetto distribution model + the per-tenant Bedrock Guardrail + the auditor-grade Evidence Pack are differentiators they don't have. Net: customers buying TriZetto already → ClinCase; greenfield no-TriZetto customers → competitors.

**Q47. What's the path from pilot to strategic acquisition?**
Day 90 ROI report opens the conversation. Day 365: 3-5 specialty bundles live across 3-5 customers proves the platform thesis. Day 730: TriZetto product GM has the option to acquire AeroFyta (the company) or license ClinCase (the product) — in either case the marginal cost to the partner is lower than building, and the time-to-revenue is lower than the build-vs-buy alternative.

**Q48. What if AHIP's 80%-real-time-by-2027 commitment slips to 2028?**
The forcing function is CMS-0057-F (federal regulation, not voluntary), not the AHIP commitment. CMS-0057-F operational provisions are in force NOW. The slip-risk is on AHIP's *target*, not on the *floor*. ClinCase's value compounds because customers who hit AHIP early get the Star-Ratings revenue lift earlier — Day 90 vs Day 365 is the difference.

## Demo-day-specific (DO)

**Q49. The demo just failed mid-run. What do you do?**
Reload the page. If the agent trace SSE doesn't reconnect within 10 seconds, switch to the pre-recorded screen capture in `ops/demo/recordings/`. Backup browser tab on staging is preconfigured. Worst case: walk the deck and call out which endpoint we'd hit at this point, and offer to email the live demo URL after Q&A.

**Q50. Show me the most recent live LLM call.**
`SELECT * FROM llm_invocations ORDER BY id DESC LIMIT 1;` — the GenAI Gateway audit table. Or hit `GET /api/v1/llm-gateway/usage` for the rolling 24h tenant view.
