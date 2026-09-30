"""Multi-payer comparison from real records — no simulated verdicts.

For one case, each payer column shows: that payer's actual policy for the requested treatment (from the corpus the
Policy Retriever searches), the case's real recorded decision (own payer) or the real decision of a *sibling case*
(same clinical bundle + treatment submitted to that payer), and an honest evaluation state. The recommendation is
ranked from recorded decisions only, so it is empty until at least two payers have actually been evaluated.
"""

from __future__ import annotations

import json
import re
from typing import Any

from app import policy_catalog
from app.db import db

PAYERS: dict[str, str] = {
    "aetna": "Aetna",
    "uhc": "UnitedHealthcare",
    "bcbs": "BlueCross BlueShield",
    "anthem": "Anthem",
}
_VERDICT_RANK = {"APPROVE": 0, "REFER": 1, "DENY": 2}


def policy_for(payer_id: str, treatment: str) -> dict[str, Any] | None:
    """The payer's corpus policy whose drug keywords appear in the requested treatment (longest keyword wins)."""
    t = treatment.lower()
    best: tuple[int, dict[str, Any]] | None = None
    for p in policy_catalog._corpus():
        if p["payer_id"] != payer_id:
            continue
        hits = [len(k) for k in policy_catalog._keywords(p) if k in t]
        if hits and (best is None or max(hits) > best[0]):
            best = (max(hits), p)
    if best is None:
        return None
    p = best[1]
    entry = policy_catalog.catalog_entry(p)
    return {
        "policy_id": p["policy_id"],
        "title": p["policy_title"],
        "source_url": p.get("source_url"),
        "section_count": entry["section_count"],
        "has_recent_change": entry["has_recent_change"],
    }


def _first_sentence(text: str | None, limit: int = 240) -> str | None:
    if not text:
        return None
    t = re.sub(r"\s+", " ", text).strip()
    m = re.match(r"(.+?[.!?])(\s|$)", t)
    s = m.group(1) if m else t
    return s if len(s) <= limit else s[: limit - 1].rstrip() + "…"


def recommend(columns: list[dict[str, Any]]) -> dict[str, Any]:
    decided = [c for c in columns if c["decision"]]
    if len(decided) < 2:
        return {
            "primary": None,
            "fallback": None,
            "summary": (
                "Only one payer has a recorded decision. Create a comparison case for another payer with a policy "
                "on file and run it to compare real outcomes."
                if len(decided) == 1
                else "No payer has a recorded decision for this case yet."
            ),
        }
    ranked = sorted(
        decided,
        key=lambda c: (_VERDICT_RANK[c["decision"]["verdict"]], -c["decision"]["confidence"]),
    )
    primary, fallback = ranked[0], (ranked[1] if len(ranked) > 1 else None)
    parts = [
        f"{c['name']} {c['decision']['verdict']} ({round(c['decision']['confidence'] * 100)}%)"
        for c in ranked
    ]
    return {
        "primary": primary["payer_id"],
        "fallback": fallback["payer_id"] if fallback else None,
        "summary": (
            f"Ranked from recorded decisions only: {'; '.join(parts)}. "
            f"{primary['name']} is the most favourable recorded outcome"
            + (f", with {fallback['name']} as the next option." if fallback else ".")
        ),
    }


async def _case_row(organization_id: str, case_id: str) -> dict[str, Any] | None:
    r = await db.fetchrow(
        """SELECT id, payer_id, patient_initials, requested_treatment_name, requested_j_code,
                  fhir_bundle, physician_note, status
           FROM cases WHERE id = $1 AND organization_id = $2""",
        case_id,
        organization_id,
    )
    return dict(r) if r else None


async def _siblings(organization_id: str, case: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Cases with the same clinical bundle, patient and treatment, keyed by payer (latest per payer)."""
    rows = await db.fetch(
        """SELECT DISTINCT ON (c.payer_id)
                  c.id, c.payer_id, c.status, c.created_at,
                  d.verdict, d.confidence, d.rationale, d.created_at AS decided_at
           FROM cases c
           LEFT JOIN LATERAL (
               SELECT verdict, confidence, rationale, created_at FROM decisions
               WHERE case_id = c.id ORDER BY id DESC LIMIT 1
           ) d ON TRUE
           WHERE c.organization_id = $1
             AND c.patient_initials = $2
             AND lower(c.requested_treatment_name) = lower($3)
             AND c.fhir_bundle = $4::jsonb
           ORDER BY c.payer_id, c.created_at DESC""",
        organization_id,
        case["patient_initials"],
        case["requested_treatment_name"],
        case["fhir_bundle"]
        if isinstance(case["fhir_bundle"], str)
        else json.dumps(case["fhir_bundle"]),
    )
    return {r["payer_id"]: dict(r) for r in rows}


async def compare_case(organization_id: str, case_id: str) -> dict[str, Any] | None:
    case = await _case_row(organization_id, case_id)
    if case is None:
        return None
    sib = await _siblings(organization_id, case)
    columns = []
    for pid, name in PAYERS.items():
        policy = policy_for(pid, case["requested_treatment_name"])
        row = sib.get(pid)
        decision = None
        if row and row["verdict"]:
            decision = {
                "verdict": row["verdict"],
                "confidence": round(float(row["confidence"]), 2),
                "rationale": _first_sentence(row["rationale"]),
                "decided_at": row["decided_at"].isoformat(),
            }
        state = (
            "decided"
            if decision
            else "in_progress"
            if row
            else "no_policy"
            if policy is None
            else "not_started"
        )
        columns.append(
            {
                "payer_id": pid,
                "name": name,
                "is_this_case": pid == case["payer_id"],
                "policy": policy,
                "case": {
                    "case_id": row["id"],
                    "status": row["status"],
                    "created_at": row["created_at"].isoformat(),
                }
                if row
                else None,
                "decision": decision,
                "state": state,
                "can_create": row is None and policy is not None,
            }
        )
    return {
        "case_id": case_id,
        "treatment": case["requested_treatment_name"],
        "j_code": case["requested_j_code"],
        "patient": case["patient_initials"],
        "payer_id": case["payer_id"],
        "payers": columns,
        "recommendation": recommend(columns),
        "method": "Recorded decisions only. A payer column is filled when a case with the same clinical bundle and "
        "treatment has been evaluated under that payer.",
    }


async def create_comparison_case(
    organization_id: str, user_id: str, case_id: str, payer_id: str
) -> tuple[str, bool] | None:
    """Create (or return the existing) sibling case for `payer_id`. Returns (case_id, created) or None if missing."""
    import uuid

    case = await _case_row(organization_id, case_id)
    if case is None:
        return None
    existing = (await _siblings(organization_id, case)).get(payer_id)
    if existing:
        return existing["id"], False
    new_id = "case_" + uuid.uuid4().hex[:8]
    bundle = (
        case["fhir_bundle"]
        if isinstance(case["fhir_bundle"], str)
        else json.dumps(case["fhir_bundle"])
    )
    await db.execute(
        """INSERT INTO cases (id, organization_id, created_by_user_id, payer_id, patient_initials,
                              requested_treatment_name, requested_j_code, fhir_bundle, physician_note, status)
           VALUES ($1,$2,$3,$4,$5,$6,$7,$8::jsonb,$9,'pending')""",
        new_id,
        organization_id,
        user_id,
        payer_id,
        case["patient_initials"],
        case["requested_treatment_name"],
        case["requested_j_code"],
        bundle,
        case["physician_note"],
    )
    return new_id, True
