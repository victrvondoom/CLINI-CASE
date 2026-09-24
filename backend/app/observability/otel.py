"""OpenTelemetry distributed tracing — W3C Trace Context propagated end-to-end.

Why this is the foundational industry-grade primitive:

  • Every span — HTTP request, agent invocation, Bedrock call, DB query, TriZetto
    submit — links into a single distributed trace via W3C Trace Context (the
    standard `traceparent` and `tracestate` headers).
  • A TriZetto SRE pulls one trace_id from a customer escalation;
    sees the entire request lifecycle from API ingress to Bedrock InvokeModel
    to TriZetto Gateway submit, in one Datadog/Honeycomb/X-Ray pane.
  • OpenTelemetry is vendor-neutral — same instrumentation exports to AWS X-Ray,
    Datadog, Honeycomb, Tempo, Jaeger, or any OTLP receiver via env config.
  • Defaults to OFF when OTEL_EXPORTER_OTLP_ENDPOINT is unset (zero overhead in
    the demo environment); production sets it via env to enable.

This module is the SINGLE init point. Every other layer (FastAPI, Bedrock client,
Postgres, agents) gets auto-instrumented or wrapped via the helpers exported here.

Hook order (FastAPI lifespan):
    1. setup_otel(...)           ← creates TracerProvider + exporters
    2. instrument_fastapi(app)   ← FastAPI middleware spans
    3. instrument_db()            ← asyncpg query spans (TODO: when otel-asyncpg lands)
    4. (per-agent invocation)    ← AgentSpan in framework/agent.py wraps the lifecycle
    5. (per-bedrock call)         ← GenAIGatewaySpan in llm/gateway.py wraps InvokeModel
"""
from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import structlog

log = structlog.get_logger()


# Module-level state — set once at startup
_initialized = False
_tracer: Any = None


def is_enabled() -> bool:
    """OTel is enabled when an OTLP endpoint is configured."""
    return bool(os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"))


def setup_otel(*, service_name: str = "clincase", service_version: str = "0.1.0") -> None:
    """Initialize OpenTelemetry. Idempotent. No-op when OTEL_EXPORTER_OTLP_ENDPOINT is unset.

    Call once at app lifespan startup. Configures:
      • Resource attributes (service.name, service.version, deployment.environment)
      • TracerProvider with batch span processor
      • OTLP HTTP exporter pointed at OTEL_EXPORTER_OTLP_ENDPOINT
      • W3C Trace Context propagator (the standard for cross-service correlation)

    To configure in production, set:
      OTEL_EXPORTER_OTLP_ENDPOINT=https://otel-collector.internal.example.com:4318
      OTEL_EXPORTER_OTLP_HEADERS=authorization=Bearer ${OTEL_TOKEN}
      OTEL_RESOURCE_ATTRIBUTES=deployment.environment=production
    """
    global _initialized, _tracer
    if _initialized:
        return

    if not is_enabled():
        log.info("otel.disabled", reason="OTEL_EXPORTER_OTLP_ENDPOINT unset")
        return

    try:
        from opentelemetry import trace
        from opentelemetry.baggage.propagation import W3CBaggagePropagator
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.propagate import set_global_textmap
        from opentelemetry.propagators.composite import CompositePropagator
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.trace.propagation.tracecontext import (
            TraceContextTextMapPropagator,
        )
    except ImportError:
        log.warning(
            "otel.deps_missing",
            hint="pip install 'opentelemetry-api opentelemetry-sdk "
                 "opentelemetry-exporter-otlp-proto-http "
                 "opentelemetry-instrumentation-fastapi'",
        )
        return

    resource = Resource.create({
        "service.name": service_name,
        "service.version": service_version,
        "service.namespace": "clincase",
        "deployment.environment": os.getenv("DEPLOYMENT_ENV", "dev"),
    })
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter()  # picks up OTEL_EXPORTER_OTLP_ENDPOINT from env
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    # W3C Trace Context + Baggage — the cross-service correlation standard
    set_global_textmap(CompositePropagator([
        TraceContextTextMapPropagator(),
        W3CBaggagePropagator(),
    ]))

    _tracer = trace.get_tracer(service_name, service_version)
    _initialized = True
    log.info("otel.initialized", endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"))


def instrument_fastapi(app: Any) -> None:
    """Wrap a FastAPI app with OTel auto-instrumentation. No-op when OTel is disabled."""
    if not is_enabled() or not _initialized:
        return
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor.instrument_app(app, excluded_urls="healthz,metrics")
        log.info("otel.fastapi.instrumented")
    except ImportError:
        log.warning("otel.fastapi.deps_missing", hint="pip install opentelemetry-instrumentation-fastapi")


@contextmanager
def agent_span(
    name: str,
    *,
    organization_id: str | None = None,
    case_id: str | None = None,
    agent_name: str | None = None,
    attributes: dict[str, Any] | None = None,
) -> Iterator[Any]:
    """Open an OTel span for an agent invocation. Use from `Agent.invoke()`.

    Falls back to a no-op when OTel is disabled.

    Example:
        with agent_span("agent.necessity_reasoner", organization_id=ctx.organization_id,
                         case_id=ctx.case_id, agent_name="necessity_reasoner") as span:
            span.set_attribute("input_tokens", 1234)
            ...
    """
    if not is_enabled() or _tracer is None:
        yield _NoOpSpan()
        return

    attrs = {
        "clincase.organization_id": organization_id or "unknown",
        "clincase.case_id": case_id or "",
        "clincase.agent_name": agent_name or "",
    }
    if attributes:
        attrs.update(attributes)

    with _tracer.start_as_current_span(name, attributes=attrs) as span:
        yield span


@contextmanager
def bedrock_span(
    *,
    model_id: str,
    organization_id: str | None = None,
    agent_name: str | None = None,
) -> Iterator[Any]:
    """Open an OTel span for a single Bedrock InvokeModel call. Use from GenAIGateway."""
    if not is_enabled() or _tracer is None:
        yield _NoOpSpan()
        return

    attrs = {
        "gen_ai.system": "aws.bedrock",
        "gen_ai.request.model": model_id,
        "clincase.organization_id": organization_id or "unknown",
        "clincase.agent_name": agent_name or "",
    }
    with _tracer.start_as_current_span("bedrock.invoke_model", attributes=attrs) as span:
        yield span


class _NoOpSpan:
    """Drop-in for OTel Span when OTel is disabled. Methods are no-ops."""

    def set_attribute(self, *args: Any, **kwargs: Any) -> None: ...
    def set_attributes(self, *args: Any, **kwargs: Any) -> None: ...
    def add_event(self, *args: Any, **kwargs: Any) -> None: ...
    def set_status(self, *args: Any, **kwargs: Any) -> None: ...
    def record_exception(self, *args: Any, **kwargs: Any) -> None: ...

    @property
    def is_recording(self) -> bool: return False


# =============================================================================
# Trace context extraction helpers
# =============================================================================


def get_current_trace_id() -> str | None:
    """Return the current trace_id as hex (or None when no active trace)."""
    if not is_enabled():
        return None
    try:
        from opentelemetry import trace
        span = trace.get_current_span()
        ctx = span.get_span_context()
        if ctx.trace_id == 0:
            return None
        return format(ctx.trace_id, "032x")
    except Exception:  # noqa: BLE001
        return None


def inject_traceparent_into_headers(headers: dict[str, str]) -> dict[str, str]:
    """Inject W3C `traceparent` + `tracestate` into outbound HTTP headers.

    Use when calling an external service (e.g. TriZetto Gateway) — the receiver's
    OTel will pick up the trace_id and continue the same trace.
    """
    if not is_enabled():
        return headers
    try:
        from opentelemetry.propagate import inject
        out = dict(headers)
        inject(out)
        return out
    except Exception:  # noqa: BLE001
        return headers
