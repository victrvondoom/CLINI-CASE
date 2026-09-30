"""Reviewer queue — REFER cases waiting for a human, built from the caller's real cases.

Each item is assembled from what the pipeline actually recorded for the case: the latest decision (rationale,
confidence) and the Necessity Reasoner's assessment (which criteria were ambiguous / not met and what evidence
would resolve them). Priority is a transparent heuristic over that confidence and how long the case has waited.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any

from app.db import db

#: confidence below which a case is high priority / medium priority
HIGH_BELOW = 0.55
MEDIUM_BELOW = 0.70
#: a case waiting at least this long is bumped one priority level
STALE_AFTER_MINUTES = 24 * 60
PRIORITY_RULE = (
    f"high: confidence < {HIGH_BELOW:.2f}; medium: < {MEDIUM_BELOW:.2f}; otherwise low. "
    f"Cases waiting over {STALE_AFTER_MINUTES // 60} h move up one level."
)
_LEVELS = ("low", "medium", "high")


def _as_obj(v: Any) -> Any:
    if isinstance(v, str):
        try:
            return json.loads(v)
        except ValueError:
            return None
    return v


def _first_sentence(text: str | None, limit: int = 220) -> str | None:
    if not text:
        return None
    t = re.sub(r"\s+", " ", text).strip()
    m = re.match(r"(.+?[.!?])(\s|$)", t)
    s = m.group(1) if m else t
    return s if len(s) <= limit else s[: limit - 1].rstrip() + "…"


def priority_for(confidence: float | None, age_minutes: float) -> str:
    level = (
        0
        if confidence is None
        else (2 if confidence < HIGH_BELOW else 1 if confidence < MEDIUM_BELOW else 0)
    )
    if confidence is None:
        level = 1  # unknown confidence should not be buried
    if age_minutes >= STALE_AFTER_MINUTES:
        level = min(2, level + 1)
    return _LEVELS[level]


def build_item(row: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    necessity = _as_obj(row.get("necessity")) or {}
    criteria = necessity.get("criteria") or []
    unresolved = [c for c in criteria if c.get("status") in ("AMBIGUOUS", "NOT_MET")]
    missing: list[str] = []
    for c in unresolved:
        m = (c.get("missing_evidence") or "").strip()
        if m and m not in missing:
            missing.append(m)
    reason = (
        _first_sentence(row.get("rationale"))
        or _first_sentence(necessity.get("summary"))
        or (unresolved[0].get("criterion_text") if unresolved else None)
        or "Referred for human review."
    )
    confs = [
        x
        for x in (row.get("decision_confidence"), necessity.get("overall_confidence"))
        if isinstance(x, int | float)
    ]
    confidence = round(float(min(confs)), 2) if confs else None
    since = row.get("decided_at") or row["created_at"]
    age = max(0.0, (now - since).total_seconds() / 60.0)
    return {
        "case_id": row["id"],
        "patient": row["patient_initials"],
        "treatment": row["treatment"],
        "payer": row["payer_id"],
        "status": row["status"],
        "priority": priority_for(confidence, age),
        "reason": reason,
        "missing_evidence": "; ".join(missing[:2]) if missing else None,
        "unresolved_criteria": len(unresolved),
        "confidence": confidence,
        "age_minutes": int(age),
        "referred_at": since.isoformat() if hasattr(since, "isoformat") else since,
    }


async def fetch_review_queue(organization_id: str, limit: int) -> list[dict[str, Any]]:
    rows = await db.fetch(
        """SELECT c.id, c.patient_initials, c.requested_treatment_name AS treatment, c.payer_id,
                  c.created_at, c.status,
                  d.rationale, d.confidence AS decision_confidence, d.created_at AS decided_at,
                  nr.output_json AS necessity
           FROM cases c
           LEFT JOIN LATERAL (
               SELECT rationale, confidence, created_at FROM decisions
               WHERE case_id = c.id ORDER BY id DESC LIMIT 1
           ) d ON TRUE
           LEFT JOIN LATERAL (
               SELECT output_json FROM agent_runs
               WHERE case_id = c.id AND agent_name = 'necessity_reasoner' AND output_json IS NOT NULL
               ORDER BY id DESC LIMIT 1
           ) nr ON TRUE
           WHERE c.organization_id = $1 AND c.status = 'referred'
           ORDER BY COALESCE(d.created_at, c.created_at) ASC
           LIMIT $2""",
        organization_id,
        limit,
    )
    now = datetime.now(UTC)
    items = [build_item(dict(r), now) for r in rows]
    rank = {"high": 0, "medium": 1, "low": 2}
    items.sort(key=lambda i: (rank[i["priority"]], -i["age_minutes"]))
    return items
