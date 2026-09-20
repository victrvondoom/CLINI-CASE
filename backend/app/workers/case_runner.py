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
import os
import signal
import socket
import time
import uuid
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


async def _heartbeat_loop(job_id: uuid.UUID, stop: asyncio.Event) -> None:
    """Background task: ping heartbeat_at every N seconds until `stop` is set."""
    while not stop.is_set():
        try:
            await jq.heartbeat(job_id)
        except Exception as e:  # noqa: BLE001
            log.warning("worker.heartbeat.failed", job_id=str(job_id), error=str(e))
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), timeout=_HEARTBEAT_INTERVAL_SECONDS)


async def _execute_run_full(job: jq.Job) -> dict[str, Any]:
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
    final_raw = await _FULL_GRAPH.ainvoke(initial)
    final = (
        final_raw if isinstance(final_raw, ClinCaseState)
        else ClinCaseState.model_validate(final_raw)
    )
    # Compose result for the result_json column
    return {
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


JOB_HANDLERS = {
    "run_full": _execute_run_full,
    # Future: "resume_after_review", "draft_appeal_only", ...
}


async def _process_job(job: jq.Job, worker_id: str) -> None:
    """Run a single job with heartbeat + retry handling."""
    log.info("worker.job.start", job_id=str(job.id), case_id=job.case_id, type=job.job_type, attempt=job.attempts)

    handler = JOB_HANDLERS.get(job.job_type)
    if handler is None:
        await jq.mark_error(job.id, f"Unknown job_type: {job.job_type}", dead=True)
        return

    stop_heartbeat = asyncio.Event()
    hb_task = asyncio.create_task(_heartbeat_loop(job.id, stop_heartbeat))
    try:
        started = time.time()
        result = await handler(job)
        elapsed = time.time() - started
        await jq.mark_done(job.id, result)
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
        await jq.mark_error(job.id, str(e), dead=False)
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
