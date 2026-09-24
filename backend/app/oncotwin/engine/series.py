"""As-of view of a patient: day-indexed signal arrays + treatment context.

`build_series(record, as_of_day)` only ever reads observations and events
dated on or before `as_of_day` — this is the no-look-ahead boundary that the
leakage test in tests/oncotwin pins down.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime

import numpy as np

from app.oncotwin.engine.quality import QualityFlag, SignalQuality, assess
from app.oncotwin.outcome import POST_DISCHARGE_EXCLUSION_DAYS
from app.oncotwin.records import ClinicalEvent, PatientProfile, PatientRecord
from app.oncotwin.signals import DAILY_SIGNALS, LAB_SIGNALS, SIGNALS
from app.oncotwin.simulator.regimens import REGIMENS, Regimen

INTERVENTION_KINDS = ("antibiotic", "hydration", "gcsf_dose", "careplan", "clinician_note")


@dataclass
class PatientSeries:
    profile: PatientProfile
    as_of_day: int
    values: dict[str, np.ndarray]                    # linear units, NaN = missing; index = day-1
    obs_ids: dict[str, list[str | None]]
    labs: dict[str, list[tuple[int, float, str]]]
    flags: list[QualityFlag]
    quality: dict[str, SignalQuality]
    dose_days: dict[int, float]
    gcsf_days: list[int]
    adherence: dict[int, tuple[int, int]]            # day -> (taken, scheduled)
    admissions: list[dict]
    interventions: list[ClinicalEvent]
    events: list[ClinicalEvent]
    regimen: Regimen
    planned_dose_days: list[int]
    reference_time: datetime | None = None
    _cache: dict = field(default_factory=dict, repr=False)

    @property
    def n(self) -> int:
        return self.as_of_day

    @property
    def first_dose_day(self) -> int | None:
        return min(self.dose_days) if self.dose_days else None

    @property
    def baseline_end_day(self) -> int:
        """Last day of the personal-baseline window (the day before C1D1)."""
        first = self.first_dose_day
        if first is None:
            planned = [d for d in self.planned_dose_days if d > 1]
            first = planned[0] if planned else None
        if first is None:
            return min(self.as_of_day, 14)
        return max(1, first - 1)

    def transformed(self, key: str) -> np.ndarray:
        cache_key = ("t", key)
        if cache_key not in self._cache:
            v = self.values[key]
            self._cache[cache_key] = np.log(np.maximum(v, 1e-6)) if SIGNALS[key].transform == "log" else v.copy()
        return self._cache[cache_key]

    def days_since_dose(self) -> np.ndarray:
        """Per day: days since the most recent chemo administration (NaN before C1)."""
        out = np.full(self.n, np.nan)
        last = None
        for day in range(1, self.n + 1):
            if day in self.dose_days:
                last = day
            if last is not None:
                out[day - 1] = day - last
        return out

    def gcsf_since_last_dose(self) -> np.ndarray:
        """Per day: 1 if a G-CSF dose was given since the last chemo administration."""
        out = np.zeros(self.n)
        last_dose = None
        given = False
        gset = set(self.gcsf_days)
        for day in range(1, self.n + 1):
            if day in self.dose_days:
                last_dose = day
                given = False
            if day in gset and last_dose is not None:
                given = True
            out[day - 1] = 1.0 if given else 0.0
        return out

    def adherence_7d(self) -> tuple[np.ndarray, np.ndarray]:
        """Per day: (7-day supportive-med adherence fraction, scheduled-dose count)."""
        frac = np.ones(self.n)
        count = np.zeros(self.n)
        for day in range(1, self.n + 1):
            taken = sched = 0
            for d in range(max(1, day - 6), day + 1):
                t, s = self.adherence.get(d, (0, 0))
                taken += t
                sched += s
            count[day - 1] = sched
            frac[day - 1] = taken / sched if sched else 1.0
        return frac, count

    def last_lab(self, key: str, day: int, max_age: int = 10) -> tuple[float | None, int | None, str | None]:
        best = None
        for d, v, oid in self.labs.get(key, []):
            if d <= day and day - d <= max_age and (best is None or d >= best[0]):
                best = (d, v, oid)
        return (best[1], best[0], best[2]) if best else (None, None, None)

    def acute_care_mask(self) -> np.ndarray:
        """True on days the patient is in, or just out of, visible acute care."""
        mask = np.zeros(self.n, dtype=bool)
        for adm in self.admissions:
            start = adm["day"]
            end = adm.get("discharge_day")
            end = self.n if end is None or end > self.as_of_day else end + POST_DISCHARGE_EXCLUSION_DAYS
            for d in range(start, min(end, self.n) + 1):
                mask[d - 1] = True
        return mask

    def in_acute_care_now(self) -> dict | None:
        for adm in self.admissions:
            end = adm.get("discharge_day")
            if adm["day"] <= self.as_of_day and (end is None or end > self.as_of_day):
                return adm
        return None


def build_series(record: PatientRecord, as_of_day: int, *, reference_time: datetime | None = None) -> PatientSeries:
    as_of_day = max(1, min(as_of_day, record.n_days))
    obs = record.observations_until(as_of_day)
    events = record.events_until(as_of_day)

    usable, flags, quality = assess(obs, as_of_day, reference_time=reference_time, signals=DAILY_SIGNALS)
    values: dict[str, np.ndarray] = {}
    obs_ids: dict[str, list[str | None]] = {}
    for key in DAILY_SIGNALS:
        arr = np.full(as_of_day, np.nan)
        ids: list[str | None] = [None] * as_of_day
        for d, o in usable.get(key, {}).items():
            arr[d - 1] = o.value
            ids[d - 1] = o.id
        values[key] = arr
        obs_ids[key] = ids

    labs: dict[str, list[tuple[int, float, str]]] = {k: [] for k in LAB_SIGNALS}
    for o in obs:
        if o.signal in labs and not math.isnan(o.value):
            lo, hi = SIGNALS[o.signal].plausible
            if lo <= o.value <= hi:
                labs[o.signal].append((o.day, o.value, o.id))
    for k in labs:
        labs[k].sort()

    dose_days: dict[int, float] = {}
    gcsf_days: list[int] = []
    adherence: dict[int, tuple[int, int]] = {}
    admissions: list[dict] = []
    interventions: list[ClinicalEvent] = []
    for e in events:
        if e.kind == "chemo_dose" and e.detail.get("status", "completed") == "completed":
            dose_days[e.day] = float(e.detail.get("dose_scale", 1.0))
        elif e.kind == "gcsf_dose":
            gcsf_days.append(e.day)
        elif e.kind == "supportive_dose" and e.detail.get("scheduled"):
            t, s = adherence.get(e.day, (0, 0))
            adherence[e.day] = (t + (1 if e.detail.get("status") == "completed" else 0), s + 1)
        elif e.kind == "encounter" and e.detail.get("qualifying"):
            discharge = e.detail.get("discharge_day")
            admissions.append({
                "id": e.id, "day": e.day, "condition": e.detail.get("condition"),
                "discharge_day": discharge if (discharge is not None and discharge <= as_of_day) else None,
                "display": e.display,
            })
        if e.kind in INTERVENTION_KINDS or (e.kind == "encounter" and not e.detail.get("qualifying")):
            if e.day >= 1:
                interventions.append(e)

    return PatientSeries(
        profile=record.profile, as_of_day=as_of_day, values=values, obs_ids=obs_ids, labs=labs,
        flags=flags, quality=quality, dose_days=dose_days, gcsf_days=sorted(gcsf_days),
        adherence=adherence, admissions=admissions, interventions=interventions, events=events,
        regimen=REGIMENS[record.profile.regimen_code], planned_dose_days=record.planned_dose_days,
        reference_time=reference_time,
    )
