"""Data-quality engine.

Detects, per signal and per day, problems that must be surfaced BEFORE a
prediction is trusted, and removes values that are physically impossible or
produced by a stuck sensor from the analysis series:

  implausible — outside the physiologically plausible range (signals.py)
  stuck       — identical wearable readings on ≥N consecutive days
  conflict    — same-day readings from different sources that disagree
  gap         — days with no reading in the recent window (completeness)
  stale       — latest reading older than the signal's expected cadence

Completeness and freshness metrics computed here feed the prediction
confidence directly; nothing downstream uses hard-coded quality numbers.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.oncotwin.records import Observation, day_to_datetime
from app.oncotwin.signals import MODEL_SIGNALS, SIGNALS

# Consecutive identical readings needed to call a sensor "stuck". Chosen per
# signal so that the chance of a natural repeat at the device's reporting
# resolution, over an 8-week course, stays below ~1 % (e.g. sleep reported to
# 0.1 h with ~0.5 h day-to-day spread repeats 3× by chance in ~16 % of courses).
STUCK_RUN = {"resting_hr": 5, "hrv_sdnn": 4, "spo2": 4, "temperature": 4, "sleep_hours": 4, "steps": 3}
STUCK_ELIGIBLE = tuple(STUCK_RUN)
CONFLICT_REL = {"weight": 0.03}   # >3 % disagreement between same-day sources
CONFLICT_REL_DEFAULT = 0.10
COMPLETENESS_WINDOW_DAYS = 7


@dataclass
class QualityFlag:
    kind: str
    signal: str
    days: list[int]
    message: str
    severity: str                   # "info" | "warning" | "critical"
    observation_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "signal": self.signal, "days": self.days, "message": self.message,
                "severity": self.severity, "observation_ids": self.observation_ids}


@dataclass
class SignalQuality:
    signal: str
    completeness_7d: float          # fraction of the last 7 days with a usable reading
    last_day: int | None
    last_effective: str | None
    hours_since_last: float | None
    fresh: bool
    freshness: float                # 1.0 fresh → 0.0 very stale

    def to_dict(self) -> dict[str, Any]:
        return {
            "signal": self.signal, "completeness_7d": round(self.completeness_7d, 3),
            "last_day": self.last_day, "last_effective": self.last_effective,
            "hours_since_last": None if self.hours_since_last is None else round(self.hours_since_last, 1),
            "fresh": self.fresh, "freshness": round(self.freshness, 3),
        }


def _primary_source_rank(o: Observation) -> int:
    """Lower is preferred when several sources report the same signal/day."""
    if o.source.startswith("api/"):
        return 0
    if o.source.startswith(("wearable/", "home/", "pro/")):
        return 1
    return 2   # clinic / other


def select_daily(
    observations: list[Observation], signal: str, as_of_day: int,
) -> tuple[dict[int, Observation], list[QualityFlag]]:
    """Pick one observation per day for a daily signal and flag conflicts."""
    by_day: dict[int, list[Observation]] = {}
    for o in observations:
        if o.signal == signal and 1 <= o.day <= as_of_day:
            by_day.setdefault(o.day, []).append(o)
    chosen: dict[int, Observation] = {}
    flags: list[QualityFlag] = []
    tol = CONFLICT_REL.get(signal, CONFLICT_REL_DEFAULT)
    for day, obs in by_day.items():
        obs.sort(key=lambda o: (_primary_source_rank(o), o.effective))
        chosen[day] = obs[0]
        others = [o for o in obs[1:] if o.source != obs[0].source]
        for other in others:
            ref = abs(obs[0].value) or 1.0
            if abs(other.value - obs[0].value) / ref > tol:
                spec = SIGNALS[signal]
                flags.append(QualityFlag(
                    kind="conflict", signal=signal, days=[day], severity="warning",
                    observation_ids=[obs[0].id, other.id],
                    message=(
                        f"Conflicting {spec.label.lower()} on Day {day}: {obs[0].value:g} {spec.unit_display} "
                        f"({obs[0].source}) vs {other.value:g} {spec.unit_display} ({other.source}). "
                        f"Twin uses the {obs[0].source.split('/')[0]} reading; reconcile the record."
                    ),
                ))
    return chosen, flags


def assess(
    observations: list[Observation], as_of_day: int, *, reference_time: datetime | None = None,
    signals: tuple[str, ...] | None = None,
) -> tuple[dict[str, dict[int, Observation]], list[QualityFlag], dict[str, SignalQuality]]:
    """Return (usable observation per signal/day, flags, per-signal quality)."""
    ref = reference_time or day_to_datetime(as_of_day, 23, 59)
    keys = signals or tuple(k for k, s in SIGNALS.items() if s.category != "lab")
    usable: dict[str, dict[int, Observation]] = {}
    flags: list[QualityFlag] = []
    quality: dict[str, SignalQuality] = {}

    for key in keys:
        spec = SIGNALS[key]
        chosen, conflict_flags = select_daily(observations, key, as_of_day)
        flags.extend(conflict_flags)

        # implausible values
        lo, hi = spec.plausible
        bad = {d: o for d, o in chosen.items() if not (lo <= o.value <= hi)}
        for d, o in sorted(bad.items()):
            flags.append(QualityFlag(
                kind="implausible", signal=key, days=[d], severity="warning", observation_ids=[o.id],
                message=(f"{spec.label} of {o.value:g} {spec.unit_display} on Day {d} is outside the "
                         f"plausible range {lo:g}–{hi:g}; treated as a sensor artefact and excluded."),
            ))
            del chosen[d]

        # stuck sensor: identical consecutive readings
        if key in STUCK_ELIGIBLE and chosen:
            need = STUCK_RUN[key]
            days_sorted = sorted(chosen)
            run = [days_sorted[0]]
            runs: list[list[int]] = []
            for d in days_sorted[1:]:
                if d == run[-1] + 1 and chosen[d].value == chosen[run[-1]].value:
                    run.append(d)
                else:
                    if len(run) >= need:
                        runs.append(run)
                    run = [d]
            if len(run) >= need:
                runs.append(run)
            for r in runs:
                flags.append(QualityFlag(
                    kind="stuck", signal=key, days=r, severity="warning",
                    observation_ids=[chosen[d].id for d in r],
                    message=(f"{spec.label} reported exactly {chosen[r[0]].value:g} {spec.unit_display} on "
                             f"{len(r)} consecutive days (Day {r[0]}–{r[-1]}) — possible stuck or off-body "
                             f"sensor. Repeated values after Day {r[0]} are excluded; verify the device."),
                ))
                for d in r[1:]:
                    del chosen[d]
        usable[key] = chosen

        # completeness + freshness
        window = range(max(1, as_of_day - COMPLETENESS_WINDOW_DAYS + 1), as_of_day + 1)
        present = sum(1 for d in window if d in chosen)
        completeness = present / len(window)
        last_day = max(chosen) if chosen else None
        last_eff = chosen[last_day].effective if last_day else None
        hours = None
        fresh = False
        freshness = 0.0
        if last_eff:
            eff = datetime.fromisoformat(last_eff.replace("Z", "+00:00"))
            hours = max(0.0, (ref - eff).total_seconds() / 3600.0)
            slack = spec.cadence_hours + 12.0
            fresh = hours <= slack
            freshness = 1.0 if fresh else max(0.0, 1.0 - (hours - slack) / (2.0 * spec.cadence_hours))
        quality[key] = SignalQuality(key, completeness, last_day, last_eff, hours, fresh, freshness)

        # Display-only signals (CGM, diastolic BP) are flagged only for patients
        # who actually have that device; a model signal is always expected.
        monitored = key in MODEL_SIGNALS or (key in ("glucose_cgm", "dbp") and bool(chosen))
        if monitored:
            missing_days = [d for d in window if d not in chosen]
            if len(missing_days) >= 2 and as_of_day >= 3:
                flags.append(QualityFlag(
                    kind="gap", signal=key, days=missing_days, severity="info" if completeness >= 0.5 else "warning",
                    message=(f"{spec.label}: {len(missing_days)} of the last {len(window)} days have no usable "
                             f"reading (completeness {completeness:.0%})."),
                ))
            if last_eff and not fresh:
                flags.append(QualityFlag(
                    kind="stale", signal=key, days=[last_day] if last_day else [], severity="warning",
                    message=(f"{spec.label} last reported {hours:.0f} h ago (expected every "
                             f"{spec.cadence_hours:.0f} h) — current state for this signal is uncertain."),
                ))
    return usable, flags, quality
