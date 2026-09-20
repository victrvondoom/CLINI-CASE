"""Generic 3-state breaker for any non-Bedrock downstream.

Same semantics as `app/llm/circuit_breaker.py` (CLOSED/OPEN/HALF_OPEN with
sliding-window failure tracking) but indexed by (component, endpoint).

Pre-registered components:
  • trizetto_facets       — POST .../facets/prior_auth_event
  • trizetto_qnxt         — POST .../qnxt/case_event
  • amazon_q_retrieve     — POST .../amazonq/retrieve
  • fhir_pas_submit       — POST .../Claim/$submit
  • anthropic_api         — POST https://api.anthropic.com/v1/messages
  • bedrock_kb_retrieve   — POST .../bedrock-kb/retrieve

A custom breaker is created on first reference via `get_breaker(name)`.
"""
from __future__ import annotations

import asyncio
import time
from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Any

import structlog

log = structlog.get_logger()


class State(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class DownstreamBreakerOpen(Exception):
    def __init__(self, name: str, opened_at: float, cooldown: int) -> None:
        self.name = name
        self.opened_at = opened_at
        self.retry_after_seconds = max(1, int(cooldown - (time.time() - opened_at)))
        super().__init__(
            f"DownstreamBreakerOpen[{name}] opened {time.time() - opened_at:.1f}s ago; "
            f"retry-after {self.retry_after_seconds}s"
        )


@dataclass
class _Cfg:
    failure_threshold: int = 5      # consecutive failures or rate breach to OPEN
    failure_rate_threshold: float = 0.5
    rolling_window_size: int = 20
    cooldown_seconds: int = 30
    probe_calls: int = 2


class DownstreamBreaker:
    def __init__(self, name: str, cfg: _Cfg | None = None) -> None:
        self.name = name
        self.cfg = cfg or _Cfg()
        self._state: State = State.CLOSED
        self._opened_at: float = 0.0
        self._half_open_remaining: int = 0
        self._results: deque[bool] = deque(maxlen=self.cfg.rolling_window_size)
        self._lock = asyncio.Lock()

    async def before_call(self) -> None:
        async with self._lock:
            now = time.time()
            if self._state is State.OPEN:
                if now - self._opened_at < self.cfg.cooldown_seconds:
                    raise DownstreamBreakerOpen(self.name, self._opened_at, self.cfg.cooldown_seconds)
                # cooldown expired → HALF_OPEN
                self._state = State.HALF_OPEN
                self._half_open_remaining = self.cfg.probe_calls
                log.info("downstream.breaker.half_open", name=self.name)
            if self._state is State.HALF_OPEN and self._half_open_remaining <= 0:
                # Concurrent probe limit reached
                raise DownstreamBreakerOpen(self.name, self._opened_at, self.cfg.cooldown_seconds)
            if self._state is State.HALF_OPEN:
                self._half_open_remaining -= 1

    async def record_success(self) -> None:
        async with self._lock:
            self._results.append(True)
            if self._state is State.HALF_OPEN:
                # Any success in HALF_OPEN closes the breaker
                self._state = State.CLOSED
                self._results.clear()
                log.info("downstream.breaker.closed", name=self.name)

    async def record_failure(self) -> None:
        async with self._lock:
            self._results.append(False)
            if self._state is State.HALF_OPEN:
                self._open_now("half_open_probe_failed")
                return
            if self._state is State.CLOSED and self._should_open():
                self._open_now("rolling_window_breach")

    def _should_open(self) -> bool:
        if len(self._results) < self.cfg.rolling_window_size:
            # consecutive-failures rule for cold start
            tail = list(self._results)[-self.cfg.failure_threshold:]
            return len(tail) >= self.cfg.failure_threshold and not any(tail)
        failures = sum(1 for r in self._results if not r)
        return (failures / self.cfg.rolling_window_size) >= self.cfg.failure_rate_threshold

    def _open_now(self, reason: str) -> None:
        self._state = State.OPEN
        self._opened_at = time.time()
        self._results.clear()
        log.warning("downstream.breaker.open", name=self.name, reason=reason, cooldown=self.cfg.cooldown_seconds)

    def snapshot(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "state": self._state.value,
            "opened_at": self._opened_at,
            "rolling_window_count": len(self._results),
            "rolling_window_failures": sum(1 for r in self._results if not r),
            "cooldown_seconds": self.cfg.cooldown_seconds,
            "failure_threshold": self.cfg.failure_threshold,
            "failure_rate_threshold": self.cfg.failure_rate_threshold,
        }


# =============================================================================
# Registry
# =============================================================================


_breakers: dict[str, DownstreamBreaker] = {}
_registry_lock = asyncio.Lock()


_PRESETS: dict[str, _Cfg] = {
    # Conservative defaults; loosened for high-volume / forgiving downstreams
    "trizetto_facets":   _Cfg(failure_threshold=5, cooldown_seconds=30),
    "trizetto_qnxt":     _Cfg(failure_threshold=5, cooldown_seconds=30),
    "amazon_q_retrieve": _Cfg(failure_threshold=5, cooldown_seconds=20),
    "fhir_pas_submit":   _Cfg(failure_threshold=3, cooldown_seconds=60),
    "anthropic_api":     _Cfg(failure_threshold=10, cooldown_seconds=15),
    "bedrock_kb_retrieve": _Cfg(failure_threshold=5, cooldown_seconds=20),
}


async def get_breaker(name: str) -> DownstreamBreaker:
    async with _registry_lock:
        b = _breakers.get(name)
        if b is None:
            cfg = _PRESETS.get(name)
            b = DownstreamBreaker(name=name, cfg=cfg)
            _breakers[name] = b
        return b


def breaker_snapshot() -> dict[str, Any]:
    """Snapshot every breaker's state for /api/v1/llm-gateway/circuit-breakers
    (round 9 endpoint extended to include downstreams)."""
    return {name: b.snapshot() for name, b in _breakers.items()}


# =============================================================================
# Helper — wrap an async call with the breaker. Common usage pattern.
# =============================================================================


async def call_with_breaker(name: str, awaitable_factory):
    """Run an async function under the named breaker.

        result = await call_with_breaker(
            "trizetto_facets",
            lambda: client.post(...),
        )

    Raises DownstreamBreakerOpen when OPEN.
    """
    b = await get_breaker(name)
    await b.before_call()
    try:
        result = await awaitable_factory()
    except Exception:
        await b.record_failure()
        raise
    else:
        await b.record_success()
        return result
