"""Stable identifiers that follow a case through agents, model calls, retrieval and review.

The case id is canonical in `app.identity` (and stored on `cases` / every run artifact); it is re-exported
here for the twin. Evidence ids stay derived: they identify a cited item within a case.
"""

from __future__ import annotations

import hashlib

from app.identity import base32, case_intelligence_id

__all__ = ["case_intelligence_id", "evidence_id"]

_EVIDENCE_NS = "clincase:evidence:v1"


def evidence_id(case_id: str, kind: str, pointer: str) -> str:
    """`EV-XXXXXXXX` — identifies one cited piece of evidence within a case."""
    digest = hashlib.sha256(f"{_EVIDENCE_NS}|{case_id}|{kind}|{pointer}".encode()).digest()
    return f"EV-{base32(digest, 8)}"
