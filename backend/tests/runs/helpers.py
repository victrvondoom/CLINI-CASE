"""Shared fixtures/helpers for the run-identity and human-review integration tests."""

from __future__ import annotations

import asyncio
import json
import uuid

from app.auth.jwt_helpers import create_access_token
from app.db import db
from app.graph.state import ClinCaseState, get_or_init_agent_context
from app.models import (
    AppealDraft,
    ClinicalSnapshot,
    Decision,
    DenialForecast,
    NecessityAssessment,
    PatientCommunication,
    PolicyExcerpt,
)
from app.models.clinical import Diagnosis, RequestedTreatment
from app.models.necessity import CriterionAssessment


async def _org(tag: str = "r", role: str = "admin") -> dict[str, str]:
    org = f"run-{tag}-{uuid.uuid4().hex[:6]}"
    uid, email = f"u-{uuid.uuid4().hex[:8]}", f"{role}@{org}.test"
    await db.execute("INSERT INTO organizations (id, name, slug) VALUES ($1,$1,$1)", org)
    await db.execute(
        "INSERT INTO users (id,email,password_hash,full_name,organization_id,role) VALUES ($1,$2,'x','n',$3,$4)",
        uid, email, org, role,
    )  # fmt: skip
    token = create_access_token(
        user_id=uid, organization_id=org, role=role, email=email, full_name="n"
    )
    return {"org": org, "uid": uid, "token": token}


async def _case(org: str, status: str = "pending") -> str:
    cid = f"run-{uuid.uuid4().hex[:10]}"
    bundle = {"resourceType": "Bundle", "entry": []}
    await db.execute(
        """INSERT INTO cases (id, organization_id, payer_id, patient_initials, requested_treatment_name,
                              fhir_bundle, physician_note, status)
           VALUES ($1,$2,'aetna','T.T.','Trastuzumab',$3::jsonb,'note',$4)""",
        cid, org, json.dumps(bundle), status,
    )  # fmt: skip
    return cid


async def _isolate_queue() -> None:
    """`claim_next` takes the globally oldest job; park leftovers from other tests/runs so a test claims its own."""
    await db.execute(
        "UPDATE case_jobs SET status='dead', finished_at=now() WHERE status IN ('queued','running')"
    )


def _h(tok: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {tok}"}


class FakeGraph:
    """Stands in for the compiled LangGraph: one real trace-sink span per run, then a canned outcome."""

    def __init__(self, *, paused: bool = False, boom: Exception | None = None, cost: float = 0.25):
        self.paused, self.boom, self.cost, self.calls = paused, boom, cost, 0

    async def ainvoke(self, state: ClinCaseState) -> ClinCaseState:
        self.calls += 1
        ctx = get_or_init_agent_context(state)
        h = await ctx.trace_sink.open_span(
            case_id=state.case_id, agent_name="fake_agent", input_payload={"n": self.calls}, identity=ctx.identity
        )  # fmt: skip
        if self.boom:
            await ctx.trace_sink.close_span_error(
                h,
                case_id=state.case_id,
                agent_name="fake_agent",
                error=str(self.boom),
                latency_ms=1,
            )
            raise self.boom
        await ctx.trace_sink.close_span_ok(
            h, case_id=state.case_id, agent_name="fake_agent", output_payload={"ok": True},
            latency_ms=7, model_id="test-model", input_tokens=10, output_tokens=5,
        )  # fmt: skip
        ctx.budget.spent_usd = self.cost
        if self.paused:
            return state.model_copy(
                update={
                    "paused_for_review": True,
                    "pause_kind": "low_confidence",
                    "pause_reason": "low confidence",
                    **sample_outputs(),
                }
            )
        decision = Decision(
            verdict="APPROVE", rationale="r", citations=[], confidence=0.9, risk_flags=[]
        )
        return state.model_copy(update={"decision": decision})


async def _drain(q: asyncio.Queue) -> list[dict]:
    out = []
    while not q.empty():
        out.append(q.get_nowait())
    return out


def sample_outputs() -> dict:
    """Real (validated) outputs of the agents that run before the review gate."""
    return {
        "clinical_snapshot": ClinicalSnapshot(
            primary_diagnosis=Diagnosis(
                icd10_code="C50.911", description="breast cancer", source_resource_id="cond-1"
            ),
            requested_treatment=RequestedTreatment(name="Trastuzumab", j_code="J9355"),
            free_text_summary="summary",
        ),
        "policy_excerpts": [
            PolicyExcerpt(
                payer_id="aetna",
                policy_id="0048",
                policy_title="Trastuzumab",
                section_heading="Criteria",
                excerpt_text="text",
                relevance_score=0.9,
            )
        ],
        "necessity_assessment": NecessityAssessment(
            criteria=[
                CriterionAssessment(
                    criterion_text="HER2 positive",
                    policy_excerpt_index=0,
                    status="AMBIGUOUS",
                    supporting_evidence=["obs-her2"],
                    confidence=0.4,
                    rationale="unclear",
                )
            ],
            overall_confidence=0.4,
            summary="s",
        ),
    }


class FakeResumeNodes:
    """Fake forecaster / appeals / patient-communicator nodes that record the order they ran in."""

    def __init__(self, boom: Exception | None = None, spans: bool = True):
        self.order: list[str] = []
        self.boom = boom
        self.spans = spans

    async def _span(self, state, name):
        self.order.append(name)
        if not self.spans:
            if self.boom:
                raise self.boom
            return
        ctx = get_or_init_agent_context(state)
        h = await ctx.trace_sink.open_span(
            case_id=state.case_id, agent_name=name, input_payload={}, identity=ctx.identity
        )
        if self.boom:
            await ctx.trace_sink.close_span_error(
                h, case_id=state.case_id, agent_name=name, error=str(self.boom), latency_ms=1
            )
            raise self.boom
        await ctx.trace_sink.close_span_ok(
            h,
            case_id=state.case_id,
            agent_name=name,
            output_payload={},
            latency_ms=3,
            model_id="test-model",
            input_tokens=4,
            output_tokens=2,
        )

    async def forecaster(self, state):
        await self._span(state, "denial_forecaster")
        return {"denial_forecast": DenialForecast.model_construct(denial_probability=0.9)}

    async def appeals(self, state):
        await self._span(state, "appeals_drafter")
        return {
            "appeal_draft": AppealDraft.model_construct(
                patient_initials="T.T.",
                payer_id="aetna",
                requested_treatment="Trastuzumab",
                denial_date="2026-10-01",
                appeal_body="letter",
                structured_arguments=[],
                attachments_referenced=[],
                requested_action="overturn",
            )
        }

    async def communicator(self, state):
        await self._span(state, "patient_communicator")
        return {
            "patient_communication": PatientCommunication.model_construct(
                headline="h", body="b", reading_level_grade=6.0
            )
        }
