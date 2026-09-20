# ClinCase — Edge Case Taxonomy

**Audience:** reviewers asking "what about when…?" · TriZetto SREs · QA on the first pilot

This is the canonical list of edge cases ClinCase handles. For each: the **trigger**, the **expected behavior**, **where it's handled**, and **where it's tested**. If a future judge asks "does the app handle X?", the answer is in this table.

---

## Lifecycle / orchestration

| # | Edge case | Trigger | Expected behavior | Where handled | Where tested |
|---|---|---|---|---|---|
| 1 | **Worker crashes mid-DAG** | Worker process dies after claiming a job | Heartbeat stops; janitor reaps after 2× heartbeat interval; case requeued with `attempts++`; dies after `max_attempts=3` | `app/workers/case_runner.py` (heartbeat loop, janitor) · `app/jobs/queue.py` (`reap_stale`) | Manual concurrent-claim test (per memory); janitor unit test |
| 2 | **Concurrent claim race** | Two workers fetch the same queued job | One wins; other gets the next job (or None) | `app/jobs/queue.py:claim_next` — `SELECT … FOR UPDATE SKIP LOCKED` | Verified concurrent-claim test (existing) |
| 3 | **Idempotent submit storm** | Client retries `POST /run-async` 50× after a 504 | Single `job_id` returned for all 50; same idempotency_key dedups | `app/api/jobs.py:_derive_idempotency_key` · `app/jobs/queue.py:enqueue` (UNIQUE index) | Manually verified at SCALE-2 demo |
| 4 | **Schema parse failure** | LLM emits malformed JSON | Framework retries with grader feedback; escalates Haiku → Sonnet on retry; raises `AgentExhausted` after `max_iterations` | `app/agents/framework/agent.py` (parse retry loop) | Contract tests in `backend/tests/agents/` |
| 5 | **Per-case `BudgetExceeded`** | Runaway loop breaches $5 / 600 K-tok / 600 s ceiling | `BudgetExceeded` raised BEFORE LLM token spent; case marked `error`; not retried | `app/agents/framework/budget.py` (reservation pattern) | Unit test with low ceiling |

## HITL / regulatory

| # | Edge case | Trigger | Expected behavior | Where handled | Where tested |
|---|---|---|---|---|---|
| 6 | **Low-confidence Necessity Reasoner** | `overall_confidence < HITL_CONFIDENCE_THRESHOLD` (0.75) | DAG routes to `review_gate` terminal; case `status='awaiting_review'`; SSE `hitl_pause` event emitted | `app/graph/build.py` (conditional edge) · `app/api/cases.py` (run_full handler) | Demo fixture cases (`oncology_low_confidence`) |
| 7 | **Reviewer resume after pause** | Coordinator/reviewer fires `POST /cases/{id}/resume` with verdict + note | Decision row written attributed to human reviewer · case status updated · reviewer_actions audit row · Foundry/Evidence-Pack records the override | `app/api/cases.py:resume_after_review` | Demo path; ADR-0007 |
| 8 | **DENY without reviewer signoff** (forbidden state) | Worker writes a DENY row with no preceding reviewer_actions row | Detected by SLO `hitl-signoff` (`/api/v1/compliance/org` `sb1120_compliance_pct < 100%`); P1 alert; SRE runbook INC-004 | `ops/sre/SLO.yaml` · `ops/sre/RUNBOOK.md` § INC-004 | Synthetic SLO breach test (TODO post-pilot) |
| 9 | **HITL_CONFIDENCE_THRESHOLD = 0** (dev/demo) | Hackathon demo wants every case to run through the full DAG | All cases bypass the gate; reviewer_queue stays empty; demo shows full 7-agent flow | `app/config.py` (env-driven) | The demo itself |

## Data / context

| # | Edge case | Trigger | Expected behavior | Where handled | Where tested |
|---|---|---|---|---|---|
| 10 | **PHI suspect pattern in prompt** | A coordinator pastes a note with raw "SSN: 123-45-6789" | GenAI Gateway logs `phi_suspect_pattern` event; Bedrock Guardrail (per-tenant) redacts at the API; `phi_sanitizer` sub-agent applies in-process redaction | `app/llm/gateway.py:_content_safety_pre_check` · `app/agents/clinical_extractor/sub_agents/phi_sanitizer.py` · `BEDROCK_GUARDRAIL_ID` per tenant | Manual `Test PHI Guardrail` button on Case Detail |
| 11 | **Empty FHIR bundle** | Submit a case with `fhir_bundle: {}` | `fhir_resource_validator` raises with structured error; case status `error`; surfaced to coordinator with actionable message | `app/agents/clinical_extractor/sub_agents/fhir_resource_validator.py` | Contract test |
| 12 | **No matching policy** | A treatment with no payer-policy hit (e.g. unindexed payer) | `policy_retriever` returns `excerpts=[]`; downstream `necessity_reasoner` flags as REFER (not enough info to decide) | `app/agents/policy_retriever/orchestrator.py` (empty candidates branch) | Demo fixture (`fixture_unmatched_payer`) |
| 13 | **Citation completeness violation** | Decision rationale has a claim with no citation pointer | `CitationCompletenessGuardrail` raises `OutputBlocked`; agent retries with feedback; if still missing, case routes to review_gate | `app/agents/framework/guardrails.py:CitationCompletenessGuardrail` | Contract test on Decision Composer |
| 14 | **Stale policy** | Policy was updated since the decision was rendered | Decision row shows the policy version it cited; PolicyDiff route flags affected in-flight cases | `app/data/policies.json` versioning · `frontend/src/routes/PolicyDiff.tsx` | TODO post-pilot |

## Cost / capacity

| # | Edge case | Trigger | Expected behavior | Where handled | Where tested |
|---|---|---|---|---|---|
| 15 | **Per-tenant Gateway quota breach** | Single tenant submits 60K cases/day exceeding their daily token cap | `GatewayQuotaExceeded` raised; case marked `error`; `Retry-After` header surfaced; SLO `llm-cost` alarm fires | `app/llm/gateway.py:_check_quota` | Live verification via `/api/v1/llm-gateway/usage` |
| 16 | **Per-org case quota (separate from Gateway)** | Tenant exceeds daily case count cap | HTTP 429 with `Retry-After` and structured error body; idempotent replays do NOT consume an additional quota slot | `app/quotas.py:consume_case_quota` (atomic SQL gate) | Live verification |
| 17 | **Bedrock 5xx during reasoning** | Bedrock regional brownout | `ModelRouter.escalate(...)` switches Haiku → Sonnet on retry; retry-with-feedback loop; SLO `api-availability` burn-rate alert | `app/agents/framework/models.py:ModelRouter` · `app/agents/framework/agent.py` retry loop | Manual fault-injection during dev |
| 18 | **Bedrock regional outage** | All workers fail to claim or call | API tier still queues jobs; backlog drains when region recovers; multi-region failover (apply-ready) | `ops/terraform/multi-region/route53.tf` (LBR + health checks) · `ops/sre/RUNBOOK.md` § INC-002 | Tabletop drill (TODO post-pilot) |
| 19 | **OpenRouter 402 Payment Required** (dev only) | Dev account out of credits | Surface as agent error in trace; fallback to `LLM_PROVIDER=anthropic` direct OR migrate to Bedrock (May 6 Pune migration) | Switching env var | Encountered + documented |

## Cache / dedup

| # | Edge case | Trigger | Expected behavior | Where handled | Where tested |
|---|---|---|---|---|---|
| 20 | **Cache key collision** (different orgs, same input) | Org A and Org B coincidentally have byte-identical sub-agent input | NO collision — cache key includes `organization_id` so they're isolated | `app/agents/framework/cache.py:CacheKey.derive` | Schema-version-pinned test |
| 21 | **Stale cache after schema change** | Agent's `output_schema` changes in a deploy | Cache key invalidates immediately (key contains `schema_version_for(output_schema)`) — no manual invalidation | `app/agents/framework/cache.py:schema_version_for` | Manual deploy verification |
| 22 | **Cache infra failure** | Cache table corrupt or DB connection lost during lookup | Caught + logged; lifecycle continues to LLM call; never blocks an agent run | `app/agents/framework/agent.py` (try/except around cache lookup) | Manual fault-injection |

## Security / multi-tenant

| # | Edge case | Trigger | Expected behavior | Where handled | Where tested |
|---|---|---|---|---|---|
| 23 | **Cross-org case access** | User from Org A queries `GET /api/v1/cases/{id}` for an Org B case | Returns 404 (not 403 — never leak existence) | `app/api/cases.py` (`WHERE organization_id = $1` everywhere) | Manual test |
| 24 | **JWT expired** | Token past TTL | API returns 401; frontend `jsonOrThrow` redirects to /login | `app/auth/dependencies.py:get_current_user` · `frontend/src/lib/api.ts:jsonOrThrow` | Manual test |
| 25 | **Disallowed model in tenant policy** | Tenant policy doesn't include a requested model_id | `GatewayPolicyViolation` raised before InvokeModel | `app/llm/gateway.py:complete` | Tested in smoke test |

## Demo-specific

| # | Edge case | Trigger | Expected behavior |
|---|---|---|---|
| 26 | **Demo mock mode for TriZetto** | `TRIZETTO_GATEWAY_URL=""` | Gateway client routes to in-process mock receiver; demo shows round-trip through `/_mock/inbox`; visibility intact for judges |
| 27 | **Demo mock mode for Q Business** | `AMAZON_Q_APPLICATION_ID=""` | `q_business_retriever` returns deterministic fixture; demo runs offline |
| 28 | **Demo mock mode for Bedrock** | `LLM_PROVIDER=openrouter` (and credits available) | Tested LLM path; falls back to Bedrock when migration done May 6 |

---

## How to verify any of these in the live demo

```bash
# Trigger HITL pause (case fixture #6)
curl -X POST http://localhost:8000/api/v1/demo-fixtures/oncology_low_confidence/create-case \
  -H "Authorization: Bearer $TOKEN"

# Verify cross-org isolation (case fixture #23)
# Login as user from Org B, then:
curl -X GET http://localhost:8000/api/v1/cases/{some_org_a_case_id} \
  -H "Authorization: Bearer $TOKEN_FROM_ORG_B"
# Expected: 404 (not 403)

# Verify Gateway quota (case fixture #15)
curl http://localhost:8000/api/v1/llm-gateway/usage -H "Authorization: Bearer $TOKEN"
# Returns rolling 24h consumption + caps
```
