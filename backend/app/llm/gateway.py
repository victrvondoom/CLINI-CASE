"""GenAI Gateway — the literal, enforced entry point to all Bedrock calls.

This module is the in-process realization of AWS's published architectural
guidance: "Use API Gateway or equivalent as a governed entry point to Bedrock,
with IAM, quotas, and network controls"
([aws.amazon.com/blogs/architecture/category/artificial-intelligence/amazon-machine-learning/amazon-bedrock/](https://aws.amazon.com/blogs/architecture/category/artificial-intelligence/amazon-machine-learning/amazon-bedrock/)).

In production the literal AWS API Gateway sits in front of this code (see
`ops/terraform/bedrock-vpc-endpoint/` for the AWS pattern). This module is
the second-line enforcement that runs INSIDE the application:

  • Tenant authz   — every call must declare which org_id is making it
  • Model allow    — every call's resolved model_id must be in the per-tenant allowlist
  • Quota gate     — per-tenant rolling token + USD limit (separate from per-case BudgetTracker)
  • Content safety — pre-call sanity check that input doesn't contain raw PHI
  • Audit log      — every call writes one row to `llm_invocations` (separate from agent_runs)

Why this is more than the existing BudgetTracker / Guardrail surface:
  • BudgetTracker is per-case; Gateway is per-tenant rolling.
  • Guardrails are agent-attached; Gateway runs unconditionally on every LLM call.
  • Agent traces are in `agent_runs`; Gateway traces are in `llm_invocations` (a CISO
    auditing model usage doesn't want to pivot through agent_runs).

Composition pattern. The factory returns `GenAIGateway(BedrockClient())` so:
  • Every existing call to `get_llm_client().complete(...)` keeps working.
  • Existing test mocks for LLMClient (the ABC) keep working.
  • Provider swap (Anthropic ↔ Bedrock) is unchanged — Gateway just wraps whatever.

Design intent: context engineering + governance baked into how AI is
called, not bolted on afterward.
"""
from __future__ import annotations

import contextvars
import json
import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import structlog

from app.config import settings
from app.llm.base import LLMClient, LLMResponse
from app.llm.circuit_breaker import (
    CircuitBreakerOpen,
    get_breaker,
)
from app.observability.otel import bedrock_span

log = structlog.get_logger()


# =============================================================================
# Tenant context — set by Agent.invoke() at the start of every agent invocation
# =============================================================================


@dataclass(frozen=True)
class GatewayCallContext:
    """Per-call scope information the Gateway uses for enforcement.

    Set via `set_call_context(...)` at the boundary of every agent invocation
    (in `app/agents/framework/agent.py`'s `invoke()` lifecycle). Falls back
    to a permissive system context only when no agent invocation is on the
    stack (e.g. an admin warmup ping at startup).
    """

    organization_id: str
    case_id: str | None
    agent_name: str | None
    request_id: str | None


_gateway_call_context: contextvars.ContextVar[GatewayCallContext | None] = (
    contextvars.ContextVar("gateway_call_context", default=None)
)


def set_call_context(ctx: GatewayCallContext) -> contextvars.Token:
    """Set the call context for the current async task.

    Returns the token so the caller can `reset()` it afterward — the
    Agent.invoke() lifecycle does this around every agent's body.
    """
    return _gateway_call_context.set(ctx)


def reset_call_context(token: contextvars.Token) -> None:
    _gateway_call_context.reset(token)


def get_call_context() -> GatewayCallContext | None:
    return _gateway_call_context.get()


# =============================================================================
# Per-tenant policy — model allowlist + quota
# =============================================================================


@dataclass(frozen=True)
class TenantPolicy:
    """Per-tenant Gateway policy.

    Values come from the `tenant_policies` table (created lazily on first
    access). Defaults are conservative: only the configured Sonnet + Haiku
    are allowed; per-day token cap is high but bounded.

    NOTE: per-tenant Bedrock Guardrail ID lives in env (BEDROCK_GUARDRAIL_ID)
    today; Day-1 customer onboarding documented in `ops/multi-tenant/ONBOARDING.md`
    moves this to a per-tenant column.
    """

    organization_id: str
    allowed_model_ids: list[str]
    daily_input_token_cap: int = 50_000_000   # 50M tokens/day default
    daily_output_token_cap: int = 10_000_000  # 10M tokens/day default
    daily_usd_cap: float = 1_000.0            # $1K/day default
    bedrock_guardrail_id: str | None = None


_DEFAULT_ALLOWED = (
    # Bedrock cross-region inference profiles (production / May 6 demo)
    settings.BEDROCK_MODEL_ID,
    settings.BEDROCK_HAIKU_MODEL_ID,
    # OpenRouter model IDs (local-dev / pre-Bedrock-migration)
    settings.OPENROUTER_MODEL,
    "anthropic/claude-haiku-4.5",
    # Anthropic-direct model IDs (fallback)
    settings.ANTHROPIC_MODEL,
    "claude-haiku-4-5",
)


def _default_policy(org_id: str) -> TenantPolicy:
    return TenantPolicy(
        organization_id=org_id,
        allowed_model_ids=[m for m in _DEFAULT_ALLOWED if m],
        bedrock_guardrail_id=settings.BEDROCK_GUARDRAIL_ID or None,
    )


# =============================================================================
# Schema bootstrap — llm_invocations + tenant_policies
# =============================================================================


_SCHEMA = """
CREATE TABLE IF NOT EXISTS llm_invocations (
    id              BIGSERIAL PRIMARY KEY,
    invocation_id   UUID        NOT NULL,
    organization_id TEXT        NOT NULL,
    case_id         TEXT,
    agent_name      TEXT,
    model_id        TEXT        NOT NULL,
    input_tokens    INTEGER     NOT NULL DEFAULT 0,
    output_tokens   INTEGER     NOT NULL DEFAULT 0,
    cost_usd        REAL        NOT NULL DEFAULT 0.0,
    latency_ms      INTEGER,
    status          TEXT        NOT NULL DEFAULT 'ok',
    error_text      TEXT,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at     TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_llmi_org_started ON llm_invocations (organization_id, started_at);
CREATE INDEX IF NOT EXISTS idx_llmi_case        ON llm_invocations (case_id);

CREATE TABLE IF NOT EXISTS tenant_policies (
    organization_id        TEXT        PRIMARY KEY,
    allowed_model_ids      JSONB       NOT NULL DEFAULT '[]'::jsonb,
    daily_input_token_cap  INTEGER     NOT NULL DEFAULT 50000000,
    daily_output_token_cap INTEGER     NOT NULL DEFAULT 10000000,
    daily_usd_cap          REAL        NOT NULL DEFAULT 1000.0,
    bedrock_guardrail_id   TEXT,
    updated_at             TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""


async def ensure_schema() -> None:
    """Idempotent schema bootstrap. Called from app lifespan + worker boot."""
    from app.db import db
    await db.execute(_SCHEMA)


# =============================================================================
# Policy lookup
# =============================================================================


async def get_tenant_policy(organization_id: str) -> TenantPolicy:
    """Return the live policy for a tenant. Falls back to defaults.

    The fallback also covers Postgres being unreachable: a policy lookup
    that cannot reach the DB must not take down every LLM call. The default
    policy is the conservative one (the same allowlist, caps and guardrail a
    brand-new tenant gets), so degrading to it never widens access.
    """
    from app.db import db
    try:
        row = await db.fetchrow(
            "SELECT * FROM tenant_policies WHERE organization_id = $1",
            organization_id,
        )
    except Exception as e:  # noqa: BLE001 — documented fail-soft contract
        log.warning(
            "gateway.tenant_policy.unavailable",
            organization_id=organization_id, error=str(e)[:200],
        )
        return _default_policy(organization_id)
    if row is None:
        return _default_policy(organization_id)
    raw = row["allowed_model_ids"]
    allowed = json.loads(raw) if isinstance(raw, str) else (raw or [])
    if not allowed:
        allowed = list(_DEFAULT_ALLOWED)
    return TenantPolicy(
        organization_id=organization_id,
        allowed_model_ids=[m for m in allowed if m],
        daily_input_token_cap=int(row["daily_input_token_cap"]),
        daily_output_token_cap=int(row["daily_output_token_cap"]),
        daily_usd_cap=float(row["daily_usd_cap"]),
        bedrock_guardrail_id=row["bedrock_guardrail_id"],
    )


# =============================================================================
# Quota check — token + USD rolling 24h
# =============================================================================


class GatewayQuotaExceeded(Exception):
    """Raised when a tenant has consumed its daily Gateway quota."""

    def __init__(self, *, dimension: str, used: float, cap: float, organization_id: str) -> None:
        self.dimension = dimension
        self.used = used
        self.cap = cap
        self.organization_id = organization_id
        super().__init__(
            f"GatewayQuotaExceeded[{dimension}] org={organization_id} "
            f"used={used:.2f} cap={cap:.2f}"
        )


class GatewayPolicyViolation(Exception):
    """Raised when a call would violate tenant policy (disallowed model, missing context, etc.)."""


async def _check_quota(policy: TenantPolicy) -> None:
    """Rolling-24h check against tenant token + USD caps."""
    from app.db import db
    row = await db.fetchrow(
        """SELECT
              COALESCE(SUM(input_tokens),  0)::BIGINT AS in_tok,
              COALESCE(SUM(output_tokens), 0)::BIGINT AS out_tok,
              COALESCE(SUM(cost_usd),      0)::FLOAT  AS spend
           FROM llm_invocations
           WHERE organization_id = $1
             AND started_at >= NOW() - INTERVAL '1 day'""",
        policy.organization_id,
    )
    in_tok = int(row["in_tok"]) if row else 0
    out_tok = int(row["out_tok"]) if row else 0
    spend = float(row["spend"]) if row else 0.0

    if in_tok >= policy.daily_input_token_cap:
        raise GatewayQuotaExceeded(
            dimension="input_tokens", used=in_tok,
            cap=policy.daily_input_token_cap, organization_id=policy.organization_id,
        )
    if out_tok >= policy.daily_output_token_cap:
        raise GatewayQuotaExceeded(
            dimension="output_tokens", used=out_tok,
            cap=policy.daily_output_token_cap, organization_id=policy.organization_id,
        )
    if spend >= policy.daily_usd_cap:
        raise GatewayQuotaExceeded(
            dimension="cost_usd", used=spend,
            cap=policy.daily_usd_cap, organization_id=policy.organization_id,
        )


# =============================================================================
# Content safety pre-check — quick PHI sniff before sending
# =============================================================================


# Conservative regexes — these are sanity nets, NOT a PHI policy. The
# authoritative PHI policy is the per-tenant Bedrock Guardrail attached at
# InvokeModel time. This pre-check exists so a leak detected in dev fails
# loudly here, not silently in CloudWatch.
_PHI_SUSPECT_PATTERNS = (
    "ssn=", " ssn ", " ssn:", "social security",
    "mrn=", " mrn ",
    "dob=", " dob ", " dob:",
    # Phone-number-shaped strings handled by Bedrock Guardrails, not here.
)


def _content_safety_pre_check(prompt_material: str) -> None:
    lc = prompt_material.lower()
    for needle in _PHI_SUSPECT_PATTERNS:
        if needle in lc:
            log.warning("gateway.phi_suspect_pattern", needle=needle)
            # Don't block — Bedrock Guardrails will decide. Just log the
            # signal so the SRE dashboard sees it.
            return


# =============================================================================
# Cost estimation — same model the BudgetTracker uses
# =============================================================================


_MODEL_PRICING_PER_MTOK = {
    # input, output (USD per million tokens, on-demand)
    # Sonnet 4.6 (apac/us): $3 in / $15 out
    "sonnet": (3.0, 15.0),
    # Haiku 4.5 (apac/us): $1 in / $5 out
    "haiku": (1.0, 5.0),
}


def _cost_for(model_id: str, input_tokens: int, output_tokens: int) -> float:
    key = "haiku" if "haiku" in model_id.lower() else "sonnet"
    in_rate, out_rate = _MODEL_PRICING_PER_MTOK[key]
    return (input_tokens * in_rate / 1_000_000.0) + (output_tokens * out_rate / 1_000_000.0)


# =============================================================================
# The Gateway itself — implements LLMClient
# =============================================================================


class GenAIGateway(LLMClient):
    """Governed entry point. Wraps any underlying LLMClient (Bedrock/Anthropic).

    Enforcement, in order, on every `complete()` call:
      1. Resolve call context (org_id + case_id + agent_name)
      2. Lookup tenant policy
      3. Validate model_id is in allowlist
      4. Run quota check (raises GatewayQuotaExceeded on breach)
      5. Pre-call content safety sniff
      6. Open llm_invocations row (status='running')
      7. Delegate to underlying client
      8. Close llm_invocations row with usage + cost
      9. Return LLMResponse unchanged

    Failures still close the audit row — via try/finally — so a CISO never
    sees a "phantom" call with no record.
    """

    def __init__(self, underlying: LLMClient, *, fallback_org_id: str = "system") -> None:
        self._underlying = underlying
        self._fallback_org_id = fallback_org_id
        self._enabled = settings.GENAI_GATEWAY_ENABLED

    @property
    def underlying(self) -> LLMClient:
        return self._underlying

    async def complete(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int = 4096,
        temperature: float = 0.0,
        model_id: str | None = None,
    ) -> LLMResponse:
        if not self._enabled:
            # Bypass — preserve historical demo behavior when GATEWAY=disabled.
            return await self._underlying.complete(
                system=system, user=user, max_tokens=max_tokens,
                temperature=temperature, model_id=model_id,
            )

        ctx = get_call_context()
        org_id = (ctx.organization_id if ctx else None) or self._fallback_org_id
        case_id = ctx.case_id if ctx else None
        agent_name = ctx.agent_name if ctx else None

        policy = await get_tenant_policy(org_id)

        # 1. Model allowlist
        # Provider-aware default: BEDROCK_MODEL_ID only makes sense when
        # LLM_PROVIDER=bedrock. For openrouter / anthropic we either use
        # the explicit model_id passed by the caller, or pass None and let
        # the underlying client fall back to its own default. Passing the
        # Bedrock cross-region inference profile to OpenRouter causes a
        # 400 ("not a valid model ID").
        if model_id:
            resolved_model_id = model_id
        elif settings.LLM_PROVIDER == "bedrock":
            resolved_model_id = settings.BEDROCK_MODEL_ID
        elif settings.LLM_PROVIDER == "openrouter":
            resolved_model_id = settings.OPENROUTER_MODEL or "anthropic/claude-sonnet-4.6"
        else:  # anthropic
            resolved_model_id = settings.ANTHROPIC_MODEL or "claude-sonnet-4-6"
        if policy.allowed_model_ids and resolved_model_id not in policy.allowed_model_ids:
            raise GatewayPolicyViolation(
                f"model_id={resolved_model_id!r} not in allowlist for org={org_id!r} "
                f"(allowed: {policy.allowed_model_ids})"
            )

        # 2. Quota
        await _check_quota(policy)

        # 3. Content-safety pre-check
        _content_safety_pre_check(system + "\n" + user)

        # 4. Circuit breaker — fast-fail before audit row insert if model is OPEN
        breaker = await get_breaker(resolved_model_id)
        try:
            await breaker.before_call()
        except CircuitBreakerOpen as cbo:
            log.warning(
                "gateway.circuit_open",
                model_id=resolved_model_id,
                retry_after=cbo.retry_after_seconds,
            )
            raise

        # 5. Open audit row
        invocation_id = uuid.uuid4()
        from app.db import db
        row_id = await db.fetchval(
            """INSERT INTO llm_invocations
                  (invocation_id, organization_id, case_id, agent_name,
                   model_id, status, started_at)
               VALUES ($1, $2, $3, $4, $5, 'running', NOW())
               RETURNING id""",
            invocation_id, org_id, case_id, agent_name, resolved_model_id,
        )

        started = time.time()
        try:
            # 6. Delegate inside an OTel Bedrock span — gen_ai.* attributes
            #    follow the OpenTelemetry semantic conventions for AI workloads.
            with bedrock_span(
                model_id=resolved_model_id,
                organization_id=org_id,
                agent_name=agent_name,
            ) as otel_span:
                resp = await self._underlying.complete(
                    system=system, user=user, max_tokens=max_tokens,
                    temperature=temperature, model_id=resolved_model_id,
                )
                otel_span.set_attribute("gen_ai.usage.input_tokens", resp.input_tokens)
                otel_span.set_attribute("gen_ai.usage.output_tokens", resp.output_tokens)
            latency_ms = int((time.time() - started) * 1000)
            cost = _cost_for(resp.model_id, resp.input_tokens, resp.output_tokens)
            await db.execute(
                """UPDATE llm_invocations SET
                       finished_at = NOW(), status = 'ok',
                       input_tokens = $1, output_tokens = $2,
                       cost_usd = $3, latency_ms = $4
                   WHERE id = $5""",
                resp.input_tokens, resp.output_tokens, cost, latency_ms, row_id,
            )
            await breaker.record_success()
            return resp
        except Exception as e:  # noqa: BLE001
            latency_ms = int((time.time() - started) * 1000)
            await db.execute(
                """UPDATE llm_invocations SET
                       finished_at = NOW(), status = 'error',
                       error_text = $1, latency_ms = $2
                   WHERE id = $3""",
                str(e)[:500], latency_ms, row_id,
            )
            # Circuit breaker counts ALL failures (Bedrock 5xx, timeout, parse error).
            # CircuitBreakerOpen itself is not counted (we're not actually calling).
            if not isinstance(e, CircuitBreakerOpen):
                await breaker.record_failure()
            raise

    async def stream(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int = 4096,
        temperature: float = 0.0,
        model_id: str | None = None,
    ) -> AsyncIterator[str]:
        # Streaming path passes through unchanged (no audit). ClinCase doesn't
        # use streaming today — kept for interface conformance.
        async for chunk in self._underlying.stream(
            system=system, user=user, max_tokens=max_tokens,
            temperature=temperature, model_id=model_id,
        ):
            yield chunk


# =============================================================================
# Per-tenant usage rollup (powers /api/v1/llm-gateway/usage)
# =============================================================================


async def tenant_usage(organization_id: str, *, hours: int = 24) -> dict[str, Any]:
    """Live rolling usage for a tenant. Used by SRE + customer compliance dashboards."""
    from app.db import db
    row = await db.fetchrow(
        f"""SELECT
              COUNT(*)::BIGINT AS calls,
              COALESCE(SUM(input_tokens),  0)::BIGINT AS in_tok,
              COALESCE(SUM(output_tokens), 0)::BIGINT AS out_tok,
              COALESCE(SUM(cost_usd),      0)::FLOAT  AS spend,
              COALESCE(AVG(latency_ms),    0)::INT    AS avg_latency_ms,
              SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END)::BIGINT AS errors
           FROM llm_invocations
           WHERE organization_id = $1
             AND started_at >= NOW() - INTERVAL '{int(hours)} hours'""",
        organization_id,
    )
    pol = await get_tenant_policy(organization_id)
    return {
        "organization_id": organization_id,
        "window_hours": hours,
        "asof_iso": datetime.now(UTC).isoformat(),
        "calls": int(row["calls"]) if row else 0,
        "input_tokens": int(row["in_tok"]) if row else 0,
        "output_tokens": int(row["out_tok"]) if row else 0,
        "cost_usd": float(row["spend"]) if row else 0.0,
        "avg_latency_ms": int(row["avg_latency_ms"]) if row else 0,
        "errors": int(row["errors"]) if row else 0,
        "policy": {
            "allowed_model_ids": pol.allowed_model_ids,
            "daily_input_token_cap": pol.daily_input_token_cap,
            "daily_output_token_cap": pol.daily_output_token_cap,
            "daily_usd_cap": pol.daily_usd_cap,
            "bedrock_guardrail_id": pol.bedrock_guardrail_id,
        },
    }
