"""Typed errors for the Document Intake layer.

Each error has a stable `code` (machine-readable, shows up in audit logs +
`agent_runs`) and a `status_code` (HTTP mapping for the API layer). This
lets the FastAPI router translate to clean error responses without leaking
internals, while clients can branch on the `code`.

Design follows AAOSA bounded responsibility: every failure mode is a
specific class, not a generic Exception. Audit + monitoring tools can
group on `code` for cohort analysis.
"""
from __future__ import annotations


class IntakeError(Exception):
    """Base class for all Document Intake errors."""

    code: str = "intake.unknown"
    status_code: int = 500
    safe_to_show_user: bool = False

    def __init__(self, message: str, *, detail: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail or {}

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "message": self.message if self.safe_to_show_user else (
                "Document intake failed. The case has been routed to the "
                "Reviewer queue."
            ),
            "detail": self.detail if self.safe_to_show_user else {},
        }


# ---------------------------------------------------------------------------
# Client / upload errors (4xx) — caller's fault, message is user-safe
# ---------------------------------------------------------------------------
class InvalidDocumentError(IntakeError):
    """The uploaded bytes are not a valid image/PDF or fail format checks."""

    code = "intake.invalid_document"
    status_code = 400
    safe_to_show_user = True


class UnsupportedMediaTypeError(IntakeError):
    """MIME type / magic bytes don't match an accepted document kind."""

    code = "intake.unsupported_media_type"
    status_code = 415
    safe_to_show_user = True


class DocumentTooLargeError(IntakeError):
    """Upload exceeds the size cap (default 8 MB)."""

    code = "intake.document_too_large"
    status_code = 413
    safe_to_show_user = True


class DecompressionBombError(IntakeError):
    """Image dimensions or pixel count exceed safety thresholds."""

    code = "intake.decompression_bomb"
    status_code = 422
    safe_to_show_user = True


# ---------------------------------------------------------------------------
# Engine / pipeline errors (5xx) — server-side, generic message to client
# ---------------------------------------------------------------------------
class EngineUnavailableError(IntakeError):
    """No OCR engine in the configured fallback chain succeeded."""

    code = "intake.engine_unavailable"
    status_code = 503


class EngineTimeoutError(IntakeError):
    """The selected OCR engine did not return within the deadline."""

    code = "intake.engine_timeout"
    status_code = 504


class EngineQuotaExceededError(IntakeError):
    """A hard rate-limit was hit upstream (Bedrock throttling, Textract quota)."""

    code = "intake.engine_quota_exceeded"
    status_code = 429


class StageFailedError(IntakeError):
    """A pipeline stage raised an unexpected exception."""

    code = "intake.stage_failed"
    status_code = 500


# ---------------------------------------------------------------------------
# Soft-fail (still 200, but flagged) — these surface as IntakeResult.risk_flags
# rather than raising; included here so observability can match on the same
# vocabulary across HTTP errors and audit-flagged successes.
# ---------------------------------------------------------------------------
SOFT_FLAG_LOW_CONFIDENCE = "low-evidence-from-intake"
SOFT_FLAG_MISSING_BINDING = "missing-required-field"
SOFT_FLAG_LOW_QUALITY = "low-quality-scan"
SOFT_FLAG_INTAKE_FAILED = "intake-failed"
SOFT_FLAG_ENGINE_FALLBACK = "engine-fallback-used"
