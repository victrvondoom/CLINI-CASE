from __future__ import annotations

import pytest

from app.db import db


@pytest.fixture(autouse=True)
async def _fresh_pool(request):
    """Integration tests run each test in its own event loop, so the shared pool must be created and closed per test."""
    if request.node.get_closest_marker("postgres") is None:
        yield
        return
    await db.disconnect()
    await db.connect()
    yield
    await db.disconnect()
