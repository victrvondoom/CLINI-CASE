"""Signal registry — the single source of truth for every dynamic signal.

Each spec says how a signal is coded in FHIR, which direction is clinically
ADVERSE in the treatment-related-deterioration context, how it is
transformed for baseline statistics, its physiologically plausible range
(used by the data-quality engine), and its expected reporting cadence (used
for freshness).

Coding: LOINC where a standard code exists and is well established; a local
code system (clearly namespaced) where it does not. Local codes are listed in
`LOCAL_CODE_SYSTEM` so a terminology service can map them later.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

LOINC = "http://loinc.org"
LOCAL_CODE_SYSTEM = "https://clincase.health/oncotwin/CodeSystem/signal"
UCUM = "http://unitsofmeasure.org"

Category = Literal["wearable", "home_device", "patient_reported", "lab"]


@dataclass(frozen=True)
class SignalSpec:
    key: str
    label: str
    unit: str                      # UCUM code
    unit_display: str
    category: Category
    code_system: str
    code: str
    code_display: str
    adverse: Literal["up", "down"]  # direction that indicates deterioration
    transform: Literal["linear", "log"]
    spread_floor: float            # minimum baseline spread, in transformed units
    plausible: tuple[float, float]
    cadence_hours: float           # expected reporting cadence
    device: str
    in_model: bool                 # used as an ML feature (vs. display / context only)
    fhir_category: str             # Observation.category code
    decimals: int = 1


SIGNALS: dict[str, SignalSpec] = {
    s.key: s
    for s in (
        SignalSpec(
            key="resting_hr", label="Resting heart rate", unit="/min", unit_display="bpm",
            category="wearable", code_system=LOINC, code="40443-4",
            code_display="Heart rate --resting", adverse="up", transform="linear",
            spread_floor=1.5, plausible=(25, 220), cadence_hours=24,
            device="smartwatch", in_model=True, fhir_category="vital-signs", decimals=0,
        ),
        SignalSpec(
            key="hrv_sdnn", label="Heart-rate variability (SDNN, overnight)", unit="ms", unit_display="ms",
            category="wearable", code_system=LOINC, code="80404-7",
            code_display="R-R interval.standard deviation (Heart rate variability)",
            adverse="down", transform="log", spread_floor=0.07, plausible=(3, 250),
            cadence_hours=24, device="smartwatch", in_model=True, fhir_category="vital-signs", decimals=0,
        ),
        SignalSpec(
            key="temperature", label="Body temperature (daily max)", unit="Cel", unit_display="°C",
            category="wearable", code_system=LOINC, code="8310-5", code_display="Body temperature",
            adverse="up", transform="linear", spread_floor=0.12, plausible=(33.0, 43.0),
            cadence_hours=24, device="smart thermometer", in_model=True, fhir_category="vital-signs", decimals=2,
        ),
        SignalSpec(
            key="spo2", label="SpO₂ (overnight mean)", unit="%", unit_display="%",
            category="wearable", code_system=LOINC, code="59408-5",
            code_display="Oxygen saturation in Arterial blood by Pulse oximetry",
            adverse="down", transform="linear", spread_floor=0.5, plausible=(70, 100),
            cadence_hours=24, device="smartwatch", in_model=True, fhir_category="vital-signs", decimals=1,
        ),
        SignalSpec(
            key="steps", label="Daily steps", unit="{steps}/d", unit_display="steps",
            category="wearable", code_system=LOINC, code="55423-8",
            code_display="Number of steps in unspecified time Pedometer",
            adverse="down", transform="log", spread_floor=0.15, plausible=(0, 60000),
            cadence_hours=24, device="smartwatch", in_model=True, fhir_category="activity", decimals=0,
        ),
        SignalSpec(
            key="sleep_hours", label="Sleep duration", unit="h", unit_display="h",
            category="wearable", code_system=LOINC, code="93832-4", code_display="Sleep duration",
            adverse="down", transform="linear", spread_floor=0.35, plausible=(0, 16),
            cadence_hours=24, device="smartwatch", in_model=True, fhir_category="activity", decimals=1,
        ),
        SignalSpec(
            key="weight", label="Body weight", unit="kg", unit_display="kg",
            category="home_device", code_system=LOINC, code="29463-7", code_display="Body weight",
            adverse="down", transform="linear", spread_floor=0.35, plausible=(25, 300),
            cadence_hours=24, device="connected scale", in_model=True, fhir_category="vital-signs", decimals=1,
        ),
        SignalSpec(
            key="sbp", label="Systolic blood pressure", unit="mm[Hg]", unit_display="mmHg",
            category="home_device", code_system=LOINC, code="8480-6", code_display="Systolic blood pressure",
            adverse="down", transform="linear", spread_floor=4.0, plausible=(50, 250),
            cadence_hours=24, device="connected BP cuff", in_model=True, fhir_category="vital-signs", decimals=0,
        ),
        SignalSpec(
            key="dbp", label="Diastolic blood pressure", unit="mm[Hg]", unit_display="mmHg",
            category="home_device", code_system=LOINC, code="8462-4", code_display="Diastolic blood pressure",
            adverse="down", transform="linear", spread_floor=3.0, plausible=(30, 150),
            cadence_hours=24, device="connected BP cuff", in_model=False, fhir_category="vital-signs", decimals=0,
        ),
        SignalSpec(
            key="glucose_cgm", label="Mean glucose (CGM, daily)", unit="mg/dL", unit_display="mg/dL",
            category="wearable", code_system=LOCAL_CODE_SYSTEM, code="cgm-daily-mean-glucose",
            code_display="Daily mean interstitial glucose from continuous glucose monitor",
            adverse="up", transform="linear", spread_floor=6.0, plausible=(40, 500),
            cadence_hours=24, device="CGM", in_model=False, fhir_category="vital-signs", decimals=0,
        ),
        SignalSpec(
            key="symptom_score", label="Symptom burden (PRO-CTCAE-based, 0–10)", unit="{score}", unit_display="/10",
            category="patient_reported", code_system=LOCAL_CODE_SYSTEM, code="pro-symptom-burden",
            code_display="Patient-reported symptom burden composite (PRO-CTCAE items: nausea, vomiting, diarrhea, fatigue, pain, chills)",
            adverse="up", transform="linear", spread_floor=0.6, plausible=(0, 10),
            cadence_hours=24, device="patient app", in_model=True, fhir_category="survey", decimals=1,
        ),
        # --- Laboratory (sparse, EHR) — context, not daily-z modelled ---------
        SignalSpec(
            key="anc", label="Absolute neutrophil count", unit="10*3/uL", unit_display="×10³/µL",
            category="lab", code_system=LOINC, code="751-8",
            code_display="Neutrophils [#/volume] in Blood by Automated count",
            adverse="down", transform="log", spread_floor=0.1, plausible=(0.0, 60.0),
            cadence_hours=24 * 7, device="EHR laboratory", in_model=False, fhir_category="laboratory", decimals=2,
        ),
        SignalSpec(
            key="wbc", label="White blood cell count", unit="10*3/uL", unit_display="×10³/µL",
            category="lab", code_system=LOINC, code="6690-2",
            code_display="Leukocytes [#/volume] in Blood by Automated count",
            adverse="down", transform="log", spread_floor=0.1, plausible=(0.0, 100.0),
            cadence_hours=24 * 7, device="EHR laboratory", in_model=False, fhir_category="laboratory", decimals=1,
        ),
        SignalSpec(
            key="hemoglobin", label="Hemoglobin", unit="g/dL", unit_display="g/dL",
            category="lab", code_system=LOINC, code="718-7", code_display="Hemoglobin [Mass/volume] in Blood",
            adverse="down", transform="linear", spread_floor=0.3, plausible=(3.0, 22.0),
            cadence_hours=24 * 7, device="EHR laboratory", in_model=False, fhir_category="laboratory", decimals=1,
        ),
        SignalSpec(
            key="platelets", label="Platelets", unit="10*3/uL", unit_display="×10³/µL",
            category="lab", code_system=LOINC, code="777-3", code_display="Platelets [#/volume] in Blood by Automated count",
            adverse="down", transform="log", spread_floor=0.1, plausible=(1.0, 2000.0),
            cadence_hours=24 * 7, device="EHR laboratory", in_model=False, fhir_category="laboratory", decimals=0,
        ),
        SignalSpec(
            key="creatinine", label="Creatinine", unit="mg/dL", unit_display="mg/dL",
            category="lab", code_system=LOINC, code="2160-0", code_display="Creatinine [Mass/volume] in Serum or Plasma",
            adverse="up", transform="linear", spread_floor=0.08, plausible=(0.1, 20.0),
            cadence_hours=24 * 7, device="EHR laboratory", in_model=False, fhir_category="laboratory", decimals=2,
        ),
    )
}

# Daily signals that participate in the personalised baseline + ML features,
# in a FIXED order (feature vectors and matrices index by this order).
MODEL_SIGNALS: tuple[str, ...] = tuple(k for k, s in SIGNALS.items() if s.in_model)
# Daily signals shown on the dashboard (model signals + display-only daily ones).
DAILY_SIGNALS: tuple[str, ...] = tuple(k for k, s in SIGNALS.items() if s.category != "lab")
LAB_SIGNALS: tuple[str, ...] = tuple(k for k, s in SIGNALS.items() if s.category == "lab")

# Reverse lookup: (system, code) → signal key. Used when ingesting FHIR.
CODE_INDEX: dict[tuple[str, str], str] = {(s.code_system, s.code): s.key for s in SIGNALS.values()}


def adverse_sign(key: str) -> float:
    """+1 when an INCREASE is adverse, -1 when a DECREASE is adverse."""
    return 1.0 if SIGNALS[key].adverse == "up" else -1.0
