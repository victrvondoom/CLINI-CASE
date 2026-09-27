"""AquaHealth state store — per-organisation waterbodies and observations.

Follows the OncoTwin store's contract exactly (see `app/oncotwin/store.py`):
the in-process copy is authoritative for the running demo, and every write is
mirrored through to Postgres when a database is configured. ClinCase already
boots fail-soft without a DB (`app/main.py` logs `db_unavailable` and carries
on), so AquaHealth must stay usable in that mode too — otherwise the module
would be undemonstrable on exactly the deployments ClinCase supports.

Nothing here touches the `cases` table or any other existing ClinCase table.
AquaHealth adds two tables of its own and leaves the clinical schema alone.
"""
from __future__ import annotations

import threading

import structlog

from app.aquahealth.models import Observation, Waterbody
from app.aquahealth.vocab import ReviewStatus

log = structlog.get_logger()

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS aquahealth_waterbodies (
    id              TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    name            TEXT NOT NULL,
    kind            TEXT NOT NULL,
    locality        TEXT,
    latitude        DOUBLE PRECISION,
    longitude       DOUBLE PRECISION,
    is_demo         BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL,
    payload         JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_aqua_wb_org
    ON aquahealth_waterbodies(organization_id, created_at);

CREATE TABLE IF NOT EXISTS aquahealth_observations (
    id              TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    reference       TEXT NOT NULL,
    waterbody_id    TEXT NOT NULL,
    observed_at     TIMESTAMPTZ NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL,
    status          TEXT,
    review_status   TEXT NOT NULL,
    source          TEXT NOT NULL,
    is_demo         BOOLEAN NOT NULL DEFAULT FALSE,
    payload         JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_aqua_obs_org
    ON aquahealth_observations(organization_id, observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_aqua_obs_wb
    ON aquahealth_observations(organization_id, waterbody_id, observed_at);
CREATE INDEX IF NOT EXISTS idx_aqua_obs_review
    ON aquahealth_observations(organization_id, review_status);
"""


async def ensure_schema() -> None:
    """Idempotent schema bootstrap, called from the app lifespan."""
    from app.db import db

    await db.execute(SCHEMA_SQL)


class OrgAquaStore:
    """One organisation's AquaHealth data.

    Thread-safe because FastAPI may serve concurrent requests and the
    reference counter must not hand out duplicate AQUA-xxxxxx ids.
    """

    def __init__(self, organization_id: str) -> None:
        self.organization_id = organization_id
        self._waterbodies: dict[str, Waterbody] = {}
        self._observations: dict[str, Observation] = {}
        self._lock = threading.Lock()
        self._seq = 0
        self.demo_seeded = False
        self.loaded_from_db = False

    # --- identifiers -------------------------------------------------------

    def next_reference(self) -> str:
        """Allocate the next human-facing AQUA-000123 reference."""
        with self._lock:
            self._seq += 1
            return f"AQUA-{self._seq:06d}"

    def note_reference(self, reference: str) -> None:
        """Advance the counter past an externally-supplied reference.

        Used when rehydrating from Postgres so a restart never reissues an
        id that is already on a stored observation.
        """
        if not reference.startswith("AQUA-"):
            return
        try:
            seq = int(reference.removeprefix("AQUA-"))
        except ValueError:
            return
        with self._lock:
            self._seq = max(self._seq, seq)

    # --- waterbodies -------------------------------------------------------

    def add_waterbody(self, wb: Waterbody) -> Waterbody:
        with self._lock:
            self._waterbodies[wb.id] = wb
        return wb

    def waterbody(self, waterbody_id: str) -> Waterbody | None:
        return self._waterbodies.get(waterbody_id)

    def waterbodies(self) -> list[Waterbody]:
        return sorted(self._waterbodies.values(), key=lambda w: w.name.lower())

    def find_waterbody_by_name(self, name: str) -> Waterbody | None:
        target = name.strip().lower()
        for wb in self._waterbodies.values():
            if wb.name.strip().lower() == target:
                return wb
        return None

    # --- observations ------------------------------------------------------

    def put_observation(self, obs: Observation) -> Observation:
        with self._lock:
            self._observations[obs.id] = obs
        return obs

    def observation(self, observation_id: str) -> Observation | None:
        return self._observations.get(observation_id)

    def observations(
        self,
        *,
        waterbody_id: str | None = None,
        review_status: ReviewStatus | None = None,
        include_demo: bool = True,
    ) -> list[Observation]:
        """Newest first. Filters applied in-process (the dataset is small)."""
        rows = list(self._observations.values())
        if waterbody_id is not None:
            rows = [o for o in rows if o.waterbody_id == waterbody_id]
        if review_status is not None:
            rows = [o for o in rows if o.review_status == review_status]
        if not include_demo:
            rows = [o for o in rows if not o.is_demo]
        rows.sort(key=lambda o: o.observed_at, reverse=True)
        return rows

    def history_for(self, waterbody_id: str) -> list[Observation]:
        """Chronological history at one waterbody — the trend agent's input."""
        rows = [o for o in self._observations.values() if o.waterbody_id == waterbody_id]
        rows.sort(key=lambda o: o.observed_at)
        return rows

    def clear_demo_data(self) -> int:
        """Remove only demo rows. Real citizen observations are never touched.

        This is what makes the demo dataset separable: a reviewer can reset the
        demonstration without risking a real contribution.
        """
        with self._lock:
            demo_obs = [k for k, v in self._observations.items() if v.is_demo]
            for k in demo_obs:
                del self._observations[k]
            demo_wb = [k for k, v in self._waterbodies.items() if v.is_demo]
            for k in demo_wb:
                del self._waterbodies[k]
            self.demo_seeded = False
        return len(demo_obs)


# --- registry ----------------------------------------------------------------

_STORES: dict[str, OrgAquaStore] = {}
_REGISTRY_LOCK = threading.Lock()


def get_store(organization_id: str) -> OrgAquaStore:
    """Return (creating if needed) the store for one organisation."""
    with _REGISTRY_LOCK:
        store = _STORES.get(organization_id)
        if store is None:
            store = OrgAquaStore(organization_id)
            _STORES[organization_id] = store
        return store


def reset_stores() -> None:
    """Drop every in-process store. Test-only helper."""
    with _REGISTRY_LOCK:
        _STORES.clear()


# --- Postgres write-through (fail-soft) --------------------------------------


async def persist_waterbody(wb: Waterbody) -> bool:
    """Mirror a waterbody to Postgres. Never raises.

    Returns True when the row was written, False when the DB was unavailable —
    the caller keeps the in-process copy either way, matching the OncoTwin
    ledger's fail-soft contract.
    """
    try:
        from app.db import db

        await db.execute(
            """INSERT INTO aquahealth_waterbodies
                   (id, organization_id, name, kind, locality, latitude, longitude,
                    is_demo, created_at, payload)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9::timestamptz,$10::jsonb)
               ON CONFLICT (id) DO UPDATE SET
                   name = EXCLUDED.name,
                   locality = EXCLUDED.locality,
                   payload = EXCLUDED.payload""",
            wb.id,
            wb.organization_id,
            wb.name,
            wb.kind,
            wb.locality,
            wb.location.latitude if wb.location else None,
            wb.location.longitude if wb.location else None,
            wb.is_demo,
            wb.created_at,
            wb.model_dump_json(),
        )
        return True
    except Exception as e:  # noqa: BLE001 — fail-soft, like ClinCase's outbox/saga bootstraps
        log.info("aquahealth.waterbody.persist_skipped", error=str(e)[:120])
        return False


async def persist_observation(obs: Observation) -> bool:
    """Mirror an observation (with its assessment and review) to Postgres.

    Never raises. The full record travels in `payload` so the assessment and
    the human review survive a restart together with the observation — a
    review decision that outlived its assessment would be unauditable.
    """
    try:
        from app.db import db

        status = obs.effective_status.value if obs.assessment else None
        await db.execute(
            """INSERT INTO aquahealth_observations
                   (id, organization_id, reference, waterbody_id, observed_at,
                    created_at, status, review_status, source, is_demo, payload)
               VALUES ($1,$2,$3,$4,$5::timestamptz,$6::timestamptz,$7,$8,$9,$10,$11::jsonb)
               ON CONFLICT (id) DO UPDATE SET
                   status = EXCLUDED.status,
                   review_status = EXCLUDED.review_status,
                   payload = EXCLUDED.payload""",
            obs.id,
            obs.organization_id,
            obs.reference,
            obs.waterbody_id,
            obs.observed_at,
            obs.created_at,
            status,
            obs.review_status.value,
            obs.source.value,
            obs.is_demo,
            obs.model_dump_json(),
        )
        return True
    except Exception as e:  # noqa: BLE001 — fail-soft
        log.info("aquahealth.observation.persist_skipped", error=str(e)[:120])
        return False


async def load_from_db(organization_id: str) -> int:
    """Rehydrate one organisation's store from Postgres.

    Called lazily on first access per process. Returns the number of
    observations loaded, or 0 when no DB is configured. Rows that fail to
    validate are skipped individually with a log line rather than aborting the
    whole load — one bad row must not hide the rest of the dataset.
    """
    store = get_store(organization_id)
    loaded = 0
    try:
        from app.db import db

        wb_rows = await db.fetch(
            "SELECT payload FROM aquahealth_waterbodies WHERE organization_id = $1",
            organization_id,
        )
        for r in wb_rows:
            try:
                store.add_waterbody(Waterbody.model_validate_json(r["payload"]))
            except Exception as e:  # noqa: BLE001
                log.info("aquahealth.waterbody.load_skipped", error=str(e)[:120])

        obs_rows = await db.fetch(
            """SELECT payload FROM aquahealth_observations
               WHERE organization_id = $1 ORDER BY observed_at""",
            organization_id,
        )
        for r in obs_rows:
            try:
                obs = Observation.model_validate_json(r["payload"])
            except Exception as e:  # noqa: BLE001
                log.info("aquahealth.observation.load_skipped", error=str(e)[:120])
                continue
            store.put_observation(obs)
            store.note_reference(obs.reference)
            loaded += 1

        if any(o.is_demo for o in store.observations()):
            store.demo_seeded = True
        store.loaded_from_db = True
    except Exception as e:  # noqa: BLE001 — DB-less mode is supported
        log.info("aquahealth.load.skipped", error=str(e)[:120])
    return loaded
