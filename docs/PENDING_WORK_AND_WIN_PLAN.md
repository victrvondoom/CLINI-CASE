# Pending work, hackathon win plan, and path to a product

Honest status first: the engineering core (run identity, real human-in-the-loop pause/resume, security fixes, Bedrock
hardening, model registry, independent verifier, twin) is built and CI-green. Nothing below has been run against live
AWS/Bedrock, a real LLM at scale, or real users. Judges reward what they can *see working*, so most pending work is
about proof and demo, not more features.

## Status update (follow-up pass)

| # | Item | Status |
|---|---|---|
| 1 | Live run with a real model | **Not done** - no LLM/AWS credentials in this environment. `scripts/eval_harness.py --mode live` is ready and refuses to run without credentials. |
| 2 | Verifier + HITL on in the demo | **Done as config**: `ops/demo.env.example` (defaults stay off). |
| 3 | Measured evaluation | **Partly**: verifier fault-injection results in `EVALUATION_RESULTS.md` (synthetic, no LLM). Clinical accuracy still needs a labelled set + live run. |
| 4 | Browser pass | **Done locally** (Playwright, seeded data): cases, case detail, reviewer, agents, cohorts render without app errors. Found and fixed: the twin panel was hidden unless a run was started in-session. |
| 5 | Reachable demo deployment | **Not done** - deployment/AWS changes were out of scope; needs a managed Postgres. |
| 6 | Security gaps | **Done**: policy mutations platform-admin only; OIDC `return_to` same-origin only; login brute-force throttle (process-local); containers run non-root (Dockerfiles changed, **images not built here**). **Open**: ALB HTTP-only (infra), shared/distributed rate limiter. |
| 7 | Extractor LLM call budget | **Done**: charged to the per-case budget; was already gateway-audited. |
| 8 | W3C trace across queue | **Done and verified** with the real OTel SDK (traceparent in job payload, restored in worker). Collector screenshot: not done. |
| 9 | Single pricing source | **Done** (`app/llm/pricing.py`). |
| 10 | AWS availability + registry | **Not done** - needs AWS access. |

## A. Pending engineering work (ordered by value for a win)

**Must do (proof):**
1. **Run the whole thing live once, end to end, with a real model** (OpenRouter is fine) on 10+ seeded cases and record
   it. Nothing has been demonstrated with a real LLM in these phases.
2. **Turn on the verifier and the HITL gate in the demo** (`VERIFIER_ENABLED=true`, `HITL_CONFIDENCE_THRESHOLD` ~0.7).
   Today both are off, so the headline features (independent verification, human escalation) never fire by default.
3. **A measured evaluation**: labelled case set -> accuracy of verdicts, verifier agreement/catch rate, % citations that
   resolve, escalation rate, cost and latency per case. One results table beats ten claims. (Plan in `PLATFORM_HARDENING.md`.)
4. **Browser pass of the UI** against seeded data (twin panel, runs list, reviewer queue). Never verified visually.
5. **Deploy a reachable demo.** The ECS demo has no database (non-dev login returns 503). A judge must open a URL and
   see it work; use one managed Postgres (or Supabase) and a seeded tenant.

**Should do (credibility):**
6. Fix the known security gaps: policy-library write hole (any authenticated user can mutate the global corpus), OIDC
   redirect token leak, login brute-force limit, ALB HTTP-only, containers running as root.
7. Route the clinical extractor's direct LLM call through `Agent.invoke` (budget/cache/trace) and the gateway.
8. Restore a W3C parent trace across the queue boundary (worker currently has correlation attributes only) and run one
   real OTel collector screenshot.
9. Single source of truth for model pricing (duplicated in two files).
10. Verify AWS account/region/model availability, then fill the model registry (`MODEL_REGISTRY_JSON`) and mark entries `active`.

**Could do (only if time remains):** SQS adapter + KEDA, AgentCore, OpenSearch, HAPI FHIR. Deliberately *not* recommended
before the proof items: they add risk and no visible demo value.

## B. How to win 1st place among ~10,000 entrants

Most entries are a chat wrapper or a dashboard. You win by being the one that is **trustworthy, demonstrable and
measured** in a domain where trust is the product.

1. **One sharp story (30 seconds):** "Prior authorization decisions are slow, opaque and unaccountable. CLINI-CASE makes
   every AI decision evidence-cited, independently verified, fully traceable, and hands uncertain cases to a human — with
   an audit twin a regulator can replay." Tie to real rules already in the code (CMS-0057-F, CA SB 1120).
2. **The 3-minute demo script (rehearse it):**
   a. Submit a clear case -> approved in seconds, every claim cited to a FHIR resource.
   b. Submit an ambiguous case -> verifier disagrees / confidence low -> **pauses**, appears in reviewer queue.
   c. Reviewer overrides -> pipeline **resumes**, appeal/communication generated, new run recorded (`superseded` history).
   d. Open the **Case Digital Twin**: run history, evidence lineage, cost reconciliation, tamper hash.
   e. Show an attempted cross-tenant access being refused (404) and the audit trail.
3. **A results slide with real numbers** (section A3). Judges cannot argue with a table.
4. **Show what you refused to do:** no silent model fallback, guardrail blocks are never returned as answers, unverified
   models are refused. This signals production maturity few competitors will have.
5. **Polish:** a 2-minute video, a one-page architecture diagram, a README that runs in one command, a live URL.
6. **Pre-empt judge questions:** cost per case, PHI handling (de-identified; routing unchanged), failure behaviour,
   what is simulated vs real. Be explicit about limits — it increases credibility.

Reality check: with 10,000 entrants no one can promise first place. These steps maximise the odds; the largest lever is
a flawless live demo plus measured results.

## C. From project to product (and to $2,000)

**Wedge customer:** mid-size health plans, TPAs and provider revenue-cycle teams drowning in prior-auth volume and facing
the CMS interoperability/prior-auth rules (electronic PA APIs due 2026-27). Buyers pay for fewer denials, faster turnaround
and audit-readiness.

**Product shape:** "Evidence-grounded authorization copilot with an audit trail" delivered as
(1) a FHIR/PAS-compatible API and (2) the reviewer console. The Case Digital Twin is the differentiator — compliance
teams buy auditability.

**Path (pragmatic):**
1. Pilot with 1-2 friendly clinics/plans on de-identified or synthetic data; measure turnaround and agreement with
   human reviewers.
2. Harden: SOC2-style controls, BAA-capable hosting (Bedrock in your account), tenant isolation tests (exist), key
   management, rate limits.
3. Pricing: per-case fee ($1-5) or per-seat reviewer licence + platform fee.
4. Regulatory posture: decision-support with mandatory human sign-off for adverse determinations (already enforced by
   design) — keep this explicit.

**Getting the $2,000 specifically:** prize money is won by the demo, not the roadmap. Prioritise A1-A5, then the demo
script and video. A prize is also a funding bridge: spend it on cloud credits for the pilot, not new features.
