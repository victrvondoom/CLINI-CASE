"""HIPAA Breach Detection Rule (§ 164.408) automation — async log signal
listener that publishes to SNS for the security-anomaly-report (SAR) pipeline.

§ 164.408 demands notification "without unreasonable delay." That bar is
operationally interpreted as:
  • Detection within 5 minutes
  • Customer notification within 60 days
  • HHS Secretary notification within 60 days (≥500 affected)

This module is the **detection** half. It listens for these signals:

  • signal_authz_denied_burst    — > N AuthzDenied within K seconds (potential
                                   reconnaissance)
  • signal_residency_violation   — any ResidencyViolation (active boundary breach)
  • signal_jwt_signature_mismatch — > N JWT signature failures within K seconds
                                   (token-forging attempt)
  • signal_phi_in_log            — log line contains PHI patterns (DOB, SSN, MRN)
                                   despite the phi_sanitizer
  • signal_cross_org_query       — any DB query that returned cross-tenant rows
                                   (RLS bypass attempt)

Each detection emits an event to SNS topic `clincase-security-anomalies` AND
writes a row to `security_anomalies` for the SOC team's review.

Pairs with: ops/architecture/HIPAA_BREACH_DETECTION.md
"""
from __future__ import annotations

import os
import re
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

import structlog

from app.db import db

log = structlog.get_logger()


_SNS_TOPIC_ARN = os.getenv("SECURITY_ANOMALY_SNS_TOPIC_ARN", "").strip()
_PHI_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),                  # SSN
    re.compile(r"\bMRN[:\s#-]*\d{6,}\b", re.IGNORECASE),   # MRN
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),                  # DOB-shaped (low-precision; review)
]


_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS security_anomalies (
    id                 BIGSERIAL PRIMARY KEY,
    detected_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    organization_id    TEXT,
    signal             TEXT NOT NULL,
    severity           TEXT NOT NULL CHECK (severity IN ('info','warn','high','critical')),
    payload            JSONB NOT NULL,
    sns_published      BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE INDEX IF NOT EXISTS idx_secanom_detected ON security_anomalies (detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_secanom_signal   ON security_anomalies (signal);
CREATE INDEX IF NOT EXISTS idx_secanom_org      ON security_anomalies (organization_id);
"""


async def ensure_schema() -> None:
    await db.execute(_SCHEMA_SQL)


# =============================================================================
# Sliding window for rate-based signals
# =============================================================================


@dataclass
class _Window:
    threshold: int
    window_s: float
    events: deque[float] = field(default_factory=deque)


_authz_denied_window = _Window(threshold=10, window_s=60)
_jwt_failure_window  = _Window(threshold=20, window_s=60)


async def _record_anomaly(
    *,
    signal: str,
    severity: str,
    payload: dict[str, Any],
    organization_id: str | None = None,
) -> None:
    """Insert into security_anomalies + best-effort SNS publish."""
    sns_ok = False
    if _SNS_TOPIC_ARN:
        try:
            import boto3  # type: ignore[import-not-found]
            client = boto3.client("sns")
            client.publish(
                TopicArn=_SNS_TOPIC_ARN,
                Subject=f"ClinCase security anomaly: {signal}",
                Message=__import__("json").dumps({
                    "signal": signal,
                    "severity": severity,
                    "organization_id": organization_id,
                    "payload": payload,
                    "ts": time.time(),
                }),
                MessageAttributes={
                    "severity": {"DataType": "String", "StringValue": severity},
                    "signal":   {"DataType": "String", "StringValue": signal},
                },
            )
            sns_ok = True
        except Exception as e:  # noqa: BLE001
            log.warning("breach_detector.sns.publish_failed", error=str(e))
    try:
        await db.execute(
            """
            INSERT INTO security_anomalies (organization_id, signal, severity, payload, sns_published)
            VALUES ($1, $2, $3, $4::jsonb, $5)
            """,
            organization_id,
            signal,
            severity,
            __import__("json").dumps(payload),
            sns_ok,
        )
    except Exception as e:  # noqa: BLE001
        log.error("breach_detector.persist_failed", error=str(e), signal=signal)
    log.info("breach_detector.signal", signal=signal, severity=severity, sns_ok=sns_ok)


# =============================================================================
# Public signals
# =============================================================================


async def signal_authz_denied(*, principal: str, action: str, resource: str, organization_id: str | None) -> None:
    now = time.time()
    w = _authz_denied_window
    w.events.append(now)
    while w.events and w.events[0] < now - w.window_s:
        w.events.popleft()
    if len(w.events) >= w.threshold:
        await _record_anomaly(
            signal="authz_denied_burst",
            severity="high",
            payload={
                "count": len(w.events),
                "window_seconds": w.window_s,
                "last_principal": principal,
                "last_action": action,
                "last_resource": resource,
            },
            organization_id=organization_id,
        )
        w.events.clear()


async def signal_residency_violation(*, organization_id: str, declared_region: str, attempted_region: str, resource: str) -> None:
    await _record_anomaly(
        signal="residency_violation",
        severity="critical",
        payload={
            "declared_region": declared_region,
            "attempted_region": attempted_region,
            "resource": resource,
        },
        organization_id=organization_id,
    )


async def signal_jwt_failure(*, reason: str) -> None:
    now = time.time()
    w = _jwt_failure_window
    w.events.append(now)
    while w.events and w.events[0] < now - w.window_s:
        w.events.popleft()
    if len(w.events) >= w.threshold:
        await _record_anomaly(
            signal="jwt_signature_mismatch_burst",
            severity="critical",
            payload={
                "count": len(w.events),
                "window_seconds": w.window_s,
                "reason": reason,
            },
        )
        w.events.clear()


async def scan_log_for_phi(*, line: str, context: dict[str, Any]) -> None:
    """Best-effort scan; called by a structlog processor in production."""
    matches: list[str] = []
    for pat in _PHI_PATTERNS:
        m = pat.search(line)
        if m:
            matches.append(m.group(0)[:4] + "***")
    if matches:
        await _record_anomaly(
            signal="phi_in_log",
            severity="critical",
            payload={"masked_matches": matches, "context": context},
        )


async def signal_cross_org_query(*, organization_id: str, principal: str, table: str, returned_rows: int) -> None:
    await _record_anomaly(
        signal="cross_org_query",
        severity="critical",
        payload={
            "principal": principal,
            "table": table,
            "returned_rows": returned_rows,
        },
        organization_id=organization_id,
    )


# =============================================================================
# Snapshot for /api/v1/security/anomalies
# =============================================================================


async def recent_anomalies(*, organization_id: str | None, limit: int = 100) -> list[dict[str, Any]]:
    if organization_id:
        rows = await db.fetch_ro(
            "SELECT * FROM security_anomalies WHERE organization_id = $1 "
            "ORDER BY detected_at DESC LIMIT $2",
            organization_id, limit,
        )
    else:
        rows = await db.fetch_ro(
            "SELECT * FROM security_anomalies ORDER BY detected_at DESC LIMIT $1",
            limit,
        )
    return [dict(r) for r in rows]
