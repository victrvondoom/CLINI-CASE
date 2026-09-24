"""The ONE outcome OncoTwin predicts.

A digital twin that only visualises data is a dashboard. OncoTwin commits to
a single, precise, measurable outcome and every risk number it shows is a
probability of THIS outcome over THIS horizon:

  OT-ACUTE-7 — an unplanned emergency-department visit or inpatient admission
  for a chemotherapy-related condition, with onset within the next 7 days.

The qualifying conditions are the ten conditions of the CMS outpatient
quality measure OP-35 ("Admissions and Emergency Department Visits for
Patients Receiving Outpatient Chemotherapy"): anemia, dehydration, diarrhea,
emesis, fever, nausea, neutropenia, pain, pneumonia, sepsis.

In the synthetic cohort the outcome is materialised as a FHIR Encounter
(class EMER or IMP) whose reasonCode is one of the ICD-10-CM codes below.
Training labels are derived ONLY from those Encounter onsets, never from
the simulator's latent state.
"""
from __future__ import annotations

OUTCOME_ID = "OT-ACUTE-7"
HORIZON_DAYS = 7
# Days after discharge that are still excluded from labelling / alerting.
POST_DISCHARGE_EXCLUSION_DAYS = 2

OUTCOME_DEFINITION = {
    "id": OUTCOME_ID,
    "name": "Unplanned acute care for a chemotherapy-related condition",
    "horizon_days": HORIZON_DAYS,
    "definition": (
        "An unplanned emergency-department visit or inpatient admission whose "
        "reason is one of the 10 CMS OP-35 chemotherapy-related conditions "
        "(anemia, dehydration, diarrhea, emesis, fever, nausea, neutropenia, "
        "pain, pneumonia, sepsis), with onset within the next 7 days."
    ),
    "label_rule": (
        "For each patient-day t, label = 1 if a qualifying Encounter starts on "
        "day t+1 … t+7. Days from an event onset through discharge + 2 days are "
        "excluded (the patient is already in, or just out of, acute care)."
    ),
    "measure_basis": "CMS OP-35 (Hospital Outpatient Quality Reporting program)",
    "prediction_unit": "patient-day, using only data available up to the end of day t",
}

# ICD-10-CM codes used on synthetic qualifying Encounters. A real deployment
# must map to the full OP-35 code set published by CMS.
QUALIFYING_CONDITIONS: dict[str, dict[str, str]] = {
    "febrile_neutropenia": {"icd10": "D70.1", "display": "Agranulocytosis secondary to cancer chemotherapy (febrile neutropenia)", "op35": "neutropenia / fever"},
    "sepsis":              {"icd10": "A41.9", "display": "Sepsis, unspecified organism", "op35": "sepsis"},
    "pneumonia":           {"icd10": "J18.9", "display": "Pneumonia, unspecified organism", "op35": "pneumonia"},
    "dehydration":         {"icd10": "E86.0", "display": "Dehydration", "op35": "dehydration"},
    "diarrhea":            {"icd10": "R19.7", "display": "Diarrhea, unspecified", "op35": "diarrhea"},
    "nausea_vomiting":     {"icd10": "R11.2", "display": "Nausea with vomiting, unspecified", "op35": "nausea / emesis"},
}
