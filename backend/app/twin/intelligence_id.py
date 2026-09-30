"""Stable identifiers that follow a case through agents, model calls, retrieval and review.

Both IDs are *derived*, not stored: anything that knows the organisation and case id
computes the same value, so they can be attached to logs, spans and SSE events without a
schema change, and a stored record can always be re-verified against them.
"""

from __future__ import annotations

import base64
import hashlib

_CASE_NS = "clincase:case-intelligence:v1"
_EVIDENCE_NS = "clincase:evidence:v1"


def _b32(digest: bytes, n: int) -> str:
    return base64.b32encode(digest).decode().rstrip("=")[:n]


def case_intelligence_id(organization_id: str, case_id: str) -> str:
    """`CI-XXXXXXXXXXXX` — 60 bits of a namespaced SHA-256 over (organisation, case)."""
    digest = hashlib.sha256(f"{_CASE_NS}|{organization_id}|{case_id}".encode()).digest()
    return f"CI-{_b32(digest, 12)}"


def evidence_id(case_id: str, kind: str, pointer: str) -> str:
    """`EV-XXXXXXXX` — identifies one cited piece of evidence within a case."""
    digest = hashlib.sha256(f"{_EVIDENCE_NS}|{case_id}|{kind}|{pointer}".encode()).digest()
    return f"EV-{_b32(digest, 8)}"
