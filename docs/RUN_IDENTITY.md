# Case, run and trace identity

**ONE CASE → MANY RUNS → EACH ARTIFACT TRACEABLE.** Implemented in `backend/app/identity.py`,
`backend/app/runs.py`, `backend/app/agents/framework/run_registry.py`.

| Identifier | Scope | Where it lives |
|---|---|---|
| `case_id` | one authorization case | `cases.id` |
| `case_intelligence_id` (`CI-…`) | the case, stable across every run | stored on `cases` and on every run artifact (derived deterministically from organisation + case, so it can always be re-verified) |
| `run_id` (`run_…`) | one execution of the case: `initial`, `rerun`, or a human-review `resume` | `case_runs` (attempt number per case, parent run, trigger, status, trace id) |
| `trace_id` | 32-hex W3C trace id of the run (the active OpenTelemetry trace when one exists) | `case_runs.trace_id` |
| `job_attempt` | the queue's retry counter | `agent_runs.job_attempt` — a crash-retry re-executes the DAG under the **same** run id |

## What carries the identity

`agent_runs`, `llm_invocations` (run, case-intelligence and trace ids), `decisions`, `appeals`,
`reviewer_actions`, the outbox `case.decided` event (`decision_run_id`, `trace_id`), every SSE event the run
emits, the queue payload (`case_jobs.payload_json.run`), the LangGraph state (`ClinCaseState`), and the
per-run `AgentContext`. All columns are additive and nullable; rows from before this change simply have no
run id and appear in the twin as a `legacy` run.

## Real propagation

```mermaid
sequenceDiagram
    autonumber
    participant C as Client
    participant API as API (jobs.py / cases.py)
    participant R as runs.start_run
    participant Q as case_jobs
    participant W as Worker (case_runner)
    participant G as LangGraph + run_registry
    participant A as Agent.invoke
    participant S as PostgresTraceSink
    participant L as GenAIGateway
    participant E as SSE (publish)

    C->>API: POST /cases/{id}/run-async
    API->>R: start_run(status=queued)   [advisory lock per case → attempt_no]
    R-->>API: RunIdentity(run_id, attempt_no, CI-id, trace_id)
    Note over R: cases.case_intelligence_id stored; case_runs row inserted
    API->>Q: enqueue(payload + run identity)   [idempotent replay → same run, no new run]
    API->>R: mark_run(queued, job_id)
    W->>Q: claim_next
    W->>R: mark_run(running, job_id)
    W->>G: ainvoke(state_for_run(identity))   [identity is graph state]
    loop each of the 7 agents
        G->>A: node(state) → get_or_init_agent_context(state)
        Note over G: one AgentContext per (run, job_attempt): shared budget, sink, identity
        A->>S: open_span(identity) → agent_runs(run_id, CI, trace_id, job_attempt)
        S->>E: agent_started {run_id, CI, trace_id}
        A->>L: complete() [GatewayCallContext carries identity]
        L-->>L: llm_invocations(run_id, CI, trace_id)
        A->>S: close_span_ok
        S->>E: agent_finished {run_id, …}
    end
    W->>W: _commit_run (one transaction)
    Note over W: decisions / appeals (run_id, CI) + outbox(decision_run_id, trace_id) + case_runs.status = completed|paused
    W->>E: hitl_pause (if paused) + done {run_id, …}
    W->>G: release context
```

A synchronous `POST /cases/{id}/run` follows the same path inside the request. A human `POST
/cases/{id}/resume` mints its own run (`trigger='resume'`, parent = the run it follows) in the same
transaction as the decision and the reviewer action; `POST /cases/{id}/review` attributes the action to the
case's latest run.

## Reruns

* A new submission is a new run (`attempt_no` = previous + 1, `trigger='rerun'`, `parent_run_id` = previous).
* An idempotent replay of an existing job returns the **same** run. Because the default idempotency key is
  derived from the case, a deliberate async rerun needs an explicit `Idempotency-Key`; the synchronous
  endpoint always starts a new run.
* Crash-retries of a job re-execute under the same run id; `agent_runs.job_attempt` separates the rows.
* Run status: `queued → running → completed | paused | failed | cancelled | superseded` (a paused run replaced by a newer execution). A job that is retried returns its
  run to `queued`; a dead-lettered or reaped job fails it.

## Digital Twin

`GET /api/v1/cases/{id}/twin` is now run-aware: the headline sections (agents, evidence, trace, queue events)
describe the **latest execution run only** (a `resume` run never replaces it), `runs` summarises every run,
decisions and reviewer actions carry their `run_id`, and trace offsets are relative to the run. Cases without
run records fall back to the previous whole-case projection. `GET /api/v1/cases/{id}/runs` lists the runs.

## Not done in this phase

OpenTelemetry spans and W3C context propagation across the queue (the `trace_id` value is carried and stored,
but no span uses it yet), snapshot persistence of the twin, and the independent verifier. Human review (pause
state, resume run, continuation) is described in [`HUMAN_REVIEW.md`](HUMAN_REVIEW.md).
