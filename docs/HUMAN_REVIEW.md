# Human review: pause, persist, wait, resume

```
LOW CONFIDENCE / (reserved: VERIFICATION DISAGREEMENT, EVIDENCE CONFLICT)
   → review_gate stops this execution of the graph (paused_for_review, pause_kind, pause_reason)
   → PERSIST: one transaction = case.status 'awaiting_review' + durable pause state (case_run_states) + run 'paused'
   → WAIT (the case sits in the reviewer queue; nothing is running)
   → HUMAN ACTION: POST /cases/{id}/resume
   → RESUME THE REMAINING GRAPH: a queued `resume_after_review` job runs build_resume_graph()
   → FINAL DECISION: the human Decision (written first, durably), then forecast → appeal (DENY) → patient letter
```

## What is persisted at the pause

`case_run_states(run_id)` holds exactly what the remaining agents need — the clinical snapshot, the policy
excerpts and the necessity assessment produced before the gate — plus `pause_kind`, `pause_reason` and a
schema version. It is written in the **same transaction** as the case status (both the synchronous `/run` and
the worker), so a case is never "awaiting review" without the state a resume needs. LangGraph is compiled
without a checkpointer; this explicit state replaces one, and a process restart loses nothing.

## What `/resume` does (one transaction)

1. Locks the case row; requires `awaiting_review` (otherwise 400 — this is what makes duplicate and
   simultaneous reviews safe: exactly one wins).
2. Finds the latest `paused` run and its pause state.
3. Mints a **resume run** (`trigger='resume'`, parent = the paused run) and marks the paused run `completed`.
4. Writes the human `Decision` (`human_override` citation, confidence 1.0), the reviewer action, the case's new
   status, and the `case.decided` event (`triggered_hitl=true`).
5. If the pause state is complete, enqueues the `resume_after_review` job in the same transaction and returns
   `continuation: {queued: true, job_id}`.

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

## Reruns and review

A newer execution that completes or pauses **supersedes** an older paused run (`superseded`): the case's state
now comes from the newer run, so a stale pause can no longer be resumed. A review therefore always resolves the
latest pause. `/review` actions (notes, escalations, overrides) are attributed to the latest run and do not
consume the pause.

## Configuration decision still open

`HITL_CONFIDENCE_THRESHOLD` defaults to `0.0`, so the confidence gate never fires by default (only the k8s
ConfigMap sets 0.75). That is a policy decision, not changed here; the mechanism above is exercised by tests
that force a pause.
