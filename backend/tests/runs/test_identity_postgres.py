"""ONE CASE → MANY RUNS → EACH ARTIFACT TRACEABLE, against a real PostgreSQL schema (CI: integration + postgres)."""

from __future__ import annotations

import asyncio
import json
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.agents.framework.trace_sink import PostgresTraceSink
from app.api import cases as cases_api
from app.api import jobs as jobs_api
from app.auth.jwt_helpers import create_access_token
from app.db import db
from app.graph.state import ClinCaseState, get_or_init_agent_context
from app.identity import case_intelligence_id
from app.jobs import queue as jq
from app.llm.base import LLMClient, LLMResponse
from app.llm.gateway import GatewayCallContext, GenAIGateway, reset_call_context, set_call_context
from app.main import app
from app.models import Decision
from app.runs import list_runs, start_run
from app.streaming import subscribe, unsubscribe
from app.workers import case_runner

pytestmark = [pytest.mark.integration, pytest.mark.postgres]


# ----------------------------------------------------------------------------- helpers
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


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        yield c


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
                update={"paused_for_review": True, "pause_reason": "low confidence"}
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


# ----------------------------------------------------------------------------- run numbering
async def test_attempt_numbers_are_unique_and_gap_free_under_concurrency():
    a = await _org()
    cid = await _case(a["org"])
    runs = await asyncio.gather(
        *(start_run(organization_id=a["org"], case_id=cid) for _ in range(8))
    )
    assert sorted(r.attempt_no for r in runs) == list(range(1, 9))
    by_attempt = {r.attempt_no: r for r in runs}
    assert by_attempt[1].trigger == "initial" and by_attempt[1].parent_run_id is None
    assert all(
        by_attempt[n].trigger == "rerun" and by_attempt[n].parent_run_id for n in range(2, 9)
    )
    assert len({r.run_id for r in runs}) == 8 and len({r.case_intelligence_id for r in runs}) == 1
    stored = await db.fetchval("SELECT case_intelligence_id FROM cases WHERE id=$1", cid)
    assert stored == case_intelligence_id(
        a["org"], cid
    )  # the stable id is stored on the case, not just computed


async def test_numbering_is_per_case():
    a = await _org()
    c1, c2 = await _case(a["org"]), await _case(a["org"])
    r1 = await start_run(organization_id=a["org"], case_id=c1)
    r2 = await start_run(organization_id=a["org"], case_id=c2)
    assert (
        r1.attempt_no == r2.attempt_no == 1 and r1.case_intelligence_id != r2.case_intelligence_id
    )


async def test_run_registry_is_tenant_scoped():
    a, b = await _org("a"), await _org("b")
    cid = await _case(a["org"])
    await start_run(organization_id=a["org"], case_id=cid)
    assert len(await list_runs(a["org"], cid)) == 1
    assert await list_runs(b["org"], cid) == []


# ----------------------------------------------------------------------------- artifacts are stamped
async def test_trace_sink_stamps_agent_runs_and_sse_events():
    a = await _org()
    cid = await _case(a["org"])
    ident = await start_run(organization_id=a["org"], case_id=cid)
    q = subscribe(cid)
    try:
        sink = PostgresTraceSink()
        h = await sink.open_span(case_id=cid, agent_name="x", input_payload={}, identity=ident)
        await sink.close_span_ok(
            h, case_id=cid, agent_name="x", output_payload={}, latency_ms=3, model_id="m",
            input_tokens=1, output_tokens=1,
        )  # fmt: skip
        events = await _drain(q)
    finally:
        unsubscribe(cid, q)
    row = await db.fetchrow("SELECT * FROM agent_runs WHERE case_id=$1", cid)
    assert (row["run_id"], row["case_intelligence_id"], row["trace_id"], row["job_attempt"]) == (
        ident.run_id, ident.case_intelligence_id, ident.trace_id, 1,
    )  # fmt: skip
    assert [e["type"] for e in events] == ["agent_started", "agent_finished"]
    assert all(e["run_id"] == ident.run_id and e["trace_id"] == ident.trace_id for e in events)


async def test_sink_without_identity_still_works_for_legacy_callers():
    a = await _org()
    cid = await _case(a["org"])
    h = await PostgresTraceSink().open_span(case_id=cid, agent_name="x", input_payload={})
    assert h.identity is None
    assert await db.fetchval("SELECT run_id FROM agent_runs WHERE case_id=$1", cid) is None


class _Fake(LLMClient):
    async def complete(self, *, system, user, max_tokens=1000, temperature=0.0, model_id=None):
        return LLMResponse(
            text="{}", input_tokens=3, output_tokens=2, stop_reason="end", model_id=model_id or "m"
        )

    async def stream(self, *a, **k):  # pragma: no cover - not used
        yield ""


async def test_gateway_stamps_llm_invocations_with_the_run():
    a = await _org()
    cid = await _case(a["org"])
    ident = await start_run(organization_id=a["org"], case_id=cid)
    tok = set_call_context(
        GatewayCallContext(
            organization_id=a["org"], case_id=cid, agent_name="x", request_id=None,
            run_id=ident.run_id, case_intelligence_id=ident.case_intelligence_id, trace_id=ident.trace_id,
        )
    )  # fmt: skip
    try:
        await GenAIGateway(_Fake()).complete(
            system="s", user="u", model_id="anthropic/claude-sonnet-4.6"
        )
    finally:
        reset_call_context(tok)
    row = await db.fetchrow(
        "SELECT run_id, case_intelligence_id, trace_id FROM llm_invocations WHERE case_id=$1", cid
    )
    assert (row["run_id"], row["case_intelligence_id"], row["trace_id"]) == (
        ident.run_id, ident.case_intelligence_id, ident.trace_id,
    )  # fmt: skip


# ----------------------------------------------------------------------------- async path (queue → worker)
async def test_run_async_mints_a_run_and_replays_do_not(client, monkeypatch):
    monkeypatch.setattr(jobs_api, "llm_unavailable_reason", lambda: None)
    a = await _org()
    cid = await _case(a["org"])
    r1 = await client.post(f"/api/v1/cases/{cid}/run-async", headers=_h(a["token"]))
    assert r1.status_code == 202, r1.text
    j1 = r1.json()
    assert (
        j1["case_intelligence_id"] == case_intelligence_id(a["org"], cid)
        and j1["run_attempt_no"] == 1
    )
    # idempotent replay: same job, same run, no new run
    r2 = await client.post(f"/api/v1/cases/{cid}/run-async", headers=_h(a["token"]))
    assert r2.json()["run_id"] == j1["run_id"] and r2.json()["job_id"] == j1["job_id"]
    assert len(await list_runs(a["org"], cid)) == 1
    # an explicit new idempotency key is a deliberate rerun: attempt 2, parented on attempt 1
    r3 = await client.post(
        f"/api/v1/cases/{cid}/run-async", headers={**_h(a["token"]), "Idempotency-Key": "again-1"}
    )
    assert r3.status_code == 202
    runs = await list_runs(a["org"], cid)
    assert [(r["attempt_no"], r["trigger"], r["status"]) for r in runs] == [
        (1, "initial", "queued"),
        (2, "rerun", "queued"),
    ]
    assert runs[1]["parent_run_id"] == runs[0]["run_id"] and all(r["job_id"] for r in runs)
    payload = json.loads(
        await db.fetchval("SELECT payload_json FROM case_jobs WHERE id=$1", runs[0]["job_id"])
    )
    assert (
        payload["run"]["run_id"] == runs[0]["run_id"]
    )  # the identity travels inside the queue payload


async def test_worker_executes_under_the_queued_run_and_stamps_everything(client, monkeypatch):
    monkeypatch.setattr(jobs_api, "llm_unavailable_reason", lambda: None)
    await _isolate_queue()
    graph = FakeGraph()
    monkeypatch.setattr(case_runner, "_FULL_GRAPH", graph)
    a = await _org()
    cid = await _case(a["org"])
    j = (await client.post(f"/api/v1/cases/{cid}/run-async", headers=_h(a["token"]))).json()
    q = subscribe(cid)
    try:
        job = await jq.claim_next(worker_id="w1")
        assert job is not None and job.case_id == cid
        await case_runner._process_job(job, "w1")
        events = await _drain(q)
    finally:
        unsubscribe(cid, q)
    run = (await list_runs(a["org"], cid))[0]
    assert (
        run["run_id"] == j["run_id"]
        and run["status"] == "completed"
        and run["finished_at"] is not None
    )
    agent = await db.fetchrow(
        "SELECT run_id, case_intelligence_id, trace_id FROM agent_runs WHERE case_id=$1", cid
    )
    dec = await db.fetchrow(
        "SELECT run_id, case_intelligence_id FROM decisions WHERE case_id=$1", cid
    )
    for row in (agent, dec):
        assert (
            row["run_id"] == j["run_id"]
            and row["case_intelligence_id"] == j["case_intelligence_id"]
        )
    assert agent["trace_id"] == j["trace_id"] == run["trace_id"]
    result = json.loads(await db.fetchval("SELECT result_json FROM case_jobs WHERE id=$1", job.id))
    assert result["run_id"] == j["run_id"] and result["cost_usd"] == pytest.approx(
        0.25
    )  # real cost, no longer 0
    outbox = await db.fetchrow(
        "SELECT trace_id, payload_json FROM event_outbox WHERE aggregate_id=$1 AND event_type LIKE '%decided%'",
        cid,
    )
    payload = (
        json.loads(outbox["payload_json"])
        if isinstance(outbox["payload_json"], str)
        else outbox["payload_json"]
    )
    assert outbox["trace_id"] == j["trace_id"] and payload["decision_run_id"] == j["run_id"]
    assert payload["cost_usd"] == pytest.approx(0.25)
    types = [e["type"] for e in events]
    assert types[0] == "agent_started" and types[-1] == "done"  # the async path now ends its stream
    assert all(e.get("run_id") == j["run_id"] for e in events)
    from app.agents.framework import run_registry

    assert run_registry.active_count() == 0  # the shared context is released after the run


async def test_paused_run_is_marked_paused_and_announced(client, monkeypatch):
    monkeypatch.setattr(jobs_api, "llm_unavailable_reason", lambda: None)
    monkeypatch.setattr(case_runner, "_FULL_GRAPH", FakeGraph(paused=True))
    await _isolate_queue()
    a = await _org()
    cid = await _case(a["org"])
    j = (await client.post(f"/api/v1/cases/{cid}/run-async", headers=_h(a["token"]))).json()
    q = subscribe(cid)
    try:
        await case_runner._process_job(await jq.claim_next(worker_id="w1"), "w1")
        events = await _drain(q)
    finally:
        unsubscribe(cid, q)
    assert (await list_runs(a["org"], cid))[0]["status"] == "paused"
    assert await db.fetchval("SELECT status FROM cases WHERE id=$1", cid) == "awaiting_review"
    pause = next(e for e in events if e["type"] == "hitl_pause")
    assert (
        pause["run_id"] == j["run_id"]
        and pause["case_intelligence_id"] == j["case_intelligence_id"]
    )
    assert await db.fetchval("SELECT count(*) FROM decisions WHERE case_id=$1", cid) == 0


async def test_failed_job_requeues_the_run_then_fails_it_when_retries_run_out(client, monkeypatch):
    monkeypatch.setattr(jobs_api, "llm_unavailable_reason", lambda: None)
    monkeypatch.setattr(case_runner, "_FULL_GRAPH", FakeGraph(boom=RuntimeError("provider down")))
    await _isolate_queue()
    a = await _org()
    cid = await _case(a["org"])
    j = (await client.post(f"/api/v1/cases/{cid}/run-async", headers=_h(a["token"]))).json()
    attempts = []
    for expected in ("queued", "queued", "failed"):  # max_attempts = 3
        job = await jq.claim_next(worker_id="w1")
        await case_runner._process_job(job, "w1")
        run = (await list_runs(a["org"], cid))[0]
        attempts.append(run["status"])
        assert run["status"] == expected, attempts
    # one run, three crash-retries: rows are separated by job_attempt, never by pretending they are new runs
    rows = await db.fetch(
        "SELECT run_id, job_attempt FROM agent_runs WHERE case_id=$1 ORDER BY id", cid
    )
    assert {r["run_id"] for r in rows} == {j["run_id"]} and [r["job_attempt"] for r in rows] == [
        1,
        2,
        3,
    ]
    assert len(await list_runs(a["org"], cid)) == 1


async def test_job_queued_before_run_identity_existed_gets_a_run_once(monkeypatch):
    monkeypatch.setattr(case_runner, "_FULL_GRAPH", FakeGraph(boom=RuntimeError("retry me")))
    await _isolate_queue()
    a = await _org()
    cid = await _case(a["org"])
    payload = {
        "fhir_bundle": {},
        "physician_note": None,
        "requested_treatment": {"name": "x"},
        "payer_id": "aetna",
    }
    await jq.enqueue(
        case_id=cid, organization_id=a["org"], payload=payload, idempotency_key=f"legacy-{cid}"
    )
    for _ in range(2):  # two executions of the same legacy job
        await case_runner._process_job(await jq.claim_next(worker_id="w1"), "w1")
    runs = await list_runs(a["org"], cid)
    assert (
        len(runs) == 1 and runs[0]["trigger"] == "initial"
    )  # the retry reused the run written back to the payload


# ----------------------------------------------------------------------------- sync path, rerun, resume, review
async def test_sync_runs_review_and_resume_are_distinct_attributed_runs(client, monkeypatch):
    monkeypatch.setattr(cases_api, "llm_unavailable_reason", lambda: None)
    monkeypatch.setattr(cases_api, "_FULL_GRAPH", FakeGraph())
    a = await _org(role="admin")
    cid = await _case(a["org"])
    q = subscribe(cid)
    try:
        r1 = (await client.post(f"/api/v1/cases/{cid}/run", headers=_h(a["token"]))).json()
        r2 = (await client.post(f"/api/v1/cases/{cid}/run", headers=_h(a["token"]))).json()
        events = await _drain(q)
    finally:
        unsubscribe(cid, q)
    assert (r1["attempt_no"], r2["attempt_no"]) == (1, 2) and r1["run_id"] != r2["run_id"]
    assert (
        r1["case_intelligence_id"]
        == r2["case_intelligence_id"]
        == case_intelligence_id(a["org"], cid)
    )
    # each run's artifacts carry its own run id — the rerun is never confused with the original
    decisions = await db.fetch("SELECT run_id FROM decisions WHERE case_id=$1 ORDER BY id", cid)
    assert [d["run_id"] for d in decisions] == [r1["run_id"], r2["run_id"]]
    agents = await db.fetch("SELECT run_id FROM agent_runs WHERE case_id=$1 ORDER BY id", cid)
    assert [x["run_id"] for x in agents] == [r1["run_id"], r2["run_id"]]
    done = [e for e in events if e["type"] == "done"]
    assert [e["run_id"] for e in done] == [r1["run_id"], r2["run_id"]]
    runs = await list_runs(a["org"], cid)
    assert [(r["trigger"], r["status"]) for r in runs] == [
        ("initial", "completed"),
        ("rerun", "completed"),
    ]

    # a review action is attributed to the case's latest run
    rv = await client.post(
        f"/api/v1/cases/{cid}/review",
        headers=_h(a["token"]),
        json={"action": "add_note", "note": "n"},
    )
    assert rv.status_code == 200, rv.text
    assert (
        await db.fetchval("SELECT run_id FROM reviewer_actions WHERE case_id=$1", cid)
        == r2["run_id"]
    )

    # a human resume is its own run (trigger='resume', parented on the run it follows)
    await db.execute("UPDATE cases SET status='awaiting_review' WHERE id=$1", cid)
    rs = await client.post(
        f"/api/v1/cases/{cid}/resume",
        headers=_h(a["token"]),
        json={"verdict": "APPROVE", "reviewer_note": "ok"},
    )
    assert rs.status_code == 200, rs.text
    body = rs.json()
    runs = await list_runs(a["org"], cid)
    assert (
        runs[-1]["trigger"] == "resume"
        and runs[-1]["attempt_no"] == 3
        and runs[-1]["parent_run_id"] == r2["run_id"]
    )
    assert body["run_id"] == runs[-1]["run_id"]
    last_dec = await db.fetchrow(
        "SELECT run_id, case_intelligence_id FROM decisions WHERE case_id=$1 ORDER BY id DESC", cid
    )
    last_act = await db.fetchrow(
        "SELECT run_id FROM reviewer_actions WHERE case_id=$1 ORDER BY id DESC", cid
    )
    assert last_dec["run_id"] == last_act["run_id"] == runs[-1]["run_id"]


async def test_failed_sync_run_is_marked_failed_and_releases_its_context(client, monkeypatch):
    monkeypatch.setattr(cases_api, "llm_unavailable_reason", lambda: None)
    monkeypatch.setattr(cases_api, "_FULL_GRAPH", FakeGraph(boom=RuntimeError("provider down")))
    a = await _org()
    cid = await _case(a["org"])
    r = await client.post(f"/api/v1/cases/{cid}/run", headers=_h(a["token"]))
    assert r.status_code == 502
    assert [x["status"] for x in await list_runs(a["org"], cid)] == ["failed"]
    from app.agents.framework import run_registry

    assert run_registry.active_count() == 0


async def test_create_case_stores_the_intelligence_id(client):
    a = await _org()
    r = await client.post(
        "/api/v1/cases",
        headers=_h(a["token"]),
        json={
            "payer_id": "aetna",
            "patient_initials": "T.T.",
            "fhir_bundle": {},
            "requested_treatment": {"name": "x"},
        },
    )
    assert r.status_code == 200, r.text
    cid = r.json()["case_id"]
    assert await db.fetchval(
        "SELECT case_intelligence_id FROM cases WHERE id=$1", cid
    ) == case_intelligence_id(a["org"], cid)


async def test_twin_and_run_history_reflect_reruns_and_resume(client, monkeypatch):
    monkeypatch.setattr(cases_api, "llm_unavailable_reason", lambda: None)
    monkeypatch.setattr(cases_api, "_FULL_GRAPH", FakeGraph())
    a, b = await _org(role="admin"), await _org("other", role="admin")
    cid = await _case(a["org"])
    r1 = (await client.post(f"/api/v1/cases/{cid}/run", headers=_h(a["token"]))).json()
    r2 = (await client.post(f"/api/v1/cases/{cid}/run", headers=_h(a["token"]))).json()
    await db.execute("UPDATE cases SET status='awaiting_review' WHERE id=$1", cid)
    rs = (
        await client.post(
            f"/api/v1/cases/{cid}/resume",
            headers=_h(a["token"]),
            json={"verdict": "DENY", "reviewer_note": "n"},
        )
    ).json()

    twin = (await client.get(f"/api/v1/cases/{cid}/twin", headers=_h(a["token"]))).json()
    assert twin["headline_run_id"] == r2["run_id"]  # the latest execution, not the resume
    assert [r["run_id"] for r in twin["runs"]] == [r1["run_id"], r2["run_id"], rs["run_id"]]
    assert [r["trigger"] for r in twin["runs"]] == ["initial", "rerun", "resume"]
    assert twin["identity"]["stored"] is True and twin["integrity"]["identity_consistent"] is True
    assert [a_["model_id"] for a_ in twin["agent_history"]] == [
        "test-model"
    ]  # only run 2's single agent row
    assert twin["trace"]["totals"]["input_tokens"] == 10
    assert {d["run_id"] for d in twin["model_decisions"]} == {
        r1["run_id"],
        r2["run_id"],
        rs["run_id"],
    }

    listing = (await client.get(f"/api/v1/cases/{cid}/runs", headers=_h(a["token"]))).json()
    assert listing["case_intelligence_id"] == case_intelligence_id(a["org"], cid)
    assert [r["attempt_no"] for r in listing["runs"]] == [1, 2, 3]
    # another tenant sees neither
    assert (
        await client.get(f"/api/v1/cases/{cid}/runs", headers=_h(b["token"]))
    ).status_code == 404
    assert (
        await client.get(f"/api/v1/cases/{cid}/twin", headers=_h(b["token"]))
    ).status_code == 404


# ----------------------------------------------------------------------------- review-hardening regressions
async def test_a_cancelled_run_keeps_its_number_and_is_skipped_as_a_parent():
    from app.runs import mark_run

    a = await _org()
    cid = await _case(a["org"])
    r1 = await start_run(organization_id=a["org"], case_id=cid)
    r2 = await start_run(organization_id=a["org"], case_id=cid)
    await mark_run(r2.run_id, "cancelled")
    r3 = await start_run(organization_id=a["org"], case_id=cid)
    assert (r1.attempt_no, r2.attempt_no, r3.attempt_no) == (1, 2, 3)  # numbers are never reused
    assert r3.parent_run_id == r1.run_id  # lineage skips the run that never executed


async def test_a_run_created_in_a_terminal_state_has_a_finish_time():
    a = await _org()
    cid = await _case(a["org"])
    r = await start_run(organization_id=a["org"], case_id=cid, trigger="resume", status="completed")
    assert (await list_runs(a["org"], cid))[0]["finished_at"] is not None and r.trigger == "resume"


async def test_resume_resolves_the_paused_run_and_is_parented_on_it(client, monkeypatch):
    monkeypatch.setattr(jobs_api, "llm_unavailable_reason", lambda: None)
    monkeypatch.setattr(case_runner, "_FULL_GRAPH", FakeGraph(paused=True))
    await _isolate_queue()
    a = await _org(role="admin")
    cid = await _case(a["org"])
    j = (await client.post(f"/api/v1/cases/{cid}/run-async", headers=_h(a["token"]))).json()
    await case_runner._process_job(await jq.claim_next(worker_id="w1"), "w1")
    assert (await list_runs(a["org"], cid))[0]["status"] == "paused"
    # a newer queued rerun exists: the resume must still point at the run that actually paused
    await client.post(
        f"/api/v1/cases/{cid}/run-async", headers={**_h(a["token"]), "Idempotency-Key": "k2"}
    )
    rs = (
        await client.post(
            f"/api/v1/cases/{cid}/resume",
            headers=_h(a["token"]),
            json={"verdict": "APPROVE", "reviewer_note": "ok"},
        )
    ).json()
    runs = {r["run_id"]: r for r in await list_runs(a["org"], cid)}
    assert runs[j["run_id"]]["status"] == "completed"  # no longer 'paused' on a resolved case
    assert (
        runs[rs["run_id"]]["parent_run_id"] == j["run_id"]
        and runs[rs["run_id"]]["finished_at"] is not None
    )


async def test_a_worker_that_lost_its_lease_does_not_flip_the_run(client, monkeypatch):
    monkeypatch.setattr(jobs_api, "llm_unavailable_reason", lambda: None)
    monkeypatch.setattr(
        case_runner, "_FULL_GRAPH", FakeGraph(boom=RuntimeError("lease lost mid-run"))
    )
    await _isolate_queue()
    a = await _org()
    cid = await _case(a["org"])
    j = (await client.post(f"/api/v1/cases/{cid}/run-async", headers=_h(a["token"]))).json()
    job = await jq.claim_next(worker_id="w1")
    # another worker takes over the lease before this worker's handler fails
    await db.execute("UPDATE case_jobs SET claimed_by='w2' WHERE id=$1", job.id)
    await db.execute(
        "UPDATE case_runs SET status='running' WHERE run_id=$1", j["run_id"]
    )  # w2 is executing it
    await case_runner._process_job(job, "w1")
    run = (await list_runs(a["org"], cid))[0]
    assert run["run_id"] == j["run_id"] and run["status"] == "running"  # untouched: w2 owns it now


async def test_dead_lettered_jobs_fail_their_runs_via_the_janitor_sweep(client, monkeypatch):
    from app.runs import fail_runs_of_dead_jobs

    monkeypatch.setattr(jobs_api, "llm_unavailable_reason", lambda: None)
    await _isolate_queue()
    a = await _org()
    cid = await _case(a["org"])
    await client.post(f"/api/v1/cases/{cid}/run-async", headers=_h(a["token"]))
    await db.execute("UPDATE case_jobs SET status='dead' WHERE case_id=$1", cid)
    assert await fail_runs_of_dead_jobs() >= 1
    assert (await list_runs(a["org"], cid))[0]["status"] == "failed"


async def test_schema_bootstrap_is_idempotent_and_matches_schema_sql():
    from pathlib import Path

    from app.runs import SCHEMA_SQL, ensure_schema

    await ensure_schema()
    await ensure_schema()
    schema_file = (Path(__file__).resolve().parents[2] / "db" / "schema.sql").read_text()
    assert SCHEMA_SQL.strip() in schema_file, "db/schema.sql drifted from app/runs.py SCHEMA_SQL"


async def test_twin_infrastructure_events_come_from_the_headline_runs_own_job(client, monkeypatch):
    monkeypatch.setattr(jobs_api, "llm_unavailable_reason", lambda: None)
    monkeypatch.setattr(case_runner, "_FULL_GRAPH", FakeGraph())
    monkeypatch.setattr(cases_api, "llm_unavailable_reason", lambda: None)
    monkeypatch.setattr(cases_api, "_FULL_GRAPH", FakeGraph())
    await _isolate_queue()
    a = await _org()
    cid = await _case(a["org"])
    await client.post(f"/api/v1/cases/{cid}/run-async", headers=_h(a["token"]))
    await case_runner._process_job(await jq.claim_next(worker_id="w1"), "w1")
    t1 = (await client.get(f"/api/v1/cases/{cid}/twin", headers=_h(a["token"]))).json()
    assert [e["event"] for e in t1["infrastructure_events"]][:2] == ["queued", "claimed"]
    await client.post(
        f"/api/v1/cases/{cid}/run", headers=_h(a["token"])
    )  # a later SYNC rerun has no job
    t2 = (await client.get(f"/api/v1/cases/{cid}/twin", headers=_h(a["token"]))).json()
    assert t2["headline_run_id"] != t1["headline_run_id"] and t2["infrastructure_events"] == []
