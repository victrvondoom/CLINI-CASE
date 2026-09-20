"""SSE pub/sub for live trace events — pluggable backend.

The framework + every agent + the SSE endpoint use the same three functions:

    await publish(case_id, event)       # producer side  (called from agents)
    queue = subscribe(case_id)          # consumer side  (called from SSE handler)
    unsubscribe(case_id, queue)         # cleanup        (called from SSE handler on disconnect)

Two backends are bundled, swapped via configuration — the call sites never change:

  • InProcessBackend   — single-process pub/sub via asyncio.Queues. Default.
                         Correct for `make dev`, tests, and single-replica deploys.
                         Zero external dependencies.

  • RedisPubSubBackend — multi-replica pub/sub via Redis. Needed once the API
                         tier scales past one replica AND a single SSE client
                         can land on a replica that did NOT execute the case.
                         Architecture: one Redis pubsub connection per process
                         multiplexes all subscribers (1 connection, not N) —
                         a fan-out reader task pushes incoming messages onto
                         the local in-process queues for each case_id.
                         Channel naming: `clincase:case:{case_id}`.

Selection: `REDIS_URL` env var is set → Redis backend is initialized at startup
in `main.py`'s lifespan. Worker process does the same in `case_runner.py` boot.
Unset → in-process backend stays. Tests inject `InProcessBackend` directly.

This is the production-grade SCALE-7 deliverable from `ops/SCALING.md`'s gap
list. The async DAG runs on worker replicas; an SSE consumer lands on whatever
API replica the ALB routes it to — without Redis, the replica running the case
publishes events to its in-memory queues and the SSE consumer on a different
replica sees nothing. Redis pub/sub closes that gap.
"""
from __future__ import annotations

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from collections import defaultdict
from typing import Any

import structlog

log = structlog.get_logger()


# =============================================================================
# Backend protocol
# =============================================================================


class PubSubBackend(ABC):
    """Pluggable pub/sub backend. The streaming module re-exports
    `publish`/`subscribe`/`unsubscribe` that delegate to the active backend."""

    @abstractmethod
    async def publish(self, case_id: str, event: dict[str, Any]) -> None: ...

    @abstractmethod
    def subscribe(self, case_id: str) -> asyncio.Queue: ...

    @abstractmethod
    def unsubscribe(self, case_id: str, queue: asyncio.Queue) -> None: ...

    async def connect(self) -> None:  # noqa: D401 — optional hook
        """Optional connection / handshake hook. No-op by default."""

    async def disconnect(self) -> None:  # noqa: D401 — optional hook
        """Optional graceful shutdown hook. No-op by default."""


# =============================================================================
# In-process backend (default)
# =============================================================================


class InProcessBackend(PubSubBackend):
    """Single-process fan-out. Correct for `make dev`, tests, single replica."""

    def __init__(self) -> None:
        self._subscribers: dict[str, list[asyncio.Queue]] = defaultdict(list)

    async def publish(self, case_id: str, event: dict[str, Any]) -> None:
        for queue in list(self._subscribers[case_id]):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                # Drop on slow consumer — never block agents on SSE pace.
                pass

    def subscribe(self, case_id: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self._subscribers[case_id].append(queue)
        return queue

    def unsubscribe(self, case_id: str, queue: asyncio.Queue) -> None:
        if queue in self._subscribers[case_id]:
            self._subscribers[case_id].remove(queue)
        if not self._subscribers[case_id]:
            del self._subscribers[case_id]


# =============================================================================
# Redis pub/sub backend (multi-replica)
# =============================================================================


_REDIS_CHANNEL_PREFIX = "clincase:case:"


class RedisPubSubBackend(PubSubBackend):
    """Multi-replica fan-out via Redis pub/sub.

    One reader task per process consumes a `psubscribe('clincase:case:*')`
    pattern; messages are demultiplexed onto local in-process queues keyed by
    case_id. Two redis connections per process (one PUBLISH, one SUBSCRIBE) —
    the SUBSCRIBE side cannot be reused for arbitrary commands once it's in
    subscribe mode (Redis protocol constraint).

    Subscriber semantics on the SSE side are unchanged — `subscribe(case_id)`
    still returns an `asyncio.Queue` that the SSE handler awaits on.
    """

    def __init__(self, url: str) -> None:
        self._url = url
        self._publish_client: Any | None = None
        self._subscribe_client: Any | None = None
        self._pubsub: Any | None = None
        self._reader_task: asyncio.Task | None = None
        self._local_queues: dict[str, list[asyncio.Queue]] = defaultdict(list)
        self._connected = False

    async def connect(self) -> None:
        if self._connected:
            return
        try:
            import redis.asyncio as aioredis  # type: ignore[import-not-found]
        except ImportError as e:  # noqa: BLE001
            raise RuntimeError(
                "RedisPubSubBackend requires the `redis>=5.0` package. "
                "Install via `pip install redis>=5.0` or add it to pyproject.toml."
            ) from e

        self._publish_client = aioredis.from_url(
            self._url, encoding="utf-8", decode_responses=True
        )
        self._subscribe_client = aioredis.from_url(
            self._url, encoding="utf-8", decode_responses=True
        )
        # Verify connectivity early so misconfig fails at startup, not first use.
        await self._publish_client.ping()
        self._pubsub = self._subscribe_client.pubsub()
        await self._pubsub.psubscribe(f"{_REDIS_CHANNEL_PREFIX}*")
        self._reader_task = asyncio.create_task(
            self._reader_loop(), name="clincase-redis-pubsub-reader"
        )
        self._connected = True
        log.info("streaming.redis.connected", url=self._sanitize_url(self._url))

    async def disconnect(self) -> None:
        if not self._connected:
            return
        if self._reader_task is not None:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
            self._reader_task = None
        if self._pubsub is not None:
            try:
                await self._pubsub.punsubscribe(f"{_REDIS_CHANNEL_PREFIX}*")
                await self._pubsub.aclose()
            except Exception:  # noqa: BLE001
                pass
            self._pubsub = None
        for client in (self._subscribe_client, self._publish_client):
            if client is not None:
                try:
                    await client.aclose()
                except Exception:  # noqa: BLE001
                    pass
        self._publish_client = None
        self._subscribe_client = None
        self._connected = False
        log.info("streaming.redis.disconnected")

    async def _reader_loop(self) -> None:
        """Single fan-out task. Reads every message, demuxes to local queues."""
        assert self._pubsub is not None
        try:
            async for msg in self._pubsub.listen():
                # Skip subscription confirmations and other control frames.
                if msg.get("type") not in ("pmessage", "message"):
                    continue
                channel = msg.get("channel") or ""
                if not channel.startswith(_REDIS_CHANNEL_PREFIX):
                    continue
                case_id = channel[len(_REDIS_CHANNEL_PREFIX):]
                try:
                    event = json.loads(msg["data"])
                except (TypeError, json.JSONDecodeError) as e:  # noqa: BLE001
                    log.warning("streaming.redis.bad_payload", error=str(e))
                    continue
                for q in list(self._local_queues.get(case_id, [])):
                    try:
                        q.put_nowait(event)
                    except asyncio.QueueFull:
                        # Slow consumer — drop rather than backpressure the loop.
                        pass
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001
            # Reader-side connection errors. Logged so ops alerting catches it;
            # agents continue to publish (they will succeed) and SSE consumers
            # will silently miss events until restart. K8s liveness probe + the
            # fact that agents are still finishing keeps the system available.
            log.exception("streaming.redis.reader_failed", error=str(e))

    async def publish(self, case_id: str, event: dict[str, Any]) -> None:
        if not self._connected or self._publish_client is None:
            log.warning("streaming.redis.publish_before_connect", case_id=case_id)
            return
        try:
            payload = json.dumps(event, default=str)
            await self._publish_client.publish(
                f"{_REDIS_CHANNEL_PREFIX}{case_id}", payload
            )
        except Exception as e:  # noqa: BLE001
            # Never let SSE failures cascade into agent failures.
            log.warning("streaming.redis.publish_failed", case_id=case_id, error=str(e))

    def subscribe(self, case_id: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self._local_queues[case_id].append(queue)
        return queue

    def unsubscribe(self, case_id: str, queue: asyncio.Queue) -> None:
        if queue in self._local_queues.get(case_id, []):
            self._local_queues[case_id].remove(queue)
        if not self._local_queues.get(case_id):
            self._local_queues.pop(case_id, None)

    @staticmethod
    def _sanitize_url(url: str) -> str:
        # Mask any password in the URL for log output.
        if "@" not in url:
            return url
        scheme_and_creds, _, host = url.rpartition("@")
        scheme, _, _creds = scheme_and_creds.partition("://")
        return f"{scheme}://***@{host}"


# =============================================================================
# Module-level facade — agents/SSE/etc call these regardless of backend
# =============================================================================


_BACKEND: PubSubBackend = InProcessBackend()


def get_backend() -> PubSubBackend:
    return _BACKEND


def set_backend(backend: PubSubBackend) -> None:
    """Swap the active backend. Used at app startup AND in tests."""
    global _BACKEND
    _BACKEND = backend


async def use_redis_backend(url: str) -> RedisPubSubBackend:
    """Bootstrap and install the Redis backend. Call from app lifespan."""
    backend = RedisPubSubBackend(url)
    await backend.connect()
    set_backend(backend)
    return backend


async def shutdown_backend() -> None:
    """Graceful shutdown — close any persistent connections."""
    await _BACKEND.disconnect()


# Exact same public functions as before — every existing import keeps working.
async def publish(case_id: str, event: dict[str, Any]) -> None:
    """Push a trace event to every subscriber of case_id."""
    await _BACKEND.publish(case_id, event)


def subscribe(case_id: str) -> asyncio.Queue:
    """Subscribe to events for case_id. Returns a queue to consume from."""
    return _BACKEND.subscribe(case_id)


def unsubscribe(case_id: str, queue: asyncio.Queue) -> None:
    """Stop receiving events. Safe to call multiple times."""
    _BACKEND.unsubscribe(case_id, queue)
