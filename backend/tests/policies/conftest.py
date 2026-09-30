from __future__ import annotations

import pytest

from app.db import db


@pytest.fixture(autouse=True)
async def _fresh_pool(request):
    if request.node.get_closest_marker("postgres") is None:
        yield
        return
    await db.disconnect()
    await db.connect()
    yield
    await db.disconnect()
