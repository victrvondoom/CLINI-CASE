"""Vercel entrypoint for the ClinCase API.

Serverless runtimes may not deliver ASGI lifespan events, and may hand requests to a new
event loop. This wrapper runs the existing app.main lifespan (DB pool + idempotent schema
bootstraps) before the first request on each event loop, so every request sees a live pool.
Shutdown is not forwarded: the platform freezes or kills the instance, and pools die with it.
"""

from __future__ import annotations

import asyncio
import weakref
from typing import Any

import structlog

from app.db import db
from app.main import app as fastapi_app
from app.main import lifespan

log = structlog.get_logger()


class _LazyLifespan:
    def __init__(self, inner: Any) -> None:
        self.inner = inner
        self._started: weakref.WeakSet[asyncio.AbstractEventLoop] = weakref.WeakSet()
        self._locks: weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Lock] = (
            weakref.WeakKeyDictionary()
        )
        # Every entered lifespan stays referenced (one per event loop seen): if one were
        # garbage-collected, its `finally` would run db.disconnect() on the current pool.
        self._contexts: list[Any] = []

    async def _ensure_started(self) -> None:
        loop = asyncio.get_running_loop()
        if loop in self._started:
            return
        lock = self._locks.setdefault(loop, asyncio.Lock())
        async with lock:
            if loop in self._started:
                return
            if self._contexts:
                # A pool created on a previous loop cannot be used here, and db.connect() is a
                # no-op while one is set. Drop it without awaiting close (its loop is gone).
                db._pool = None
                db._ro_pool = None
            context = lifespan(self.inner)
            await context.__aenter__()
            self._contexts.append(context)
            self._started.add(loop)

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] == "lifespan":
            while True:
                message = await receive()
                if message["type"] == "lifespan.startup":
                    try:
                        await self._ensure_started()
                    except Exception as exc:  # noqa: BLE001 — reported to the server per ASGI spec
                        log.exception("vercel.startup_failed")
                        await send({"type": "lifespan.startup.failed", "message": str(exc)})
                        return
                    await send({"type": "lifespan.startup.complete"})
                elif message["type"] == "lifespan.shutdown":
                    await send({"type": "lifespan.shutdown.complete"})
                    return
        try:
            await self._ensure_started()
        except Exception:  # noqa: BLE001 — answer 503 and retry startup on the next request
            log.exception("vercel.startup_failed")
            if scope["type"] == "http":
                await send(
                    {
                        "type": "http.response.start",
                        "status": 503,
                        "headers": [(b"content-type", b"application/json")],
                    }
                )
                await send({"type": "http.response.body", "body": b'{"detail":"Service starting"}'})
            return
        await self.inner(scope, receive, send)


app = _LazyLifespan(fastapi_app)
