# Human review: pause, persist, wait, resume

```
LOW CONFIDENCE / MISSING ASSESSMENT / VERIFIER CONFLICT / EVERY AI-PROPOSED DENY
   → pause execution or hold advisory outputs before authoritative persistence
   → PERSIST: one transaction = case.status 'awaiting_review' + durable pause state (case_run_states) + run 'paused'
   → WAIT (the case sits in the reviewer queue; nothing is running)
   → HUMAN ACTION: POST /cases/{id}/resume
   → RESUME THE REMAINING GRAPH: a durable `resume_after_review` job runs build_resume_graph()
     (inline in the Vercel review request; otherwise a persistent worker)
   → FINAL DECISION: the human Decision (written first, durably), then forecast → appeal (DENY) → patient letter
```

## What is persisted at the pause

`case_run_states(run_id)` holds exactly what the remaining agents need — the clinical snapshot, the policy
excerpts and the necessity assessment produced before the gate — plus `pause_kind`, `pause_reason` and a
schema version. It is written in the **same transaction** as the case status (both the synchronous `/run` and
the worker), so a case is never "awaiting review" without the state a resume needs. LangGraph is compiled
without a checkpointer; this explicit state replaces one, and a process restart loses nothing.

Every AI-proposed DENY is held at **both persistence boundaries**, independent of confidence
and `HITL_CONFIDENCE_THRESHOLD`. After normal draft generation, the advisory decision, forecast,
appeal and patient letter are included in the pause state's `draft_outputs`. The response and
reloaded case expose `provisional_decision`, `human_review_required` and `documents_draft`;
the authoritative `decision` remains absent. No final decision row or `case.decided` event is
written for that proposal. The UI/PDF marks the letters as drafts and blocks final patient
email/submission until review. A low-confidence pause may occur earlier, before such drafts exist.

## What `/resume` does (one transaction)

1. Locks the case row; requires `awaiting_review` (otherwise 400 — this is what makes duplicate and
   simultaneous reviews safe: exactly one wins).
2. Finds the latest `paused` run and its pause state.
3. Mints a **resume run** (`trigger='resume'`, parent = the paused run) and marks the paused run `completed`.
4. Writes the human `Decision` (`human_override` citation, confidence 1.0), the reviewer action, the case's new
   status, and the `case.decided` event (`triggered_hitl=true`).
5. If the pause state is complete, enqueues the `resume_after_review` job in the same transaction.
   Worker mode returns `continuation: {queued: true, job_id}`. Inline mode reserves the job in
   that transaction and awaits the continuation after committing, returning its completion
   status and available results. `continuation.mode` distinguishes the paths.

The decision does not depend on the LLM being available. A case paused before pause state existed (or a
`missing_assessment` pause with no outputs to continue from) still gets its decision recorded; the response says
`continuation: {queued: false, reason: "no_pause_state" | "incomplete_pause_state"}`.

## The continuation

`build_resume_graph()`: `human_decision → denial_forecaster → (DENY → appeals_drafter) → patient_communicator`.
It is built from the same node functions and routing as the full graph; `human_decision` turns the reviewer's
verdict into the `Decision` using the same function the endpoint used for the stored row. The worker restores
the paused outputs from the pause state (an unknown version or corrupt state is **dead-lettered at once**, not
retried), runs the graph under the resume run, then in one transaction stores the appeal (stamped with the
resume run; case `denied → appealed`), marks the run `completed`, and publishes `done`.

If the continuation fails after its retries the reviewer's decision stands, the run is `failed`, SSE gets
`continuation_failed` then `done`, and `POST /cases/{id}/resume/retry` re-queues it (only while it is the
latest run and its job is dead-lettered).

### Serverless continuation and recovery

`continuation_mode: "auto"` selects inline execution when `VERCEL=1`; callers can explicitly
choose `"inline"` or `"worker"`. Inline execution uses the same durable job/graph with a
**240-second** application timeout, per-request cancellation and heartbeat/attempt fencing.
It does not require a process to remain alive after the response. A hosting platform may
enforce a shorter request limit; the deployment must accommodate the configured workflow.

For a failed current continuation, the reviewer can call `POST /cases/{id}/resume/retry`.
Inline retry may also recover a running job whose lease has had no heartbeat for more than
**60 seconds**. The tenant, case, latest run and expired lease are checked transactionally;
an active attempt or a newer run cannot be displaced. Incremented attempts fence old writes.
The human decision remains durable if letter generation times out or fails. Readback reloads
only the newest run's completed outputs, so an older DENY draft cannot replace a newer human
APPROVE or REFER.

## Reruns and review

A newer execution that completes or pauses **supersedes** an older paused run (`superseded`): the case's state
now comes from the newer run, so a stale pause can no longer be resumed. A review therefore always resolves the
latest pause. `/review` actions (notes, escalations, overrides) are attributed to the latest run and do not
consume the pause.

## Confidence threshold and mandatory denial review

`HITL_CONFIDENCE_THRESHOLD` defaults to `0.0`, so the **confidence-only** gate does not normally
fire by default (the local k8s ConfigMap sets 0.75). This setting does not bypass mandatory
review of an AI-proposed DENY. Optional independent verification can also pause a conflicting
decision when `VERIFIER_ENABLED` is configured. These paths share the durable review mechanism.

Current implementation: `backend/app/review/{human,pause_state}.py`, `backend/app/api/cases.py`,
`backend/app/workers/case_runner.py`. Tests and live-deployment limits are recorded in
[ONCOLOGY_UPLOAD_REVIEW_REPAIR.md](ONCOLOGY_UPLOAD_REVIEW_REPAIR.md).
