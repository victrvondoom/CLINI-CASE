"""Contract tests for the Guardrails framework."""
from __future__ import annotations

import asyncio

from pydantic import BaseModel

from app.agents.framework import (
    GuardrailDecision,
    SchemaGuardrail,
    TokenBudgetGuardrail,
)


class _DummyOut(BaseModel):
    text: str


class _OtherOut(BaseModel):
    text: str


def test_schema_guardrail_passes_correct_type():
    gr = SchemaGuardrail(_DummyOut)
    out = _DummyOut(text="ok")
    res = asyncio.run(gr.check(out, agent_name="t", case_id="c"))
    assert res.decision == GuardrailDecision.PASS


def test_schema_guardrail_retries_wrong_type():
    gr = SchemaGuardrail(_DummyOut)
    other = _OtherOut(text="wrong")
    res = asyncio.run(gr.check(other, agent_name="t", case_id="c"))
    assert res.decision == GuardrailDecision.RETRY
    assert "_DummyOut" in res.reason


def test_token_budget_guardrail_blocks_oversized():
    gr = TokenBudgetGuardrail(max_input_tokens=10)
    payload = _DummyOut(text="x" * 200)  # ~50 tokens
    res = asyncio.run(gr.check(payload, agent_name="t", case_id="c"))
    assert res.decision == GuardrailDecision.BLOCK


def test_token_budget_guardrail_passes_small():
    gr = TokenBudgetGuardrail(max_input_tokens=10_000)
    payload = _DummyOut(text="hello")
    res = asyncio.run(gr.check(payload, agent_name="t", case_id="c"))
    assert res.decision == GuardrailDecision.PASS
