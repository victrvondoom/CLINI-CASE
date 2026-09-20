# ADR-0007 — HITL `review_gate` as a LangGraph node, not a separate workflow

## Status
Accepted · 2026-04-25

## Context

CMS-0057-F § IV.C and CA SB 1120 (Physicians Make Decisions Act, eff. 2025-01-01) require a *qualified clinician* to make and sign every adverse determination. AI may not autonomously deny medical necessity. ClinCase must therefore route low-confidence cases to a human reviewer before any DENY verdict is finalized.

Two structural options were on the table:

1. **Separate workflow** — when `necessity_reasoner.overall_confidence < HITL_CONFIDENCE_THRESHOLD`, drop the case into a `reviewer_queue` table. A separate API endpoint (`POST /cases/{id}/review-action`) lets a reviewer decide. Then a *different* DAG run finalizes the case.
2. **In-DAG review_gate node** — make `review_gate` a real LangGraph node terminating the case in a `paused_for_review` status. The reviewer's resume action (`POST /cases/{id}/resume`) writes the decision row + reviewer_action audit row directly, without re-running the DAG.

## Decision

**`review_gate` as a LangGraph node.**

- Conditional edge after `necessity_reasoner` routes to `review_gate` if `overall_confidence < HITL_CONFIDENCE_THRESHOLD`.
- The node sets `state.paused_for_review = True`, `state.pause_reason = ...`; the case row's `status` becomes `awaiting_review`.
- A separate API endpoint `POST /cases/{id}/resume` accepts the reviewer's verdict + note. It writes a `decisions` row attributed to the human reviewer (with provenance text *"HUMAN REVIEWER OVERRIDE — clinician {email} ..."*) and a `reviewer_actions` row.
- The DAG's audit chain shows: extractor → retriever → reasoner → **review_gate** → (resume) → terminal.

## Consequences

**Positive**
- **One DAG = one audit chain.** Every case has a single `agent_runs` trace + a single `reviewer_actions` history. A CMS auditor pivots from `case_id` → all rows; no need to join across two DAG runs.
- **Reviewer signoff is inline with the trace.** SB 1120's required *"clinician reviewed and signed"* is provable from the same `case_id`-scoped query that proves the decision was made within 90 s.
- **Operator UX is single-screen.** The Case Detail page shows the agent trace + the reviewer action from the same SSE stream. No "go to a different queue" context switch.
- **Resume is cheap.** Resume doesn't re-run the DAG — it writes a Decision row sourced from the human reviewer (with confidence 1.0 by definition of human override). Avoids re-charging Bedrock for an already-reasoned case.

**Negative**
- **Adds a node to LangGraph** the LangGraph compiler treats as terminal; the DAG isn't strictly DAG-shaped (review_gate has only an explicit "exit" path, not a cycle back to decision_composer). Tradeoff: the simplicity of "the reviewer decides; we record it" beats trying to model human override as a re-run.
- **Reviewer can't easily "send back to the agents" with new constraints.** If the reviewer wants more analysis, they can't tell the DAG "rerun with this hint" — they decide manually. Mitigated by the `add_note` reviewer action + cohort eval feeding back into the next prompt revision.

**Neutral**
- HITL_CONFIDENCE_THRESHOLD is per-deployment configurable (env var). 0.0 in dev for full DAG runs; 0.75 in prod per CA SB 1120 conservative interpretation.

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| Separate `reviewer_queue` workflow | Two audit chains per case (the agent run + the reviewer run). Joining them is bug-prone; a row-level audit query goes from one table scan to a multi-table join. |
| Reviewer overrides go back into LangGraph as a new state | Modeling "rerun with reviewer hint" inside LangGraph is complex (would need cycle support + a "human input" step type). Not worth the complexity for the marginal benefit. The override path is straight-line: reviewer decides, we record, done. |
| AgentCore Gateway-driven HITL | AgentCore could expose an "ask the human" tool. We'd still need our own `reviewer_actions` audit table for SB 1120; the LangGraph node already integrates that. |

## References

- CA SB 1120 statute summary: https://www.sheppardhealthlaw.com/2024/11/articles/state-legislation/california-limits-health-plan-use-of-ai-in-utilization-management/
- Implementation: `backend/app/graph/build.py` (review_gate node + conditional edge)
- Resume endpoint: `backend/app/api/cases.py` (`POST /cases/{id}/resume`)
- Reviewer audit: `reviewer_actions` table (schema `backend/db/schema.sql`)
