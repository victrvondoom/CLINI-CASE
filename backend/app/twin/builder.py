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


def _agent_history(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "agent": r["agent_name"],
            "started_at": _iso(r["started_at"]),
            "latency_ms": r.get("latency_ms"),
            "model_id": r.get("model_id"),
            "input_tokens": r.get("input_tokens"),
            "output_tokens": r.get("output_tokens"),
            "error": r.get("error_text"),
        }
        for r in rows
    ]


def _continuation(
    case_runs: list[dict[str, Any]], agent_rows: list[dict[str, Any]], headline_id: str | None
) -> dict[str, Any] | None:
    """The agents a human-review resume ran after THE headline run paused (forecast / appeal / patient letter).

    Only the resume that continues the headline execution counts: after a rerun, an older run's resume is
    history, not this execution's continuation."""
    resumes = [
        r
        for r in case_runs
        if r.get("trigger") == "resume" and headline_id and r.get("parent_run_id") == headline_id
    ]
    if not resumes:
        return None
    run = resumes[-1]
    rows = [a for a in agent_rows if a.get("run_id") == run["run_id"]]
    if rows:
        last_attempt = max(int(a.get("job_attempt") or 1) for a in rows)
        rows = [a for a in rows if int(a.get("job_attempt") or 1) == last_attempt]
    return {
        "run_id": run["run_id"],
        "parent_run_id": run.get("parent_run_id"),
        "status": run.get("status"),
        "agent_history": _agent_history(rows),
    }


def _headline_run(case_runs: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The run whose execution the twin foregrounds: the latest EXECUTION run (initial/rerun).

    A human-review `resume` run is a continuation, not an execution of the agents, so it never replaces the
    execution it follows; its decision and reviewer actions still appear in the decision/human sections."""
    # A cancelled run never executed (lost an idempotency race / failed to enqueue): it must not hide the real one.
    execution = [
        r for r in case_runs if r.get("trigger") != "resume" and r.get("status") != "cancelled"
    ]
    return execution[-1] if execution else None


def _run_summaries(
    case_runs: list[dict[str, Any]],
    agent_rows: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
    actions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """One record per run (plus one 'legacy' record for rows written before run identity existed)."""

    def summary(run: dict[str, Any] | None) -> dict[str, Any] | None:
        rid = run["run_id"] if run else None
        rows = [a for a in agent_rows if a.get("run_id") == rid]
        decs = [d for d in decisions if d.get("run_id") == rid]
        acts = [a for a in actions if a.get("run_id") == rid]
        if run is None and not (rows or decs or acts):
            return None
        last = decs[-1] if decs else None
        return {
            "run_id": rid,
            "attempt_no": run["attempt_no"] if run else 0,
            "trigger": run["trigger"] if run else "legacy",
            "parent_run_id": run.get("parent_run_id") if run else None,
            "status": run["status"] if run else None,
            "trace_id": run.get("trace_id") if run else None,
            "job_id": str(run["job_id"]) if run and run.get("job_id") else None,
            "created_at": _iso(run.get("created_at")) if run else None,
            "finished_at": _iso(run.get("finished_at")) if run else None,
            "job_attempts": sorted({int(a["job_attempt"]) for a in rows if a.get("job_attempt")}),
            "agent_rows": len(rows),
            "agent_errors": sum(1 for a in rows if a.get("error_text")),
            "input_tokens": sum(int(a.get("input_tokens") or 0) for a in rows),
            "output_tokens": sum(int(a.get("output_tokens") or 0) for a in rows),
            "verdict": last["verdict"] if last else None,
            "confidence": last["confidence"] if last else None,
            "human_actions": len(acts),
        }

    out: list[dict[str, Any]] = []
    if (legacy := summary(None)) is not None:
        out.append(legacy)
    for run in case_runs:
        if (item := summary(run)) is not None:
            out.append(item)
    return out


def build_twin(
    *,
    organization_id: str,
    case: dict[str, Any],
    job: dict[str, Any] | None,
    runs: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
    appeal: dict[str, Any] | None,
    actions: list[dict[str, Any]],
    case_runs: list[dict[str, Any]] | None = None,
    appeals: list[dict[str, Any]] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Project a case's persisted records into the twin.

    `runs` are the agent rows. With `case_runs` (the run registry) the twin is run-aware: the headline
    sections (agents, evidence, trace, queue) describe the latest execution run only — a rerun is never mixed
    with the original — and a `runs` list summarises every run. Without it (cases from before run identity
    existed) the previous whole-case projection is used unchanged."""
    case_id = case["id"]
    derived_ciid = case_intelligence_id(organization_id, case_id)
    stored_ciid = case.get("case_intelligence_id")
    ciid = stored_ciid or derived_ciid
    run_list = case_runs or []
    all_agent_rows, all_decisions, all_actions = runs, decisions, actions
    headline = _headline_run(run_list)
    trace_origin = case["created_at"]
    run_summaries: list[dict[str, Any]] = []
    if run_list:
        run_summaries = _run_summaries(run_list, all_agent_rows, all_decisions, all_actions)
        if headline is not None:
            hid = headline["run_id"]
            runs = [a for a in all_agent_rows if a.get("run_id") == hid]
            if runs:
                # A crash-retry re-executes under the same run id: show the attempt that produced the outcome
                # (the latest), not the dead attempts' rows as well.
                last_attempt = max(int(a.get("job_attempt") or 1) for a in runs)
                runs = [a for a in runs if int(a.get("job_attempt") or 1) == last_attempt]
            decisions = [d for d in all_decisions if d.get("run_id") == hid]
            # An appeal belongs to the execution (drafted in its run) or to the human-review resume that
            # continued it (the continuation drafts it under the resume run).
            mine = {hid} | {
                r["run_id"]
                for r in run_list
                if r.get("trigger") == "resume" and r.get("parent_run_id") == hid
            }
            appeal = next(
                (a for a in reversed(appeals or []) if a.get("run_id") in mine),
                None if appeals is not None else appeal,
            )
            trace_origin = headline.get("created_at") or case["created_at"]
        else:
            runs, decisions, appeal = [], [], None
    latest = decisions[-1] if decisions else None
    trace_decision = latest
    if (
        latest is None
        and headline is not None
        and headline.get("finished_at") is not None
        and (
            headline.get("status") == "paused"
            or any(
                r.get("trigger") == "resume" and r.get("parent_run_id") == headline["run_id"]
                for r in run_list
            )
        )
    ):
        # The run stopped at the review gate (no model decision): anchor the human-review stage at the pause.
        trace_decision = {"created_at": headline["finished_at"], "verdict": "REFER"}
    last_decision = all_decisions[-1] if all_decisions else None
    patient = _patient_state(case.get("fhir_bundle"))
    by_id = {r["id"]: r["type"] for r in patient["resources"] if r.get("id")}
    evidence = _evidence(case_id, latest, set(by_id), runs, by_id, _snapshot_pointers(runs))
    criteria = _criteria(runs)
    dangling = [e["evidence_id"] for e in evidence if e["resolved"] is False]
    twin: dict[str, Any] = {
        "case_intelligence_id": ciid,
        "case_id": case_id,
        "identity": {
            "case_intelligence_id": ciid,
            "stored": stored_ciid is not None,
            "matches_derived": ciid == derived_ciid,
        },
        "runs": run_summaries,
        "headline_run_id": headline["run_id"] if headline else None,
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
        "agent_history": _agent_history(runs),
        "continuation": _continuation(
            run_list, all_agent_rows, headline["run_id"] if headline else None
        ),
        "model_decisions": [
            {
                "verdict": d["verdict"],
                "confidence": d["confidence"],
                "rationale": d["rationale"],
                "decided_at": _iso(d["created_at"]),
                "run_id": d.get("run_id"),
            }
            for d in all_decisions
        ],
        "human_decisions": [
            {
                "reviewer_id": a["reviewer_id"],
                "action": a["action"],
                "note": a.get("note"),
                "at": _iso(a["created_at"]),
                "run_id": a.get("run_id"),
            }
            for a in all_actions
        ],
        "infrastructure_events": _infra(job),
        "trace": _trace(
            {**case, "created_at": trace_origin}, runs, trace_decision, all_actions, appeal
        ),
        "outcome": {
            "status": case["status"],
            "final": case["status"] in _TERMINAL,
            # The case's current decision — the human's after a review, otherwise the model's.
            "last_verdict": last_decision["verdict"] if last_decision else None,
            "latest_decision_run_id": last_decision.get("run_id") if last_decision else None,
            "appeal_drafted": appeal is not None,
        },
        "integrity": {
            "dangling_citations": dangling,
            "citations_total": len(evidence),
            "all_clinical_citations_resolve": not dangling,
            "identity_consistent": ciid == derived_ciid,
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
                  fhir_bundle, status, case_intelligence_id
           FROM cases WHERE id = $1 AND organization_id = $2""",
        case_id,
        organization_id,
    )
    if case is None:
        return None
    case_runs = await db.fetch(
        """SELECT run_id, attempt_no, trigger, parent_run_id, trace_id, job_id, status,
                  created_at, finished_at
           FROM case_runs WHERE case_id = $1 AND organization_id = $2 ORDER BY attempt_no""",
        case_id,
        organization_id,
    )
    headline = _headline_run([dict(r) for r in case_runs])
    # The queue record of the headline run (not merely the case's newest job).
    job_filter = (
        "AND id = $3::uuid"  # the headline run's own job (none for a synchronous run)
        if headline is not None
        else "AND $3::uuid IS NULL"  # no run records (pre-identity case): the newest job, as before
    )
    job = None
    if headline is None or headline["job_id"] is not None:
        job = await db.fetchrow(
            f"""SELECT status, attempts, claimed_by, claimed_at, created_at, finished_at, error_text
               FROM case_jobs WHERE case_id = $1 AND organization_id = $2 {job_filter}
               ORDER BY created_at DESC LIMIT 1""",
            case_id,
            organization_id,
            headline["job_id"] if headline is not None else None,
        )
    runs = await db.fetch(
        """SELECT agent_name, started_at, finished_at, output_json, latency_ms, error_text,
                  model_id, input_tokens, output_tokens, run_id, job_attempt
           FROM agent_runs WHERE case_id = $1 ORDER BY id ASC""",
        case_id,
    )
    decisions = await db.fetch(
        """SELECT verdict, rationale, citations_json, confidence, created_at, run_id
           FROM decisions WHERE case_id = $1 ORDER BY id ASC""",
        case_id,
    )
    appeals = await db.fetch(
        "SELECT created_at, run_id FROM appeals WHERE case_id = $1 ORDER BY id ASC", case_id
    )
    appeal = appeals[-1] if appeals else None
    actions = await db.fetch(
        """SELECT reviewer_id, action, note, created_at, run_id
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
        case_runs=[dict(r) for r in case_runs],
        appeals=[dict(a) for a in appeals],
    )
