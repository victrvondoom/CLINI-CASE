"""Contract tests for ModelRouter + cost estimation."""
from __future__ import annotations

import pytest

from app.agents.framework import (
    HAIKU_LITE,
    SONNET_REASONING,
    ModelRouter,
    ModelSpec,
    estimate_cost,
)


def test_haiku_escalates_to_sonnet():
    out = ModelRouter.escalate(HAIKU_LITE)
    assert out.size == "sonnet"
    assert out.role.endswith("_escalated")


def test_sonnet_escalation_is_idempotent():
    out = ModelRouter.escalate(SONNET_REASONING)
    assert out.size == "sonnet"  # already strongest


def test_cost_estimate_known_pricing():
    # Sonnet: $3 / Mtok in, $15 / Mtok out
    cost = estimate_cost(SONNET_REASONING, input_tokens=1_000_000, output_tokens=1_000_000)
    assert cost == pytest.approx(18.0)


def test_haiku_is_5x_cheaper_than_sonnet():
    s = estimate_cost(SONNET_REASONING, input_tokens=10_000, output_tokens=2_000)
    h = estimate_cost(HAIKU_LITE,        input_tokens=10_000, output_tokens=2_000)
    assert h * 3 == pytest.approx(s, rel=0.0001)
    # Sonnet $3/$15 vs Haiku $1/$5 → exactly 1/3 the cost.


def test_custom_modelspec():
    custom = ModelSpec(
        size="haiku",
        role="custom_test",
        cost_per_million_input_tokens=2.0,
        cost_per_million_output_tokens=10.0,
    )
    cost = estimate_cost(custom, input_tokens=1_000_000, output_tokens=500_000)
    assert cost == pytest.approx(2.0 + 5.0)
