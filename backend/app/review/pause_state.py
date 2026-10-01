"""Durable state of a run that stopped for human review.

LangGraph is compiled without a checkpointer, so the graph cannot be resumed from memory (and the process that
paused it may be gone). Instead the pause records exactly what the remaining agents need — the outputs of the
agents that already ran — keyed by the paused run. The resume job rebuilds the state from this plus the case
row and runs the remaining graph (`build_resume_graph`). The payload is versioned; an unknown version is
refused rather than guessed at.
"""

from __future__ import annotations

import json
from typing import Any

from app.graph.state import ClinCaseState
from app.models import ClinicalSnapshot, NecessityAssessment, PolicyExcerpt

STATE_VERSION = 1


class PauseStateError(ValueError):
    """The stored pause state is missing, from an unknown version, or no longer valid."""


def dump_pause_state(final: ClinCaseState) -> dict[str, Any]:
    """The agent outputs a resume needs (everything produced before the review gate)."""
    return {
        "snapshot": final.clinical_snapshot.model_dump(mode="json")
        if final.clinical_snapshot
        else None,
        "excerpts": [e.model_dump(mode="json") for e in final.policy_excerpts],
        "assessment": final.necessity_assessment.model_dump(mode="json")
        if final.necessity_assessment
        else None,
    }


def restore_pause_outputs(blob: dict[str, Any], version: int) -> dict[str, Any]:
    """Validated `ClinCaseState` field values for the resumed run."""
    if version != STATE_VERSION:
        raise PauseStateError(f"unsupported pause state version {version}")
    try:
        return {
            "clinical_snapshot": ClinicalSnapshot.model_validate(blob["snapshot"])
            if blob.get("snapshot")
            else None,
            "policy_excerpts": [
                PolicyExcerpt.model_validate(e) for e in blob.get("excerpts") or []
            ],
            "necessity_assessment": NecessityAssessment.model_validate(blob["assessment"])
            if blob.get("assessment")
            else None,
        }
    except Exception as exc:  # noqa: BLE001
        raise PauseStateError(f"stored pause state is invalid: {exc}") from exc


def has_continuation_inputs(blob: dict[str, Any] | None) -> bool:
    """True when the stored outputs are enough for the remaining agents (they need the snapshot AND the
    assessment). A 'missing_assessment' pause is not: the human decision is still recorded, but no continuation
    can be run for it."""
    return bool(blob and blob.get("snapshot") and blob.get("assessment"))


async def save_pause_state(conn: Any, final: ClinCaseState, *, organization_id: str) -> None:
    """Persist the pause state of `final.run_id` (idempotent per run). Requires a run identity.

    Raises (rather than silently skipping) without one, so the caller's transaction rolls back instead of
    committing a case that is 'awaiting review' with no state to resume from."""
    if not final.run_id:
        raise PauseStateError("cannot persist pause state without a run identity")
    await conn.execute(
        """INSERT INTO case_run_states
              (run_id, case_id, organization_id, schema_version, pause_kind, pause_reason, state_json)
           VALUES ($1,$2,$3,$4,$5,$6,$7::jsonb)
           ON CONFLICT (run_id) DO UPDATE SET
              schema_version = EXCLUDED.schema_version, pause_kind = EXCLUDED.pause_kind,
              pause_reason = EXCLUDED.pause_reason, state_json = EXCLUDED.state_json""",
        final.run_id,
        final.case_id,
        organization_id,
        STATE_VERSION,
        final.pause_kind or "low_confidence",
        final.pause_reason,
        json.dumps(dump_pause_state(final)),
    )


async def load_pause_state(conn: Any, run_id: str) -> dict[str, Any] | None:
    """`{pause_kind, pause_reason, version, state}` for a paused run, or None if none was saved."""
    row = await conn.fetchrow(
        "SELECT pause_kind, pause_reason, schema_version, state_json FROM case_run_states WHERE run_id = $1",
        run_id,
    )
    if row is None:
        return None
    raw = row["state_json"]
    return {
        "pause_kind": row["pause_kind"],
        "pause_reason": row["pause_reason"],
        "version": row["schema_version"],
        "state": json.loads(raw) if isinstance(raw, str) else raw,
    }
