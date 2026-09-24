"""OncoTwin observability — process-wide metrics + per-organisation traces.

  counters     events published / handled by type, evaluations, alerts, gate
               outcomes, LLM calls, errors
  latencies    evaluation, history (full vs incremental), agents, event handling,
               simulation, LLM — p50 / p95 / p99 over a bounded window
  gauges       set by the caller (e.g. patients per triage category)

Exposed as JSON (engineering dashboard) and Prometheus text exposition
(`/api/v1/oncotwin/metrics`). No patient identifier or clinical value is ever
used as a metric label — labels are bounded enums (event type, agent name,
status, gate name), which also keeps cardinality small.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from contextlib import contextmanager
from typing import Any

import numpy as np

WINDOW = 2000


class Metrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.counters: dict[tuple[str, tuple], float] = defaultdict(float)
        self.latency: dict[tuple[str, tuple], deque] = defaultdict(lambda: deque(maxlen=WINDOW))
        self.gauges: dict[tuple[str, tuple], float] = {}
        self.started = time.time()

    @staticmethod
    def _key(name: str, labels: dict[str, Any]) -> tuple[str, tuple]:
        return name, tuple(sorted((k, str(v)) for k, v in labels.items()))

    def inc(self, name: str, value: float = 1.0, **labels: Any) -> None:
        with self._lock:
            self.counters[self._key(name, labels)] += value

    def observe_ms(self, name: str, ms: float, **labels: Any) -> None:
        with self._lock:
            self.latency[self._key(name, labels)].append(float(ms))

    def gauge(self, name: str, value: float, **labels: Any) -> None:
        with self._lock:
            self.gauges[self._key(name, labels)] = float(value)

    @contextmanager
    def timed(self, name: str, **labels: Any):
        t0 = time.perf_counter()
        ok = True
        try:
            yield
        except Exception:
            ok = False
            self.inc("oncotwin_errors_total", where=name)
            raise
        finally:
            self.observe_ms(name, (time.perf_counter() - t0) * 1000.0, **labels, status="ok" if ok else "error")

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            counters = [{"name": n, "labels": dict(lb), "value": v} for (n, lb), v in sorted(self.counters.items())]
            lat = []
            for (n, lb), q in sorted(self.latency.items()):
                a = np.array(q)
                lat.append({"name": n, "labels": dict(lb), "count": int(a.size),
                            "p50_ms": round(float(np.percentile(a, 50)), 2), "p95_ms": round(float(np.percentile(a, 95)), 2),
                            "p99_ms": round(float(np.percentile(a, 99)), 2), "max_ms": round(float(a.max()), 2)})
            gauges = [{"name": n, "labels": dict(lb), "value": v} for (n, lb), v in sorted(self.gauges.items())]
        return {"uptime_seconds": round(time.time() - self.started, 1), "counters": counters, "latencies": lat,
                "gauges": gauges, "window": WINDOW}

    def prometheus(self) -> str:
        snap = self.snapshot()

        def lbl(d: dict[str, str]) -> str:
            return "" if not d else "{" + ",".join(f'{k}="{str(v).replace(chr(34), "")}"' for k, v in d.items()) + "}"
        out = [f"{c['name']}{lbl(c['labels'])} {c['value']}" for c in snap["counters"]]
        out += [f"{g['name']}{lbl(g['labels'])} {g['value']}" for g in snap["gauges"]]
        for h in snap["latencies"]:
            base = h["name"].replace(".", "_")
            out += [f"{base}_{q}_ms{lbl(h['labels'])} {h[q + '_ms']}" for q in ("p50", "p95", "p99")]
            out.append(f"{base}_count{lbl(h['labels'])} {h['count']}")
        return "\n".join(out) + "\n"


METRICS = Metrics()
