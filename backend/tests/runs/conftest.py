from __future__ import annotations

import pytest

from app.db import db


@pytest.fixture(autouse=True)
async def _fresh_pool(request):
    """Per-test pool (each integration test has its own event loop) plus the startup-created tables."""
    if request.node.get_closest_marker("postgres") is None:
        yield
        return
    await db.disconnect()
    await db.connect()
    from app.api.idempotency_middleware import ensure_schema as idempotency_schema
    from app.events.outbox import ensure_schema as outbox_schema
    from app.jobs.queue import ensure_schema as queue_schema
    from app.llm.gateway import ensure_schema as gateway_schema
    from app.quotas import ensure_schema as quota_schema
    from app.runs import ensure_schema as runs_schema

    for ensure in (
        queue_schema, runs_schema, outbox_schema, gateway_schema, quota_schema, idempotency_schema,
    ):  # fmt: skip
        await ensure()
    yield
    await db.disconnect()
