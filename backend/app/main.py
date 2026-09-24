"""FastAPI application entry point."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db import db


def _configure_logging() -> None:
    logging.basicConfig(level=settings.LOG_LEVEL, format="%(message)s")
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(settings.LOG_LEVEL)
        ),
    )


_configure_logging()
log = structlog.get_logger()


async def _bootstrap_optional(label: str, coro_factory) -> None:
    """Run an OPTIONAL bootstrap step with consistent fail-soft logging.

    Optional steps are: schema migrations (idempotent — worker can re-run),
    observability hooks (OTEL exporters), and the Redis SSE backend wiring
    (in-process pub/sub is the safe fallback). Failure here MUST NOT crash
    the API. Critical bootstraps (DB connect, mandatory schemas) live
    OUTSIDE this helper and re-raise.

    By making the fail-soft contract explicit and named, code reviewers see
    intent rather than a sea of duplicated `try/except Exception: log.warning`
    blocks.
    """
    try:
        await coro_factory()
    except Exception as e:  # noqa: BLE001 — fail-soft is the documented contract
        log.warning(f"clincase.bootstrap.{label}.failed", error=str(e))


def _install_optional_sync(label: str, fn) -> None:
    """Synchronous variant of _bootstrap_optional (for OTEL + signal handlers)."""
    try:
        fn()
    except Exception as e:  # noqa: BLE001
        log.warning(f"clincase.bootstrap.{label}.failed", error=str(e))


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    log.info(
        "clincase.startup",
        llm_provider=settings.LLM_PROVIDER,
        environment=settings.ENVIRONMENT,
    )
    # DB connect — fail-soft so DB-less deployments (S3 policies API only,
    # public ECS demo without RDS, etc.) can still boot. Endpoints that need
    # DB will return 503 at request time when the pool is unavailable.
    db_disabled = "disabled" in (settings.DATABASE_URL or "")
    if db_disabled:
        log.warning("clincase.startup.db_skipped", reason="DATABASE_URL points to disabled host")
    else:
        try:
            await db.connect()
        except Exception as e:  # noqa: BLE001
            log.warning("clincase.startup.db_unavailable", error=str(e)[:200])
            db_disabled = True

    # OpenTelemetry — no-op when OTEL_EXPORTER_OTLP_ENDPOINT is unset.
    def _otel_setup():
        from app.observability.otel import setup_otel, instrument_fastapi
        setup_otel(service_name="clincase", service_version="0.1.0")
        instrument_fastapi(_app)
    _install_optional_sync("otel", _otel_setup)

    # Idempotent schema bootstraps. Each is safe to re-run; the worker
    # process also runs them. Failure here does NOT prevent boot.
    async def _outbox():
        from app.events.outbox import ensure_schema
        await ensure_schema()
    await _bootstrap_optional("outbox_schema", _outbox)

    async def _saga():
        from app.saga import ensure_schema
        await ensure_schema()
    await _bootstrap_optional("saga_schema", _saga)

    async def _dlq():
        from app.events.dlq import ensure_schema
        await ensure_schema()
    await _bootstrap_optional("dlq_schema", _dlq)

    async def _secanom():
        from app.security.breach_detector import ensure_schema
        await ensure_schema()
    await _bootstrap_optional("security_anomalies_schema", _secanom)

    def _shutdown_handlers():
        from app.graceful_shutdown import install_signal_handlers
        install_signal_handlers()
    _install_optional_sync("graceful_shutdown", _shutdown_handlers)

    # Round-13 batch (idempotent)
    for module_path, label in (
        ("app.api.idempotency_middleware", "idempotency_schema"),
        ("app.api.fhir_bulk",              "fhir_bulk_jobs_schema"),
        ("app.privacy.erasure",            "subject_redactions_schema"),
        ("app.privacy.tokenization",       "phi_vault_schema"),
        ("app.prompts_versioning",         "prompts_schema"),
    ):
        async def _ensure(mp=module_path):
            mod = __import__(mp, fromlist=["ensure_schema"])
            await mod.ensure_schema()
        await _bootstrap_optional(label, _ensure)

    async def _jobs_queue():
        from app.jobs import queue
        await queue.ensure_schema()
    await _bootstrap_optional("jobs_queue_schema", _jobs_queue)

    async def _quotas():
        from app.quotas import ensure_schema
        await ensure_schema()
    await _bootstrap_optional("quotas_schema", _quotas)

    async def _cache():
        from app.agents.framework.cache import ensure_schema
        await ensure_schema()
    await _bootstrap_optional("cache_schema", _cache)

    async def _gateway():
        from app.llm.gateway import ensure_schema
        await ensure_schema()
    await _bootstrap_optional("genai_gateway_schema", _gateway)

    # OncoTwin (digital-twin layer) — hash-chained prediction/HITL audit ledger.
    async def _oncotwin():
        from app.oncotwin.store import ensure_schema
        await ensure_schema()
    await _bootstrap_optional("oncotwin_audit_schema", _oncotwin)

    # Redis SSE pub/sub — in-process is the safe fallback for single-replica.
    # Multi-replica deploys MUST set REDIS_URL or live SSE traces fan-out
    # asymmetrically. We log loudly when this fails because in production
    # it's a degraded mode worth alerting on.
    if settings.REDIS_URL:
        async def _redis_backend():
            from app.streaming import use_redis_backend
            await use_redis_backend(settings.REDIS_URL)
        await _bootstrap_optional("redis_sse_backend", _redis_backend)

    # Seed demo admin/reviewer/coordinator if not present (idempotent).
    # Password is sourced from settings.DEMO_USER_PASSWORD (env-configurable).
    # The model_validator in app/config.py rejects boot if a non-dev environment
    # ships with the public demo password — see app/config.py:_enforce_production_secrets.
    try:
        from app.auth import hash_password

        _DEMO_USERS = (
            ("user_demoadmin",    "admin@aerofyta.health",       "Demo Administrator", "admin"),
            ("user_demoreviewer", "reviewer@aerofyta.health",    "Demo Reviewer",      "reviewer"),
            ("user_democoord",    "coordinator@aerofyta.health", "Demo Coordinator",   "coordinator"),
        )

        existing = await db.fetchval(
            "SELECT id FROM users WHERE email = $1", _DEMO_USERS[0][1],
        )
        if existing is None:
            _hashed_demo_password = hash_password(settings.DEMO_USER_PASSWORD)
            for user_id, email, full_name, role in _DEMO_USERS:
                await db.execute(
                    """INSERT INTO users (id, email, password_hash, full_name,
                                          organization_id, role)
                       VALUES ($1, $2, $3, $4, $5, $6)
                       ON CONFLICT (email) DO NOTHING""",
                    user_id, email, _hashed_demo_password,
                    full_name, "org_demo", role,
                )
            log.info("clincase.seed.demo_users_created", count=len(_DEMO_USERS))

        # Backfill any cases without an org_id (idempotent migration helper)
        await db.execute(
            "UPDATE cases SET organization_id = 'org_demo' WHERE organization_id IS NULL"
        )
    except Exception as e:  # noqa: BLE001
        # Demo seeding is non-critical: production deployments do not seed
        # demo users (real users come from the OIDC SSO flow). Fail-soft.
        log.warning("clincase.seed.failed", error=str(e))

    try:
        yield
    finally:
        try:
            from app.streaming import shutdown_backend
            await shutdown_backend()
        except Exception as e:  # noqa: BLE001
            log.warning("clincase.redis.shutdown_failed", error=str(e))
        await db.disconnect()
        log.info("clincase.shutdown")


app = FastAPI(
    title="ClinCase API",
    version="0.1.0",
    description="Provider-side prior-authorisation copilot for oncology",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Stamp X-API-Version + RFC 8594 Sunset/Deprecation headers on every response.
# Reads V1_SUNSET_DATE env at module import; safe no-op when unset.
from app.api.version_headers import VersionHeadersMiddleware  # noqa: E402
app.add_middleware(VersionHeadersMiddleware)

# Stamp X-ClinCase-Cell-Id on every authenticated response (round 11).
# Decodes JWT to resolve cell; no-op for anonymous traffic.
from app.api.cell_router_middleware import CellRouterMiddleware  # noqa: E402
app.add_middleware(CellRouterMiddleware)

# Per-tenant per-second + per-minute rate limiter (round 11).
# Skips healthz/metrics/login routes (those are protected at the WAF tier).
# Falls back to in-memory store; multi-replica deploys must configure REDIS_URL.
from app.api.rate_limit_middleware import RateLimitMiddleware  # noqa: E402
app.add_middleware(RateLimitMiddleware)

# Bind organization_id to a contextvar so the DB layer can SET LOCAL it
# for Postgres Row Level Security (round 12).
from app.api.tenant_context_middleware import TenantContextMiddleware  # noqa: E402
app.add_middleware(TenantContextMiddleware)

# Generalized Stripe-style Idempotency-Key on all write endpoints (round 13).
from app.api.idempotency_middleware import IdempotencyMiddleware  # noqa: E402
app.add_middleware(IdempotencyMiddleware)

# Gzip OncoTwin JSON (50–400 KB payloads); scoped so ClinCase SSE streams are never buffered.
from app.api.oncotwin_gzip_middleware import OncoTwinGZipMiddleware  # noqa: E402
app.add_middleware(OncoTwinGZipMiddleware)


@app.middleware("http")
async def request_id_middleware(request, call_next):
    """Propagate X-Request-Id header through every request.

    If client provided one, echo it back (lets a customer correlate their
    side's logs with ours). If not, mint one. The ID is also set on a
    structlog contextvar so every log line in this request carries it.
    """
    import uuid as _uuid
    rid = request.headers.get("x-request-id") or _uuid.uuid4().hex[:16]
    structlog.contextvars.bind_contextvars(request_id=rid)
    response = await call_next(request)
    response.headers["X-Request-Id"] = rid
    structlog.contextvars.unbind_contextvars("request_id")
    return response

# --- Routes ------------------------------------------------------------------
from app.api import (  # noqa: E402
    agents_manifest,
    appeals as appeals_api,
    architecture as architecture_api,
    auth,
    intake as intake_api,
    auth_oidc as auth_oidc_api,
    authz as authz_api,
    business_value as business_value_api,
    cases,
    compliance as compliance_api,
    compliance_controls as compliance_controls_api,
    demo,
    dlq as dlq_api,
    eval as eval_api,
    evidence_pack as evidence_pack_api,
    fhir_pas,
    finops as finops_api,
    foundry as foundry_api,
    healthz,
    jobs as jobs_api,
    kiro as kiro_api,
    llm_gateway as llm_gateway_api,
    llm_ping,
    metrics as metrics_api,
    ops as ops_api,
    quotas as quotas_api,
    rate_limits as rate_limits_api,
    residency as residency_api,
    responsible_ai as responsible_ai_api,
    sagas as sagas_api,
    security_anomalies as security_anomalies_api,
    stream,
    stream_completion as stream_completion_api,
    tenants as tenants_api,
    fhir_bulk as fhir_bulk_api,
    privacy as privacy_api,
    prompts as prompts_api,
    v2 as v2_api,
    policies as policies_api,
    oncology_stack,
    oncotwin as oncotwin_api,
    oncotwin_intel as oncotwin_intel_api,
)
from app.integrations.trizetto.router import router as trizetto_router  # noqa: E402
from app.mcp.server import router as mcp_router  # noqa: E402

app.include_router(healthz.router,         prefix="/api/v1")
app.include_router(llm_ping.router,        prefix="/api/v1")
app.include_router(auth.router,            prefix="/api/v1")
app.include_router(cases.router,           prefix="/api/v1")
app.include_router(appeals_api.router,     prefix="/api/v1")
app.include_router(intake_api.router,      prefix="/api/v1")
app.include_router(jobs_api.router,        prefix="/api/v1")
app.include_router(stream.router,          prefix="/api/v1")
app.include_router(demo.router,            prefix="/api/v1")
# /metrics is mounted at root (no /api/v1 prefix) per Prometheus convention
app.include_router(metrics_api.router)
app.include_router(eval_api.router,        prefix="/api/v1")
app.include_router(agents_manifest.router, prefix="/api/v1")
app.include_router(quotas_api.router,      prefix="/api/v1")
app.include_router(compliance_api.router,  prefix="/api/v1")
app.include_router(business_value_api.router, prefix="/api/v1")
app.include_router(kiro_api.router,        prefix="/api/v1")
app.include_router(trizetto_router,        prefix="/api/v1")
app.include_router(evidence_pack_api.router, prefix="/api/v1")
app.include_router(foundry_api.router,     prefix="/api/v1")
app.include_router(responsible_ai_api.router, prefix="/api/v1")
app.include_router(architecture_api.router, prefix="/api/v1")
app.include_router(llm_gateway_api.router, prefix="/api/v1")
app.include_router(ops_api.router, prefix="/api/v1")
app.include_router(residency_api.router, prefix="/api/v1")
app.include_router(rate_limits_api.router, prefix="/api/v1")
app.include_router(authz_api.router, prefix="/api/v1")
app.include_router(auth_oidc_api.router, prefix="/api/v1")
# Round-12 routers
app.include_router(sagas_api.router, prefix="/api/v1")
app.include_router(dlq_api.router, prefix="/api/v1")
app.include_router(security_anomalies_api.router, prefix="/api/v1")
app.include_router(compliance_controls_api.router, prefix="/api/v1")
app.include_router(finops_api.router, prefix="/api/v1")
app.include_router(stream_completion_api.router, prefix="/api/v1")
# Round-13 routers
app.include_router(tenants_api.router, prefix="/api/v1")
app.include_router(privacy_api.router, prefix="/api/v1")
app.include_router(prompts_api.router, prefix="/api/v1")
app.include_router(policies_api.router, prefix="/api/v1")
app.include_router(oncology_stack.router, prefix="/api/v1")
# OncoTwin — dynamic digital-twin layer (additive; hands off into the cases API above)
app.include_router(oncotwin_api.router, prefix="/api/v1")
app.include_router(oncotwin_intel_api.router, prefix="/api/v1")    # OncoTwin 2.0 (additive)
# fhir_bulk router carries its own /fhir prefix
app.include_router(fhir_bulk_api.router)

# Da Vinci PAS / CMS-0057-F § IV.A endpoint mounted at root /fhir/* (no /api/v1 prefix)
# so it matches the Da Vinci PAS Implementation Guide URL convention.
app.include_router(fhir_pas.router)

# MCP server (JSON-RPC 2.0 over HTTP) at /mcp — Cognizant TriZetto AI Gateway-compatible.
app.include_router(mcp_router)

# /api/v2 scaffold — proof-of-life of the deprecation pipeline.
# v2 router carries its own /api/v2 prefix; no extra prefix here.
app.include_router(v2_api.router)
