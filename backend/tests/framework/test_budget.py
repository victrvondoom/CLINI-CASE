"""Contract tests for BudgetTracker — production-grade budget enforcement."""
from __future__ import annotations

import pytest

from app.agents.framework import BudgetExceeded, BudgetTracker


def _budget(*, max_cost_usd=1.0, max_total_tokens=100_000, max_latency_ms=60_000):
    return BudgetTracker(
        max_cost_usd=max_cost_usd,
        max_total_tokens=max_total_tokens,
        max_latency_ms=max_latency_ms,
    )


def test_reservation_then_commit_subtracts_actual():
    b = _budget()
    res = b.reserve(estimated_usd=0.10, estimated_input_tokens=1000, estimated_output_tokens=500)
    assert b.remaining_usd == pytest.approx(0.90)
    b.commit(res, actual_usd=0.08, actual_input_tokens=900, actual_output_tokens=480, model_id="x")
    assert b.spent_usd == pytest.approx(0.08)
    assert b.remaining_usd == pytest.approx(0.92)


def test_cancel_releases_reservation_without_spend():
    b = _budget()
    res = b.reserve(estimated_usd=0.20)
    assert b.remaining_usd == pytest.approx(0.80)
    b.cancel(res)
    assert b.remaining_usd == pytest.approx(1.00)
    assert b.spent_usd == 0.0


def test_overreservation_raises_budget_exceeded():
    b = _budget(max_cost_usd=0.50)
    with pytest.raises(BudgetExceeded) as exc:
        b.reserve(estimated_usd=0.75)
    assert exc.value.dimension == "cost_usd"
    assert exc.value.requested == 0.75
    assert exc.value.ceiling == 0.50


def test_token_ceiling_enforced():
    b = _budget(max_total_tokens=1000)
    with pytest.raises(BudgetExceeded) as exc:
        b.reserve(estimated_usd=0.01, estimated_input_tokens=800, estimated_output_tokens=400)
    assert exc.value.dimension == "tokens"


def test_concurrent_reservations_dont_double_book():
    """Two open reservations subtract from remaining together."""
    b = _budget(max_cost_usd=1.0)
    r1 = b.reserve(estimated_usd=0.40)
    r2 = b.reserve(estimated_usd=0.40)
    assert b.remaining_usd == pytest.approx(0.20)
    with pytest.raises(BudgetExceeded):
        b.reserve(estimated_usd=0.30)  # only 0.20 remaining, this exceeds
    b.commit(r1, actual_usd=0.30, actual_input_tokens=0, actual_output_tokens=0, model_id="x")
    b.commit(r2, actual_usd=0.30, actual_input_tokens=0, actual_output_tokens=0, model_id="x")
    assert b.spent_usd == pytest.approx(0.60)
    assert b.remaining_usd == pytest.approx(0.40)


def test_snapshot_for_telemetry():
    b = _budget()
    b.reserve(estimated_usd=0.10)
    snap = b.snapshot()
    assert snap["max_cost_usd"] == 1.0
    assert snap["open_reservations"] == 1
    assert "spent_usd" in snap
    assert "remaining_latency_ms" in snap
