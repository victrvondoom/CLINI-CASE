"""Worker process that consumes case_jobs and runs the LangGraph DAG.

Run as a separate process (or container) from the FastAPI API tier. Both tiers
hit the same Postgres; the worker is what actually burns LLM tokens. This is
the production-ready separation:

  ┌─────────────┐         ┌──────────────────┐
  │  FastAPI    │ enqueue │   case_jobs      │ claim
  │   tier      │────────▶│   (Postgres)     │◀──────  case-runner workers (N replicas)
  │ (stateless) │         │                  │
  └─────────────┘         └──────────────────┘
        │                                              │
        ▼ SSE stream                                   ▼ runs DAG, writes agent_runs,
   browser                                              publishes SSE events

Run locally:
    cd backend && .venv/Scripts/python.exe -m app.workers.case_runner

Run in Docker / K8s:
    image: clincase/worker:latest
    command: ["python", "-m", "app.workers.case_runner"]

Concurrency:
  - Each worker process claims one job at a time (sequential within process)
  - Multiple worker REPLICAS scale horizontally — Postgres SKIP LOCKED prevents
    race conditions
  - Recommended: 2× CPU cores per replica × 4 replicas = 8 concurrent cases
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import os
import signal
import socket
import time
from typing import Any

import structlog

from app.db import db
from app.graph.build import build_full_graph
from app.graph.state import ClinCaseState
from app.jobs import queue as jq

log = structlog.get_logger()

# How often the worker pings heartbeat_at while a job is running
_HEARTBEAT_INTERVAL_SECONDS = 5
# How often the janitor reaps stale-heartbeat jobs
_REAP_INTERVAL_SECONDS = 30
# How long the worker sleeps when the queue is empty
_POLL_IDLE_SECONDS = 2

_FULL_GRAPH = build_full_graph()


# =============================================================================
# Job execution
# =============================================================================


async def _heartbeat_loop(job: jq.Job, worker_id: str, stop: asyncio.Event) -> None:
    """Background task: ping heartbeat_at every N seconds until `stop` is set."""
    while not stop.is_set():
        try:
            owned = await jq.heartbeat(job.id, worker_id=worker_id, attempt=job.attempts)
            if not owned:
                log.warning("worker.lease.lost", job_id=str(job.id), attempt=job.attempts)
                stop.set()
                return
        except Exception as e:  # noqa: BLE001
            log.warning("worker.heartbeat.failed", job_id=str(job.id), error=str(e))
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), timeout=_HEARTBEAT_INTERVAL_SECONDS)


async def _execute_run_full(job: jq.Job) -> tuple[ClinCaseState, dict[str, Any]]:
    """Run the full 7-agent DAG against the job's payload."""
    payload = job.payload
    initial = ClinCaseState(
        case_id=job.case_id,
        organization_id=job.organization_id,
        fhir_bundle=payload["fhir_bundle"],
        physician_note=payload.get("physician_note"),
        requested_treatment=payload["requested_treatment"],
        payer_id=payload["payer_id"],
    )
    # The shared agent budget is ten minutes; enforce it at the outer boundary
    # too so a hung provider cannot heartbeat forever.
    final_raw = await asyncio.wait_for(_FULL_GRAPH.ainvoke(initial), timeout=600)
    final = (
        final_raw if isinstance(final_raw, ClinCaseState)
        else ClinCaseState.model_validate(final_raw)
    )
    # Compose result for the result_json column
    result = {
        "case_id": job.case_id,
        "verdict": final.decision.verdict if final.decision else None,
        "paused_for_review": final.paused_for_review,
        "n_policy_excerpts": len(final.policy_excerpts),
        "n_criteria": len(final.necessity_assessment.criteria) if final.necessity_assessment else 0,
        "appeal_drafted": final.appeal_draft is not None,
        "patient_communication_grade": (
            final.patient_communication.reading_level_grade
            if final.patient_communication else None
        ),
    }
    return final, result


async def _commit_run(
    job: jq.Job,
    worker_id: str,
    final: ClinCaseState,
    result: dict[str, Any],
) -> bool:
    """Atomically persist the clinical outcome and fenced job completion."""
    from app.events.outbox import emit_appeal_drafted, emit_case_decided

    async with db.pool.acquire() as conn, conn.transaction():
        owns_lease = await conn.fetchval(
            """SELECT 1 FROM case_jobs WHERE id=$1 AND status='running'
               AND claimed_by=$2 AND attempts=$3 FOR UPDATE""",
            job.id, worker_id, job.attempts,
        )
        if not owns_lease:
            return False

        if final.paused_for_review:
            await conn.execute(
                "UPDATE cases SET status='awaiting_review' WHERE id=$1 AND organization_id=$2",
                job.case_id, job.organization_id,
            )
        elif final.decision is not None:
            await conn.execute(
                """INSERT INTO decisions (case_id, verdict, rationale, citations_json, confidence)
                   VALUES ($1,$2,$3,$4,$5)""",
                job.case_id,
                final.decision.verdict,
                final.decision.rationale,
                json.dumps([c.model_dump() for c in final.decision.citations]),
                final.decision.confidence,
            )
            status_map = {"APPROVE": "approved", "DENY": "denied", "REFER": "referred"}
            case_status = "appealed" if final.appeal_draft else status_map[final.decision.verdict]
            await conn.execute(
                "UPDATE cases SET status=$1 WHERE id=$2 AND organization_id=$3",
                case_status, job.case_id, job.organization_id,
            )
            await emit_case_decided(
                organization_id=job.organization_id,
                case_id=job.case_id,
                verdict=final.decision.verdict,
                confidence=float(final.decision.confidence),
                triggered_hitl=False,
                decision_run_id=str(job.id),
                primary_model_id="recorded-per-agent",
                cost_usd=float(final._agent_context.budget.spent_usd) if final._agent_context else 0.0,
                duration_seconds=(float(final._agent_context.budget.elapsed_ms) / 1000) if final._agent_context else 0.0,
                conn=conn,
            )
        if final.appeal_draft is not None:
            appeal_id = await conn.fetchval(
                """INSERT INTO appeals (case_id, appeal_body, structured_arguments_json)
                   VALUES ($1,$2,$3) RETURNING id""",
                job.case_id,
                final.appeal_draft.appeal_body,
                json.dumps([a.model_dump() for a in final.appeal_draft.structured_arguments]),
            )
            await emit_appeal_drafted(
                organization_id=job.organization_id,
                case_id=job.case_id,
                appeal_id=appeal_id,
                structured_arguments_count=len(final.appeal_draft.structured_arguments),
                conn=conn,
            )
        completed = await conn.fetchval(
            """UPDATE case_jobs SET status='done',result_json=$2,finished_at=now(),heartbeat_at=now()
               WHERE id=$1 AND status='running' AND claimed_by=$3 AND attempts=$4 RETURNING id""",
            job.id, json.dumps(result), worker_id, job.attempts,
        )
        return completed is not None


JOB_HANDLERS = {
    "run_full": _execute_run_full,
    # Future: "resume_after_review", "draft_appeal_only", ...
}


async def _process_job(job: jq.Job, worker_id: str) -> None:
    """Run a single job with heartbeat + retry handling."""
    log.info("worker.job.start", job_id=str(job.id), case_id=job.case_id, type=job.job_type, attempt=job.attempts)

    handler = JOB_HANDLERS.get(job.job_type)
    if handler is None:
        await jq.mark_error(
            job.id, f"Unknown job_type: {job.job_type}",
            worker_id=worker_id, attempt=job.attempts, dead=True,
        )
        return

    stop_heartbeat = asyncio.Event()
    hb_task = asyncio.create_task(_heartbeat_loop(job, worker_id, stop_heartbeat))
    try:
        started = time.time()
        handler_task = asyncio.create_task(handler(job))
        lease_signal = asyncio.create_task(stop_heartbeat.wait())
        done, _pending = await asyncio.wait(
            {handler_task, lease_signal}, return_when=asyncio.FIRST_COMPLETED
        )
        if lease_signal in done and not handler_task.done():
            handler_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await handler_task
            raise RuntimeError("Worker lease expired during model execution")
        lease_signal.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await lease_signal
        final, result = await handler_task
        elapsed = time.time() - started
        if not await _commit_run(job, worker_id, final, result):
            raise RuntimeError("Worker lease expired before result commit")
        log.info(
            "worker.job.done",
            job_id=str(job.id),
            case_id=job.case_id,
            elapsed_s=round(elapsed, 2),
            verdict=result.get("verdict"),
        )
    except Exception as e:  # noqa: BLE001
        log.error(
            "worker.job.error",
            job_id=str(job.id),
            case_id=job.case_id,
            error=str(e),
            attempt=job.attempts,
        )
        await jq.mark_error(
            job.id, str(e), worker_id=worker_id, attempt=job.attempts, dead=False,
        )
    finally:
        stop_heartbeat.set()
        with contextlib.suppress(Exception):  # noqa: BLE001
            await hb_task


# =============================================================================
# Worker main loop
# =============================================================================


_shutdown = asyncio.Event()


def _install_signal_handlers() -> None:
    """SIGTERM / SIGINT → graceful drain. Production-essential for K8s rolling
    deploys: K8s sends SIGTERM, gives us 30s grace, then SIGKILL. We must
    finish in-flight jobs and stop claiming new ones."""
    loop = asyncio.get_running_loop()
    def _stop():
        log.info("worker.signal.shutdown")
        _shutdown.set()
    try:
        loop.add_signal_handler(signal.SIGTERM, _stop)
        loop.add_signal_handler(signal.SIGINT, _stop)
    except NotImplementedError:
        # Windows asyncio doesn't support signal handlers on the proactor loop.
        # In production this code runs on Linux containers; on Windows dev we
        # rely on Ctrl-C raising KeyboardInterrupt instead.
        pass


async def _janitor_loop(worker_id: str) -> None:
    """Periodically reap stale-heartbeat jobs."""
    while not _shutdown.is_set():
        try:
            n = await jq.reap_stale(stale_after_seconds=_HEARTBEAT_INTERVAL_SECONDS * 6)
            if n:
                log.info("worker.janitor.reaped", count=n, by=worker_id)
        except Exception as e:  # noqa: BLE001
            log.warning("worker.janitor.failed", error=str(e))
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(_shutdown.wait(), timeout=_REAP_INTERVAL_SECONDS)


async def main() -> None:
    worker_id = f"{socket.gethostname()}:{os.getpid()}"
    log.info("worker.boot", worker_id=worker_id, heartbeat_s=_HEARTBEAT_INTERVAL_SECONDS)

    await db.connect()
    await jq.ensure_schema()

    # Bootstrap quota + cache schemas (idempotent — both API and worker
    # paths run this so a worker started before the API still has the tables).
    try:
        from app.quotas import ensure_schema as _ensure_quota_schema
        await _ensure_quota_schema()
    except Exception as e:  # noqa: BLE001
        log.warning("worker.quotas.schema_bootstrap_failed", error=str(e))
    try:
        from app.agents.framework.cache import ensure_schema as _ensure_cache_schema
        await _ensure_cache_schema()
    except Exception as e:  # noqa: BLE001
        log.warning("worker.cache.schema_bootstrap_failed", error=str(e))

    # Wire Redis SSE pub/sub so events from this worker reach SSE
    # consumers landed on any API replica. See SCALE-7 in ops/SCALING.md.
    from app.config import settings
    if settings.REDIS_URL:
        try:
            from app.streaming import use_redis_backend
            await use_redis_backend(settings.REDIS_URL)
            log.info("worker.redis.connected")
        except Exception as e:  # noqa: BLE001
            log.warning("worker.redis.bootstrap_failed", error=str(e))

    _install_signal_handlers()

    janitor = asyncio.create_task(_janitor_loop(worker_id))

    try:
        while not _shutdown.is_set():
            try:
                job = await jq.claim_next(worker_id=worker_id)
            except Exception as e:  # noqa: BLE001
                log.error("worker.claim.failed", error=str(e))
                await asyncio.sleep(_POLL_IDLE_SECONDS)
                continue

            if job is None:
                # Empty queue — back off briefly, recheck shutdown
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(_shutdown.wait(), timeout=_POLL_IDLE_SECONDS)
                continue

            await _process_job(job, worker_id)
    finally:
        log.info("worker.draining")
        _shutdown.set()
        with contextlib.suppress(Exception):
            await janitor
        try:
            from app.streaming import shutdown_backend
            await shutdown_backend()
        except Exception:  # noqa: BLE001
            pass
        await db.disconnect()
        log.info("worker.exit")


if __name__ == "__main__":
    asyncio.run(main())
