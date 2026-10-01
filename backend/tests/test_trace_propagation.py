import pytest

from app.observability import otel


def test_noop_when_otel_disabled(monkeypatch):
    monkeypatch.setattr(otel, "is_enabled", lambda: False)
    assert otel.current_traceparent() is None
    with otel.restored_trace_context("00-" + "a" * 32 + "-" + "b" * 16 + "-01"):
        pass


def test_traceparent_roundtrip_links_worker_span_to_producer():
    pytest.importorskip("opentelemetry.sdk.trace")
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider

    provider = TracerProvider()
    tracer = provider.get_tracer("t")
    otel.is_enabled = lambda: True  # type: ignore[assignment]
    try:
        with tracer.start_as_current_span("producer") as prod:
            tp = otel.current_traceparent()
        assert tp is not None
        with (
            otel.restored_trace_context(tp),
            tracer.start_as_current_span("worker") as w,
        ):
            assert w.get_span_context().trace_id == prod.get_span_context().trace_id
            assert trace.get_current_span() is w
    finally:
        import importlib

        importlib.reload(otel)
