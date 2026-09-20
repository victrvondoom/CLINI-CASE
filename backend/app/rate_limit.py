"""Per-tenant per-route token-bucket rate limiter.

Round-9 quotas are 24h rolling — they catch month-end blowouts but NOT
per-second bursts. A coordinator hammering POST /cases at 200 RPS can
saturate the case_jobs queue before the 24h quota even notices.

This module adds a sliding-window per-second + per-minute backpressure layer.
The shape:

    bucket_key   = f"rl:{org_id}:{route}:{window}"  in Redis (sorted set)
    member       = f"{request_uuid}:{ts_ms}"         (unique per call)
    score        = ts_ms

    on call:
      ZREMRANGEBYSCORE bucket_key 0 (now_ms - window_ms)   # evict old
      ZCARD bucket_key                                      # count remaining
      if count >= limit: REJECT 429 with Retry-After
      ZADD bucket_key score member                           # record this call
      EXPIRE bucket_key window_ms_ttl                        # tidy

In-memory fallback works for dev (single replica). Multi-replica deploys
MUST configure REDIS_URL — otherwise each replica has its own bucket and
the global rate is multiplied by replica count.

Pairs with: ops/architecture/RATE_LIMITING.md (the policy doc).
"""
from __future__ import annotations

import asyncio
import time
import uuid
from collections import deque
from dataclasses import dataclass
from typing import Awaitable, Callable

import structlog

from app.config import settings

log = structlog.get_logger()


# =============================================================================
# Per-tier per-route limit table
# =============================================================================
# Tier × route → (per-second, per-minute) limits
# Tighter buckets at the case-create + case-run endpoints (the expensive ones).
# Healthz / metrics get a generous limit so monitoring doesn't get throttled.

@dataclass(frozen=True)
class RateLimit:
    per_second: int
    per_minute: int


_DEFAULT_LIMITS: dict[str, dict[str, RateLimit]] = {
    "bronze": {
        "default":             RateLimit(per_second=10,  per_minute=300),
        "POST /api/v1/cases":  RateLimit(per_second=2,   per_minute=60),
        "POST /api/v1/cases/{case_id}/run-async": RateLimit(per_second=2, per_minute=60),
        "GET /metrics":        RateLimit(per_second=100, per_minute=6000),
        "GET /api/v1/healthz": RateLimit(per_second=100, per_minute=6000),
    },
    "silver": {
        "default":             RateLimit(per_second=50,  per_minute=1500),
        "POST /api/v1/cases":  RateLimit(per_second=10,  per_minute=300),
        "POST /api/v1/cases/{case_id}/run-async": RateLimit(per_second=10, per_minute=300),
        "GET /metrics":        RateLimit(per_second=100, per_minute=6000),
        "GET /api/v1/healthz": RateLimit(per_second=100, per_minute=6000),
    },
    "gold": {
        "default":             RateLimit(per_second=200, per_minute=6000),
        "POST /api/v1/cases":  RateLimit(per_second=50,  per_minute=1500),
        "POST /api/v1/cases/{case_id}/run-async": RateLimit(per_second=50, per_minute=1500),
        "GET /metrics":        RateLimit(per_second=100, per_minute=6000),
        "GET /api/v1/healthz": RateLimit(per_second=100, per_minute=6000),
    },
}


# =============================================================================
# Backend abstractions — Redis (multi-replica) + in-memory (dev fallback)
# =============================================================================


class _InMemoryBucketStore:
    """Single-process sliding window. Each (org, route, window) maps to a deque
    of timestamps in milliseconds. Race-free under asyncio because asyncio
    is single-threaded per event loop."""

    def __init__(self) -> None:
        self._buckets: dict[str, deque[float]] = {}
        self._lock = asyncio.Lock()

    async def take(self, key: str, *, limit: int, window_ms: int) -> tuple[bool, int, float]:
        now_ms = time.time() * 1000.0
        cutoff = now_ms - window_ms
        async with self._lock:
            dq = self._buckets.setdefault(key, deque())
            while dq and dq[0] < cutoff:
                dq.popleft()
            count = len(dq)
            if count >= limit:
                retry_after_ms = (dq[0] + window_ms) - now_ms
                return False, count, max(retry_after_ms, 0.0)
            dq.append(now_ms)
            return True, count + 1, 0.0


class _RedisBucketStore:
    """Sliding-window Redis sorted set."""

    def __init__(self, client: object) -> None:  # noqa: ANN001 — duck-typed Redis client
        self._r = client

    async def take(self, key: str, *, limit: int, window_ms: int) -> tuple[bool, int, float]:
        now_ms = time.time() * 1000.0
        cutoff = now_ms - window_ms
        member = f"{uuid.uuid4().hex}:{int(now_ms)}"
        # Pipeline: prune old, count, conditionally add. CHECK-then-ADD is
        # not atomic across replicas — close enough for rate limiting.
        try:
            await self._r.zremrangebyscore(key, 0, cutoff)  # type: ignore[attr-defined]
            count_raw = await self._r.zcard(key)             # type: ignore[attr-defined]
            count = int(count_raw or 0)
            if count >= limit:
                # Find the oldest member's score for Retry-After
                oldest_list = await self._r.zrange(key, 0, 0, withscores=True)  # type: ignore[attr-defined]
                if oldest_list:
                    _, oldest_score = oldest_list[0]
                    retry_after_ms = (float(oldest_score) + window_ms) - now_ms
                    return False, count, max(retry_after_ms, 0.0)
                return False, count, float(window_ms)
            await self._r.zadd(key, {member: now_ms})        # type: ignore[attr-defined]
            await self._r.expire(key, max(int(window_ms / 1000.0) + 1, 1))  # type: ignore[attr-defined]
            return True, count + 1, 0.0
        except Exception as e:  # noqa: BLE001
            log.warning("rate_limit.redis.error", error=str(e))
            # Fail-open under Redis outage. Documented in RATE_LIMITING.md.
            return True, 0, 0.0


# =============================================================================
# Module-level singleton store + entry point
# =============================================================================


_store: _InMemoryBucketStore | _RedisBucketStore = _InMemoryBucketStore()


def configure_redis_backend(redis_client: object) -> None:
    """Switch to Redis-backed bucket. Call from main.py after Redis bootstrap."""
    global _store
    _store = _RedisBucketStore(redis_client)
    log.info("rate_limit.backend.switched", backend="redis")


def _route_key(method: str, path: str) -> str:
    """Normalize a request to a bucket key. Strips path params via FastAPI's
    canonical path template ('/cases/{case_id}' not '/cases/abc')."""
    return f"{method} {path}"


def _resolve_limits(*, tier: str, route: str) -> RateLimit:
    """Resolve the (per_second, per_minute) tuple for a (tier, route) pair."""
    tier_table = _DEFAULT_LIMITS.get(tier, _DEFAULT_LIMITS["silver"])
    return tier_table.get(route, tier_table["default"])


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    bucket: str          # "per_second" | "per_minute" | "ok"
    count: int
    limit: int
    retry_after_ms: float


async def check_rate_limit(*, organization_id: str, tier: str, method: str, path: str) -> RateLimitDecision:
    """Top-level entry. Checks per-second AND per-minute buckets; returns the
    first one that rejects (or "ok" if both pass).
    """
    route = _route_key(method, path)
    limits = _resolve_limits(tier=tier, route=route)

    # per-second
    key_s = f"rl:{organization_id}:{route}:1s"
    ok, count, retry = await _store.take(key_s, limit=limits.per_second, window_ms=1000)
    if not ok:
        return RateLimitDecision(False, "per_second", count, limits.per_second, retry)

    # per-minute
    key_m = f"rl:{organization_id}:{route}:60s"
    ok, count_m, retry_m = await _store.take(key_m, limit=limits.per_minute, window_ms=60_000)
    if not ok:
        return RateLimitDecision(False, "per_minute", count_m, limits.per_minute, retry_m)

    return RateLimitDecision(True, "ok", count_m, limits.per_minute, 0.0)


# =============================================================================
# Snapshot for /api/v1/rate-limits/me
# =============================================================================


async def snapshot_for_tier(*, tier: str) -> dict:
    """Return the limit table for a tier, used by /rate-limits/me to show
    the caller what their declared limits are."""
    table = _DEFAULT_LIMITS.get(tier, _DEFAULT_LIMITS["silver"])
    return {
        "tier": tier,
        "limits_by_route": {
            route: {"per_second": rl.per_second, "per_minute": rl.per_minute}
            for route, rl in table.items()
        },
        "backend": "redis" if isinstance(_store, _RedisBucketStore) else "in-memory",
        "redis_url_configured": bool(settings.REDIS_URL),
    }
