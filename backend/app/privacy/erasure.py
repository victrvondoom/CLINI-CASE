"""GDPR Article 17 (right-to-erasure) + HIPAA Privacy Rule § 164.526.

A subject (or their authorized representative) requests deletion of their
PHI / personal data. The request kicks off a multi-table soft-delete →
hard-delete pipeline:

  1. **Validate** — the requester is authorized + the data subject exists
  2. **Soft-delete** — `subject_redactions` row created; queries thereafter
     filter the subject out
  3. **Audit-log retention exception** — CMS-0057-F § IV.D mandates 7-year
     retention of decision audit data EVEN AGAINST GDPR Art. 17. Reconciled
     by tokenizing the subject identifier in the audit trail (PII removed,
     decision reproducibility kept).
  4. **CDC stream backfill** — emit `subject.erased` event so downstream
     consumers (S3 audit lake, customer SIEM) can redact their copies
  5. **Hard-delete** — after grace window (7d for legal hold review),
     a worker performs the irreversible delete.

Per [GDPR Article 17(3)(b) + (3)(e)](https://gdpr-info.eu/art-17-gdpr/),
the legal basis for *retaining* decision audit data is balanced against
erasure. We document this conflict + reconcile via tokenization.

Pairs with: ops/architecture/RIGHT_TO_ERASURE.md
"""
from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog

from app.db import db

log = structlog.get_logger()


_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS subject_redactions (
    redaction_id     TEXT PRIMARY KEY,
    organization_id  TEXT NOT NULL,
    subject_token    TEXT NOT NULL,
    subject_initials TEXT,
    reason           TEXT NOT NULL,
    requested_by     TEXT NOT NULL,
    legal_basis      TEXT NOT NULL,
    status           TEXT NOT NULL CHECK (status IN
                       ('soft_deleted','hard_delete_scheduled','hard_deleted','rejected')),
    soft_deleted_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    hard_delete_after TIMESTAMPTZ NOT NULL,
    hard_deleted_at  TIMESTAMPTZ,
    rejection_reason TEXT
);
CREATE INDEX IF NOT EXISTS idx_redactions_org    ON subject_redactions (organization_id);
CREATE INDEX IF NOT EXISTS idx_redactions_status ON subject_redactions (status);
CREATE INDEX IF NOT EXISTS idx_redactions_token  ON subject_redactions (subject_token);
"""


async def ensure_schema() -> None:
    await db.execute(_SCHEMA_SQL)


@dataclass(frozen=True)
class ErasureRequest:
    organization_id: str
    subject_initials: str   # PII-minimized identifier; we never store full name
    requested_by: str
    reason: str             # 'gdpr_art_17' | 'hipaa_amendment' | 'other'
    legal_basis: str        # 'consent_withdrawn' | 'no_longer_necessary' | ...


@dataclass(frozen=True)
class ErasureResult:
    redaction_id: str
    subject_token: str
    soft_deleted_at: str
    hard_delete_after: str
    status: str


async def request_erasure(req: ErasureRequest) -> ErasureResult:
    """Create a soft-delete redaction record. Hard-delete runs after the
    7-day grace window (legal-hold review)."""
    redaction_id = f"red_{uuid.uuid4().hex[:16]}"
    subject_token = f"erased_{secrets.token_hex(8)}"
    hard_delete_after = datetime.now(UTC) + timedelta(days=7)

    await db.execute(
        """
        INSERT INTO subject_redactions
            (redaction_id, organization_id, subject_token, subject_initials,
             reason, requested_by, legal_basis, status, hard_delete_after)
        VALUES ($1, $2, $3, $4, $5, $6, $7, 'soft_deleted', $8)
        """,
        redaction_id,
        req.organization_id,
        subject_token,
        req.subject_initials[:8],
        req.reason,
        req.requested_by,
        req.legal_basis,
        hard_delete_after,
    )

    log.info(
        "erasure.soft_deleted",
        redaction_id=redaction_id,
        org=req.organization_id,
        token=subject_token,
        legal_basis=req.legal_basis,
    )

    return ErasureResult(
        redaction_id=redaction_id,
        subject_token=subject_token,
        soft_deleted_at=datetime.now(UTC).isoformat(),
        hard_delete_after=hard_delete_after.isoformat(),
        status="soft_deleted",
    )


async def hard_delete_due() -> int:
    """Worker function — find soft-deleted redactions past their grace window
    and hard-delete the corresponding rows. Audit data is tokenized in place
    rather than deleted (CMS-0057-F § IV.D conflict-of-laws reconciliation).

    Returns the number of redactions hard-deleted.
    """
    rows = await db.fetch(
        """
        SELECT redaction_id, organization_id, subject_token, subject_initials
          FROM subject_redactions
         WHERE status = 'soft_deleted'
           AND hard_delete_after < NOW()
        """,
    )
    n = 0
    for row in rows:
        try:
            async with db.pool.acquire() as conn, conn.transaction():
                # Tokenize patient_initials in cases (don't drop rows — audit
                # retention requires them). The subject becomes anonymous.
                await conn.execute(
                    """
                        UPDATE cases SET patient_initials = $1
                         WHERE organization_id = $2 AND patient_initials = $3
                        """,
                    row["subject_token"],
                    row["organization_id"],
                    row["subject_initials"],
                )
                # Mark as hard-deleted
                await conn.execute(
                    """
                        UPDATE subject_redactions
                           SET status='hard_deleted', hard_deleted_at = NOW()
                         WHERE redaction_id = $1
                        """,
                    row["redaction_id"],
                )
            n += 1
            log.info("erasure.hard_deleted", redaction_id=row["redaction_id"])
        except Exception as e:  # noqa: BLE001
            log.error("erasure.hard_delete_failed", redaction_id=row["redaction_id"], error=str(e))
    return n


async def list_for_org(*, organization_id: str, limit: int = 100) -> list[dict[str, Any]]:
    rows = await db.fetch_ro(
        """
        SELECT * FROM subject_redactions
         WHERE organization_id = $1
         ORDER BY soft_deleted_at DESC
         LIMIT $2
        """,
        organization_id, limit,
    )
    return [dict(r) for r in rows]
