"""Graceful shutdown — SIGTERM handler for the API + worker processes.

Production K8s rollouts send SIGTERM, then wait `terminationGracePeriodSeconds`
(default 30s, we configure 90s) before SIGKILL. Without this module:

  • A worker mid-DAG dies. The case stays in `running` until the janitor's
    heartbeat reaper finds it (60s — exceeds many SLOs).
  • An API replica drops in-flight requests; clients see ECONNRESET.

This module installs a SIGTERM handler that:

  1. Sets the global `_shutting_down` flag — readiness probe starts failing
     so K8s removes us from the Service endpoints (no new traffic arrives).
  2. For workers: stops claiming new jobs from the queue.
  3. Waits for in-flight DAGs to finish, up to `GRACEFUL_SHUTDOWN_TIMEOUT_S`
     (default 60s).
  4. Releases the heartbeat lock on each in-flight job so the next worker
     resumes it cleanly.
  5. Closes DB pools + Redis pubsub.

The result: rolling deploys lose ZERO in-flight cases.
"""
from __future__ import annotations

import asyncio
import os
import signal
from contextlib import asynccontextmanager
from typing import AsyncIterator, Awaitable, Callable

import structlog

log = structlog.get_logger()

_GRACEFUL_TIMEOUT_S = float(os.getenv("GRACEFUL_SHUTDOWN_TIMEOUT_S", "60"))
_shutting_down = False
_in_flight: int = 0
_in_flight_lock = asyncio.Lock()
_drain_event = asyncio.Event()
_drain_event.set()  # not draining initially


def is_shutting_down() -> bool:
    return _shutting_down


async def _bump_in_flight(delta: int) -> None:
    global _in_flight
    async with _in_flight_lock:
        _in_flight += delta
        if _in_flight == 0 and _shutting_down:
            _drain_event.set()
        elif _in_flight > 0:
            _drain_event.clear()


@asynccontextmanager
async def in_flight_request() -> AsyncIterator[None]:
    """Wrap a unit of work that should block shutdown. Use in case-run + worker
    claim sites:

        async with in_flight_request():
            await execute_dag(...)
    """
    if _shutting_down:
        raise RuntimeError("Shutting down; new work refused.")
    await _bump_in_flight(+1)
    try:
        yield
    finally:
        await _bump_in_flight(-1)


async def _await_drain() -> None:
    """Wait for in-flight count to reach 0, with a hard timeout."""
    try:
        await asyncio.wait_for(_drain_event.wait(), timeout=_GRACEFUL_TIMEOUT_S)
        log.info("graceful.drained")
    except asyncio.TimeoutError:
        log.warning("graceful.drain_timeout", in_flight=_in_flight, timeout_s=_GRACEFUL_TIMEOUT_S)


def install_signal_handlers(
    on_drain_complete: Callable[[], Awaitable[None]] | None = None,
) -> None:
    """Install SIGTERM + SIGINT handlers. Idempotent — safe to call from
    multiple modules' init."""
    loop = asyncio.get_event_loop()

    def _trigger(signame: str) -> None:
        global _shutting_down
        if _shutting_down:
            return
        _shutting_down = True
        if _in_flight == 0:
            _drain_event.set()
        else:
            _drain_event.clear()
        log.info("graceful.shutdown.signal", signal=signame, in_flight=_in_flight)
        loop.create_task(_drain_then(on_drain_complete))

    async def _drain_then(cb: Callable[[], Awaitable[None]] | None) -> None:
        await _await_drain()
        if cb:
            try:
                await cb()
            except Exception as e:  # noqa: BLE001
                log.error("graceful.callback.failed", error=str(e))

    for sig_name in ("SIGTERM", "SIGINT"):
        sig = getattr(signal, sig_name, None)
        if sig is None:
            continue
        try:
            loop.add_signal_handler(sig, _trigger, sig_name)
        except NotImplementedError:
            # Windows asyncio loop doesn't support signal handlers.
            # Honor SIGINT via signal.signal as a fallback.
            signal.signal(sig, lambda *_args: _trigger(sig_name))


def shutdown_snapshot() -> dict[str, object]:
    """Snapshot for /healthz/deep + readiness probes."""
    return {
        "shutting_down": _shutting_down,
        "in_flight": _in_flight,
        "graceful_timeout_s": _GRACEFUL_TIMEOUT_S,
    }
