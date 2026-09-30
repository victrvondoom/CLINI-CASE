"""Build the Case Digital Twin from the records the platform already persists.

The twin is a pure projection over `cases`, `case_jobs`, `agent_runs`, `decisions`,
`appeals` and `reviewer_actions`. It invents nothing: a field with no source is `None`
(never a guess), and every decision citation is checked against the submitted FHIR
bundle so a pointer that resolves to nothing is reported as dangling.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from datetime import UTC, datetime
from typing import Any

from app.agents.decision_composer.integrity import clinical_pointers
from app.analytics.agent_metrics import price_for
from app.db import db
from app.twin.intelligence_id import case_intelligence_id, evidence_id

_POLICY_KINDS = {"policy", "compendium", "fda_label", "guideline"}
_VERSION_RE = re.compile(r"\bv(?:\.)?\s?(\d[\w.\-]*)", re.IGNORECASE)
_SECTION_RE = re.compile(r"(§\s*[^\s,;]+(?:\s*[A-Z0-9.]+)*|\bBINV-\w+)")
_TERMINAL = {"approved", "denied", "overturned"}


def _obj(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None
    return value


def _iso(value: Any) -> str | None:
    return value.isoformat() if hasattr(value, "isoformat") else None


def _ms(a: Any, b: Any) -> int | None:
    if not (hasattr(a, "timestamp") and hasattr(b, "timestamp")):
        return None
    return max(0, int((b.timestamp() - a.timestamp()) * 1000))


def _bundle_resources(bundle: Any) -> list[dict[str, Any]]:
    data = _obj(bundle)
    if not isinstance(data, dict):
        return []
    out = []
    for entry in data.get("entry") or []:
        res = entry.get("resource") if isinstance(entry, dict) else None
        if isinstance(res, dict) and res.get("resourceType"):
            out.append(res)
    return out


def _patient_state(bundle: Any) -> dict[str, Any]:
    resources = _bundle_resources(bundle)
    counts = Counter(r["resourceType"] for r in resources)
    return {
        "resource_counts": dict(sorted(counts.items())),
        "resources": [{"type": r["resourceType"], "id": r.get("id")} for r in resources],
        "fhir_version": "R4",
    }


def _citations(decision: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not decision:
        return []
    raw = _obj(decision.get("citations_json"))
    return [c for c in raw if isinstance(c, dict)] if isinstance(raw, list) else []


def _find_source_run(pointer: str, runs: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The earliest agent run whose recorded output mentions this pointer."""
    if not pointer:
        return None
    for run in runs:
        if pointer in json.dumps(
            _obj(run.get("output_json")) or {}, default=str, ensure_ascii=False
        ):
            return run
    return None


def _snapshot_pointers(runs: list[dict[str, Any]]) -> set[str]:
    """Pointers valid against the clinical snapshot the extractor produced (same rule the composer enforces)."""
    for run in reversed(runs):
        if run["agent_name"] == "clinical_extractor":
            out = _obj(run.get("output_json"))
            if isinstance(out, dict):
                return clinical_pointers(out.get("snapshot", out))
    return set()


def _evidence(
    case_id: str,
    decision: dict[str, Any] | None,
    bundle_ids: set[str],
    runs: list[dict[str, Any]],
    by_id: dict[str, str],
    snapshot: set[str],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for c in _citations(decision):
        kind, pointer = str(c.get("kind", "")), str(c.get("pointer", ""))
        eid = evidence_id(case_id, kind, pointer)
        if eid in seen:  # the same fact cited twice is one piece of evidence
            continue
        seen.add(eid)
        run = _find_source_run(pointer, runs)
        version = _VERSION_RE.search(pointer) if kind in _POLICY_KINDS else None
        section = _SECTION_RE.search(pointer)
        items.append(
            {
                "evidence_id": eid,
                "kind": kind,
                "pointer": pointer,
                "text": c.get("text"),
                "fhir_resource_id": pointer if kind == "clinical" else None,
                "fhir_resource_type": by_id.get(pointer) if kind == "clinical" else None,
                "resolved": (pointer in bundle_ids or pointer in snapshot)
                if kind == "clinical"
                else None,
                "resolution": (
                    "fhir_resource"
                    if pointer in bundle_ids
                    else "snapshot_path"
                    if pointer in snapshot
                    else None
                )
                if kind == "clinical"
                else None,
                "policy_version": version.group(1) if version else None,
                "section": section.group(0).strip() if section else None,
                "source_document": None,  # no document store is wired to citations yet
                "page": None,
                "first_seen_agent": run["agent_name"] if run else None,
                "model_id": run.get("model_id") if run else None,
                "recorded_at": _iso(run.get("finished_at")) if run else None,
                "decision_confidence": decision.get("confidence") if decision else None,
            }
        )
    return items


def _criteria(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for run in reversed(runs):
        if run["agent_name"] == "necessity_reasoner":
            out = _obj(run.get("output_json")) or {}
            crit = out.get("criteria") if isinstance(out, dict) else None
            if isinstance(crit, list):
                return [c for c in crit if isinstance(c, dict)]
    return []


def _graph(
    case_id: str,
    decision: dict[str, Any] | None,
    evidence: list[dict[str, Any]],
    criteria: list[dict[str, Any]],
    ciid: str,
) -> dict[str, Any]:
    nodes: list[dict[str, Any]] = [{"id": ciid, "type": "case"}]
    edges: list[dict[str, str]] = []
    if decision:
        nodes.append(
            {
                "id": "decision",
                "type": "decision",
                "verdict": decision.get("verdict"),
                "confidence": decision.get("confidence"),
            }
        )
        edges.append({"from": ciid, "to": "decision", "rel": "concluded"})
    for i, c in enumerate(criteria):
        nid = f"criterion:{i}"
        nodes.append(
            {
                "id": nid,
                "type": "criterion",
                "text": c.get("criterion_text"),
                "status": c.get("status"),
                "confidence": c.get("confidence"),
            }
        )
        edges.append({"from": ciid, "to": nid, "rel": "assessed"})
    for e in evidence:
        nodes.append(
            {
                "id": e["evidence_id"],
                "type": f"evidence:{e['kind']}",
                "pointer": e["pointer"],
                "resolved": e["resolved"],
            }
        )
        if decision:
            edges.append({"from": "decision", "to": e["evidence_id"], "rel": "cites"})
    return {"nodes": nodes, "edges": edges}


def _trace(
    case: dict[str, Any],
    runs: list[dict[str, Any]],
    decision: dict[str, Any] | None,
    actions: list[dict[str, Any]],
    appeal: dict[str, Any] | None,
) -> dict[str, Any]:
    t0 = case["created_at"]
    stages: list[dict[str, Any]] = []
    for r in runs:
        stages.append(
            {
                "stage": r["agent_name"],
                "actor": "agent",
                "offset_ms": _ms(t0, r["started_at"]),
                "duration_ms": r.get("latency_ms"),
                "status": "error"
                if r.get("error_text")
                else ("ok" if r.get("finished_at") else "running"),
            }
        )
    human_wait = None
    later = [a for a in actions if decision and a["created_at"] >= decision["created_at"]]
    if decision and later:
        human_wait = _ms(decision["created_at"], later[0]["created_at"])
        stages.append(
            {
                "stage": "human_review",
                "actor": "human",
                "offset_ms": _ms(t0, decision["created_at"]),
                "duration_ms": human_wait,
                "status": "ok",
            }
        )
    elif case["status"] == "awaiting_review" or (decision and decision["verdict"] == "REFER"):
        stages.append(
            {
                "stage": "human_review",
                "actor": "human",
                "offset_ms": _ms(t0, decision["created_at"]) if decision else None,
                "duration_ms": None,
                "status": "waiting",
            }
        )
    if appeal:
        stages.append(
            {
                "stage": "appeal_generated",
                "actor": "system",
                "offset_ms": _ms(t0, appeal["created_at"]),
                "duration_ms": None,
                "status": "ok",
            }
        )
    agent_ms = sum(int(r.get("latency_ms") or 0) for r in runs)
    cost = 0.0
    for r in runs:
        pin, pout = price_for(r.get("model_id"))
        cost += (
            int(r.get("input_tokens") or 0) * pin / 1e6
            + int(r.get("output_tokens") or 0) * pout / 1e6
        )
    return {
        "stages": stages,
        "totals": {
            "agent_ms": agent_ms,
            "human_wait_ms": human_wait,
            "input_tokens": sum(int(r.get("input_tokens") or 0) for r in runs),
            "output_tokens": sum(int(r.get("output_tokens") or 0) for r in runs),
            "estimated_cost_usd": round(cost, 4),
        },
    }


def _infra(job: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not job:
        return []
    events: list[dict[str, Any]] = [{"event": "queued", "at": _iso(job.get("created_at"))}]
    if job.get("claimed_at"):
        events.append(
            {"event": "claimed", "at": _iso(job["claimed_at"]), "worker": job.get("claimed_by")}
        )
    if int(job.get("attempts") or 0) > 1:
        events.append({"event": "retried", "attempts": int(job["attempts"])})
    if job.get("finished_at"):
        events.append(
            {"event": job["status"], "at": _iso(job["finished_at"]), "error": job.get("error_text")}
        )
    return events


def build_twin(
    *,
    organization_id: str,
    case: dict[str, Any],
    job: dict[str, Any] | None,
    runs: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
    appeal: dict[str, Any] | None,
    actions: list[dict[str, Any]],
    now: datetime | None = None,
) -> dict[str, Any]:
    case_id = case["id"]
    ciid = case_intelligence_id(organization_id, case_id)
    latest = decisions[-1] if decisions else None
    patient = _patient_state(case.get("fhir_bundle"))
    by_id = {r["id"]: r["type"] for r in patient["resources"] if r.get("id")}
    evidence = _evidence(case_id, latest, set(by_id), runs, by_id, _snapshot_pointers(runs))
    criteria = _criteria(runs)
    dangling = [e["evidence_id"] for e in evidence if e["resolved"] is False]
    twin: dict[str, Any] = {
        "case_intelligence_id": ciid,
        "case_id": case_id,
        "patient_fhir": patient,
        "authorization": {
            "status": case["status"],
            "payer_id": case["payer_id"],
            "treatment": case["requested_treatment_name"],
            "j_code": case.get("requested_j_code"),
            "submitted_at": _iso(case["created_at"]),
        },
        "policy": {
            "citations": [e for e in evidence if e["kind"] in _POLICY_KINDS],
            "criteria_total": len(criteria),
            "criteria_met": sum(1 for c in criteria if c.get("status") == "MET"),
            "criteria_ambiguous": sum(1 for c in criteria if c.get("status") == "AMBIGUOUS"),
            "criteria_not_met": sum(1 for c in criteria if c.get("status") == "NOT_MET"),
        },
        "evidence_graph": _graph(case_id, latest, evidence, criteria, ciid),
        "evidence": evidence,
        "agent_history": [
            {
                "agent": r["agent_name"],
                "started_at": _iso(r["started_at"]),
                "latency_ms": r.get("latency_ms"),
                "model_id": r.get("model_id"),
                "input_tokens": r.get("input_tokens"),
                "output_tokens": r.get("output_tokens"),
                "error": r.get("error_text"),
            }
            for r in runs
        ],
        "model_decisions": [
            {
                "verdict": d["verdict"],
                "confidence": d["confidence"],
                "rationale": d["rationale"],
                "decided_at": _iso(d["created_at"]),
            }
            for d in decisions
        ],
        "human_decisions": [
            {
                "reviewer_id": a["reviewer_id"],
                "action": a["action"],
                "note": a.get("note"),
                "at": _iso(a["created_at"]),
            }
            for a in actions
        ],
        "infrastructure_events": _infra(job),
        "trace": _trace(case, runs, latest, actions, appeal),
        "outcome": {
            "status": case["status"],
            "final": case["status"] in _TERMINAL,
            "last_verdict": latest["verdict"] if latest else None,
            "appeal_drafted": appeal is not None,
        },
        "integrity": {
            "dangling_citations": dangling,
            "citations_total": len(evidence),
            "all_clinical_citations_resolve": not dangling,
        },
    }
    twin["twin_sha256"] = hashlib.sha256(
        json.dumps(twin, sort_keys=True, default=str, separators=(",", ":")).encode()
    ).hexdigest()
    twin["generated_at"] = (now or datetime.now(UTC)).isoformat()
    return twin


async def fetch_twin(organization_id: str, case_id: str) -> dict[str, Any] | None:
    case = await db.fetchrow(
        """SELECT id, created_at, payer_id, requested_treatment_name, requested_j_code,
                  fhir_bundle, status
           FROM cases WHERE id = $1 AND organization_id = $2""",
        case_id,
        organization_id,
    )
    if case is None:
        return None
    job = await db.fetchrow(
        """SELECT status, attempts, claimed_by, claimed_at, created_at, finished_at, error_text
           FROM case_jobs WHERE case_id = $1 AND organization_id = $2
           ORDER BY created_at DESC LIMIT 1""",
        case_id,
        organization_id,
    )
    runs = await db.fetch(
        """SELECT agent_name, started_at, finished_at, output_json, latency_ms, error_text,
                  model_id, input_tokens, output_tokens
           FROM agent_runs WHERE case_id = $1 ORDER BY id ASC""",
        case_id,
    )
    decisions = await db.fetch(
        """SELECT verdict, rationale, citations_json, confidence, created_at
           FROM decisions WHERE case_id = $1 ORDER BY id ASC""",
        case_id,
    )
    appeal = await db.fetchrow(
        "SELECT created_at FROM appeals WHERE case_id = $1 ORDER BY id DESC LIMIT 1", case_id
    )
    actions = await db.fetch(
        """SELECT reviewer_id, action, note, created_at
           FROM reviewer_actions WHERE case_id = $1 ORDER BY id ASC""",
        case_id,
    )
    return build_twin(
        organization_id=organization_id,
        case=dict(case),
        job=dict(job) if job else None,
        runs=[dict(r) for r in runs],
        decisions=[dict(d) for d in decisions],
        appeal=dict(appeal) if appeal else None,
        actions=[dict(a) for a in actions],
    )
