from __future__ import annotations

import math

import pytest

from app.agents.framework.budget import BudgetTracker


@pytest.mark.parametrize("value", [-1.0, math.inf, math.nan])
def test_budget_rejects_invalid_cost_ceiling(value: float) -> None:
    with pytest.raises(ValueError):
        BudgetTracker(max_cost_usd=value, max_total_tokens=100, max_latency_ms=100)


def test_budget_rejects_negative_estimates_and_actuals() -> None:
    budget = BudgetTracker(max_cost_usd=1, max_total_tokens=100, max_latency_ms=1000)
    with pytest.raises(ValueError):
        budget.reserve(estimated_usd=-0.1)
    reservation = budget.reserve(estimated_usd=0.1)
    with pytest.raises(ValueError):
        budget.commit(
            reservation,
            actual_usd=-0.1,
            actual_input_tokens=0,
            actual_output_tokens=0,
        )
    budget.cancel(reservation)
    assert budget.snapshot()["open_reservations"] == 0
