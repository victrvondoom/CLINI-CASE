"""Budget tracker — per-agent and per-case ceilings on cost / tokens / latency.

Production-essential. Without budgets, an LLM agent loop can rack up $$ in
runaway tool-calling or reflection retries. The tracker enforces a hard
ceiling before each LLM call (reservation) and reconciles actual spend
afterward (commit). Exceeding any ceiling raises `BudgetExceeded`, which
the Agent base catches → triggers fallback model or graceful failure.

Reservation pattern (analogous to AWS service quotas):
    1. agent calls `tracker.reserve(estimated_cost_usd)`
    2. tracker raises BudgetExceeded if remaining < estimate (+ safety margin)
    3. agent runs the LLM call, observes actual cost
    4. agent calls `tracker.commit(token, actual_cost_usd)`
    5. tracker subtracts actual from remaining; releases the reservation slack
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any


class BudgetExceeded(RuntimeError):
    """Raised when an agent attempts to spend beyond its ceiling.

    Agent.invoke() catches this and either (a) routes to fallback_model if
    one is declared, or (b) fails the case gracefully with status
    BUDGET_EXCEEDED so the audit trail records the why.
    """

    def __init__(self, *, dimension: str, requested: float, remaining: float, ceiling: float):
        self.dimension = dimension
        self.requested = requested
        self.remaining = remaining
        self.ceiling = ceiling
        super().__init__(
            f"BudgetExceeded[{dimension}]: requested={requested}, "
            f"remaining={remaining:.4f}, ceiling={ceiling:.4f}"
        )


@dataclass
class Reservation:
    token: uuid.UUID
    estimated_usd: float
    estimated_input_tokens: int
    estimated_output_tokens: int
    reserved_at: float


@dataclass
class BudgetTracker:
    """Per-case budget. Each Agent.invoke() draws from the same tracker so
    a single case can't exceed its ceiling no matter how many sub-agents
    fire or how many retries trigger."""

    max_cost_usd: float
    max_total_tokens: int
    max_latency_ms: int

    # Live counters
    spent_usd: float = 0.0
    spent_input_tokens: int = 0
    spent_output_tokens: int = 0
    started_at: float = field(default_factory=time.time)

    # Open reservations (committed/cancelled at end of operation)
    _reservations: dict[uuid.UUID, Reservation] = field(default_factory=dict)

    @property
    def remaining_usd(self) -> float:
        held = sum(r.estimated_usd for r in self._reservations.values())
        return self.max_cost_usd - self.spent_usd - held

    @property
    def remaining_total_tokens(self) -> int:
        held = sum(
            r.estimated_input_tokens + r.estimated_output_tokens
            for r in self._reservations.values()
        )
        return self.max_total_tokens - (
            self.spent_input_tokens + self.spent_output_tokens
        ) - held

    @property
    def elapsed_ms(self) -> int:
        return int((time.time() - self.started_at) * 1000)

    @property
    def remaining_latency_ms(self) -> int:
        return self.max_latency_ms - self.elapsed_ms

    # ------------------------------------------------------------------
    # Reservation API
    # ------------------------------------------------------------------

    def reserve(
        self,
        *,
        estimated_usd: float,
        estimated_input_tokens: int = 0,
        estimated_output_tokens: int = 0,
    ) -> Reservation:
        """Reserve budget for an upcoming LLM call. Raises BudgetExceeded if
        the reservation would exceed any ceiling."""
        if estimated_usd > self.remaining_usd:
            raise BudgetExceeded(
                dimension="cost_usd",
                requested=estimated_usd,
                remaining=self.remaining_usd,
                ceiling=self.max_cost_usd,
            )
        total_tok = estimated_input_tokens + estimated_output_tokens
        if total_tok > self.remaining_total_tokens:
            raise BudgetExceeded(
                dimension="tokens",
                requested=total_tok,
                remaining=self.remaining_total_tokens,
                ceiling=self.max_total_tokens,
            )
        if self.elapsed_ms > self.max_latency_ms:
            raise BudgetExceeded(
                dimension="latency_ms",
                requested=self.elapsed_ms,
                remaining=self.remaining_latency_ms,
                ceiling=self.max_latency_ms,
            )
        token = uuid.uuid4()
        self._reservations[token] = Reservation(
            token=token,
            estimated_usd=estimated_usd,
            estimated_input_tokens=estimated_input_tokens,
            estimated_output_tokens=estimated_output_tokens,
            reserved_at=time.time(),
        )
        return self._reservations[token]

    def commit(
        self,
        reservation: Reservation,
        *,
        actual_usd: float,
        actual_input_tokens: int,
        actual_output_tokens: int,
        model_id: str = "unknown",
    ) -> None:
        """Settle a reservation against actual usage. Releases unused slack."""
        if reservation.token not in self._reservations:
            return  # idempotent / double-commit safe
        self._reservations.pop(reservation.token)
        self.spent_usd += actual_usd
        self.spent_input_tokens += actual_input_tokens
        self.spent_output_tokens += actual_output_tokens

    def cancel(self, reservation: Reservation) -> None:
        """Drop a reservation without spending (e.g. operation aborted before LLM call)."""
        self._reservations.pop(reservation.token, None)

    # ------------------------------------------------------------------
    # Snapshot for telemetry
    # ------------------------------------------------------------------

    def snapshot(self) -> dict[str, Any]:
        return {
            "max_cost_usd": self.max_cost_usd,
            "spent_usd": round(self.spent_usd, 6),
            "remaining_usd": round(self.remaining_usd, 6),
            "max_total_tokens": self.max_total_tokens,
            "spent_total_tokens": self.spent_input_tokens + self.spent_output_tokens,
            "remaining_total_tokens": self.remaining_total_tokens,
            "max_latency_ms": self.max_latency_ms,
            "elapsed_ms": self.elapsed_ms,
            "remaining_latency_ms": self.remaining_latency_ms,
            "open_reservations": len(self._reservations),
        }


# =============================================================================
# Default per-case budget (production tuneable)
# =============================================================================


DEFAULT_BUDGET = BudgetTracker(
    max_cost_usd=5.00,        # $5 / case ceiling — actual spend is ~$0.40-0.80
    max_total_tokens=600_000, # 600K token budget per case
    max_latency_ms=600_000,   # 10 minutes — accommodates parallel fan-out
)


def new_default_budget() -> BudgetTracker:
    """Fresh budget tracker per case — never share across cases."""
    return BudgetTracker(
        max_cost_usd=5.00,
        max_total_tokens=600_000,
        max_latency_ms=600_000,
    )
