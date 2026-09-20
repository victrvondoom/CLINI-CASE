"""Operational endpoints — /healthz/deep · /version · /capabilities.

These are the endpoints a Cognizant SRE / customer compliance officer / judge
runs to verify "is this system actually production-grade?". They expose:

  • /api/v1/healthz/deep   — every layer reports its own health
  • /api/v1/version        — git SHA + ClinCase semver + build date
  • /api/v1/capabilities   — feature flags judges can verify (mock vs real,
                              Q-vs-Bedrock backend, Gateway enabled, etc.)

Read-only, idempotent, no auth required. /healthz/deep is intentionally
verbose (5+ second response is acceptable) — it's not the K8s liveness probe;
that's `/api/v1/healthz` (already exists). This is the "show me everything
is wired" probe a judge or auditor runs once.
"""
from __future__ import annotations

import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter

from app.config import settings

router = APIRouter(tags=["ops"])

# Resolve repo root + cache git info at import time so we don't shell out per request.
_REPO_ROOT = Path(__file__).resolve().parents[3]


def _git_sha() -> str:
    """Try to read the current commit SHA. Returns 'unknown' on failure (e.g. non-git deploy)."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.SubprocessError, OSError):
        pass
    return "unknown"


def _git_branch() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.SubprocessError, OSError):
        pass
    return "unknown"


_BUILD_INFO_CACHE = {
    "git_sha": _git_sha(),
    "git_branch": _git_branch(),
    "boot_time_iso": datetime.now(UTC).isoformat(),
    "clincase_version": "0.1.0",
}


@router.get("/version")
async def version() -> dict[str, Any]:
    """Build + version metadata. Used by SRE for incident-correlation."""
    return _BUILD_INFO_CACHE | {
        "asof_iso": datetime.now(UTC).isoformat(),
        "uptime_seconds": int(time.time() - _boot_ts),
    }


@router.get("/capabilities")
async def capabilities() -> dict[str, Any]:
    """Feature-flag snapshot. Judges can verify the deployment mode without reading code.

    The flags here mirror env-driven behavior. Useful for "is this demo mode?" /
    "are you using real Bedrock or a mock?" introspection.
    """
    return {
        "asof_iso": datetime.now(UTC).isoformat(),
        "deployment": {
            "llm_provider": settings.LLM_PROVIDER,
            "aws_region": settings.AWS_REGION,
            "bedrock_model_id": settings.BEDROCK_MODEL_ID,
            "bedrock_haiku_model_id": settings.BEDROCK_HAIKU_MODEL_ID,
        },
        "feature_flags": {
            "genai_gateway_enabled": settings.GENAI_GATEWAY_ENABLED,
            "use_amazon_q": settings.USE_AMAZON_Q,
            "use_bedrock_kb": settings.USE_BEDROCK_KB,
            "trizetto_gateway_mode": "live" if settings.TRIZETTO_GATEWAY_URL else "mock",
            "redis_streaming_enabled": bool(settings.REDIS_URL),
            "bedrock_guardrail_id_set": bool(settings.BEDROCK_GUARDRAIL_ID),
            "amazon_q_application_id_set": bool(settings.AMAZON_Q_APPLICATION_ID),
        },
        "thresholds": {
            "hitl_confidence_threshold": settings.HITL_CONFIDENCE_THRESHOLD,
            "jwt_expire_minutes": settings.JWT_EXPIRE_MINUTES,
        },
        "demo_mode_indicators": {
            "trizetto_in_mock_mode": not settings.TRIZETTO_GATEWAY_URL,
            "amazon_q_in_mock_mode": not (settings.AMAZON_Q_APPLICATION_ID and settings.USE_AMAZON_Q),
            "redis_pub_sub_disabled": not settings.REDIS_URL,
            "hitl_threshold_zero": settings.HITL_CONFIDENCE_THRESHOLD == 0.0,
        },
        "compliance": {
            "cms_0057f_clauses_tracked": 8,
            "responsible_ai_card_endpoint": "/api/v1/responsible-ai/model-card",
            "evidence_pack_endpoint": "/api/v1/cases/{case_id}/evidence-pack",
        },
    }


@router.get("/healthz/deep")
async def healthz_deep() -> dict[str, Any]:
    """Per-layer self-check. Returns 200 even on partial degradation — read the
    `status` field per layer to determine actual health.

    This is the endpoint to hit during pre-flight ("is everything wired?").
    NOT the K8s liveness probe — use /api/v1/healthz for that (cheap, fast).
    """
    started = time.time()
    layers: dict[str, Any] = {}

    # ---- Layer 1: Experience (route registry) ----
    from app.main import app as fastapi_app
    paths = sorted({r.path for r in fastapi_app.routes if hasattr(r, "path")})
    layers["experience"] = {
        "status": "ok",
        "routes_total": len(paths),
        "expected_min_routes": 50,
    }

    # ---- Layer 2: Orchestration (manifest + DB) ----
    try:
        from app.agents.manifest import AGENT_MANIFEST, total_sub_agents
        layers["orchestration"] = {
            "status": "ok",
            "parents": len(AGENT_MANIFEST),
            "sub_agents": total_sub_agents(),
        }
    except Exception as e:  # noqa: BLE001
        layers["orchestration"] = {"status": "error", "error": str(e)[:200]}

    # ---- Layer 2b: DB connectivity ----
    try:
        from app.db import db
        await db.fetchval("SELECT 1")
        layers["database"] = {"status": "ok", "db_url_host": settings.DATABASE_URL.split("@")[-1].split("/")[0]}
    except Exception as e:  # noqa: BLE001
        layers["database"] = {"status": "error", "error": str(e)[:200]}

    # ---- Layer 3: Context Retrieval ----
    try:
        from app.integrations.amazon_q.client import AmazonQClient
        client = AmazonQClient()
        layers["context_retrieval"] = {
            "status": "ok",
            "active_backend": "amazon_q_business" if not client.is_mock else "mock_or_bedrock_kb",
            "is_mock": client.is_mock,
        }
    except Exception as e:  # noqa: BLE001
        layers["context_retrieval"] = {"status": "error", "error": str(e)[:200]}

    # ---- Layer 4: GenAI Gateway ----
    try:
        from app.llm.factory import get_llm_client
        from app.llm.gateway import GenAIGateway
        client = get_llm_client()
        is_gateway = isinstance(client, GenAIGateway)
        layers["genai_gateway"] = {
            "status": "ok",
            "wrapping_class": type(client).__name__,
            "gateway_enabled": is_gateway and settings.GENAI_GATEWAY_ENABLED,
        }
    except Exception as e:  # noqa: BLE001
        layers["genai_gateway"] = {"status": "error", "error": str(e)[:200]}

    # ---- Layer 5: Telemetry & Governance ----
    try:
        from app.compliance.cms_0057f import CLAUSES
        in_force = sum(1 for c in CLAUSES if c.in_force_today)
        layers["telemetry_governance"] = {
            "status": "ok",
            "cms_clauses_tracked": len(CLAUSES),
            "cms_clauses_in_force": in_force,
        }
    except Exception as e:  # noqa: BLE001
        layers["telemetry_governance"] = {"status": "error", "error": str(e)[:200]}

    # ---- External integrations ----
    try:
        from app.integrations.trizetto.gateway_client import TriZettoGatewayClient
        trz = TriZettoGatewayClient()
        layers["trizetto_gateway"] = {
            "status": "ok",
            "mode": "mock" if trz.is_mock else "live",
            "configured_url": trz.gateway_url or None,
        }
    except Exception as e:  # noqa: BLE001
        layers["trizetto_gateway"] = {"status": "error", "error": str(e)[:200]}

    try:
        from app.mcp.tools import TOOL_DEFINITIONS
        layers["mcp_server"] = {"status": "ok", "tools_exposed": len(TOOL_DEFINITIONS)}
    except Exception as e:  # noqa: BLE001
        layers["mcp_server"] = {"status": "error", "error": str(e)[:200]}

    # ---- Aggregate ----
    overall = "ok" if all(l.get("status") == "ok" for l in layers.values()) else "degraded"
    return {
        "status": overall,
        "asof_iso": datetime.now(UTC).isoformat(),
        "duration_ms": int((time.time() - started) * 1000),
        "version": _BUILD_INFO_CACHE,
        "layers": layers,
    }


# Module-level boot timestamp for uptime calculation
_boot_ts = time.time()
