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
from app.runs import latest_run_id, mark_run, paused_run_id, start_run
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
                "verdict": r["verdict"],
                "confidence": r["confidence"],
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
    return {
        "case_id": row["id"],
        "payer_id": row["payer_id"],
        "patient_initials": row["patient_initials"],
        "status": row["status"],
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

        # HITL pause: graph stopped at review_gate. Persist what we have, mark
        # the case as awaiting_review, and return without writing a decision.
        if final.paused_for_review:
            await db.execute(
                "UPDATE cases SET status = 'awaiting_review' WHERE id = $1",
                case_id,
            )
            await publish(
                case_id,
                {
                    "type": "hitl_pause",
                    "case_id": case_id,
                    **identity.event_fields(),
                    "reason": final.pause_reason,
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
        if final.decision is not None:
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
                status_map = {"APPROVE": "approved", "DENY": "denied", "REFER": "referred"}
                new_status = status_map.get(final.decision.verdict, "pending")
                if final.appeal_draft is not None:
                    new_status = "appealed"
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
            await mark_run(identity.run_id, run_status)
        except Exception:  # noqa: BLE001 - never mask the real outcome
            log.warning("case.run.status_update_failed", run_id=identity.run_id)
        await publish(case_id, {"type": "done", "case_id": case_id, **identity.event_fields()})

    return {
        "case_id": case_id,
        **identity.event_fields(),
        "attempt_no": identity.attempt_no,
        "clinical_snapshot": final.clinical_snapshot.model_dump()
        if final.clinical_snapshot
        else None,
        "policy_excerpts": [e.model_dump() for e in final.policy_excerpts],
        "necessity_assessment": final.necessity_assessment.model_dump()
        if final.necessity_assessment
        else None,
        "decision": final.decision.model_dump() if final.decision else None,
        "denial_forecast": final.denial_forecast.model_dump() if final.denial_forecast else None,
        "appeal_draft": final.appeal_draft.model_dump() if final.appeal_draft else None,
        "patient_communication": final.patient_communication.model_dump()
        if final.patient_communication
        else None,
        "paused_for_review": final.paused_for_review,
        "pause_reason": final.pause_reason,
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


@router.post("/{case_id}/resume")
async def resume_after_review(
    case_id: str,
    req: ResumeRequest,
    user: dict[str, Any] = Depends(require_role("reviewer", "admin")),
) -> dict[str, Any]:
    """Resume a HITL-paused case with the reviewer's verdict.

    Persists a Decision row sourced from the human reviewer (with full audit
    trail noting the human override), updates case status, and inserts a
    reviewer_actions row. Per CMS-0057-F § IV.C, adverse determinations
    require this human clinician sign-off.
    """
    rationale = (
        f"HUMAN REVIEWER OVERRIDE — clinician {user['email']} (role={user['role']}) "
        f"reviewed this case after ClinCase paused at the review_gate due to "
        f"low Necessity Reasoner confidence. Reviewer verdict: {req.verdict}. "
        f"Reviewer note: {req.reviewer_note or '(none)'}. "
        f"Provenance per CMS-0057-F § IV.C and CA SB 1120."
    )

    citations = [
        {
            "kind": "human_override",
            "text": f"Reviewer {user['email']} clinical sign-off",
            "pointer": f"reviewer_action:{user['id']}",
        }
    ]

    status_map = {"APPROVE": "approved", "DENY": "denied", "REFER": "referred"}
    new_status = status_map.get(req.verdict, "referred")
    identity: RunIdentity | None = None
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
            if row["status"] != "awaiting_review":
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Case {case_id} is in state {row['status']!r}; only "
                        "'awaiting_review' cases can be resumed via this endpoint."
                    ),
                )

            # The human continuation is its own run (trigger='resume', parent = the run that paused),
            # so the review is never confused with the execution it follows. Decision, state
            # transition, run record and audit identity commit together.
            reviewed_run = await paused_run_id(case_id, conn=conn)
            identity = await start_run(
                organization_id=user["organization_id"],
                case_id=case_id,
                trigger="resume",
                parent_run_id=reviewed_run,
                status="completed",
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
                req.verdict,
                rationale,
                json.dumps(citations),
                1.0,
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
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Review service unavailable") from exc

    await publish(
        case_id,
        {
            "type": "hitl_resume",
            "case_id": case_id,
            "verdict": req.verdict,
            "reviewer_id": user["id"],
            **(identity.event_fields() if identity else {}),
        },
    )
    await publish(
        case_id,
        {"type": "done", "case_id": case_id, **(identity.event_fields() if identity else {})},
    )

    return {
        "case_id": case_id,
        **(identity.event_fields() if identity else {}),
        "verdict": req.verdict,
        "status": new_status,
        "reviewer_id": user["id"],
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
