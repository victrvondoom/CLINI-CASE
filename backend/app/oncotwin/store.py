"""OncoTwin state store + hash-chained audit ledger.

Per organisation (tenant) the store holds:
  • the demo patients' data feeds (synthetic, re-generated deterministically
    from their scripts) and each patient's twin clock (`live_day`);
  • alerts raised by the twin and their clinician actions;
  • an append-only ledger in which every entry carries the SHA-256 of the
    previous entry — evaluations, alerts, clinician actions, handoffs,
    ingestions and demo-control events.

Ledger entries are written through to Postgres (`oncotwin_audit`) whenever a
database is configured, following ClinCase's fail-soft bootstrap pattern; the
in-process copy remains authoritative for the running demo.
"""
from __future__ import annotations

import copy
import hashlib
import json
import threading
import uuid
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Any

import structlog

from app.oncotwin.records import Observation, PatientRecord
from app.oncotwin.simulator.archetypes import DEMO_SCRIPTS, DEMO_START_DAY
from app.oncotwin.simulator.patients import SimScript, SimulationResult, simulate

log = structlog.get_logger()

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS oncotwin_audit (
    id              TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    seq             BIGINT NOT NULL,
    kind            TEXT NOT NULL,
    patient_id      TEXT,
    actor           TEXT,
    created_at      TIMESTAMPTZ NOT NULL,
    payload         JSONB NOT NULL,
    prev_hash       TEXT NOT NULL,
    hash            TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_oncotwin_audit_org ON oncotwin_audit(organization_id, created_at);
CREATE INDEX IF NOT EXISTS idx_oncotwin_audit_patient ON oncotwin_audit(organization_id, patient_id);
"""


async def ensure_schema() -> None:
    from app.db import db
    await db.execute(SCHEMA_SQL)


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _entry_hash(body: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()


class AuditLedger:
    GENESIS = "GENESIS"

    def __init__(self, organization_id: str):
        self.organization_id = organization_id
        self.entries: list[dict[str, Any]] = []
        self.tip = self.GENESIS
        self.genesis = self.GENESIS
        self._tip_loaded = False
        self._lock = threading.Lock()

    def append(self, kind: str, *, patient_id: str | None, actor: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            body = {
                "id": f"otl_{uuid.uuid4().hex[:16]}", "seq": len(self.entries) + 1, "kind": kind,
                "organization_id": self.organization_id, "patient_id": patient_id, "actor": actor,
                "created_at": _now(), "payload": payload, "prev_hash": self.tip,
            }
            entry = {**body, "hash": _entry_hash(body)}
            self.entries.append(entry)
            self.tip = entry["hash"]
            return entry

    def verify(self, entries: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        rows = self.entries if entries is None else entries
        prev = rows[0]["prev_hash"] if rows else self.genesis
        for i, e in enumerate(rows):
            body = {k: v for k, v in e.items() if k not in ("hash", "persisted")}
            if e["prev_hash"] != prev or _entry_hash(body) != e["hash"]:
                return {"valid": False, "entries": len(rows), "broken_at_seq": e["seq"], "broken_index": i}
            prev = e["hash"]
        return {"valid": True, "entries": len(rows), "tip": prev, "genesis": rows[0]["prev_hash"] if rows else self.genesis}

    async def load_tip(self) -> None:
        """Continue the chain from the last persisted entry for this org (if a DB is configured)."""
        if self._tip_loaded:
            return
        self._tip_loaded = True
        try:
            from app.db import db
            row = await db.fetchrow(
                "SELECT hash FROM oncotwin_audit WHERE organization_id = $1 ORDER BY created_at DESC, seq DESC LIMIT 1",
                self.organization_id,
            )
            if row and not self.entries:
                self.tip = self.genesis = row["hash"]
        except Exception as e:  # noqa: BLE001 — DB-less deployments keep the in-process chain
            log.info("oncotwin.ledger.db_unavailable", error=str(e)[:120])

    async def persist(self, entry: dict[str, Any]) -> None:
        try:
            from app.db import db
            await db.execute(
                """INSERT INTO oncotwin_audit (id, organization_id, seq, kind, patient_id, actor, created_at,
                                               payload, prev_hash, hash)
                   VALUES ($1,$2,$3,$4,$5,$6,$7::timestamptz,$8::jsonb,$9,$10) ON CONFLICT (id) DO NOTHING""",
                entry["id"], entry["organization_id"], entry["seq"], entry["kind"], entry["patient_id"],
                entry["actor"], datetime.fromisoformat(entry["created_at"].replace("Z", "+00:00")),
                json.dumps(entry["payload"], default=str), entry["prev_hash"], entry["hash"],
            )
            entry["persisted"] = True
        except Exception as e:  # noqa: BLE001 — fail-soft, like ClinCase's outbox/saga bootstraps
            entry["persisted"] = False
            log.info("oncotwin.ledger.persist_skipped", error=str(e)[:120])


@dataclass
class PatientState:
    script: SimScript
    sim: SimulationResult
    live_day: int
    data_version: int = 0
    ingested: list[Observation] = field(default_factory=list)
    injections: list[dict[str, Any]] = field(default_factory=list)
    history_cache: tuple[int, int, list[dict[str, Any]]] | None = None
    # (data_version, HistoryBundle) — extended incrementally as the twin clock advances
    bundle_cache: tuple[int, Any] | None = None
    # (data_version, until_day, per-day Living Twin State list)
    states_cache: tuple[int, int, list[dict[str, Any]]] | None = None
    # (data_version, live_day, as_of_day) → intelligence payload (bounded)
    intel_cache: dict[tuple[int, int, int], dict[str, Any]] = field(default_factory=dict)
    interventions: list[dict[str, Any]] = field(default_factory=list)
    last_committed_day: int | None = None

    def record(self) -> PatientRecord:
        rec = self.sim.record
        if not self.ingested:
            return rec
        obs = sorted(rec.observations + self.ingested, key=lambda o: (o.day, o.effective, o.id))
        return replace(rec, observations=obs)

    def invalidate(self) -> None:
        """New or changed data: drop every derived cache (history is recomputed on next read)."""
        self.data_version += 1
        self.history_cache = None
        self.bundle_cache = None
        self.states_cache = None
        self.intel_cache.clear()

    def resimulate(self, script: SimScript) -> None:
        self.script = script
        self.sim = simulate(script)
        self.invalidate()


class OrgTwinStore:
    def __init__(self, organization_id: str):
        from collections import deque

        from app.oncotwin.events import TwinEventBus

        self.organization_id = organization_id
        self.lock = threading.RLock()
        self.patients: dict[str, PatientState] = {}
        self.alerts: dict[str, dict[str, Any]] = {}
        self.handoffs: list[dict[str, Any]] = []
        self.ledger = AuditLedger(organization_id)
        self.bus = TwinEventBus(organization_id)
        self.dirty: dict[str, list[dict[str, Any]]] = {}      # patient → data events awaiting a twin update
        self.predictions: list[dict[str, Any]] = []           # MLOps prediction log (ground truth resolved later)
        self.agent_runs: deque = deque(maxlen=200)            # twin-graph traces (per-agent status + latency)
        self.llm_traces: list[dict[str, Any]] = []            # explanation-agent LLM calls (no patient text)
        self.drift_cache: tuple[tuple, dict[str, Any]] | None = None
        self.stress_runs: deque = deque(maxlen=20)
        self.bus.subscribe("data", self._on_data_event)
        self._seed()

    def _on_data_event(self, ev: dict[str, Any]) -> None:
        """Twin-update handler: a data event marks its patient dirty; `runtime.drain` performs ONE
        incremental update per batch instead of rebuilding the record per observation."""
        if ev["patient_id"]:
            self.dirty.setdefault(ev["patient_id"], []).append(ev)

    def _seed(self) -> None:
        for pid, script in DEMO_SCRIPTS.items():
            s = copy.deepcopy(script)
            self.patients[pid] = PatientState(script=s, sim=simulate(s), live_day=DEMO_START_DAY[pid])

    def patient(self, pid: str) -> PatientState:
        if pid not in self.patients:
            raise KeyError(pid)
        return self.patients[pid]

    def reset(self) -> None:
        """Demo reset: patients, clocks, alerts, predictions and traces. The audit ledger and the
        event log are history and are NOT reset."""
        with self.lock:
            self.patients.clear()
            self.alerts.clear()
            self.handoffs.clear()
            self.dirty.clear()
            self.predictions.clear()
            self.agent_runs.clear()
            self.drift_cache = None
            self._seed()


_STORES: dict[str, OrgTwinStore] = {}
_STORES_LOCK = threading.Lock()


def get_store(organization_id: str) -> OrgTwinStore:
    with _STORES_LOCK:
        if organization_id not in _STORES:
            _STORES[organization_id] = OrgTwinStore(organization_id)
        return _STORES[organization_id]
