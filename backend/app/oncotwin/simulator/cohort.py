"""Random synthetic training/validation cohort (seeded, reproducible).

Patients differ in regimen, drug sensitivity, baselines, GI susceptibility,
adherence behaviour, infection seeding (stochastic, neutropenia-dependent)
and data quality. No clinician interventions are scripted, so the only acute
care in the cohort is the qualifying outcome itself — labels therefore
reflect the natural course, which is what the model is asked to anticipate.
"""
from __future__ import annotations

import numpy as np

from app.oncotwin.simulator.patients import QualityIssue, SimScript, SimulationResult, simulate
from app.oncotwin.simulator.regimens import REGIMENS

_REGIMEN_WEIGHTS = {"TCHP": 0.24, "DDAC": 0.14, "CARBO_PACLI": 0.24, "CAPOX": 0.22, "PEMBRO": 0.16}
_TUMOR = {
    "breast": ("Invasive ductal carcinoma of breast", "C50.919"),
    "ovarian": ("High-grade serous carcinoma of ovary", "C56.9"),
    "lung": ("Non-small cell lung carcinoma", "C34.90"),
    "colon": ("Adenocarcinoma of colon", "C18.9"),
    "melanoma": ("Malignant melanoma of skin", "C43.9"),
}


def cohort_script(index: int, seed: int) -> SimScript:
    rng = np.random.default_rng([seed, index, 7])
    codes = list(_REGIMEN_WEIGHTS)
    probs = np.array(list(_REGIMEN_WEIGHTS.values()))
    regimen = codes[int(rng.choice(len(codes), p=probs / probs.sum()))]
    reg = REGIMENS[regimen]
    tumor = reg.tumor_types[int(rng.integers(len(reg.tumor_types)))]
    sex = "female" if tumor in ("breast", "ovarian") else ("female" if rng.uniform() < 0.45 else "male")
    age = int(np.clip(rng.normal(61, 11), 28, 88))
    ecog = int(rng.choice([0, 1, 2], p=[0.35, 0.5, 0.15]))

    pattern = rng.uniform()
    if pattern < 0.68:
        plan = [(1, float(rng.uniform(0.88, 1.0)))]
    elif pattern < 0.88:
        plan = [(1, float(rng.uniform(0.88, 1.0))),
                (int(rng.integers(16, 40)), float(rng.uniform(0.15, 0.6)))]
    else:
        plan = [(1, float(rng.uniform(0.35, 0.7)))]

    issues: list[QualityIssue] = []
    if rng.uniform() < 0.3:
        issues.append(QualityIssue(kind="gap", day=int(rng.integers(5, 50)), n_days=int(rng.integers(1, 4))))
    if rng.uniform() < 0.08:
        issues.append(QualityIssue(kind="stuck", day=int(rng.integers(5, 50)), n_days=int(rng.integers(2, 5)),
                                   signal=str(rng.choice(["spo2", "resting_hr", "sleep_hours"]))))
    if rng.uniform() < 0.05:
        issues.append(QualityIssue(kind="implausible", day=int(rng.integers(5, 55)),
                                   signal=str(rng.choice(["resting_hr", "temperature", "spo2"]))))

    diabetic = bool(rng.uniform() < 0.2)
    return SimScript(
        patient_id=f"coh-{seed}-{index:04d}", label=f"COH-{index:04d}", seed=seed * 100_003 + index,
        archetype="cohort", age=age, sex=sex,  # type: ignore[arg-type]
        cancer=_TUMOR[tumor][0], icd10=_TUMOR[tumor][1], stage=str(rng.choice(["II", "III", "IV"])),
        biomarkers={}, regimen=regimen, ecog=ecog, diabetic=diabetic,
        comorbidities=[{"icd10": "E11.9", "display": "Type 2 diabetes mellitus"}] if diabetic else [],
        treatment_start=int(rng.integers(10, 17)),
        sensitivity=float(np.exp(rng.normal(0.1, 0.3))),
        circ0=float(np.clip(rng.normal(4.4, 1.1), 2.0, 8.0)),
        infection_growth=float(np.clip(rng.normal(0.6, 0.08), 0.4, 0.8)),
        gi_sensitivity=float(np.exp(rng.normal(0.15, 0.3))),
        adherence_plan=plan,
        quality_issues=issues,
        stochastic_infections=True,
        stochastic_seed_rate=float(rng.uniform(0.06, 0.16)),
        primary_gcsf=bool(reg.myelo_tier == "high"),
        missing_wear=float(rng.uniform(0.01, 0.1)),
        missing_home=float(rng.uniform(0.05, 0.25)),
        missing_pro=float(rng.uniform(0.1, 0.4)),
    )


def generate_cohort(n: int, seed: int = 20260923) -> list[SimulationResult]:
    return [simulate(cohort_script(i, seed)) for i in range(n)]
