"""Policy catalog read model — built from the policy corpus the Policy Retriever actually searches
(`app/data/policies.json`) and the recorded payer policy-change snapshot. Counts are computed, never typed in.

Diffs are matched to catalog policies by payer + treatment; the change snapshot is a bundled demo dataset, so every
response carries its `snapshot` metadata and the UI labels it as such.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.db import db

_DATA = Path(__file__).resolve().parent / "data"
#: case statuses that are still open (a policy change can still affect them)
OPEN_STATUSES = ("pending", "running", "awaiting_review", "referred")


@lru_cache(maxsize=1)
def _corpus() -> list[dict[str, Any]]:
    return json.loads((_DATA / "policies.json").read_text(encoding="utf-8"))["policies"]


@lru_cache(maxsize=1)
def _snapshot() -> dict[str, Any]:
    return json.loads((_DATA / "oncology" / "payer_policy_diffs.json").read_text(encoding="utf-8"))


def payer_id_from_name(name: str) -> str:
    n = name.lower()
    if "aetna" in n:
        return "aetna"
    if "united" in n or n == "uhc":
        return "uhc"
    if "blue" in n or "bcbs" in n:
        return "bcbs"
    if "anthem" in n:
        return "anthem"
    return re.sub(r"[^a-z0-9]+", "", n) or "unknown"


def _words(text: str) -> int:
    return len(re.findall(r"\w+", text))


def _keywords(p: dict[str, Any]) -> list[str]:
    return [k.lower() for k in p.get("treatment_keywords", [])]


def _drug_names(treatment: str) -> set[str]:
    """'trastuzumab deruxtecan (T-DXd)' -> {'trastuzumab deruxtecan', 't-dxd'} — whole names only, so a change
    to one drug is never attributed to a different drug that merely shares a word with it."""
    t = treatment.lower().strip()
    names = {re.sub(r"\(.*?\)", "", t).strip()}
    names.update(m.strip() for m in re.findall(r"\((.*?)\)", t))
    return {n for n in names if n}


def matches_diff(policy: dict[str, Any], diff: dict[str, Any]) -> bool:
    if payer_id_from_name(diff["payer"]) != policy["payer_id"]:
        return False
    return bool(_drug_names(diff["treatment"]) & set(_keywords(policy)))


def _diffs_for(policy: dict[str, Any]) -> list[dict[str, Any]]:
    return [d for d in _snapshot()["diffs"] if matches_diff(policy, d)]


def catalog() -> dict[str, Any]:
    items = []
    for p in _corpus():
        diffs = _diffs_for(p)
        items.append(
            {
                "payer_id": p["payer_id"],
                "policy_id": p["policy_id"],
                "title": p["policy_title"],
                "treatment_keywords": p["treatment_keywords"],
                "source_url": p.get("source_url"),
                "section_count": len(p.get("sections", [])),
                "word_count": sum(_words(s.get("text", "")) for s in p.get("sections", [])),
                "recent_change_at": max((d["changed_at"] for d in diffs), default=None),
                "has_recent_change": bool(diffs),
            }
        )
    payers = sorted({i["payer_id"] for i in items})
    return {
        "n": len(items),
        "payers": payers,
        "n_with_recent_change": sum(1 for i in items if i["has_recent_change"]),
        "snapshot": {
            "taken_at": _snapshot()["_meta"]["snapshots_taken_at"],
            "version": _snapshot()["_meta"]["version"],
        },
        "policies": items,
    }


def find_policy(policy_id: str) -> dict[str, Any] | None:
    pid = policy_id.lower()
    return next((p for p in _corpus() if p["policy_id"].lower() == pid), None)


def _like_patterns(policy: dict[str, Any]) -> list[str]:
    return [f"%{k}%" for k in _keywords(policy)]


async def open_cases_for(
    organization_id: str, policy: dict[str, Any], limit: int = 50
) -> list[dict[str, Any]]:
    """The caller's OPEN cases that this policy governs (same payer, requested treatment matches a policy keyword)."""
    rows = await db.fetch(
        """SELECT id, patient_initials, requested_treatment_name AS treatment, status, created_at
           FROM cases
           WHERE organization_id = $1 AND payer_id = $2 AND status = ANY($3::text[])
             AND lower(requested_treatment_name) LIKE ANY($4::text[])
           ORDER BY created_at DESC
           LIMIT $5""",
        organization_id,
        policy["payer_id"],
        list(OPEN_STATUSES),
        _like_patterns(policy),
        limit,
    )
    return [
        {
            "case_id": r["id"],
            "patient": r["patient_initials"],
            "treatment": r["treatment"],
            "status": r["status"],
            "created_at": r["created_at"].isoformat(),
        }
        for r in rows
    ]


def detail(policy: dict[str, Any]) -> dict[str, Any]:
    sections = [
        {
            "heading": s.get("heading"),
            "page_number": s.get("page_number"),
            "word_count": _words(s.get("text", "")),
            "text": s.get("text", ""),
        }
        for s in policy.get("sections", [])
    ]
    related = [
        {"payer_id": q["payer_id"], "policy_id": q["policy_id"], "title": q["policy_title"]}
        for q in _corpus()
        if q["policy_id"] != policy["policy_id"]
        and (q["payer_id"] == policy["payer_id"] or set(_keywords(q)) & set(_keywords(policy)))
    ][:6]
    meta = catalog_entry(policy)
    return {
        **meta,
        "sections": sections,
        "diffs": _diffs_for(policy),
        "related": related,
        "snapshot": {
            "taken_at": _snapshot()["_meta"]["snapshots_taken_at"],
            "version": _snapshot()["_meta"]["version"],
            "note": _snapshot()["_meta"]["description"],
        },
    }


def catalog_entry(policy: dict[str, Any]) -> dict[str, Any]:
    return next(i for i in catalog()["policies"] if i["policy_id"] == policy["policy_id"])
