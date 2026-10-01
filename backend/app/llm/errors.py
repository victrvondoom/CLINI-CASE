"""Typed LLM errors so callers can decide retry / fallback / escalate without parsing strings."""

from __future__ import annotations

from typing import Any


class LLMError(Exception):
    """Base. `retryable` says whether the same request may be retried."""

    retryable = False
    code = "llm_error"

    def __init__(self, message: str, *, model_id: str | None = None):
        super().__init__(message)
        self.model_id = model_id


class LLMThrottledError(LLMError):
    retryable, code = True, "throttled"


class LLMTimeoutError(LLMError):
    retryable, code = True, "timeout"


class LLMUnavailableError(LLMError):
    retryable, code = True, "unavailable"


class LLMAccessDeniedError(LLMError):
    code = "access_denied"


class LLMModelNotFoundError(LLMError):
    code = "model_not_found"


class LLMValidationError(LLMError):
    code = "validation"


class LLMQuotaError(LLMError):
    code = "quota_exceeded"


class LLMGuardrailBlockedError(LLMError):
    """The Bedrock guardrail intervened; the output must not be used as a model answer."""

    code = "guardrail_blocked"


_BY_CODE: dict[str, type[LLMError]] = {
    "ThrottlingException": LLMThrottledError,
    "TooManyRequestsException": LLMThrottledError,
    "ServiceQuotaExceededException": LLMQuotaError,
    "ModelTimeoutException": LLMTimeoutError,
    "ReadTimeoutError": LLMTimeoutError,
    "ServiceUnavailableException": LLMUnavailableError,
    "InternalServerException": LLMUnavailableError,
    "ModelNotReadyException": LLMUnavailableError,
    "ModelErrorException": LLMUnavailableError,
    "AccessDeniedException": LLMAccessDeniedError,
    "ResourceNotFoundException": LLMModelNotFoundError,
    "ValidationException": LLMValidationError,
}


def map_bedrock_error(exc: BaseException, model_id: str | None = None) -> LLMError:
    """Translate a botocore ClientError / timeout into a typed LLMError (unknown -> non-retryable LLMError)."""
    code = ""
    resp: Any = getattr(exc, "response", None)
    if isinstance(resp, dict):
        code = str(resp.get("Error", {}).get("Code", ""))
    code = code or type(exc).__name__
    cls = _BY_CODE.get(code, LLMError)
    err = cls(f"{code}: {exc}", model_id=model_id)
    err.__cause__ = exc
    return err


def guardrail_intervened(response: dict[str, Any]) -> bool:
    """True when Converse reports the guardrail blocked or rewrote the output."""
    if response.get("stopReason") == "guardrail_intervened":
        return True
    g = (response.get("trace") or {}).get("guardrail") or {}
    return bool(g.get("action") == "GUARDRAIL_INTERVENED")
