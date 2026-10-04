"""Case management + per-agent test endpoints.

Day-2 minimum:
    POST /api/v1/cases
        Create a case row from a FHIR bundle + treatment + payer.
    POST /api/v1/cases/{case_id}/extract
        Run the Clinical Extractor agent against an existing case.
        Returns the ClinicalSnapshot. Used to validate the agent stack
        end-to-end before the full LangGraph DAG is wired.
"""

from __future__ import annotations

import json
import os
from typing import Any, Literal
from uuid import uuid4

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.agents.clinical_extractor import extract_clinical_snapshot
from app.agents.framework.run_registry import release as release_run_context
from app.agents.framework.run_registry import run_cost
from app.auth import get_current_user, require_role
from app.db import db
from app.graph.build import build_full_graph, build_partial_graph
from app.graph.state import ClinCaseState, state_for_run
from app.identity import RunIdentity, case_intelligence_id
from app.llm.factory import llm_unavailable_reason
from app.quotas import QuotaExceededError, consume_case_quota, quota_exceeded_to_http
from app.review.human import ai_case_status, public_run_outputs, require_denial_review
from app.review.pause_state import has_continuation_inputs, load_pause_state, save_pause_state
from app.runs import (
    latest_run_id,
    mark_run,
    paused_run_id,
    settle_execution_run,
    start_run,
)
from app.services.intake_fhir import bundle_from_note, clinical_document_text
from app.streaming import publish

# Compile both graphs once at module load (compile is non-trivial)
_PARTIAL_GRAPH = build_partial_graph()
_FULL_GRAPH = build_full_graph()

router = APIRouter(prefix="/cases", tags=["cases"])
log = structlog.get_logger()

CASE_STATUSES = (
    "pending",
    "running",
    "awaiting_review",
    "approved",
    "denied",
    "referred",
    "appealed",
    "overturned",
)


async def ensure_schema() -> None:
    """Widen cases.status CHECK on databases created before 'awaiting_review' existed."""
    current = await db.fetchval(
        "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
        "WHERE conrelid = 'cases'::regclass AND conname = 'cases_status_check'"
    )
    if current is None or "'awaiting_review'" in current:
        return
    allowed = ", ".join(f"'{s}'" for s in CASE_STATUSES)
    async with db.pool.acquire() as conn, conn.transaction():
        await conn.execute("ALTER TABLE cases DROP CONSTRAINT cases_status_check")
        await conn.execute(
            f"ALTER TABLE cases ADD CONSTRAINT cases_status_check CHECK (status IN ({allowed}))"
        )
    log.info("cases.status_check.widened", statuses=CASE_STATUSES)


def _require_llm() -> None:
    reason = llm_unavailable_reason()
    if reason:
        raise HTTPException(status_code=503, detail=reason)


class CreateCaseRequest(BaseModel):
    payer_id: str = Field(..., examples=["aetna"])
    patient_initials: str = Field(..., examples=["JD"])
    fhir_bundle: dict
    physician_note: str | None = None
    requested_treatment: dict = Field(..., examples=[{"name": "trastuzumab", "j_code": "J9355"}])


class CreateCaseResponse(BaseModel):
    case_id: str


def _bundle_from_note(initials: str, note: str) -> dict[str, Any]:
    """Shape explicit note facts for older upload clients."""
    return bundle_from_note(initials, note)


def _validate_case_input(req: CreateCaseRequest) -> None:
    """Reject incomplete input before storing a case that agent 1 cannot run."""
    bundle = req.fhir_bundle
    entries = bundle.get("entry") if bundle.get("resourceType") == "Bundle" else None
    resources = [e.get("resource", {}) for e in entries if isinstance(e, dict)] if isinstance(entries, list) else []
    resources = [r for r in resources if isinstance(r, dict)]
    missing = []
    if not req.patient_initials.strip() or not any(r.get("resourceType") == "Patient" for r in resources):
        missing.append("patient data")
    conditions = [r for r in resources if r.get("resourceType") == "Condition"]
    def has_diagnosis(resource: dict[str, Any]) -> bool:
        code = resource.get("code")
        if not isinstance(code, dict):
            return False
        text = code.get("text")
        if isinstance(text, str) and text.strip():
            return True
        coding = code.get("coding")
        return isinstance(coding, list) and any(
            isinstance(c, dict) and any(isinstance(c.get(key), str) and c[key].strip()
                                       for key in ("code", "display"))
            for c in coding
        )

    if not any(has_diagnosis(r) for r in conditions):
        missing.append("a documented diagnosis")
    treatment_name = req.requested_treatment.get("name")
    if not isinstance(treatment_name, str) or not treatment_name.strip():
        missing.append("a requested treatment")
    if not req.payer_id.strip():
        missing.append("a payer")
    if missing:
        raise HTTPException(status_code=422, detail="Cannot create case yet: supply " + ", ".join(missing) + ".")


@router.get("")
async def list_cases(
    user: dict[str, Any] = Depends(get_current_user),
    limit: int = 50,
    status: str | None = None,
    payer_id: str | None = None,
    search: str | None = None,
) -> dict[str, Any]:
    """List cases scoped to the current user's organization."""
    where: list[str] = ["c.organization_id = $1"]
    params: list[Any] = [user["organization_id"]]

    def add(condition: str, *vals: Any) -> None:
        where.append(condition)
        params.extend(vals)

    if status:
        add(f"c.status = ${len(params) + 1}", status)
    if payer_id:
        add(f"c.payer_id = ${len(params) + 1}", payer_id)
    if search:
        idx = len(params) + 1
        add(
            f"(c.requested_treatment_name ILIKE ${idx} "
            f"OR c.patient_initials ILIKE ${idx} "
            f"OR c.id ILIKE ${idx})",
            f"%{search}%",
        )

    where_clause = "WHERE " + " AND ".join(where)
    count_params = list(params)
    params.append(limit)
    limit_idx = len(params)

    try:
        rows = await db.fetch(
            f"""SELECT c.id, c.payer_id, c.patient_initials, c.status,
                       c.requested_treatment_name, c.requested_j_code, c.created_at,
                       d.verdict, d.confidence
                FROM cases c
                LEFT JOIN LATERAL (
                    SELECT verdict, confidence
                    FROM decisions WHERE case_id = c.id
                    ORDER BY id DESC LIMIT 1
                ) d ON TRUE
                {where_clause}
                ORDER BY c.created_at DESC
                LIMIT ${limit_idx}""",
            *params,
        )
        # True total for the filter (not capped by LIMIT) — nav badges and
        # "N total" headers need the real count, not just len(page).
        total = await db.fetchval(f"SELECT COUNT(*) FROM cases c {where_clause}", *count_params)
    except Exception as exc:
        log.warning("cases.list.unavailable", error_type=type(exc).__name__)
        raise HTTPException(
            status_code=503, detail="Case storage is unavailable. Please retry."
        ) from exc

    return {
        "cases": [
            {
                "case_id": r["id"],
                "payer_id": r["payer_id"],
                "patient_initials": r["patient_initials"],
                "status": r["status"],
                "treatment": r["requested_treatment_name"],
                "j_code": r["requested_j_code"],
                "verdict": None if r["status"] == "awaiting_review" else r["verdict"],
                "confidence": None if r["status"] == "awaiting_review" else r["confidence"],
                "human_review_required": r["status"] == "awaiting_review",
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in rows
        ],
        "total": int(total) if total is not None else len(rows),
    }


@router.post("", response_model=CreateCaseResponse)
async def create_case(
    req: CreateCaseRequest,
    user: dict[str, Any] = Depends(get_current_user),
) -> CreateCaseResponse:
    case_id = "case_" + uuid4().hex[:8]
    if not (req.fhir_bundle or {}).get("entry") and (req.physician_note or "").strip():
        req.fhir_bundle = _bundle_from_note(req.patient_initials, req.physician_note or "")
    req.physician_note = clinical_document_text(req.physician_note) if req.physician_note else None
    _validate_case_input(req)
    try:
        await db.execute(
            """INSERT INTO cases (id, organization_id, created_by_user_id,
                                  payer_id, patient_initials,
                                  requested_treatment_name, requested_j_code,
                                  fhir_bundle, physician_note, status,
                                  case_intelligence_id)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, 'pending', $10)""",
            case_id,
            user["organization_id"],
            user["id"],
            req.payer_id,
            req.patient_initials,
            req.requested_treatment.get("name", "unknown"),
            req.requested_treatment.get("j_code"),
            json.dumps(req.fhir_bundle),
            req.physician_note,
            case_intelligence_id(user["organization_id"], case_id),
        )
    except Exception as exc:
        log.warning("cases.create.unavailable", error_type=type(exc).__name__)
        raise HTTPException(status_code=503, detail="Case was not saved. Please retry.") from exc
    return CreateCaseResponse(case_id=case_id)


@router.post("/{case_id}/extract")
async def run_clinical_extractor(
    case_id: str,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Run Clinical Extractor on the given case. Returns ClinicalSnapshot."""
    row = await db.fetchrow(
        "SELECT * FROM cases WHERE id = $1 AND organization_id = $2",
        case_id,
        user["organization_id"],
    )
    if row is None:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")

    state = ClinCaseState(
        case_id=case_id,
        organization_id=user["organization_id"],
        fhir_bundle=json.loads(row["fhir_bundle"])
        if isinstance(row["fhir_bundle"], str)
        else row["fhir_bundle"],
        physician_note=row["physician_note"],
        requested_treatment={
            "name": row["requested_treatment_name"],
            "j_code": row["requested_j_code"],
        },
        payer_id=row["payer_id"],
    )

    out = await extract_clinical_snapshot(state)
    assert out.clinical_snapshot is not None
    return {
        "case_id": case_id,
        "clinical_snapshot": out.clinical_snapshot.model_dump(),
    }


@router.get("/{case_id}")
async def get_case(
    case_id: str,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    try:
        row = await db.fetchrow(
            "SELECT * FROM cases WHERE id = $1 AND organization_id = $2",
            case_id,
            user["organization_id"],
        )
    except Exception as exc:
        log.warning("cases.get.unavailable", error_type=type(exc).__name__)
        raise HTTPException(
            status_code=503, detail="Case storage is unavailable. Please retry."
        ) from exc
    if row is None:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")
    pending_review = None
    latest_result = None
    continuation = None
    if row["status"] == "awaiting_review":
        run_id = await paused_run_id(case_id)
        paused = await load_pause_state(db, run_id) if run_id else None
        if paused:
            pending_review = {
                "case_id": case_id,
                "run_id": run_id,
                "clinical_snapshot": paused["state"].get("snapshot"),
                "necessity_assessment": paused["state"].get("assessment"),
                "policy_excerpts": paused["state"].get("excerpts", []),
                **(paused["state"].get("draft_outputs") or {}),
                "decision": None,
                "paused_for_review": True,
                "human_review_required": True,
                "documents_draft": True,
                "pause_kind": paused["pause_kind"],
                "pause_reason": paused["pause_reason"],
            }
    else:
        # Select the newest run before checking completion, so an earlier
        # proposed DENY can never replace a newer human APPROVE or REFER.
        stored = await db.fetchrow(
            """SELECT r.status AS run_status, r.trigger, j.status AS job_status, j.result_json,
                      COALESCE(j.heartbeat_at,j.claimed_at,j.created_at)
                        < now() - interval '60 seconds' AS lease_expired
               FROM case_runs r LEFT JOIN case_jobs j ON j.id = r.job_id
                 AND j.organization_id = r.organization_id AND j.case_id = r.case_id
               WHERE r.case_id = $1 AND r.organization_id = $2
               ORDER BY r.attempt_no DESC LIMIT 1""",
            case_id,
            user["organization_id"],
        )
        if stored and stored["run_status"] == "completed" and stored["job_status"] == "done":
            raw = stored["result_json"]
            latest_result = json.loads(raw) if isinstance(raw, str) else raw
        if stored and stored.get("trigger") == "resume" and stored["run_status"] != "completed":
            continuation = {
                "status": stored["run_status"],
                "can_retry": stored["run_status"] == "failed"
                or (stored["job_status"] == "running" and bool(stored.get("lease_expired"))),
            }
    return {
        "case_id": row["id"],
        "payer_id": row["payer_id"],
        "patient_initials": row["patient_initials"],
        "status": row["status"],
        "pending_review": pending_review,
        "latest_result": latest_result,
        "continuation": continuation,
        "physician_note": row["physician_note"],
        "requested_treatment": {
            "name": row["requested_treatment_name"],
            "j_code": row["requested_j_code"],
        },
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
    }


@router.post("/{case_id}/run-partial")
async def run_partial(
    case_id: str,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Run the 3-agent partial graph: Extractor -> Retriever -> Reasoner."""
    row = await db.fetchrow(
        "SELECT * FROM cases WHERE id = $1 AND organization_id = $2",
        case_id,
        user["organization_id"],
    )
    if row is None:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")
    _require_llm()

    fhir = (
        json.loads(row["fhir_bundle"])
        if isinstance(row["fhir_bundle"], str)
        else row["fhir_bundle"]
    )
    initial = ClinCaseState(
        case_id=case_id,
        organization_id=user["organization_id"],
        fhir_bundle=fhir,
        physician_note=row["physician_note"],
        requested_treatment={
            "name": row["requested_treatment_name"],
            "j_code": row["requested_j_code"],
        },
        payer_id=row["payer_id"],
    )

    try:
        final_raw = await _PARTIAL_GRAPH.ainvoke(initial)
    except Exception as exc:
        log.exception("case.run_partial.failed", case_id=case_id)
        raise HTTPException(
            status_code=502, detail=f"Case run failed: {type(exc).__name__}: {exc}"
        ) from exc

    # LangGraph 0.2.x returns either a dict or a Pydantic model depending
    # on internal state. Coerce to ClinCaseState for uniform handling.
    final = (
        final_raw
        if isinstance(final_raw, ClinCaseState)
        else ClinCaseState.model_validate(final_raw)
    )

    return {
        "case_id": case_id,
        "clinical_snapshot": final.clinical_snapshot.model_dump()
        if final.clinical_snapshot
        else None,
        "policy_excerpts": [e.model_dump() for e in final.policy_excerpts],
        "necessity_assessment": final.necessity_assessment.model_dump()
        if final.necessity_assessment
        else None,
    }


@router.post("/{case_id}/run")
async def run_full(
    case_id: str,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Run the full 7-agent graph; org-scoped."""
    try:
        row = await db.fetchrow(
            "SELECT * FROM cases WHERE id = $1 AND organization_id = $2",
            case_id,
            user["organization_id"],
        )
    except Exception as exc:
        log.warning("case.run.storage_unavailable", error_type=type(exc).__name__)
        raise HTTPException(
            status_code=503,
            detail="Case storage is unavailable; no clinical decision was generated.",
        ) from exc
    if row is None:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")
    _require_llm()

    # Per-org quota gate (SCALE-8). Enforced before LLM tokens are spent so
    # an over-quota tenant gets a fast 429 instead of cost runaway.
    try:
        await consume_case_quota(user["organization_id"])
    except QuotaExceededError as exc:
        raise HTTPException(
            status_code=429,
            detail=quota_exceeded_to_http(exc),
        ) from exc

    fhir = (
        json.loads(row["fhir_bundle"])
        if isinstance(row["fhir_bundle"], str)
        else row["fhir_bundle"]
    )
    try:
        identity = await start_run(organization_id=user["organization_id"], case_id=case_id)
    except Exception as exc:
        log.warning("case.run.identity_unavailable", error_type=type(exc).__name__)
        raise HTTPException(
            status_code=503,
            detail="Case storage is unavailable; no clinical decision was generated.",
        ) from exc
    initial = state_for_run(
        identity,
        fhir_bundle=fhir,
        physician_note=row["physician_note"],
        requested_treatment={
            "name": row["requested_treatment_name"],
            "j_code": row["requested_j_code"],
        },
        payer_id=row["payer_id"],
    )
    run_status = "failed"

    try:
        final_raw = await _FULL_GRAPH.ainvoke(initial)
        final = (
            final_raw
            if isinstance(final_raw, ClinCaseState)
            else ClinCaseState.model_validate(final_raw)
        )
        final = require_denial_review(final)

        # HITL pause: graph stopped at review_gate. Persist what we have, mark
        # the case as awaiting_review, and return without writing a decision.
        if final.paused_for_review:
            # Case status and the durable pause state commit together: a case is never "awaiting review"
            # without the state a resume needs.
            async with db.pool.acquire() as conn, conn.transaction():
                await conn.execute(
                    "UPDATE cases SET status = 'awaiting_review' WHERE id = $1",
                    case_id,
                )
                await save_pause_state(conn, final, organization_id=user["organization_id"])
            await publish(
                case_id,
                {
                    "type": "hitl_pause",
                    "case_id": case_id,
                    **identity.event_fields(),
                    "reason": final.pause_reason,
                    "pause_kind": final.pause_kind,
                    "overall_confidence": (
                        final.necessity_assessment.overall_confidence
                        if final.necessity_assessment
                        else None
                    ),
                },
            )

        # Persist the decision to the decisions table — and emit a domain event
        # in the SAME transaction (transactional outbox pattern). Downstream
        # consumers (analytics, audit lake, customer's MDM) subscribe to
        # `clincase.case.decided.v1` on the EventBridge bus.
        if final.decision is not None and not final.paused_for_review:
            from app.events.outbox import emit_appeal_drafted, emit_case_decided
            from app.observability.otel import get_current_trace_id

            run_cost_usd, run_seconds = run_cost(identity)
            async with db.pool.acquire() as conn, conn.transaction():
                await conn.execute(
                    """INSERT INTO decisions (case_id, verdict, rationale,
                                                  citations_json, confidence,
                                                  run_id, case_intelligence_id)
                           VALUES ($1, $2, $3, $4, $5, $6, $7)""",
                    case_id,
                    final.decision.verdict,
                    final.decision.rationale,
                    json.dumps([c.model_dump() for c in final.decision.citations]),
                    final.decision.confidence,
                    identity.run_id,
                    identity.case_intelligence_id,
                )

                # Update case status
                # Pending decisions are held above; only authoritative outcomes reach this table.
                new_status = ai_case_status(final.decision.verdict)
                await conn.execute(
                    "UPDATE cases SET status = $1 WHERE id = $2", new_status, case_id
                )

                # Atomic event emit — decision row + outbox row in one txn
                await emit_case_decided(
                    organization_id=user["organization_id"],
                    case_id=case_id,
                    verdict=final.decision.verdict,
                    confidence=float(final.decision.confidence or 0.0),
                    triggered_hitl=False,
                    decision_run_id=identity.run_id,
                    primary_model_id="apac.anthropic.claude-sonnet-4-6-20251022-v1:0",
                    cost_usd=run_cost_usd,
                    duration_seconds=run_seconds,
                    conn=conn,
                    trace_id=get_current_trace_id() or identity.trace_id,
                )

                # The appealed status, appeal body, and both outbox events are
                # one clinical state transition. Any failure rolls all of it back.
                if final.appeal_draft is not None:
                    appeal_id = await conn.fetchval(
                        """INSERT INTO appeals (case_id, appeal_body,
                                                structured_arguments_json,
                                                run_id, case_intelligence_id)
                           VALUES ($1, $2, $3, $4, $5)
                           RETURNING id""",
                        case_id,
                        final.appeal_draft.appeal_body,
                        json.dumps(
                            [a.model_dump() for a in final.appeal_draft.structured_arguments]
                        ),
                        identity.run_id,
                        identity.case_intelligence_id,
                    )
                    await emit_appeal_drafted(
                        organization_id=user["organization_id"],
                        case_id=case_id,
                        appeal_id=appeal_id,
                        structured_arguments_count=len(final.appeal_draft.structured_arguments),
                        conn=conn,
                        trace_id=get_current_trace_id() or identity.trace_id,
                    )
        run_status = "paused" if final.paused_for_review else "completed"
    except Exception as exc:
        log.exception("case.run.failed", case_id=case_id, run_id=identity.run_id)
        raise HTTPException(
            status_code=502,
            detail="Case processing failed safely. No decision was recorded; review the audit log.",
        ) from exc
    finally:
        release_run_context(identity)
        try:
            await settle_execution_run(identity.run_id, run_status)
        except Exception:  # noqa: BLE001 - never mask the real outcome
            log.warning("case.run.status_update_failed", run_id=identity.run_id)
        await publish(case_id, {"type": "done", "case_id": case_id, **identity.event_fields()})

    return {
        "case_id": case_id,
        **identity.event_fields(),
        "attempt_no": identity.attempt_no,
        **public_run_outputs(final),
    }


# =============================================================================
# HITL resume — reviewer supplies the verdict on a paused case
# =============================================================================


class ResumeRequest(BaseModel):
    verdict: Literal["APPROVE", "DENY", "REFER"]
    reviewer_note: str = Field(
        default="",
        description="Reviewer's clinical justification — appears in the audit trail.",
    )
    continuation_mode: Literal["auto", "inline", "worker"] = "auto"


def _inline_continuation(mode: str | None = "auto") -> bool:
    """Vercel has no persistent worker; finish the durable continuation in this request."""
    return mode == "inline" or (mode in (None, "auto") and os.getenv("VERCEL") == "1")


@router.post("/{case_id}/resume")
async def resume_after_review(
    case_id: str,
    req: ResumeRequest,
    user: dict[str, Any] = Depends(require_role("reviewer", "admin")),
) -> dict[str, Any]:
    """Resume a HITL-paused case with the reviewer's verdict.

    In ONE transaction: the human Decision, the reviewer action, the case's new status, the resume run (its own
    execution, parented on the run that paused), the `case.decided` domain event, and — when the paused run
    left durable state — the queued `resume_after_review` job. A worker then runs the REMAINING graph
    (denial forecast, appeal if DENY, patient communication) under the resume run; the human decision is
    durable even if that continuation later fails. Per CMS-0057-F § IV.C, adverse determinations require
    this human clinician sign-off.

    A case paused before pause state was persisted (legacy) still gets the decision recorded, without a
    continuation.
    """
    from app.events.outbox import emit_case_decided
    from app.jobs import queue as jq
    from app.review.human import STATUS_FOR_VERDICT, HumanReview, build_human_decision

    new_status = STATUS_FOR_VERDICT.get(req.verdict, "referred")
    identity: RunIdentity | None = None
    job_id: str | None = None
    inline_job = None
    inline_worker = f"review-inline:{uuid4().hex}"
    inline = _inline_continuation(req.continuation_mode)
    no_continuation_reason: str | None = None
    try:
        async with db.pool.acquire() as conn, conn.transaction():
            row = await conn.fetchrow(
                """SELECT id, status, payer_id, fhir_bundle, physician_note,
                          requested_treatment_name, requested_j_code
                   FROM cases
                   WHERE id = $1 AND organization_id = $2
                   FOR UPDATE""",
                case_id,
                user["organization_id"],
            )
            if row is None:
                raise HTTPException(status_code=404, detail=f"Case {case_id} not found")
            if row["status"] != "awaiting_review":
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Case {case_id} is in state {row['status']!r}; only "
                        "'awaiting_review' cases can be resumed via this endpoint."
                    ),
                )

            reviewed_run = await paused_run_id(case_id, conn=conn)
            paused = await load_pause_state(conn, reviewed_run) if reviewed_run else None
            # A continuation needs the agent outputs the pause saved; without them (legacy pause, or a
            # 'missing_assessment' pause) the human decision is still recorded, just not continued.
            continuable = paused is not None and has_continuation_inputs(paused["state"])
            no_continuation_reason = (
                None
                if continuable
                else ("no_pause_state" if paused is None else "incomplete_pause_state")
            )
            review = HumanReview(
                verdict=req.verdict,
                reviewer_id=user["id"],
                reviewer_email=user["email"],
                reviewer_role=user["role"],
                note=req.reviewer_note,
                pause_kind=paused["pause_kind"] if paused else None,
                pause_run_id=reviewed_run,
            )
            decision = build_human_decision(review)

            # The human continuation is its own run (trigger='resume', parent = the run that paused), so the
            # review is never confused with the execution it follows. It stays 'running' while a queued
            # continuation still has agents to run; otherwise it is complete.
            identity = await start_run(
                organization_id=user["organization_id"],
                case_id=case_id,
                trigger="resume",
                parent_run_id=reviewed_run,
                status="running" if continuable else "completed",
                conn=conn,
            )
            if reviewed_run is not None:
                # The human decision resolves the paused execution; it must not stay 'paused' forever.
                await mark_run(reviewed_run, "completed", conn=conn)
            await conn.execute(
                """INSERT INTO decisions (case_id, verdict, rationale,
                                          citations_json, confidence,
                                          run_id, case_intelligence_id)
                   VALUES ($1, $2, $3, $4, $5, $6, $7)""",
                case_id,
                decision.verdict,
                decision.rationale,
                json.dumps([c.model_dump() for c in decision.citations]),
                decision.confidence,
                identity.run_id,
                identity.case_intelligence_id,
            )
            await conn.execute("UPDATE cases SET status = $1 WHERE id = $2", new_status, case_id)
            await conn.execute(
                """INSERT INTO reviewer_actions (case_id, reviewer_id, action, note,
                                                 run_id, case_intelligence_id)
                   VALUES ($1, $2, $3, $4, $5, $6)""",
                case_id,
                user["id"],
                f"resume_with_{req.verdict.lower()}",
                req.reviewer_note,
                identity.run_id,
                identity.case_intelligence_id,
            )
            await emit_case_decided(
                organization_id=user["organization_id"],
                case_id=case_id,
                verdict=decision.verdict,
                confidence=float(decision.confidence),
                triggered_hitl=True,
                decision_run_id=identity.run_id,
                primary_model_id="human_reviewer",
                cost_usd=0.0,
                duration_seconds=0.0,
                conn=conn,
                trace_id=identity.trace_id,
            )
            if continuable:
                fhir = (
                    json.loads(row["fhir_bundle"])
                    if isinstance(row["fhir_bundle"], str)
                    else row["fhir_bundle"]
                )
                job = await jq.enqueue(
                    case_id=case_id,
                    organization_id=user["organization_id"],
                    job_type="resume_after_review",
                    payload={
                        "run": identity.to_payload(),
                        "review": review.model_dump(),
                        "parent_run_id": reviewed_run,
                        "fhir_bundle": fhir,
                        "physician_note": row["physician_note"],
                        "requested_treatment": {
                            "name": row["requested_treatment_name"],
                            "j_code": row["requested_j_code"],
                        },
                        "payer_id": row["payer_id"],
                    },
                    idempotency_key=f"resume:{identity.run_id}",
                    max_attempts=1 if inline else 3,
                    conn=conn,
                )
                job_id = str(job.id)
                await mark_run(identity.run_id, "running", job_id=job.id, finished=False, conn=conn)
                if inline:
                    inline_job = await jq.claim_job(job.id, worker_id=inline_worker, conn=conn)
                    if inline_job is None:
                        raise RuntimeError("Unable to reserve inline continuation")
    except HTTPException:
        raise
    except Exception as exc:
        log.warning("case.resume.failed", case_id=case_id, error=str(exc)[:200])
        raise HTTPException(status_code=503, detail="Review service unavailable") from exc

    await publish(
        case_id,
        {
            "type": "hitl_resume",
            "case_id": case_id,
            "verdict": req.verdict,
            "reviewer_id": user["id"],
            **identity.event_fields(),
        },
    )
    continuation_completed = False
    continuation_error = None
    continuation_result = None
    if inline_job is not None:
        from app.workers.case_runner import _process_job

        await _process_job(inline_job, inline_worker, timeout_seconds=240)
        completed_job = await jq.get_job(inline_job.id)
        continuation_completed = completed_job is not None and completed_job.status == "done"
        continuation_error = completed_job.error if completed_job else "Continuation unavailable"
        continuation_result = completed_job.result if completed_job else None
        status_row = await db.fetchrow(
            "SELECT status FROM cases WHERE id=$1 AND organization_id=$2",
            case_id,
            user["organization_id"],
        )
        if status_row:
            new_status = status_row["status"]
    if job_id is None:
        await publish(case_id, {"type": "done", "case_id": case_id, **identity.event_fields()})
    # else: the worker publishes `done` when the continuation finishes.

    return {
        "case_id": case_id,
        **identity.event_fields(),
        "verdict": req.verdict,
        "status": new_status,
        "reviewer_id": user["id"],
        "result": continuation_result,
        "continuation": {
            "queued": job_id is not None and not inline,
            "job_id": job_id,
            "reason": no_continuation_reason,
            "mode": "inline" if inline else "worker",
            "completed": continuation_completed,
            "error": continuation_error,
        },
    }


@router.post("/{case_id}/resume/retry")
async def retry_continuation(
    case_id: str,
    user: dict[str, Any] = Depends(require_role("reviewer", "admin")),
    continuation_mode: Literal["inline", "worker"] | None = None,
) -> dict[str, Any]:
    """Re-queue a human-review continuation that failed (its job was dead-lettered).

    The human decision is untouched; only the remaining agents (forecast / appeal / patient letter) are run
    again, under the same resume run. Refused (409) unless the latest resume run is `failed` and no newer run
    has started since."""
    from app.jobs import queue as jq

    inline = _inline_continuation(continuation_mode)
    inline_job = None
    inline_worker = f"review-retry-inline:{uuid4().hex}"
    try:
        async with db.pool.acquire() as conn, conn.transaction():
            row = await conn.fetchrow(
                "SELECT id FROM cases WHERE id = $1 AND organization_id = $2 FOR UPDATE",
                case_id,
                user["organization_id"],
            )
            if row is None:
                raise HTTPException(status_code=404, detail=f"Case {case_id} not found")
            run = await conn.fetchrow(
                """SELECT run_id, status, job_id, attempt_no FROM case_runs
                   WHERE case_id = $1 AND trigger = 'resume' ORDER BY attempt_no DESC LIMIT 1""",
                case_id,
            )
            if run is None:
                raise HTTPException(status_code=404, detail="No human-review continuation to retry")
            newer = await conn.fetchval(
                "SELECT 1 FROM case_runs WHERE case_id = $1 AND attempt_no > $2 LIMIT 1",
                case_id,
                run["attempt_no"],
            )
            if newer:
                raise HTTPException(
                    status_code=409,
                    detail="A newer run exists; this continuation is no longer current.",
                )
            run_status = run["status"]
            if inline and run_status == "running" and run["job_id"] is not None:
                # A serverless request may be killed before its finally block.
                # There is no janitor on Vercel: recover only this current job,
                # and only after its lease stopped heartbeating. A live attempt
                # cannot be displaced; attempts increments below fence old writes.
                stale = await conn.fetchval(
                    """UPDATE case_jobs SET status='dead', finished_at=now(),
                              error_text='Inline continuation lease expired'
                       WHERE id=$1 AND case_id=$2 AND organization_id=$3
                         AND status='running'
                         AND COALESCE(heartbeat_at,claimed_at,created_at) < now() - interval '60 seconds'
                       RETURNING id""",
                    run["job_id"],
                    case_id,
                    user["organization_id"],
                )
                if stale is not None:
                    await mark_run(run["run_id"], "failed", conn=conn)
                    run_status = "failed"
            if run_status != "failed" or run["job_id"] is None:
                raise HTTPException(
                    status_code=409,
                    detail=f"The continuation is {run_status!r}; only a failed or expired one can be retried.",
                )
            requeued = await conn.fetchval(
                # Attempts are NOT reset: job_attempt stays unique per (run, attempt), so the retry's agent rows
                # can never be confused with the dead attempts'. The retry just gets a fresh allowance.
                """UPDATE case_jobs SET status = 'queued', max_attempts = attempts + $2, error_text = NULL,
                          finished_at = NULL, claimed_at = NULL, claimed_by = NULL, heartbeat_at = NULL
                   WHERE id = $1 AND status = 'dead' RETURNING id""",
                run["job_id"],
                1 if inline else 3,
            )
            if requeued is None:
                raise HTTPException(
                    status_code=409, detail="The continuation job is not dead-lettered."
                )
            await conn.execute(
                "UPDATE case_runs SET status = 'queued', finished_at = NULL WHERE run_id = $1",
                run["run_id"],
            )
            if inline:
                inline_job = await jq.claim_job(run["job_id"], worker_id=inline_worker, conn=conn)
                if inline_job is None:
                    raise RuntimeError("Unable to reserve inline retry")
    except HTTPException:
        raise
    except Exception as exc:
        log.warning("case.resume.retry_failed", case_id=case_id, error=str(exc)[:200])
        raise HTTPException(status_code=503, detail="Review service unavailable") from exc
    status = "queued"
    if inline_job is not None:
        from app.workers.case_runner import _process_job

        await _process_job(inline_job, inline_worker, timeout_seconds=240)
        completed = await jq.get_job(inline_job.id)
        status = completed.status if completed else "failed"
    return {
        "case_id": case_id,
        "run_id": run["run_id"],
        "job_id": str(run["job_id"]),
        "status": status,
    }


class ReviewActionRequest(BaseModel):
    action: str = Field(
        ..., examples=["override_to_approve", "override_to_deny", "escalate", "add_note"]
    )
    note: str | None = None
    reviewer_id: str | None = Field(
        default=None,
        description="Deprecated compatibility field; authenticated identity is always used.",
    )


@router.post("/{case_id}/review")
async def submit_review(
    case_id: str,
    req: ReviewActionRequest,
    user: dict[str, Any] = Depends(require_role("reviewer", "admin")),
) -> dict[str, Any]:
    """Reviewer (HITL) override action. Reviewer/Admin only.

    Action values:
      - approve            → case.status = 'approved'
      - override_to_approve → case.status = 'approved'
      - override_to_deny    → case.status = 'denied'
      - escalate           → case.status unchanged; logs escalation
      - add_note           → case.status unchanged; logs note
    """
    valid_actions = {"approve", "override_to_approve", "override_to_deny", "escalate", "add_note"}
    if req.action not in valid_actions:
        raise HTTPException(
            status_code=400, detail=f"Invalid action. Must be one of {valid_actions}"
        )

    # A pending outcome must use the same authenticated, transactional decision
    # path as /resume; a status-only override would leave no reviewed Decision.
    verdict = {
        "approve": "APPROVE",
        "override_to_approve": "APPROVE",
        "override_to_deny": "DENY",
    }.get(req.action)
    if verdict:
        try:
            async with db.pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT status FROM cases WHERE id=$1 AND organization_id=$2",
                    case_id,
                    user["organization_id"],
                )
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Review service unavailable") from exc
        if row is None:
            raise HTTPException(status_code=404, detail=f"Case {case_id} not found")
        if row["status"] == "awaiting_review":
            resumed = await resume_after_review(
                case_id,
                ResumeRequest(verdict=verdict, reviewer_note=req.note or ""),
                user,
            )
            return {
                **resumed,
                "action": req.action,
                "old_status": "awaiting_review",
                "new_status": resumed["status"],
            }

    try:
        async with db.pool.acquire() as conn, conn.transaction():
            row = await conn.fetchrow(
                """SELECT id, status FROM cases
                   WHERE id = $1 AND organization_id = $2
                   FOR UPDATE""",
                case_id,
                user["organization_id"],
            )
            if row is None:
                raise HTTPException(status_code=404, detail=f"Case {case_id} not found")

            old_status = row["status"]
            if verdict and old_status == "awaiting_review":
                # The case may have entered review after the preflight read.
                # Never let that race fall through to a status-only override.
                raise HTTPException(
                    status_code=409,
                    detail="Case entered human review; submit the verdict through /resume.",
                )
            new_status = old_status
            if req.action in ("approve", "override_to_approve"):
                new_status = "approved"
            elif req.action == "override_to_deny":
                new_status = "denied"

            # Ignore client-supplied reviewer_id: audit identity comes from JWT/DB auth.
            # The action is attributed to the run it was taken against (the case's latest run).
            await conn.execute(
                """INSERT INTO reviewer_actions (case_id, reviewer_id, action, note,
                                                 run_id, case_intelligence_id)
                   VALUES ($1, $2, $3, $4, $5, $6)""",
                case_id,
                user["id"],
                req.action,
                req.note,
                await latest_run_id(case_id, conn=conn),
                case_intelligence_id(user["organization_id"], case_id),
            )
            if new_status != old_status:
                await conn.execute(
                    "UPDATE cases SET status = $1 WHERE id = $2", new_status, case_id
                )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Review service unavailable") from exc

    return {
        "case_id": case_id,
        "action": req.action,
        "old_status": old_status,
        "new_status": new_status,
        "reviewer_id": user["id"],
    }


@router.get("/{case_id}/audit")
async def get_audit(
    case_id: str,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Return all agent_runs rows for a case - the audit trail. Org-scoped."""
    try:
        own = await db.fetchval(
            "SELECT 1 FROM cases WHERE id = $1 AND organization_id = $2",
            case_id,
            user["organization_id"],
        )
        if not own:
            raise HTTPException(status_code=404, detail=f"Case {case_id} not found")
        rows = await db.fetch(
            """SELECT id, agent_name, started_at, finished_at, latency_ms,
                      model_id, input_tokens, output_tokens, error_text
               FROM agent_runs WHERE case_id = $1 ORDER BY id ASC""",
            case_id,
        )
        return {"case_id": case_id, "agent_runs": [dict(r) for r in rows]}
    except HTTPException:
        raise
    except Exception:
        return {"case_id": case_id, "agent_runs": [], "db_unavailable": True}
