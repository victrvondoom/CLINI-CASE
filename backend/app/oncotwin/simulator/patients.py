"""Synthetic longitudinal patient generator (every output is labelled SYNTHETIC).

`simulate(script)` walks a patient day by day through

    baseline → diagnosis → treatment → (stable | physiological deviation
    → deterioration → acute care | intervention → recovery)

using the mechanistic model in `physiology.py`, and emits two things:

  • a `PatientRecord` — the observations and clinical events a real data
    feed would deliver (wearables, home devices, PROs, labs, EHR events),
    each with provenance and an ISO timestamp;
  • a `SimulationTruth` — latent loads and true event onsets, used ONLY for
    training labels, validation and tests.

Determinism: every day draws from its own RNG keyed on (seed, day) and always
consumes the same number of variates, so changing a FUTURE event (e.g. the
"introduce deterioration" demo control) never alters PAST observations.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Literal

import numpy as np

from app.oncotwin.outcome import QUALIFYING_CONDITIONS
from app.oncotwin.records import (
    ANCHOR_DATE,
    ClinicalEvent,
    Observation,
    PatientProfile,
    PatientRecord,
    SimulationTruth,
    day_to_iso,
)
from app.oncotwin.signals import DAILY_SIGNALS, SIGNALS
from app.oncotwin.simulator import physiology as P
from app.oncotwin.simulator.regimens import REGIMENS, RXNORM, SUPPORTIVE

ICD10 = "http://hl7.org/fhir/sid/icd-10-cm"
SNOMED = "http://snomed.info/sct"
LOINC = "http://loinc.org"

WATCH_SIGNALS = ("resting_hr", "hrv_sdnn", "spo2", "steps", "sleep_hours")
HOME_SIGNALS = ("weight", "sbp", "dbp")


@dataclass
class InfectionSeed:
    day: int
    size: float
    virulence: float = 0.0
    pneumonia: bool = False


@dataclass
class QualityIssue:
    kind: Literal["gap", "stuck", "implausible", "conflict"]
    day: int
    n_days: int = 1
    signal: str | None = None


@dataclass
class SimScript:
    patient_id: str
    label: str
    seed: int
    archetype: str
    age: int
    sex: Literal["female", "male"]
    cancer: str
    icd10: str
    stage: str
    biomarkers: dict[str, str]
    regimen: str
    payer_id: str = "aetna"
    comorbidities: list[dict[str, str]] = field(default_factory=list)
    ecog: int = 1
    diabetic: bool = False
    narrative: str = ""
    n_days: int = 56
    treatment_start: int = 14
    sensitivity: float = 1.0
    circ0: float = 4.5
    infection_growth: float = 0.60
    gi_sensitivity: float = 1.0
    baselines: dict[str, float] | None = None       # linear-unit overrides
    infection_seeds: list[InfectionSeed] = field(default_factory=list)
    adherence_plan: list[tuple[int, float]] = field(default_factory=lambda: [(1, 0.95)])
    gi_insults: list[tuple[int, float, int]] = field(default_factory=list)   # (day, size, n_days)
    interventions: list[tuple[int, str]] = field(default_factory=list)
    extra_lab_days: list[int] = field(default_factory=list)
    quality_issues: list[QualityIssue] = field(default_factory=list)
    isolated_blips: list[tuple[int, dict[str, float]]] = field(default_factory=list)
    stochastic_infections: bool = False
    stochastic_seed_rate: float = 0.05
    primary_gcsf: bool = False
    missing_wear: float = 0.04
    missing_temp: float = 0.06
    missing_home: float = 0.10
    missing_pro: float = 0.18


@dataclass
class SimulationResult:
    record: PatientRecord
    truth: SimulationTruth
    script: SimScript


# =============================================================================
# Helpers
# =============================================================================


def _baselines(script: SimScript, rng: np.random.Generator) -> dict[str, float]:
    """Patient's true baseline per daily signal, in LINEAR units."""
    age_adj = max(0.0, script.age - 50)
    b = {
        "resting_hr": float(rng.uniform(56, 80)),
        "hrv_sdnn": float(max(18.0, rng.uniform(28, 62) - 0.3 * age_adj)),
        "temperature": float(rng.normal(36.55, 0.12)),
        "spo2": float(rng.uniform(95.8, 98.2)),
        "steps": float(max(1800.0, rng.uniform(3800, 9000) - 60 * age_adj - 900 * script.ecog)),
        "sleep_hours": float(rng.uniform(6.3, 7.8)),
        "weight": float(rng.uniform(58, 78) if script.sex == "female" else rng.uniform(68, 95)),
        "sbp": float(rng.uniform(112, 138)),
        "symptom_score": float(rng.uniform(0.6, 1.8)),
        "glucose_cgm": float(rng.uniform(118, 150)),
    }
    b["dbp"] = b["sbp"] * 0.63
    if script.baselines:
        b.update(script.baselines)
    return b


def _to_transformed(key: str, value: float) -> float:
    return math.log(max(value, 1e-6)) if SIGNALS[key].transform == "log" else value


def _from_transformed(key: str, value: float) -> float:
    return math.exp(value) if SIGNALS[key].transform == "log" else value


def _adherence_level(plan: list[tuple[int, float]], day: int) -> float:
    level = plan[0][1] if plan else 1.0
    for start, lvl in sorted(plan):
        if day >= start:
            level = lvl
    return level


def _round(key: str, value: float) -> float:
    return round(value, SIGNALS[key].decimals)


def _code(system: str, code: str, display: str) -> dict[str, str]:
    return {"system": system, "code": code, "display": display}


# =============================================================================
# Simulation
# =============================================================================


def simulate(script: SimScript) -> SimulationResult:
    reg = REGIMENS[script.regimen]
    base_rng = np.random.default_rng([script.seed, 0])
    base_lin = _baselines(script, base_rng)
    base_t = {k: _to_transformed(k, v) for k, v in base_lin.items()}
    hgb0 = float(base_rng.uniform(12.2, 14.2) if script.sex == "female" else base_rng.uniform(13.2, 15.4))
    plt0 = float(base_rng.uniform(210, 320))
    cr0 = float(base_rng.uniform(0.7, 1.05))

    pid = script.patient_id
    n = script.n_days
    slope = reg.myelotox * script.sensitivity * P.SLOPE_PER_MYELOTOX
    circ0 = np.array([script.circ0])
    fstate = P.FribergState.steady(circ0)

    observations: list[Observation] = []
    events: list[ClinicalEvent] = []
    ev_counter = [0]

    def add_event(day: int, kind: str, display: str, fhir_type: str, *, code=None, hour=9, **detail) -> None:
        ev_counter[0] += 1
        events.append(ClinicalEvent(
            id=f"{pid}-ev{ev_counter[0]:03d}", day=day, kind=kind, display=display,  # type: ignore[arg-type]
            effective=day_to_iso(day, hour), fhir_type=fhir_type, code=code, detail=dict(detail),
        ))

    _pre_treatment_history(script, reg, add_event)

    # ---- schedule state ------------------------------------------------------
    planned = [script.treatment_start + k * reg.cycle_days
               for k in range(0, 1 + (n - script.treatment_start) // reg.cycle_days)
               if script.treatment_start + k * reg.cycle_days <= n]
    next_dose_queue = list(planned)
    dose_days: dict[int, float] = {}
    gcsf_days: list[int] = []
    dose_scale = 1.0
    secondary_gcsf = script.primary_gcsf or reg.myelo_tier == "high"
    last_dose_day: int | None = None

    interventions: dict[int, list[str]] = {}
    for d, kind in script.interventions:
        interventions.setdefault(d, []).append(kind)
    seeds = {s.day: s for s in script.infection_seeds}
    gi_insult_days: dict[int, float] = {}
    for d0, size, nd in script.gi_insults:
        for k in range(nd):
            gi_insult_days[d0 + k] = gi_insult_days.get(d0 + k, 0.0) + size
    blips = {d: deltas for d, deltas in script.isolated_blips}
    lab_days = set(script.extra_lab_days) | {script.treatment_start - 4}
    adherence_override: float | None = None

    inf = np.zeros(1)
    deh = np.zeros(1)
    fat = np.zeros(1)
    virulence = 0.0
    pneumonia = False
    abx_until = 0
    activity_until = 0
    admitted_until = 0
    event_onsets: list[dict] = []
    admitted_days: list[int] = []
    truth_I, truth_D, truth_F, truth_anc = [], [], [], []
    stuck_values: dict[str, float] = {}

    for day in range(1, n + 1):
        rng = np.random.default_rng([script.seed, day])
        u_miss = rng.uniform(size=5)            # watch, temp, home, pro, cgm
        z = rng.normal(size=len(DAILY_SIGNALS))
        u_seed = rng.uniform(size=4)            # stochastic infection
        u_doses = rng.uniform(size=2)
        z_lab = rng.normal(size=5)

        admitted = day <= admitted_until
        todays = interventions.get(day, [])

        # ---- treatment administration ------------------------------------
        dose_today = 0.0
        if next_dose_queue and day >= next_dose_queue[0]:
            if admitted:
                next_dose_queue[0] = admitted_until + 1
            else:
                next_dose_queue.pop(0)
                dose_today = dose_scale
                dose_days[day] = dose_scale
                last_dose_day = day
                lab_days.add(day)
                for drug in reg.drugs:
                    add_event(day, "chemo_dose", f"{drug.name} administered (cycle {len(dose_days)}, {int(dose_scale * 100)}% dose)",
                              "MedicationAdministration", code=_code(RXNORM, drug.rxnorm, drug.name),
                              hour=10, cycle=len(dose_days), dose_scale=dose_scale, route=drug.route,
                              status="completed")
                if secondary_gcsf:
                    gcsf_days.append(day + 1)
                    add_event(day + 1, "gcsf_dose", "pegfilgrastim 6 mg SC (G-CSF prophylaxis)",
                              "MedicationAdministration",
                              code=_code(RXNORM, SUPPORTIVE["pegfilgrastim"].rxnorm, "pegfilgrastim"),
                              hour=10, indication="prophylaxis", status="completed")

        dsd = (day - last_dose_day) if last_dose_day is not None else None

        # ---- interventions (clinician actions recorded in the EHR) --------
        abx_boost = 0.0
        hydration_boost = 0.0
        for kind in todays:
            if kind == "urgent_eval_abx":
                abx_until = day + 6
                lab_days.add(day)
                add_event(day, "encounter", "Urgent oncology clinic evaluation (twin early warning)",
                          "Encounter", code=_code("http://terminology.hl7.org/CodeSystem/v3-ActCode", "AMB", "ambulatory"),
                          hour=11, encounter_class="AMB", qualifying=False, reason="Early-warning review")
                for key in ("amoxicillin_clavulanate", "ciprofloxacin"):
                    drug = SUPPORTIVE[key]
                    add_event(day, "antibiotic", f"{drug.name} PO × 7 days (empiric outpatient therapy)",
                              "MedicationRequest", code=_code(RXNORM, drug.rxnorm, drug.name), hour=12,
                              status="active", duration_days=7)
            elif kind == "gcsf":
                gcsf_days.append(day)
                add_event(day, "gcsf_dose", "pegfilgrastim 6 mg SC", "MedicationAdministration",
                          code=_code(RXNORM, SUPPORTIVE["pegfilgrastim"].rxnorm, "pegfilgrastim"),
                          hour=12, indication="treatment", status="completed")
            elif kind == "gcsf_secondary":
                secondary_gcsf = True
                add_event(day, "careplan", "CarePlan revised: add pegfilgrastim secondary prophylaxis from next cycle",
                          "CarePlan", hour=13, change="add_gcsf_secondary_prophylaxis")
            elif kind == "hydration":
                hydration_boost = 1.0
                lab_days.add(day)
                add_event(day, "hydration", "IV fluids 1 L 0.9% NaCl at infusion center", "MedicationAdministration",
                          code=_code(RXNORM, SUPPORTIVE["iv_fluids"].rxnorm, "sodium chloride 0.9%"),
                          hour=11, status="completed")
            elif kind == "adherence_support":
                adherence_override = 0.95
                add_event(day, "clinician_note", "Nurse navigator call: supportive-medication adherence plan",
                          "Communication", hour=15)
            elif kind == "dose_reduction":
                dose_scale = 0.8
                add_event(day, "careplan", "CarePlan revised: 20% dose reduction from next cycle",
                          "CarePlan", hour=13, change="dose_reduction_20pct")
            elif kind == "activity":
                activity_until = day + 14
                add_event(day, "careplan", "Exercise-oncology referral: supervised activity program",
                          "CarePlan", hour=13, change="activity_program")
        if day <= abx_until:
            abx_boost = 0.8
        if admitted:
            abx_boost = max(abx_boost, 1.2)
            hydration_boost = max(hydration_boost, 0.9)
            virulence = 0.0          # inpatient therapy controls the pathogen
            admitted_days.append(day)
        activity_boost = 0.8 if day <= activity_until else 0.0

        # ---- supportive-medication adherence (observed) --------------------
        sched_last = (reg.oral_days + 2) if reg.oral_days else 4
        scheduled = dsd is not None and 0 <= dsd <= sched_last and not admitted
        level = adherence_override if adherence_override is not None else _adherence_level(script.adherence_plan, day)
        if scheduled:
            taken = [bool(u_doses[i] < level) for i in range(2)]
            adherence_today = sum(taken) / 2.0
            drug = SUPPORTIVE["loperamide"] if (reg.oral_days and dsd is not None and dsd > 4) else SUPPORTIVE["ondansetron"]
            for i, ok in enumerate(taken):
                add_event(day, "supportive_dose", f"{drug.name} dose {'taken' if ok else 'missed'}",
                          "MedicationAdministration", code=_code(RXNORM, drug.rxnorm, drug.name),
                          hour=8 + 12 * i, status="completed" if ok else "not-done", scheduled=True)
        else:
            adherence_today = 1.0

        # ---- neutrophils (morning) ----------------------------------------
        anc_morning = float(fstate.circ[0])
        gcsf_active = any(g < day <= g + P.GCSF_ACTIVE_DAYS for g in gcsf_days)
        fstate = P.friberg_advance_day(fstate, circ0, np.array([slope]), dose_scale=dose_today, gcsf_active=gcsf_active)

        # ---- infection seeding ---------------------------------------------
        seed_size = 0.0
        if day in seeds:
            s = seeds[day]
            seed_size = s.size
            virulence = max(virulence, s.virulence)
            pneumonia = pneumonia or s.pneumonia
        elif script.stochastic_infections and not admitted and inf[0] < 0.05:
            hazard = script.stochastic_seed_rate * float(P.neutropenia_factor(anc_morning)) + P.BACKGROUND_INFECTION_HAZARD
            if u_seed[0] < hazard:
                seed_size = 0.06 + 0.26 * u_seed[1]
                virulence = P.seed_virulence(float(u_seed[2]))
                pneumonia = u_seed[3] < 0.3
        if inf[0] < 0.02 and seed_size == 0.0:
            virulence = 0.0
            pneumonia = False

        drv = P.DayDrivers(
            days_since_dose=dsd, emeto=reg.emeto, diarrhea=reg.diarrhea, fatigue=reg.fatigue,
            oral_days=reg.oral_days, adherence=adherence_today, infection_seed=seed_size,
            virulence=virulence, abx_boost=abx_boost, hydration_boost=hydration_boost,
            activity_boost=activity_boost, gi_insult=gi_insult_days.get(day, 0.0),
        )
        inf, deh, fat, emesis = P.latent_step(inf, deh, fat, np.array([anc_morning]), drv,
                                              infection_growth=script.infection_growth,
                                              gi_sensitivity=script.gi_sensitivity)
        truth_I.append(float(inf[0]))
        truth_D.append(float(deh[0]))
        truth_F.append(float(fat[0]))
        truth_anc.append(anc_morning)

        # ---- qualifying acute-care event -----------------------------------
        if not admitted:
            cond = None
            if inf[0] >= P.EVENT_THRESHOLDS["infection"]:
                cond = "febrile_neutropenia" if anc_morning < 1.0 else ("pneumonia" if pneumonia else "sepsis")
            elif deh[0] >= P.EVENT_THRESHOLDS["dehydration"]:
                cond = "dehydration"
            if cond is not None:
                los = 4 if cond != "dehydration" else 3
                admitted_until = day + los - 1
                discharge = day + los
                event_onsets.append({"day": day, "condition": cond, "discharge_day": discharge})
                qc = QUALIFYING_CONDITIONS[cond]
                add_event(day, "encounter", f"Emergency department visit → inpatient admission: {qc['display']}",
                          "Encounter", code=_code(ICD10, qc["icd10"], qc["display"]), hour=21,
                          encounter_class="IMP", admit_source="emergency", qualifying=True,
                          condition=cond, discharge_day=discharge, length_of_stay_days=los)
                lab_days.add(day)
                lab_days.add(min(n, discharge))
                if cond in ("febrile_neutropenia", "sepsis", "pneumonia"):
                    dose_scale = 0.8
                    secondary_gcsf = True
                    if anc_morning < 1.0:
                        gcsf_days.append(day + 1)
                else:
                    adherence_override = 0.9

        # ---- daily observations ---------------------------------------------
        steroid = 1.0 if (reg.steroid_premed and dsd is not None and 0 <= dsd <= 2) else 0.0
        means = P.observation_means(base_t, inf, deh, fat, emesis=emesis, steroid=steroid)
        weekday = (ANCHOR_DATE.toordinal() + day - 1) % 7  # 0 = Monday
        on_treatment = last_dose_day is not None
        watch_missing = u_miss[0] < script.missing_wear
        for idx, key in enumerate(DAILY_SIGNALS):
            if key == "glucose_cgm" and not script.diabetic:
                continue
            spec = SIGNALS[key]
            mu = float(means[key][0])
            if key == "steps":
                if weekday >= 5:
                    mu += math.log(0.85)
                if admitted:
                    mu += math.log(0.35)
            if key == "weight" and on_treatment:
                mu -= 0.02 * (day - (planned[0] if planned else day))
            mu += blips.get(day, {}).get(key, 0.0)
            val_t = mu + P.OBS_NOISE[key] * float(z[idx])
            value = _from_transformed(key, val_t)
            lo, hi = spec.plausible
            if key == "spo2":
                hi = 100.0
            if key == "symptom_score":
                lo, hi = 0.0, 10.0
            value = float(min(max(value, lo if key != "steps" else 150.0), hi))

            missing = (
                (key in WATCH_SIGNALS and watch_missing)
                or (key == "temperature" and u_miss[1] < script.missing_temp)
                or (key in HOME_SIGNALS and u_miss[2] < script.missing_home)
                or (key == "symptom_score" and u_miss[3] < script.missing_pro)
                or (key == "glucose_cgm" and u_miss[4] < 0.03)
            )
            source = {
                "wearable": f"wearable/{spec.device.replace(' ', '-')}",
                "home_device": f"home/{spec.device.replace(' ', '-')}",
                "patient_reported": "pro/patient-app",
            }[spec.category]
            # Injected data-quality issues
            for qi in script.quality_issues:
                if not (qi.day <= day < qi.day + qi.n_days):
                    continue
                if qi.kind == "gap" and key in WATCH_SIGNALS:
                    missing = True
                elif qi.kind == "stuck" and key == qi.signal:
                    stuck_values.setdefault(key, round(value, 1))
                    value = stuck_values[key]
                elif qi.kind == "implausible" and key == qi.signal:
                    value = {"resting_hr": 250.0, "temperature": 44.9, "spo2": 58.0}.get(key, value * 10)
            if missing:
                continue
            hour = {"steps": 23, "sleep_hours": 7, "resting_hr": 7, "hrv_sdnn": 7, "spo2": 7,
                    "temperature": 18, "weight": 7, "sbp": 8, "dbp": 8, "glucose_cgm": 23,
                    "symptom_score": 20}.get(key, 8)
            observations.append(Observation(
                id=f"{pid}-{key}-d{day}", signal=key, day=day, value=_round(key, value),
                effective=day_to_iso(day, hour, 55 if hour == 23 else 0), source=source,
                device_id=f"{pid}-{spec.device.replace(' ', '-')}",
            ))
        for qi in script.quality_issues:
            if qi.kind == "conflict" and qi.day == day:
                w = next((o for o in observations if o.signal == "weight" and o.day == day), None)
                ref = w.value if w else base_lin["weight"]
                observations.append(Observation(
                    id=f"{pid}-weight-d{day}-clinic", signal="weight", day=day,
                    value=round(ref + 4.6, 1), effective=day_to_iso(day, 14), source="ehr/clinic-vitals",
                    device_id="clinic-scale",
                ))

        # ---- laboratory results ----------------------------------------------
        if day in lab_days:
            anc_meas = anc_morning * math.exp(0.08 * float(z_lab[0]))
            cycles = len(dose_days)
            labs = {
                "anc": anc_meas,
                "wbc": anc_meas / 0.62 + 1.3 + 0.2 * float(z_lab[1]),
                # hemoconcentration: dehydration raises measured hemoglobin slightly
                "hemoglobin": hgb0 - 0.45 * cycles + 0.3 * float(deh[0]) + 0.2 * float(z_lab[2]),
                "platelets": plt0 * (0.55 + 0.45 * min(1.0, anc_morning / script.circ0)) * math.exp(0.06 * float(z_lab[3])),
                "creatinine": cr0 * (1.0 + 0.3 * float(deh[0])) * math.exp(0.04 * float(z_lab[4])),
            }
            for key, v in labs.items():
                observations.append(Observation(
                    id=f"{pid}-{key}-d{day}", signal=key, day=day, value=_round(key, max(v, 0.01)),
                    effective=day_to_iso(day, 7, 30), source="ehr/lab", device_id="lab-analyzer",
                ))

    profile = PatientProfile(
        patient_id=pid, label=script.label, age=script.age, sex=script.sex, cancer=script.cancer,
        icd10=script.icd10, stage=script.stage, biomarkers=script.biomarkers,
        regimen_code=script.regimen, payer_id=script.payer_id, comorbidities=script.comorbidities,
        ecog=script.ecog, archetype=script.archetype, narrative=script.narrative, diabetic=script.diabetic,
    )
    events.sort(key=lambda e: (e.day, e.effective, e.id))
    observations.sort(key=lambda o: (o.day, o.effective, o.id))
    record = PatientRecord(profile=profile, observations=observations, events=events,
                           n_days=n, planned_dose_days=planned)
    truth = SimulationTruth(infection=truth_I, dehydration=truth_D, fatigue=truth_F,
                            anc_true=truth_anc, event_onsets=event_onsets, admitted_days=admitted_days)
    return SimulationResult(record=record, truth=truth, script=script)


def _pre_treatment_history(script: SimScript, reg, add_event) -> None:
    """Diagnosis, pathology, genomics, staging, plan — the static EHR world."""
    t0 = script.treatment_start
    add_event(-34, "diagnosis", f"{script.cancer}, stage {script.stage}", "Condition",
              code=_code(ICD10, script.icd10, script.cancer), stage=script.stage, clinical_status="active")
    bm = "; ".join(f"{k} {v}" for k, v in script.biomarkers.items())
    add_event(-32, "pathology", f"Surgical pathology: {script.cancer}. Biomarkers: {bm}", "DiagnosticReport",
              code=_code(LOINC, "60567-5", "Comprehensive pathology report panel"), biomarkers=script.biomarkers)
    add_event(-26, "imaging", f"Staging CT chest/abdomen/pelvis: consistent with stage {script.stage}", "DiagnosticReport",
              code=_code(LOINC, "24627-2", "Chest CT"))
    genomic = {k: v for k, v in script.biomarkers.items() if k not in ("ER", "PR", "Ki-67")}
    if genomic:
        add_event(-20, "genomics", "Molecular profiling report: " + "; ".join(f"{k} {v}" for k, v in genomic.items()),
                  "DiagnosticReport", code=_code(LOINC, "81247-9", "Master HL7 genetic variant reporting panel"),
                  biomarkers=genomic)
    for c in script.comorbidities:
        add_event(-400, "diagnosis", c["display"], "Condition", code=_code(ICD10, c["icd10"], c["display"]),
                  clinical_status="active", comorbidity=True)
    if any(d.name == "trastuzumab" for d in reg.drugs):
        add_event(t0 - 3, "imaging", "Transthoracic echocardiogram: LVEF 62%", "Observation",
                  code=_code(LOINC, "10230-1", "Left ventricular Ejection fraction"), value=62, unit="%")
    add_event(t0 - 7, "careplan", f"Treatment plan: {reg.name}", "CarePlan", regimen=reg.code,
              cycle_days=reg.cycle_days, myelo_tier=reg.myelo_tier)
    for drug in reg.drugs:
        add_event(t0 - 7, "medication_request", f"{drug.name} ordered ({reg.code})", "MedicationRequest",
                  code=_code(RXNORM, drug.rxnorm, drug.name), status="active", route=drug.route)
    if any(d.route == "IV" for d in reg.drugs):
        add_event(t0 - 5, "procedure", "Implanted venous access port placement", "Procedure",
                  code=_code(SNOMED, "233527006", "Insertion of central venous access port"))
    add_event(t0 - 2, "performance_status", f"ECOG performance status {script.ecog}", "Observation",
              code=_code(LOINC, "89247-1", "ECOG Performance Status score"), value=script.ecog)
