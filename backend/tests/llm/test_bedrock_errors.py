"""Bedrock client hardening: typed errors + guardrail handling, with a stubbed boto3 client (no AWS)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.llm.bedrock_client import BedrockClient
from app.llm.errors import (
    LLMAccessDeniedError,
    LLMGuardrailBlockedError,
    LLMThrottledError,
    LLMValidationError,
    map_bedrock_error,
)


class _ClientError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.response = {"Error": {"Code": code}}


class _Stub:
    def __init__(self, result=None, exc=None):
        self.result, self.exc = result, exc

    def converse(self, **_):
        if self.exc:
            raise self.exc
        return self.result


def _client(stub) -> BedrockClient:
    with patch("app.llm.bedrock_client.boto3.client", return_value=stub):
        return BedrockClient()


_OK = {
    "output": {"message": {"content": [{"text": "hi"}]}},
    "usage": {"inputTokens": 3, "outputTokens": 2},
    "stopReason": "end_turn",
}


@pytest.mark.parametrize(
    ("code", "cls", "retryable"),
    [
        ("ThrottlingException", LLMThrottledError, True),
        ("AccessDeniedException", LLMAccessDeniedError, False),
        ("ValidationException", LLMValidationError, False),
    ],
)
async def test_errors_are_typed(code, cls, retryable):
    c = _client(_Stub(exc=_ClientError(code)))
    with pytest.raises(cls) as ei:
        await c.complete(system="s", user="u", model_id="m")
    assert ei.value.retryable is retryable and ei.value.model_id == "m"


def test_unknown_error_is_non_retryable():
    e = map_bedrock_error(RuntimeError("boom"))
    assert not e.retryable


async def test_guardrail_intervention_is_not_returned_as_an_answer():
    blocked = {**_OK, "stopReason": "guardrail_intervened"}
    with pytest.raises(LLMGuardrailBlockedError):
        await _client(_Stub(result=blocked)).complete(system="s", user="u")
    traced = {**_OK, "trace": {"guardrail": {"action": "GUARDRAIL_INTERVENED"}}}
    with pytest.raises(LLMGuardrailBlockedError):
        await _client(_Stub(result=traced)).complete(system="s", user="u")


async def test_ok_response_passes_through():
    r = await _client(_Stub(result=_OK)).complete(system="s", user="u", model_id="m")
    assert r.text == "hi" and r.input_tokens == 3
