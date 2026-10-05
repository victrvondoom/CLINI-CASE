"""
Data models for OneAquaHealth Semantic Interoperability Bridge (OAH-Bridge).
Defines normalized structures for raw multi-source environmental inputs,
evidence aggregation, spatial exposure zones, and scenario configurations.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CitizenReport:
    report_id: str
    timestamp: str
    site_id: str
    observer_type: str  # e.g., "citizen-scientist", "recreational-swimmer", "field-volunteer"
    sighting_type: str  # e.g., "surface-scum", "water-discoloration", "larval-cluster", "dead-fish"
    severity_rating: int  # 1 to 5
    description: str
    coordinates: list[float]  # [longitude, latitude]


@dataclass
class SensorReading:
    reading_id: str
    timestamp: str
    site_id: str
    parameter: str  # e.g., "turbidity", "chlorophyll-a", "water-temperature", "dissolved-oxygen", "pH"
    value: float
    unit: str
    nominal_baseline: float
    threshold_exceeded: bool


@dataclass
class LabAssay:
    sample_id: str
    timestamp: str
    site_id: str
    analyte: str  # e.g., "Microcystin-LR", "Escherichia coli", "Total Cyanotoxins"
    concentration: float
    unit: str  # e.g., "ug/L", "CFU/100mL"
    regulatory_threshold: float
    confirmed_positive: bool
    laboratory_name: str


@dataclass
class ModelInference:
    model_name: str  # e.g., "DipteraCAST-EcoSurv", "Mondego-BloomPredict-AI"
    version: str
    timestamp: str
    site_id: str
    predicted_hazard: str
    confidence: float
    ecological_factors: dict[str, Any]


@dataclass
class EvidenceSubScores:
    sensor_corroboration: float  # Cs: 0.00 - 1.00
    citizen_agreement: float     # Cc: 0.00 - 1.00
    temporal_consistency: float  # Ct: 0.00 - 1.00


@dataclass
class CompositeEvidenceResult:
    score: float  # S = 0.40*Cs + 0.30*Cc + 0.30*Ct
    methodology_version: str  # "v0.1-prototype"
    weights: dict[str, float]
    sub_scores: EvidenceSubScores
    epistemic_status: str  # "observed" | "inferred" | "confirmed"
    epistemic_display: str
    is_lab_confirmed: bool
    disclaimer: str = "Prototype composite score — methodology v0.1. Not clinically validated."


@dataclass
class SpatialExposureZone:
    site_id: str
    site_name: str
    city: str
    river_system: str
    geojson_polygon: dict[str, Any]
    recreational_use_category: str  # "primary-water-contact", "secondary-recreation", "urban-riparian-park"
    estimated_exposed_population: int
    buffer_meters: float


@dataclass
class ScenarioDefinition:
    scenario_id: str
    title: str
    city: str
    river_system: str
    grounding_statement: str
    hazard_code: str
    hazard_display: str
    exposure_pathway_code: str
    exposure_pathway_display: str
    snomed_outcome_code: str
    snomed_outcome_display: str
    snomed_preferred_term: str
    qualitative_risk: str  # "moderate", "high", "low"
    risk_summary: str
    ascertainment_technique: str
    ascertainment_display: str
    spatial_zone: SpatialExposureZone
    citizen_reports: list[CitizenReport] = field(default_factory=list)
    sensor_readings: list[SensorReading] = field(default_factory=list)
    lab_assays: list[LabAssay] = field(default_factory=list)
    model_inferences: list[ModelInference] = field(default_factory=list)
