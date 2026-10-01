"""Case / run / trace identity — pure, import-safe (no database, no framework imports).

ONE CASE → MANY RUNS → EACH ARTIFACT TRACEABLE.

* ``case_intelligence_id`` (``CI-…``): stable per (organisation, case); the same for every run of the case.
* ``run_id`` (``run_…``): one per execution attempt of the case — an initial run, a rerun, or a human-review
  resume. Every artifact a run produces (agent rows, LLM invocations, decisions, appeals, reviewer actions,
  SSE events) carries it, so a rerun can never be confused with the original execution.
* ``trace_id``: 32-hex W3C trace id for the run (the active OpenTelemetry trace when one exists).
* ``job_attempt``: the queue's retry counter for the job that executes the run (a crash-retry re-executes the
  DAG under the *same* run id, so rows are further separated by this counter).
"""

from __future__ import annotations

import base64
import hashlib
import secrets
import uuid
from dataclasses import dataclass
from typing import Any

RUN_TRIGGERS = ("initial", "rerun", "resume")
RUN_STATUSES = ("queued", "running", "paused", "completed", "failed", "cancelled", "superseded")

_CASE_NS = "clincase:case-intelligence:v1"


def case_intelligence_id(organization_id: str, case_id: str) -> str:
    """`CI-XXXXXXXXXXXX` — 60 bits of a namespaced SHA-256 over (organisation, case)."""
    digest = hashlib.sha256(f"{_CASE_NS}|{organization_id}|{case_id}".encode()).digest()
    return f"CI-{base32(digest, 12)}"


def base32(digest: bytes, n: int) -> str:
    return base64.b32encode(digest).decode().rstrip("=")[:n]


def new_run_id() -> str:
    return f"run_{uuid.uuid4().hex[:16]}"


def new_trace_id() -> str:
    return secrets.token_hex(16)


@dataclass(frozen=True)
class RunIdentity:
    case_id: str
    organization_id: str
    case_intelligence_id: str
    run_id: str
    attempt_no: int
    trigger: str
    trace_id: str
    job_attempt: int = 1
    parent_run_id: str | None = None

    def with_job_attempt(self, job_attempt: int) -> RunIdentity:
        return RunIdentity(**{**self.__dict__, "job_attempt": max(1, int(job_attempt))})

    def to_payload(self) -> dict[str, Any]:
        """JSON form carried in the queue payload."""
        return dict(self.__dict__)

    @classmethod
    def from_payload(cls, data: dict[str, Any] | None) -> RunIdentity | None:
        """Parse the payload form; None (not an exception) for a missing/legacy/malformed value."""
        if not isinstance(data, dict):
            return None
        try:
            return cls(
                case_id=str(data["case_id"]),
                organization_id=str(data["organization_id"]),
                case_intelligence_id=str(data["case_intelligence_id"]),
                run_id=str(data["run_id"]),
                attempt_no=int(data["attempt_no"]),
                trigger=str(data["trigger"]),
                trace_id=str(data["trace_id"]),
                job_attempt=int(data.get("job_attempt") or 1),
                parent_run_id=data.get("parent_run_id"),
            )
        except (KeyError, TypeError, ValueError):
            return None

    def event_fields(self) -> dict[str, Any]:
        """Correlation fields added to every SSE event of the run."""
        return {
            "case_intelligence_id": self.case_intelligence_id,
            "run_id": self.run_id,
            "trace_id": self.trace_id,
        }

    def baggage(self) -> dict[str, str]:
        return {
            "case_id": self.case_id,
            "case_intelligence_id": self.case_intelligence_id,
            "run_id": self.run_id,
            "trace_id": self.trace_id,
            "job_attempt": str(self.job_attempt),
        }
