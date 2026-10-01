"""In-process login brute-force throttle: N failures per (email, client) in a window -> 429.

Process-local by design (no new infrastructure); a shared limiter (Redis/WAF) is needed for multi-replica
deployments and is listed in the pending-work doc.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque

MAX_FAILURES = 5
WINDOW_SECONDS = 900

_failures: dict[str, deque[float]] = defaultdict(deque)


def _key(email: str, client: str) -> str:
    return f"{email.lower()}|{client}"


def _prune(q: deque[float], now: float) -> None:
    while q and now - q[0] > WINDOW_SECONDS:
        q.popleft()


def retry_after(email: str, client: str, now: float | None = None) -> int:
    """Seconds the caller must wait (0 = allowed)."""
    now = time.time() if now is None else now
    q = _failures.get(_key(email, client))
    if not q:
        return 0
    _prune(q, now)
    if len(q) < MAX_FAILURES:
        return 0
    return max(1, int(WINDOW_SECONDS - (now - q[0])))


def record_failure(email: str, client: str, now: float | None = None) -> None:
    _failures[_key(email, client)].append(time.time() if now is None else now)


def reset(email: str, client: str) -> None:
    _failures.pop(_key(email, client), None)


def clear_all() -> None:
    _failures.clear()
