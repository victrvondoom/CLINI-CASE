"""3-state circuit breaker for Bedrock InvokeModel calls.

Industry-standard resilience primitive (Resilience4j-equivalent).

States:
  CLOSED  - calls flow through; failures are counted in a sliding window
  OPEN    - calls fail fast (no Bedrock invocation); cool-down for `cooldown_seconds`
  HALF_OPEN - allow `probe_calls` test calls; if any succeed → CLOSED, else → OPEN

Per-model breaker — Sonnet failures don't trip Haiku. The GenAI Gateway routes
around an OPEN breaker by escalating to the fallback model (Haiku → Sonnet, or
vice versa). When ALL models in a tenant's allowlist have OPEN breakers, the
caller sees `CircuitBreakerOpen` raised before any Bedrock TPM is consumed.

Why this matters at industry scale:
  • Without it, a 5xx storm from Bedrock translates directly into 5xx storms
    at the customer's API. Every retry burns the failing region's TPM.
  • With it, after N consecutive failures the breaker OPENS. We stop calling
    that model for `cooldown_seconds`. The customer gets a fast 503 with
    `Retry-After`, NOT a slow 5xx after timeout.
  • Recovery is graceful — HALF_OPEN probes the model with a few calls and
    transitions back to CLOSED only if it's actually healthy.

Pairs with `app/sre/SLO.yaml` SLO `api-availability` — circuit breaker state
transitions are exposed as Prometheus gauge metrics for the burn-rate alerts.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import structlog

log = structlog.get_logger()


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerOpen(Exception):
    """Raised when an OPEN breaker rejects a call before invocation."""

    def __init__(self, model_id: str, opened_at: float, cooldown_seconds: int) -> None:
        self.model_id = model_id
        self.opened_at = opened_at
        self.cooldown_seconds = cooldown_seconds
        self.retry_after_seconds = max(1, int(cooldown_seconds - (time.time() - opened_at)))
        super().__init__(
            f"CircuitBreakerOpen[{model_id}] opened {time.time() - opened_at:.1f}s ago; "
            f"retry-after {self.retry_after_seconds}s"
        )


@dataclass
class CircuitBreakerConfig:
    """Per-model breaker configuration. Tuned for Bedrock characteristic latencies."""

    # Sliding window of recent calls
    window_size: int = 50
    # OPEN if failures / window_size >= failure_rate_threshold (with min sample size)
    failure_rate_threshold: float = 0.5
    min_samples_to_open: int = 10
    # Cool-down before transitioning OPEN → HALF_OPEN
    cooldown_seconds: int = 30
    # Number of test calls in HALF_OPEN before deciding next state
    half_open_probe_calls: int = 3


@dataclass
class CircuitBreaker:
    """Per-model breaker. Thread-safe via asyncio.Lock."""

    model_id: str
    config: CircuitBreakerConfig = field(default_factory=CircuitBreakerConfig)

    state: CircuitState = CircuitState.CLOSED
    opened_at: float = 0.0
    half_open_attempts: int = 0
    half_open_successes: int = 0

    # Sliding window of last N call outcomes (True = success, False = failure)
    _outcomes: list[bool] = field(default_factory=list)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def before_call(self) -> None:
        """Raise CircuitBreakerOpen if the breaker is OPEN. Call before InvokeModel."""
        async with self._lock:
            now = time.time()
            if self.state == CircuitState.OPEN:
                # Cool-down elapsed → transition to HALF_OPEN
                if now - self.opened_at >= self.config.cooldown_seconds:
                    self._transition(CircuitState.HALF_OPEN)
                    self.half_open_attempts = 0
                    self.half_open_successes = 0
                    log.info("circuit.half_open", model_id=self.model_id)
                else:
                    raise CircuitBreakerOpen(self.model_id, self.opened_at, self.config.cooldown_seconds)

            if self.state == CircuitState.HALF_OPEN:
                if self.half_open_attempts >= self.config.half_open_probe_calls:
                    # Probe quota exhausted; defer to next eval
                    raise CircuitBreakerOpen(self.model_id, self.opened_at, self.config.cooldown_seconds)
                self.half_open_attempts += 1

    async def record_success(self) -> None:
        async with self._lock:
            self._record_outcome(True)
            if self.state == CircuitState.HALF_OPEN:
                self.half_open_successes += 1
                # All probes succeeded → CLOSED
                if self.half_open_successes >= self.config.half_open_probe_calls:
                    self._transition(CircuitState.CLOSED)
                    self._outcomes.clear()
                    log.info("circuit.closed", model_id=self.model_id)

    async def record_failure(self) -> None:
        async with self._lock:
            self._record_outcome(False)
            if self.state == CircuitState.HALF_OPEN:
                # Any failure in HALF_OPEN → re-OPEN immediately
                self._transition(CircuitState.OPEN)
                self.opened_at = time.time()
                log.warning("circuit.reopened_from_half_open", model_id=self.model_id)
                return

            if self.state == CircuitState.CLOSED:
                # Evaluate failure rate
                if len(self._outcomes) >= self.config.min_samples_to_open:
                    failures = sum(1 for o in self._outcomes if not o)
                    rate = failures / len(self._outcomes)
                    if rate >= self.config.failure_rate_threshold:
                        self._transition(CircuitState.OPEN)
                        self.opened_at = time.time()
                        log.warning(
                            "circuit.opened",
                            model_id=self.model_id,
                            failure_rate=round(rate, 3),
                            samples=len(self._outcomes),
                        )

    def snapshot(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "state": self.state.value,
            "opened_at": self.opened_at if self.state != CircuitState.CLOSED else None,
            "samples": len(self._outcomes),
            "failure_rate": (
                round(sum(1 for o in self._outcomes if not o) / max(1, len(self._outcomes)), 3)
                if self._outcomes else 0.0
            ),
            "config": {
                "window_size": self.config.window_size,
                "failure_rate_threshold": self.config.failure_rate_threshold,
                "cooldown_seconds": self.config.cooldown_seconds,
            },
        }

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------

    def _record_outcome(self, success: bool) -> None:
        self._outcomes.append(success)
        if len(self._outcomes) > self.config.window_size:
            self._outcomes.pop(0)

    def _transition(self, new_state: CircuitState) -> None:
        self.state = new_state


# =============================================================================
# Per-model breaker registry
# =============================================================================


_BREAKERS: dict[str, CircuitBreaker] = {}
_REGISTRY_LOCK = asyncio.Lock()


async def get_breaker(model_id: str) -> CircuitBreaker:
    """Lazily create the breaker for a model_id. One per model."""
    async with _REGISTRY_LOCK:
        if model_id not in _BREAKERS:
            _BREAKERS[model_id] = CircuitBreaker(model_id=model_id)
        return _BREAKERS[model_id]


def all_breaker_snapshots() -> list[dict[str, Any]]:
    """Snapshot every breaker. Used by /api/v1/llm-gateway/circuit-breakers + /metrics."""
    return [b.snapshot() for b in _BREAKERS.values()]
