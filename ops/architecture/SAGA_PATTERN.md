# ClinCase — Saga Pattern (formalized)

**Companion to:** [`AGENTIC_ACTIONS.md`](./AGENTIC_ACTIONS.md) — defines the 5 typed actions
**Industry-grade primitive that prevents inconsistency between ClinCase and downstream systems.**

## The problem

ClinCase's case lifecycle has **5 typed actions** that span multiple systems:

1. `persist_decision` — writes a `decisions` row in our Postgres
2. `route_to_review` — writes `cases.status = awaiting_review` and emits SSE
3. `submit_to_trizetto_gateway` — POSTs Facets v3 + QNXT v2 envelopes to TriZetto
4. `draft_appeal` — writes an `appeals` row + emits the `clincase.appeal.drafted.v1` event
5. `notify_patient` — patient communication is generated; downstream notification dispatch (future)

Today the orchestrator runs these sequentially. **Failure modes that produce inconsistency:**

| Scenario | What goes wrong |
|---|---|
| `submit_to_trizetto` 200 OK, then network blip → `persist_decision` fails | TriZetto knows about the decision; we don't |
| `persist_decision` succeeds, `submit_to_trizetto` returns 500 | We have a decision; TriZetto doesn't |
| `draft_appeal` succeeds, `notify_patient` LLM call times out | Appeal exists; patient never told |

A simple `try/except` retry can't fix this — the actions touch *different transactional domains* (our DB, TriZetto's bus, customer's notification channel). This is the textbook **distributed transaction** problem.

## The solution: Saga + compensating transactions

A **saga** is a sequence of local transactions where each step has a defined **compensating action** that semantically undoes it. If step N fails, we run the compensations for steps 1..N-1 to restore consistency.

Two shapes:
- **Orchestrated saga** (we use this) — a central coordinator (the case worker) drives the steps and compensations.
- **Choreographed saga** — each service emits events; others subscribe and compensate. Higher coupling. Not for us today.

## The 5-action saga

```
┌──────────────────────────────────────────────────────────────────────────┐
│  Step           │  Forward action                │  Compensating action │
├─────────────────┼────────────────────────────────┼──────────────────────┤
│  1. persist_dec.│  INSERT decisions row          │  INSERT decisions    │
│                 │  + emit clincase.case.decided   │   row marked          │
│                 │                                │   `superseded=true`  │
├─────────────────┼────────────────────────────────┼──────────────────────┤
│  2. route_review│  UPDATE cases status=          │  UPDATE cases status=│
│                 │   'awaiting_review'            │   prior_status       │
├─────────────────┼────────────────────────────────┼──────────────────────┤
│  3. submit_triz │  POST envelope; receive        │  POST withdrawal     │
│                 │   gateway_id; record SHA-256   │   envelope refrng    │
│                 │                                │   prior SHA-256      │
├─────────────────┼────────────────────────────────┼──────────────────────┤
│  4. draft_appeal│  INSERT appeals row            │  UPDATE appeals      │
│                 │   + emit appeal.drafted.v1     │   status='withdrawn' │
├─────────────────┼────────────────────────────────┼──────────────────────┤
│  5. notify_patt │  Generate patient comm         │  No compensation     │
│                 │                                │   needed (additive)  │
└──────────────────────────────────────────────────────────────────────────┘
```

## Saga state persistence

Each in-flight saga is persisted in a new `case_sagas` table:

```sql
CREATE TABLE case_sagas (
    id           BIGSERIAL PRIMARY KEY,
    case_id      TEXT NOT NULL,
    saga_type    TEXT NOT NULL,                 -- 'full_run' | 'reviewer_resume' | 'appeal_draft_only'
    status       TEXT NOT NULL CHECK (status IN ('running', 'committed', 'compensating', 'compensated', 'failed')),
    completed_steps  TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    failed_step      TEXT,
    failure_reason   TEXT,
    started_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at     TIMESTAMPTZ,
    correlation_id   TEXT NOT NULL,             -- for OTel trace correlation
    UNIQUE (case_id, saga_type, started_at)
);
```

A saga's status transitions are observable in `/api/v1/cases/{case_id}/saga` (TODO post-pilot endpoint).

## Compensating action choreography

If step 3 (`submit_to_trizetto_gateway`) fails after step 1 succeeded:

```
1. persist_decision        → ✅ committed
2. route_to_review (skip)  → not applicable for APPROVE path
3. submit_to_trizetto      → ❌ FAILED (Bedrock-equivalent network 500)
   ↓ saga compensates
   COMPENSATE step 1 → INSERT decisions row marked superseded=true
   ↓
   case status: 'pending_compensation'
   ↓ alert SRE per ops/sre/RUNBOOK.md INC-008 (TODO)
```

This guarantees: **either all steps committed, or only consistent state remains**.

## Why this is industry-grade

- **Microservices.io / Chris Richardson's Saga pattern** — a standard reference in distributed-systems training.
- **TLA+ verifiable** — the saga state machine is finite (5 states); model-checkable in TLA+.
- **Observability** — each step's start + end is an OTel span; the full saga is one trace.
- **Idempotency** — every step has a unique `(case_id, step_name, attempt_id)` so retry-on-restart is safe.

## Where this lives in code

- **Today (round 9):** the case-completion path in `app/api/cases.py:run_full` runs steps 1, 4 atomically inside a single Postgres transaction (transactional outbox covers the event emit). Step 3 (TriZetto submit) is a separate user action — currently NOT in the saga.
- **Day 30 of pilot:** wire all 5 steps into a `Saga` orchestrator class in `app/sagas/case_lifecycle.py`. Add `case_sagas` table + Saga endpoint.
- **Day 60:** TLA+ specification of the state machine in `ops/architecture/saga.tla` for formal verification.

## What's deferred (with reason)

- ⚪ `case_sagas` table — the foundation is in `event_outbox` + `agent_runs`; standalone saga state lands at first multi-step failure incident
- ⚪ Saga visualization in `/architecture` page — TODO once `case_sagas` lands
- ⚪ Choreographed alternative — overkill at our scale; orchestrated saga is correct here

## Sources

- Saga pattern — https://microservices.io/patterns/data/saga.html
- Transactional outbox — https://microservices.io/patterns/data/transactional-outbox.html
- Companion: [`AGENTIC_ACTIONS.md`](./AGENTIC_ACTIONS.md)
- Companion: [`backend/app/events/outbox.py`](../../backend/app/events/outbox.py)
