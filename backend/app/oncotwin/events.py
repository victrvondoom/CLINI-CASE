"""OncoTwin event bus — typed domain events drive the twin.

    WearableObservationReceived · FHIRObservationCreated · LabResultCreated ·
    SymptomReported · TreatmentEventRecorded      ── data events
            │  (twin-update handler marks the patient dirty)
            ▼
    drain → incremental twin update → TwinEvaluated · RiskUpdated ·
            TwinStateChanged · ChangePointDetected · DataQualityIssueDetected ·
            EarlyWarningGenerated
            ▼
    ClinicianReviewed · InterventionRecorded · HandoffCreated  ── HITL events

Why a bus: new data update the twin WITHOUT rebuilding the patient record —
the handler only marks a patient dirty; the drain runs ONE incremental
evaluation per batch (the history extends by the new days only).

Delivery: in-process, synchronous, in publication order (at-most-once per
subscriber; handler errors are counted and logged, never propagated to the
publisher). Durable fan-out: every event is also queued for ClinCase's
transactional outbox (`app/events/outbox.py`, CloudEvents type
`oncotwin.<event>.v1`), whose publisher forwards to EventBridge / Kinesis when
configured. Without a database the bridge is skipped and the event records
`bridged: false` — nothing pretends to have been published.
"""
from __future__ import annotations

import threading
import time
import uuid
from collections import deque
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import structlog

from app.oncotwin.observability import METRICS

log = structlog.get_logger()

EVENT_TYPES = {
    "WearableObservationReceived": "data", "FHIRObservationCreated": "data", "LabResultCreated": "data",
    "SymptomReported": "data", "TreatmentEventRecorded": "data",
    "TwinEvaluated": "twin", "TwinStateChanged": "twin", "RiskUpdated": "twin", "ChangePointDetected": "twin",
    "DataQualityIssueDetected": "twin", "EarlyWarningGenerated": "twin", "SafetyGateBlocked": "twin",
    "ClinicianReviewed": "hitl", "InterventionRecorded": "hitl", "HandoffCreated": "hitl",
    "ModelDriftDetected": "mlops",
}
LOG_SIZE = 2000

Handler = Callable[[dict[str, Any]], None]


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class TwinEventBus:
    def __init__(self, organization_id: str):
        self.organization_id = organization_id
        self.log: deque[dict[str, Any]] = deque(maxlen=LOG_SIZE)
        self.pending_outbox: list[dict[str, Any]] = []
        self._subs: list[tuple[str, Handler]] = []
        self._lock = threading.RLock()
        self.seq = 0

    def subscribe(self, prefix: str, handler: Handler) -> None:
        """`prefix` is an event type or a category ('data', 'twin', 'hitl', 'mlops') or '*'."""
        self._subs.append((prefix, handler))

    def publish(self, event_type: str, *, patient_id: str | None, payload: dict[str, Any],
                twin_day: int | None = None, source: str = "oncotwin") -> dict[str, Any]:
        if event_type not in EVENT_TYPES:
            raise ValueError(f"unknown event type {event_type!r}")
        with self._lock:
            self.seq += 1
            ev = {"id": str(uuid.uuid4()), "seq": self.seq, "type": event_type, "category": EVENT_TYPES[event_type],
                  "cloudevent_type": f"oncotwin.{event_type}.v1", "organization_id": self.organization_id,
                  "patient_id": patient_id, "twin_day": twin_day, "source": source, "at": _now(),
                  "payload": payload, "bridged": None, "handled_by": []}
            self.log.append(ev)
            self.pending_outbox.append(ev)
        METRICS.inc("oncotwin_events_published_total", type=event_type)
        for prefix, handler in list(self._subs):
            if prefix not in ("*", event_type, EVENT_TYPES[event_type]):
                continue
            t0 = time.perf_counter()
            try:
                handler(ev)
                ev["handled_by"].append(getattr(handler, "__name__", "handler"))
                METRICS.inc("oncotwin_events_handled_total", type=event_type, status="ok")
            except Exception as e:  # noqa: BLE001 — a failing subscriber never breaks the publisher
                METRICS.inc("oncotwin_events_handled_total", type=event_type, status="error")
                log.warning("oncotwin.event.handler_failed", type=event_type, error=str(e)[:200])
            finally:
                METRICS.observe_ms("oncotwin_event_handler", (time.perf_counter() - t0) * 1000.0, type=event_type)
        return ev

    def recent(self, limit: int = 200, patient_id: str | None = None, category: str | None = None) -> list[dict[str, Any]]:
        rows = [e for e in self.log if (patient_id is None or e["patient_id"] == patient_id)
                and (category is None or e["category"] == category)]
        return rows[-limit:][::-1]

    async def flush_outbox(self) -> dict[str, int]:
        """Forward queued events to ClinCase's transactional outbox (fail-soft, never raises)."""
        with self._lock:
            batch, self.pending_outbox = self.pending_outbox, []
        if not batch:
            return {"bridged": 0, "skipped": 0}
        ok = skipped = 0
        try:
            from app.events.outbox import DomainEvent, emit_event
        except Exception:  # noqa: BLE001
            for ev in batch:
                ev["bridged"] = False
            return {"bridged": 0, "skipped": len(batch)}
        for ev in batch:
            try:
                await emit_event(DomainEvent(
                    event_type=ev["cloudevent_type"], organization_id=self.organization_id,
                    aggregate_type="oncotwin_patient", aggregate_id=ev["patient_id"] or "oncotwin",
                    payload={k: ev[k] for k in ("id", "seq", "type", "twin_day", "at", "payload")}))
                ev["bridged"] = True
                ok += 1
            except Exception as e:  # noqa: BLE001 — DB-less deployments keep the in-process log only
                ev["bridged"] = False
                skipped += 1
                if skipped == 1:
                    log.info("oncotwin.events.outbox_unavailable", error=str(e)[:120])
        METRICS.inc("oncotwin_events_bridged_total", ok, target="clincase_outbox")
        METRICS.inc("oncotwin_events_bridge_skipped_total", skipped, target="clincase_outbox")
        return {"bridged": ok, "skipped": skipped}

    def stats(self) -> dict[str, Any]:
        by_type: dict[str, int] = {}
        for e in self.log:
            by_type[e["type"]] = by_type.get(e["type"], 0) + 1
        return {"events_in_log": len(self.log), "sequence": self.seq, "by_type": by_type,
                "bridged_to_outbox": sum(1 for e in self.log if e["bridged"]),
                "not_bridged": sum(1 for e in self.log if e["bridged"] is False),
                "pending_bridge": len(self.pending_outbox), "subscribers": [p for p, _ in self._subs]}


def data_event_for(category: str) -> str:
    """Map an observation's signal category to its data-event type."""
    return {"lab": "LabResultCreated", "patient_reported": "SymptomReported", "wearable": "WearableObservationReceived",
            "home_device": "WearableObservationReceived"}.get(category, "FHIRObservationCreated")
