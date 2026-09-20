# ClinCase — Smoke Test Results

**Run command:**
```bash
cd backend && .venv/Scripts/python.exe -m scripts.smoke_test
```

**Run script:** [`backend/scripts/smoke_test.py`](../../backend/scripts/smoke_test.py)
**Last run:** 2026-05-02 (round-7 verification)
**Result: PASS** ✓

---

## What this verifies

The smoke test boots the full FastAPI app + walks every architecture layer's primitives, executing them where they don't require live infra (DB, Bedrock, Q Business). Each layer's pass condition is concrete:

| Layer | Pass condition | Verified |
|---|---|---|
| **1 — Experience Layer** | All routes register | ✓ 56 routes |
| **2 — Orchestration & Policy Engine** | Auto-discovered manifest + budget primitive lifecycle | ✓ 7 parents · 22 sub-agents · BudgetTracker reserve→commit cycle |
| **3 — Context Retrieval** | Q Business client returns deterministic mock snippets | ✓ 2 snippets returned with score 0.94 |
| **4 — GenAI Gateway** | Factory returns Gateway-wrapped LLMClient · cost math correct | ✓ `GenAIGateway` returned · Sonnet 24k+4.5k = $0.1395 |
| **5 — Telemetry & Governance** | CMS-0057-F clauses tracked · live `/architecture/layers` returns descriptor · Foundry manifest matches | ✓ 8 clauses (6 in force today) · 6 layers · 4 KPIs · agents_total=7 · sub_agents_total=22 |
| **External Integrations** | Facets event builds + emits valid SHA-256 · TriZetto mock client active | ✓ action=`closed_approved` · hash=`640bcceeeb7379c6...` |
| **Business Value Math** | Humana 0.5-star = $1.26B · per-case savings = $1,499.75 | ✓ both verified |

---

## Raw output (last run)

```
LAYER 1 - EXPERIENCE LAYER
  routes registered:                  56

LAYER 2 - ORCHESTRATION & POLICY ENGINE
  parent agents auto-discovered:      7
  sub-agents auto-discovered:         22
  BudgetTracker.reserve works:        ok
  BudgetTracker.commit works:         ok (remaining=$4.96)

LAYER 3 - CONTEXT RETRIEVAL
  AmazonQClient.retrieve (mock):      2 snippets
  first snippet score:                0.94

LAYER 4 - GENAI GATEWAY
  factory returns:                    GenAIGateway
  Gateway implements LLMClient:       True
  cost(Sonnet 24k+4.5k tok):          $0.1395

LAYER 5 - TELEMETRY & GOVERNANCE
  CMS-0057-F clauses tracked:         8
  clauses in force today:             6 of 8
  /architecture/layers:               6 layers, 4 KPIs
  /foundry/manifest agents_total:     7
  /foundry/manifest sub_agents_total: 22

EXTERNAL INTEGRATIONS
  Facets event build:                 action=closed_approved
  SHA-256 (first 16):                 640bcceeeb7379c6
  TriZetto client mode:               mock

BUSINESS VALUE SPOT-CHECK
  Humana 0.5-star revenue lift:       $1.26B / yr
  AMA manual PA baseline:             $1500 / case
  ClinCase clean APPROVE cost:         $0.25 / case
  per-case savings (clean APPROVE):   $1499.75

SMOKE TEST: PASS
  - all 5 layers' primitives import + execute correctly
  - external integrations build without error
  - business-value math anchored to public sources
```

---

## What this does NOT verify (and the procedure for each)

| Path | Why not in smoke | Procedure |
|---|---|---|
| **Live Bedrock InvokeModel** | Requires Bedrock account + credits + region access | Run end-to-end demo fixture after May 6 Pune migration; cohort eval at `GET /api/v1/eval/cohort` produces real F1/accuracy numbers |
| **Concurrent worker claim** | Already verified separately ([`ops/sre/LOAD_TEST_RESULTS.md`](../sre/LOAD_TEST_RESULTS.md) Tier 1) | `pytest backend/tests/jobs/test_concurrent_claim.py` |
| **Live RDS connection** | Smoke runs without DB; `agent_runs` writes are exercised in actual case runs | Backend boot logs `db.connected`; verified at T-24h preflight |
| **End-to-end SSE trace** | Requires running frontend | T-24h preflight in [`DEMO_DAY_CHECKLIST.md`](./DEMO_DAY_CHECKLIST.md) |
| **HITL pause + resume** | Requires DB + LLM | Verified by demo fixture run with `oncology_low_confidence` |

These are scheduled in the demo-day checklist.

---

## How to re-run

```bash
cd backend
.venv/Scripts/python.exe -m scripts.smoke_test
```

If anything fails, the missing import or assertion will surface in the output. The script is fail-fast (no try/except wrapping) so a regression is immediately visible.
