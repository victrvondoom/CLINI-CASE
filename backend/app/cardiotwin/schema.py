"""Domain schema: dataset columns, feature specification, targets and API models.

The feature specification is the single source of truth for (a) encoding the
raw dataset, (b) validating API input, and (c) rendering the input form in the
UI (`GET /cardiotwin/features`). Adding a clinical feature = one entry here +
retraining; nothing else needs to change.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Targets and leakage policy
# ---------------------------------------------------------------------------

#: Dataset label columns. NOTE: the dataset has no column literally named
#: "CAD" — the overall CAD label is the `Cath` column (values CAD / Normal).
LABEL_COLUMNS: tuple[str, ...] = ("Cath", "LAD", "LCX", "RCA")

#: model target name -> (dataset column, positive class value)
TARGETS: dict[str, tuple[str, str]] = {
    "CAD": ("Cath", "CAD"),
    "LAD": ("LAD", "Stenotic"),
    "LCX": ("LCX", "Stenotic"),
    "RCA": ("RCA", "Stenotic"),
}
TARGET_ORDER: tuple[str, ...] = ("CAD", "LAD", "LCX", "RCA")
VESSELS: tuple[str, ...] = ("LAD", "LCX", "RCA")

#: Coronary vessel display names (semantic ids shared with the 3D layer).
VESSEL_NAMES: dict[str, str] = {
    "LAD": "Left anterior descending artery",
    "LCX": "Left circumflex artery",
    "RCA": "Right coronary artery",
}

SOURCE_DATASET = {
    "name": "Extension of Z-Alizadeh Sani Dataset",
    "uci_id": 411,
    "url": "https://archive.ics.uci.edu/dataset/411/extention+of+z+alizadeh+sani+dataset",
    "download": "https://archive.ics.uci.edu/static/public/411/extention+of+z+alizadeh+sani+dataset.zip",
    "license": "CC BY 4.0",
    "records": 303,
    "citation": (
        "Alizadehsani, R., Roshanzamir, M., Sani, Z. A. (2017). Extension of Z-Alizadeh Sani "
        "dataset [Dataset]. UCI Machine Learning Repository."
    ),
}

FeatureKind = Literal["binary", "numeric", "ordinal", "categorical"]


@dataclass(frozen=True)
class FeatureSpec:
    """One raw dataset input column."""

    name: str  # exact dataset column name
    label: str  # human label
    group: Literal["demographics", "history", "exam", "ecg", "lab", "echo"]
    kind: FeatureKind
    unit: str = ""
    lo: float | None = None  # hard validation bounds (physiologically possible)
    hi: float | None = None
    ref_lo: float | None = None  # general adult reference range (context only)
    ref_hi: float | None = None
    options: tuple[str, ...] = ()  # categorical / ordinal levels, in order
    core: bool = False  # shown expanded in the form
    note: str = ""
    #: values that mean "absent / normal" for the binary encoding of Y/N columns
    yes: str = "Y"

    def to_public(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "label": self.label,
            "group": self.group,
            "kind": self.kind,
            "unit": self.unit,
            "min": self.lo,
            "max": self.hi,
            "ref_low": self.ref_lo,
            "ref_high": self.ref_hi,
            "options": list(self.options),
            "core": self.core,
            "note": self.note,
        }


def _yn(name: str, label: str, group: str, *, core: bool = False, note: str = "") -> FeatureSpec:
    return FeatureSpec(name, label, group, "binary", core=core, note=note)  # type: ignore[arg-type]


def _bin01(name: str, label: str, group: str, *, core: bool = False, note: str = "") -> FeatureSpec:
    """Binary column already coded 0/1 in the source."""
    return FeatureSpec(name, label, group, "binary", core=core, note=note, yes="1")  # type: ignore[arg-type]


FEATURES: tuple[FeatureSpec, ...] = (
    # ---- demographics -----------------------------------------------------
    FeatureSpec("Age", "Age", "demographics", "numeric", "years", 18, 100, core=True),
    FeatureSpec("Weight", "Weight", "demographics", "numeric", "kg", 30, 250),
    FeatureSpec("Length", "Height", "demographics", "numeric", "cm", 120, 220),
    FeatureSpec(
        "Sex",
        "Sex",
        "demographics",
        "categorical",
        options=("Female", "Male"),
        core=True,
        note="Dataset column values 'Fmale'/'Male'; 'Fmale' is normalised to 'Female'.",
    ),
    FeatureSpec(
        "BMI", "Body-mass index", "demographics", "numeric", "kg/m²", 10, 60, 18.5, 24.9, core=True
    ),
    # ---- history / risk factors -------------------------------------------
    _bin01("DM", "Diabetes mellitus", "history", core=True),
    _bin01("HTN", "Hypertension", "history", core=True),
    _bin01("Current Smoker", "Current smoker", "history", core=True),
    _bin01("EX-Smoker", "Ex-smoker", "history"),
    _bin01("FH", "Family history of CAD", "history", core=True),
    _yn("Obesity", "Obesity", "history"),
    _yn("CRF", "Chronic renal failure", "history"),
    _yn("CVA", "Cerebrovascular accident", "history"),
    _yn("Airway disease", "Airway disease", "history"),
    _yn("Thyroid Disease", "Thyroid disease", "history"),
    _yn("CHF", "Congestive heart failure", "history"),
    _yn("DLP", "Dyslipidaemia", "history", core=True),
    # ---- examination ------------------------------------------------------
    FeatureSpec(
        "BP", "Systolic blood pressure", "exam", "numeric", "mmHg", 60, 260, 90, 120, core=True
    ),
    FeatureSpec("PR", "Pulse rate", "exam", "numeric", "bpm", 30, 200, 60, 100, core=True),
    _bin01("Edema", "Edema", "exam"),
    _yn("Weak Peripheral Pulse", "Weak peripheral pulse", "exam"),
    _yn("Lung rales", "Lung rales", "exam"),
    _yn("Systolic Murmur", "Systolic murmur", "exam"),
    _yn("Diastolic Murmur", "Diastolic murmur", "exam"),
    _bin01("Typical Chest Pain", "Typical chest pain", "exam", core=True),
    _yn("Dyspnea", "Dyspnea", "exam", core=True),
    FeatureSpec(
        "Function Class",
        "Functional class (0-3)",
        "exam",
        "ordinal",
        lo=0,
        hi=3,
        options=("0", "1", "2", "3"),
        core=True,
    ),
    _yn("Atypical", "Atypical chest pain", "exam"),
    _yn("Nonanginal", "Non-anginal chest pain", "exam"),
    _yn("LowTH Ang", "Low-threshold angina", "exam"),
    # ---- ECG --------------------------------------------------------------
    _bin01("Q Wave", "Q wave", "ecg"),
    _bin01("St Elevation", "ST elevation", "ecg", core=True),
    _bin01("St Depression", "ST depression", "ecg", core=True),
    _bin01("Tinversion", "T-wave inversion", "ecg", core=True),
    _yn("LVH", "Left-ventricular hypertrophy", "ecg", core=True),
    _yn("Poor R Progression", "Poor R-wave progression", "ecg"),
    FeatureSpec("BBB", "Bundle-branch block", "ecg", "categorical", options=("N", "LBBB", "RBBB")),
    # ---- laboratory -------------------------------------------------------
    FeatureSpec(
        "FBS", "Fasting blood sugar", "lab", "numeric", "mg/dL", 40, 700, 70, 99, core=True
    ),
    FeatureSpec("CR", "Creatinine", "lab", "numeric", "mg/dL", 0.2, 15, 0.6, 1.3),
    FeatureSpec("TG", "Triglycerides", "lab", "numeric", "mg/dL", 20, 1500, None, 150, core=True),
    FeatureSpec("LDL", "LDL cholesterol", "lab", "numeric", "mg/dL", 10, 500, None, 100, core=True),
    FeatureSpec("HDL", "HDL cholesterol", "lab", "numeric", "mg/dL", 10, 150, 40, None, core=True),
    FeatureSpec("BUN", "Blood urea nitrogen", "lab", "numeric", "mg/dL", 2, 150, 7, 20),
    FeatureSpec("ESR", "Erythrocyte sedimentation rate", "lab", "numeric", "mm/h", 0, 150, 0, 20),
    FeatureSpec("HB", "Haemoglobin", "lab", "numeric", "g/dL", 4, 22, 12, 17.5, core=True),
    FeatureSpec("K", "Potassium", "lab", "numeric", "mEq/L", 2, 8, 3.5, 5.0),
    FeatureSpec("Na", "Sodium", "lab", "numeric", "mEq/L", 110, 170, 135, 145),
    FeatureSpec("WBC", "White-cell count", "lab", "numeric", "cells/µL", 1000, 50000, 4000, 11000),
    FeatureSpec("Lymph", "Lymphocytes", "lab", "numeric", "%", 0, 100, 20, 40),
    FeatureSpec("Neut", "Neutrophils", "lab", "numeric", "%", 0, 100, 40, 75),
    FeatureSpec("PLT", "Platelets", "lab", "numeric", "×10³/µL", 20, 1000, 150, 450),
    # ---- echo -------------------------------------------------------------
    FeatureSpec(
        "EF-TTE", "Ejection fraction (echo)", "echo", "numeric", "%", 10, 80, 55, 70, core=True
    ),
    FeatureSpec(
        "Region RWMA",
        "Regions with wall-motion abnormality",
        "echo",
        "ordinal",
        lo=0,
        hi=4,
        options=("0", "1", "2", "3", "4"),
        core=True,
        note="Count of regions with RWMA — a clinical feature, not an anatomical coordinate.",
    ),
    FeatureSpec(
        "VHD",
        "Valvular heart disease",
        "echo",
        "ordinal",
        options=("N", "mild", "Moderate", "Severe"),
        note="Ordinal severity: N < mild < Moderate < Severe.",
    ),
)

#: Source columns that are constant in the dataset ('Exertional CP' is always 'N')
#: — excluded from modelling. Kept in this list so the exclusion is explicit.
CONSTANT_COLUMNS: tuple[str, ...] = ("Exertional CP",)

FEATURE_INDEX: dict[str, FeatureSpec] = {f.name: f for f in FEATURES}
FEATURE_NAMES: tuple[str, ...] = tuple(f.name for f in FEATURES)

#: Every column expected in the raw dataset file.
EXPECTED_COLUMNS: frozenset[str] = (
    frozenset(FEATURE_NAMES) | frozenset(LABEL_COLUMNS) | frozenset(CONSTANT_COLUMNS)
)

GROUP_LABELS: dict[str, str] = {
    "demographics": "Demographics",
    "history": "History & risk factors",
    "exam": "Clinical examination",
    "ecg": "ECG",
    "lab": "Laboratory",
    "echo": "Echocardiography",
}

# ---------------------------------------------------------------------------
# API models
# ---------------------------------------------------------------------------


class PatientInput(BaseModel):
    """Feature values keyed by dataset column name. Every field is optional:
    absent features are imputed with the training median/mode and reported."""

    features: dict[str, float | int | str | None] = Field(default_factory=dict)


class PredictRequest(PatientInput):
    scenario_id: str | None = Field(
        default=None, description="Optional demo scenario id (provenance only)"
    )


class CounterfactualRequest(PatientInput):
    perturbations: dict[str, float | int | str] = Field(
        default_factory=dict,
        description="Feature overrides applied on top of `features` (model sensitivity simulation).",
    )


class SensitivityRequest(PatientInput):
    feature: str
    points: int = Field(default=15, ge=3, le=41)


@dataclass
class EncodedRecord:
    """A validated record: raw values, encoded vector, and bookkeeping."""

    raw: dict[str, Any]
    vector: list[float]
    provided: list[str]
    imputed: list[str]
    warnings: list[str] = field(default_factory=list)
