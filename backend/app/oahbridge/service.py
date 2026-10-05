"""OAH-Bridge orchestration for CLINI-CASE.

Does what OneAquaHealth-Bridge's stdlib server (api/server.py) did inline: demo run,
FHIR search, CDS Hooks discovery and evaluation, conformance and terminology listing.
On top of that it adds:

- per-stage timings, so the globe can replay the *actual* run rather than a canned animation;
- process-local counters and a cached engine self-test, for the live system monitor.

The scenarios are synthetic demonstration data, not live public-health surveillance.
"""

from __future__ import annotations

import copy
import json
import threading
import time
import uuid
from collections import deque
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from . import weather
from .composer import compose_scenario_bundle
from .models import EvidenceSubScores, ScenarioDefinition
from .scenarios import SCENARIOS
from .scoring import (
    calculate_citizen_agreement,
    calculate_sensor_corroboration,
    calculate_temporal_consistency,
    compute_composite_evidence,
)
from .spatial import evaluate_patient_exposure_intersection
from .validator import OAHValidator

CONFORMANCE_DIR = Path(__file__).resolve().parent / "conformance"
ENGINE_VERSION = "OAH-Bridge engine v0.1 (ported into CLINI-CASE)"
DEFAULT_SCENARIO = "coimbra-cyanobacteria"
SELF_TEST_TTL_S = 60.0

# Where each scenario's synthetic demo patient is, used only when a CDS request carries no
# coordinates. The response says so (location_source), so a default is never mistaken for
# a real patient location.
DEFAULT_PATIENT_COORDS: dict[str, tuple[float, float]] = {
    "coimbra-cyanobacteria": (-8.4285, 40.2035),
    "toulouse-diptera": (1.4355, 43.5870),
    "mondego-storm-surge": (-8.8450, 40.1510),
}


class UnknownScenarioError(KeyError):
    """Raised for a scenario id that is not in SCENARIOS."""


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _ms(start: float) -> float:
    return round((time.perf_counter() - start) * 1000, 3)


# ---------------------------------------------------------------------------
# Engine access
# ---------------------------------------------------------------------------

_validator_lock = threading.Lock()
_validator: OAHValidator | None = None


def get_validator() -> OAHValidator:
    global _validator
    if _validator is None:
        with _validator_lock:
            if _validator is None:
                _validator = OAHValidator(str(CONFORMANCE_DIR))
    return _validator


def _load(scenario_id: str) -> ScenarioDefinition:
    factory = SCENARIOS.get(scenario_id)
    if factory is None:
        raise UnknownScenarioError(scenario_id)
    return factory()


def _corroborate(scenario: ScenarioDefinition):
    """Same result as scenarios.load_scenario_and_compute, split so each stage can be timed."""
    sub_scores = EvidenceSubScores(
        sensor_corroboration=calculate_sensor_corroboration(scenario.sensor_readings),
        citizen_agreement=calculate_citizen_agreement(scenario.citizen_reports),
        temporal_consistency=calculate_temporal_consistency(
            scenario.sensor_readings, scenario.citizen_reports
        ),
    )
    return compute_composite_evidence(sub_scores=sub_scores, lab_assays=scenario.lab_assays)


_UNIT_LABEL = {"degC": "°C", "ug/L": "µg/L", "uS/cm": "µS/cm", "pH": ""}


def _key_inputs(scenario: ScenarioDefinition) -> list[dict[str, Any]]:
    """Latest reading per sensor parameter, every lab assay and model confidence."""
    latest: dict[str, Any] = {}
    for reading in sorted(scenario.sensor_readings, key=lambda r: r.timestamp):
        latest[reading.parameter] = reading
    rows: list[dict[str, Any]] = [
        {
            "kind": "sensor",
            "label": r.parameter,
            "value": r.value,
            "unit": _UNIT_LABEL.get(r.unit, r.unit),
            "exceeded": r.threshold_exceeded,
        }
        for r in latest.values()
    ]
    rows += [
        {
            "kind": "lab",
            "label": a.analyte,
            "value": a.concentration,
            "unit": a.unit,
            "exceeded": a.concentration > a.regulatory_threshold,
        }
        for a in scenario.lab_assays
    ]
    rows += [
        {"kind": "model", "label": f"{m.model_name} confidence", "value": m.confidence, "unit": "", "exceeded": None}
        for m in scenario.model_inferences
    ]
    return rows


def _centroid(polygon: dict[str, Any]) -> tuple[float, float]:
    ring = polygon["coordinates"][0]
    points = ring[:-1] if len(ring) > 1 and ring[0] == ring[-1] else ring
    return (
        sum(p[0] for p in points) / len(points),
        sum(p[1] for p in points) / len(points),
    )


# ---------------------------------------------------------------------------
# Scenario catalogue (globe pins)
# ---------------------------------------------------------------------------


def list_scenarios() -> list[dict[str, Any]]:
    out = []
    for scenario_id in SCENARIOS:
        scenario = _load(scenario_id)
        evidence = _corroborate(scenario)
        zone = scenario.spatial_zone
        lon, lat = _centroid(zone.geojson_polygon)
        patient = DEFAULT_PATIENT_COORDS.get(scenario_id)
        out.append(
            {
                "id": scenario_id,
                "title": scenario.title,
                "city": scenario.city,
                "river_system": scenario.river_system,
                "hazard_code": scenario.hazard_code,
                "hazard_display": scenario.hazard_display,
                "evidence_score": evidence.score,
                "epistemic_status": evidence.epistemic_status,
                "epistemic_display": evidence.epistemic_display,
                "is_lab_confirmed": evidence.is_lab_confirmed,
                "qualitative_risk": scenario.qualitative_risk,
                "snomed_outcome_code": scenario.snomed_outcome_code,
                "snomed_outcome_display": scenario.snomed_outcome_display,
                "snomed_outcome": f"{scenario.snomed_outcome_code} ({scenario.snomed_outcome_display})",
                "grounding_statement": scenario.grounding_statement,
                "synthetic": True,
                "site": {
                    "id": zone.site_id,
                    "name": zone.site_name,
                    "centroid": {"longitude": round(lon, 5), "latitude": round(lat, 5)},
                    "polygon": zone.geojson_polygon["coordinates"][0],
                    "buffer_meters": zone.buffer_meters,
                    "estimated_exposed_population": zone.estimated_exposed_population,
                    "recreational_use_category": zone.recreational_use_category,
                },
                "citizen_points": [
                    {
                        "id": c.report_id,
                        "longitude": c.coordinates[0],
                        "latitude": c.coordinates[1],
                        "sighting": c.sighting_type,
                        "severity": c.severity_rating,
                    }
                    for c in scenario.citizen_reports
                ],
                "default_patient": (
                    {"longitude": patient[0], "latitude": patient[1]} if patient else None
                ),
                # Multi-city matrix columns, straight from the engine (not from prose).
                "sub_scores": {
                    "sensor_corroboration": evidence.sub_scores.sensor_corroboration,
                    "citizen_agreement": evidence.sub_scores.citizen_agreement,
                    "temporal_consistency": evidence.sub_scores.temporal_consistency,
                },
                "exposure_pathway_display": scenario.exposure_pathway_display,
                "snomed_preferred_term": scenario.snomed_preferred_term,
                "key_inputs": _key_inputs(scenario),
            }
        )
    return out


# ---------------------------------------------------------------------------
# Demo run (the 8-step decision chain, with real timings)
# ---------------------------------------------------------------------------

# Synthetic clinical encounter personas, verbatim from OAH-Bridge. Not real people.
CLINICAL_PROFILES: dict[str, dict[str, str]] = {
    "coimbra-cyanobacteria": {
        "facility": "Hospital Pediátrico de Coimbra • Emergency Department",
        "bay": "Bay 03 • Encounter #ENC-9281",
        "patient_name": "Maria Silva, 14 yo female",
        "triage": "Urgency 2 (Yellow) • HR: 112 bpm • T: 38.2°C",
        "reason": "Patient reports acute pruritic erythematous rash on limbs and torso following recreational freshwater immersion.",
        "location_context": "40.2033° N, -8.4285° W (Intersects Monitored Reach #4)",
        "snomed_outcome": "SNOMED CT 40275004 (Contact dermatitis)",
        "clinical_consideration": "Consider freshwater microcystin contact dermatitis in differential diagnosis vs. standard atopic etiology. Inquire regarding recreational immersion duration and visible scum.",
        "doc_text": "Patient confirmed recreational water contact at Mondego Reach #4 within last 24h during active Cyanobacteria surveillance alert. Environmental history documented in clinical encounter notes.",
        "dispatch_target": "Municipal Water Inspection Unit (Coimbra)",
        "dispatch_action": "Pontoon Cautionary Signage & Reference Grab Testing",
        "dossier_ref": "DEMO-OAH-2026-PT04",
    },
    "toulouse-diptera": {
        "facility": "Centre Hospitalier Universitaire de Toulouse (CHU Purpan) • Triage",
        "bay": "Cubicle 07 • Encounter #ENC-4418",
        "patient_name": "Lucas Bernard, 28 yo male",
        "triage": "Urgency 3 (Green) • HR: 88 bpm • T: 38.9°C",
        "reason": "Patient presents with acute febrile syndrome, localized lymphadenopathy, and multiple erythematous insect bites sustained during evening run along riparian park margins.",
        "location_context": "43.5875° N, 1.4345° E (Intersects Île du Ramier Zone)",
        "snomed_outcome": "SNOMED CT 416113008 (Preferred term: Disorder characterized by fever | Display: Acute febrile illness)",
        "clinical_consideration": "Evaluate acute febrile illness (SNOMED CT 416113008) in context of documented Diptera vector surge in riparian zone. Inquire about outdoor mosquito bites and duration of exposure.",
        "doc_text": "Patient confirmed high-density mosquito bite exposure in Île du Ramier riparian corridor during active Diptera vector alert. Vector exposure history documented in EHR.",
        "dispatch_target": "Service Communal d'Hygiène et de Santé (SCHS Toulouse)",
        "dispatch_action": "Biological Vector Larvicide Treatment & Riparian Drainage Clearing",
        "dossier_ref": "DEMO-OAH-2026-FR02",
    },
    "mondego-storm-surge": {
        "facility": "Hospital Distrital da Figueira da Foz • Emergency Ward",
        "bay": "Bay 01 • Encounter #ENC-7703",
        "patient_name": "João Ferreira, 34 yo male",
        "triage": "Urgency 2 (Yellow) • HR: 104 bpm • T: 38.6°C",
        "reason": "Patient reports sudden onset watery diarrhea, severe crampy abdominal pain, and nausea 18 hours after windsurfing in lower estuary reaches.",
        "location_context": "40.1510° N, -8.8450° W (Intersects Estuary Transition Reach)",
        "snomed_outcome": "SNOMED CT 69776003 (Acute gastroenteritis)",
        "clinical_consideration": "Incorporate confirmed enteropathogen (E. coli >2400 CFU/100mL) storm surge contamination into clinical history taking for acute gastroenteritis (SNOMED CT 69776003).",
        "doc_text": "Patient confirmed recreational water inhalation/ingestion during windsurfing in Mondego Estuary reach during storm surge runoff alert. Enteropathogen exposure documented in EHR.",
        "dispatch_target": "Administração Regional de Saúde (ARS Centro / APA)",
        "dispatch_action": "Immediate Recreational Bathing Water Closure & Microbial Resampling",
        "dossier_ref": "DEMO-OAH-2026-PT09",
    },
}


def _steps(scenario, evidence, report: dict[str, Any], all_passed: bool) -> list[dict[str, Any]]:
    """The 8 audit steps from OAH-Bridge's Judge Mode, each tagged with the timed stage it ran in."""
    sub = evidence.sub_scores
    summary = report["summary"]
    return [
        {
            "step": 1,
            "stage": "ingest",
            "title": "Multi-Source Evidence Ingestion",
            "detail": f"Ingested {len(scenario.citizen_reports)} citizen reports, {len(scenario.sensor_readings)} calibrated sensor telemetry readings, and {len(scenario.lab_assays)} lab assays for {scenario.city}.",
            "status": "COMPLETED",
        },
        {
            "step": 2,
            "stage": "corroborate",
            "title": "Deterministic Corroboration Scoring",
            "detail": f"Calculated sub-scores (Cs={sub.sensor_corroboration}, Cc={sub.citizen_agreement}, Ct={sub.temporal_consistency}) yielding composite score S = {evidence.score} (Methodology v0.1 fixed weights: 0.4/0.3/0.3).",
            "status": "COMPLETED",
        },
        {
            "step": 3,
            "stage": "corroborate",
            "title": "Epistemic Status Classification",
            "detail": f"Evaluated score and laboratory evidence. Classified assertion as '{evidence.epistemic_status}' ({evidence.epistemic_display}).",
            "status": "COMPLETED",
        },
        {
            "step": 4,
            "stage": "compose",
            "title": "Observation Semantic Synthesis",
            "detail": f"Created Hazard Observation with ascertainment technique '{scenario.ascertainment_technique}' and epistemic extension oah-evidence-status (valueCodeableConcept). Created standalone Evidence Support Observation (focus: Hazard Obs).",
            "status": "COMPLETED",
        },
        {
            "step": 5,
            "stage": "compose",
            "title": "Geospatial Exposure & Definitional Cohort Computation",
            "detail": f"Computed GIS buffer and boundary for {scenario.spatial_zone.site_name}. Represented definitional exposed population as FHIR Group (actual=false) with criteria.",
            "status": "COMPLETED",
        },
        {
            "step": 6,
            "stage": "compose",
            "title": "Population-Level Risk Assessment",
            "detail": f"Assembled FHIR RiskAssessment: subject=Group, basis=Evidence Support Observation, method=oah-environmental-exposure-assessment, prediction.outcome=SNOMED CT {scenario.snomed_outcome_code} ({scenario.snomed_outcome_display}), qualitativeRisk={scenario.qualitative_risk}.",
            "status": "COMPLETED",
        },
        {
            "step": 7,
            "stage": "compose",
            "title": "Provenance & Operational Workflow Dispatch",
            "detail": "Recorded FHIR Provenance audit trail. Dispatched operational FHIR Flag (surveillance alert) and CommunicationRequest (field inspection ticket).",
            "status": "COMPLETED",
        },
        {
            "step": 8,
            "stage": "validate",
            "title": "6-Tier Standards Conformance Verification",
            "detail": f"Ran automated validation harness. {summary['passed_checks']}/{summary['total_checks']} checks passed across all 6 tiers.",
            "status": "PASSED" if all_passed else "FAILED",
        },
    ]


def _scenario_detail(scenario, evidence) -> dict[str, Any]:
    zone = scenario.spatial_zone
    encounter: dict[str, Any] = dict(
        CLINICAL_PROFILES.get(scenario.scenario_id, CLINICAL_PROFILES[DEFAULT_SCENARIO])
    )
    encounter["dispatch_id"] = f"CommunicationRequest/oah-comm-{scenario.scenario_id}"
    encounter["synthetic"] = True
    return {
        "id": scenario.scenario_id,
        "title": scenario.title,
        "city": scenario.city,
        "river_system": scenario.river_system,
        "site_id": zone.site_id,
        "site_name": zone.site_name,
        "grounding_statement": scenario.grounding_statement,
        "hazard_code": scenario.hazard_code,
        "hazard_display": scenario.hazard_display,
        "evidence_score": evidence.score,
        "epistemic_status": evidence.epistemic_status,
        "epistemic_display": evidence.epistemic_display,
        "is_lab_confirmed": evidence.is_lab_confirmed,
        "methodology_version": evidence.methodology_version,
        "weights": evidence.weights,
        "disclaimer": evidence.disclaimer,
        "sub_scores": {
            "sensor_corroboration": evidence.sub_scores.sensor_corroboration,
            "citizen_agreement": evidence.sub_scores.citizen_agreement,
            "temporal_consistency": evidence.sub_scores.temporal_consistency,
        },
        "estimated_exposed_population": zone.estimated_exposed_population,
        "buffer_meters": zone.buffer_meters,
        "recreational_use_category": zone.recreational_use_category,
        "qualitative_risk": scenario.qualitative_risk,
        "risk_summary": scenario.risk_summary,
        "exposure_pathway_code": scenario.exposure_pathway_code,
        "exposure_pathway_display": scenario.exposure_pathway_display,
        "ascertainment_technique": scenario.ascertainment_technique,
        "ascertainment_display": scenario.ascertainment_display,
        "snomed_outcome_code": scenario.snomed_outcome_code,
        "snomed_outcome_display": scenario.snomed_outcome_display,
        "snomed_preferred_term": scenario.snomed_preferred_term,
        "snomed_outcome": f"{scenario.snomed_outcome_code} | Preferred term: {scenario.snomed_preferred_term} | Display: {scenario.snomed_outcome_display}",
        "sensor_readings": [
            {
                "id": r.reading_id,
                "timestamp": r.timestamp,
                "parameter": r.parameter,
                "value": r.value,
                "unit": r.unit,
                "baseline": r.nominal_baseline,
                "exceeded": r.threshold_exceeded,
            }
            for r in scenario.sensor_readings
        ],
        "citizen_reports": [
            {
                "id": c.report_id,
                "timestamp": c.timestamp,
                "sighting": c.sighting_type,
                "severity": c.severity_rating,
                "description": c.description,
                "observer": c.observer_type,
                "longitude": c.coordinates[0],
                "latitude": c.coordinates[1],
            }
            for c in scenario.citizen_reports
        ],
        "lab_assays": [
            {
                "id": a.sample_id,
                "timestamp": a.timestamp,
                "analyte": a.analyte,
                "concentration": a.concentration,
                "unit": a.unit,
                "threshold": a.regulatory_threshold,
                "laboratory": a.laboratory_name,
                "confirmed": a.confirmed_positive,
            }
            for a in scenario.lab_assays
        ],
        "model_inferences": [
            {
                "model": m.model_name,
                "version": m.version,
                "timestamp": m.timestamp,
                "predicted_hazard": m.predicted_hazard,
                "confidence": m.confidence,
                "ecological_factors": m.ecological_factors,
            }
            for m in scenario.model_inferences
        ],
        "clinical_encounter": encounter,
        "synthetic": True,
    }


def run_pipeline(scenario_id: str, *, fhir_base: str) -> dict[str, Any]:
    started = time.perf_counter()
    timings: dict[str, float] = {}

    t = time.perf_counter()
    scenario = _load(scenario_id)
    timings["ingest"] = _ms(t)

    t = time.perf_counter()
    evidence = _corroborate(scenario)
    timings["corroborate"] = _ms(t)

    t = time.perf_counter()
    bundle = compose_scenario_bundle(scenario, evidence, fhir_base=fhir_base)
    timings["compose"] = _ms(t)

    t = time.perf_counter()
    report = get_validator().validate_bundle(bundle, scenario, evidence)
    report_dict = report.to_dict()
    timings["validate"] = _ms(t)

    total_ms = _ms(started)
    run = {
        "id": f"run-{uuid.uuid4().hex[:12]}",
        "ran_at": _now_iso(),
        "engine": ENGINE_VERSION,
        "timings_ms": timings,
        "total_ms": total_ms,
    }
    METRICS.record_run(
        run_id=run["id"],
        scenario_id=scenario_id,
        ran_at=run["ran_at"],
        total_ms=total_ms,
        passed=report.all_passed,
        checks=report_dict["summary"],
    )
    return {
        "run": run,
        "scenario": _scenario_detail(scenario, evidence),
        "steps": _steps(scenario, evidence, report_dict, report.all_passed),
        "validation_report": report_dict,
        "bundle": bundle,
    }


# ---------------------------------------------------------------------------
# FHIR search (with the OAH custom search parameters)
# ---------------------------------------------------------------------------


def fhir_search(
    resource_type: str,
    scenario_id: str,
    *,
    hazard: str | None,
    location: str | None,
    fhir_base: str,
) -> dict[str, Any]:
    scenario = _load(scenario_id)
    evidence = _corroborate(scenario)
    bundle = compose_scenario_bundle(scenario, evidence, fhir_base=fhir_base)
    if resource_type == "Bundle":
        return bundle

    matched = []
    for entry in bundle.get("entry", []):
        res = entry.get("resource", {})
        if res.get("resourceType") != resource_type:
            continue
        if hazard is not None:
            codes = [c.get("code") for c in res.get("code", {}).get("coding", [])]
            if hazard not in codes:
                continue
        if location is not None and location not in res.get("subject", {}).get("reference", ""):
            continue
        matched.append(entry)
    return {
        "resourceType": "Bundle",
        "type": "searchset",
        "total": len(matched),
        "entry": [{"fullUrl": e.get("fullUrl"), "resource": e["resource"]} for e in matched],
    }


# ---------------------------------------------------------------------------
# CDS Hooks 1.0 (patient-view, informational only)
# ---------------------------------------------------------------------------

CDS_DISCOVERY: dict[str, Any] = {
    "services": [
        {
            "hook": "patient-view",
            "name": "OneAquaHealth Aquatic Environmental Exposure Advisory",
            "description": "Evaluates patient authorized location context against active environmental exposure zones and surfaces non-diagnostic clinical history taking alerts.",
            "id": "oah-exposure-advisory",
            "prefetch": {"patient": "Patient/{{context.patientId}}"},
        }
    ]
}


def cds_discovery() -> dict[str, Any]:
    return copy.deepcopy(CDS_DISCOVERY)


def evaluate_exposure_advisory(
    scenario_id: str,
    coordinates: tuple[float, float] | None,
    *,
    fhir_base: str,
) -> dict[str, Any]:
    scenario = _load(scenario_id)
    if coordinates is None:
        coords = DEFAULT_PATIENT_COORDS[scenario_id]
        location_source = "scenario-default (synthetic demo patient)"
    else:
        coords = coordinates
        location_source = "request"

    intersection = evaluate_patient_exposure_intersection((coords[0], coords[1]), scenario.spatial_zone)
    intersection["patient_coordinates"] = list(intersection["patient_coordinates"])

    cards = []
    if intersection["intersects"]:
        base = fhir_base.rstrip("/")
        cards.append(
            {
                "summary": "Environmental exposure context available",
                "indicator": "info",
                "detail": f"The patient's authorized location context intersects an active environmental exposure zone ({scenario.spatial_zone.site_name}, {scenario.city}). Recent recreational-water exposure may be relevant to clinical history taking regarding {scenario.snomed_outcome_display} (SNOMED CT {scenario.snomed_outcome_code}).",
                "source": {
                    "label": "OneAquaHealth Semantic Interoperability Bridge",
                    "url": "http://oneaquahealth.eu",
                },
                "suggestions": [
                    {
                        "label": "Inquire about recreational water contact",
                        "actions": [
                            {
                                "type": "create",
                                "description": "Document recreational aquatic exposure history in clinical notes.",
                            }
                        ],
                    }
                ],
                "links": [
                    {
                        "label": "Inspect Population RiskAssessment (FHIR R4)",
                        "url": f"{base}/RiskAssessment?scenario={scenario.scenario_id}",
                        "type": "absolute",
                    },
                    {
                        "label": f"View Location GeoJSON ({scenario.city})",
                        "url": f"{base}/Location?scenario={scenario.scenario_id}",
                        "type": "absolute",
                    },
                ],
            }
        )

    METRICS.record_cds(len(cards))
    return {
        "cards": cards,
        "intersection_evaluation": intersection,
        "location_source": location_source,
    }


# ---------------------------------------------------------------------------
# Conformance pack and terminology
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _conformance_items_cached() -> tuple[dict[str, Any], ...]:
    items = []
    for path in sorted(CONFORMANCE_DIR.rglob("*.json")):
        if path.name == "terminology_manifest.json":
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        items.append(
            {
                "resourceType": data.get("resourceType"),
                "id": data.get("id"),
                "url": data.get("url"),
                "title": data.get("title") or data.get("name"),
                "status": data.get("status"),
                "version": data.get("version"),
                "description": data.get("description"),
                "raw": data,
            }
        )
    return tuple(items)


def conformance_items() -> dict[str, Any]:
    items = copy.deepcopy(list(_conformance_items_cached()))
    return {"total": len(items), "items": items}


@lru_cache(maxsize=4)
def _json_file(name: str) -> dict[str, Any]:
    return json.loads((CONFORMANCE_DIR / name).read_text(encoding="utf-8"))


def terminology_manifest() -> dict[str, Any]:
    return copy.deepcopy(_json_file("terminology_manifest.json"))


def capability_statement(*, fhir_base: str) -> dict[str, Any]:
    data = copy.deepcopy(_json_file("capabilitystatement.json"))
    data.setdefault("implementation", {})["url"] = fhir_base.rstrip("/")
    return data


# ---------------------------------------------------------------------------
# Live system monitor
# ---------------------------------------------------------------------------


class _Metrics:
    """Process-local counters. They reset on restart and are per worker; the monitor says so."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.started_monotonic = time.monotonic()
        self.started_at = _now_iso()
        self.runs = 0
        self.runs_passed = 0
        self.runs_failed = 0
        self.cds_evaluations = 0
        self.cds_cards = 0
        self.recent_runs: deque[dict[str, Any]] = deque(maxlen=12)

    def record_run(self, *, run_id, scenario_id, ran_at, total_ms, passed, checks) -> None:
        with self._lock:
            self.runs += 1
            if passed:
                self.runs_passed += 1
            else:
                self.runs_failed += 1
            self.recent_runs.appendleft(
                {
                    "id": run_id,
                    "scenario": scenario_id,
                    "ran_at": ran_at,
                    "total_ms": total_ms,
                    "passed": passed,
                    "checks": f"{checks['passed_checks']}/{checks['total_checks']}",
                }
            )

    def record_cds(self, cards: int) -> None:
        with self._lock:
            self.cds_evaluations += 1
            self.cds_cards += cards

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "started_at": self.started_at,
                "uptime_seconds": int(time.monotonic() - self.started_monotonic),
                "counters": {
                    "pipeline_runs": self.runs,
                    "pipeline_runs_passed": self.runs_passed,
                    "pipeline_runs_failed": self.runs_failed,
                    "cds_evaluations": self.cds_evaluations,
                    "cds_cards_issued": self.cds_cards,
                },
                "recent_runs": list(self.recent_runs),
            }


METRICS = _Metrics()

_self_test_lock = threading.Lock()
_self_test: dict[str, Any] | None = None
_self_test_at = 0.0


def engine_self_test() -> dict[str, Any]:
    """Compose and validate every scenario. Cached for SELF_TEST_TTL_S so polling stays cheap."""
    global _self_test, _self_test_at
    with _self_test_lock:
        if _self_test is not None and time.monotonic() - _self_test_at < SELF_TEST_TTL_S:
            return _self_test
        started = time.perf_counter()
        results = []
        error = None
        try:
            for scenario_id in SCENARIOS:
                scenario = _load(scenario_id)
                evidence = _corroborate(scenario)
                bundle = compose_scenario_bundle(scenario, evidence)
                report = get_validator().validate_bundle(bundle, scenario, evidence)
                summary = report.to_dict()["summary"]
                results.append(
                    {
                        "scenario": scenario_id,
                        "passed": report.all_passed,
                        "checks": f"{summary['passed_checks']}/{summary['total_checks']}",
                    }
                )
        except Exception as exc:  # pragma: no cover - surfaced on the monitor, never raised
            error = type(exc).__name__
        _self_test = {
            "ran_at": _now_iso(),
            "duration_ms": _ms(started),
            "passed": error is None and all(r["passed"] for r in results),
            "results": results,
            "error": error,
        }
        _self_test_at = time.monotonic()
        return _self_test


def monitor_snapshot() -> dict[str, Any]:
    validator_ok = True
    codesystems = 0
    try:
        codesystems = len(get_validator().codesystems)
    except Exception:  # pragma: no cover
        validator_ok = False
    artefacts = len(_conformance_items_cached())
    self_test = engine_self_test()
    weather_state = weather.weather_status()

    components = [
        {
            "id": "engine",
            "label": "Corroboration engine",
            "status": "ok" if self_test["passed"] else "error",
            "detail": f"{len(SCENARIOS)} scenarios · self-test {self_test['duration_ms']} ms",
        },
        {
            "id": "validator",
            "label": "6-tier FHIR validator",
            "status": "ok" if validator_ok and codesystems > 0 else "error",
            "detail": f"{codesystems} OAH CodeSystems loaded",
        },
        {
            "id": "conformance",
            "label": "Conformance pack",
            "status": "ok" if artefacts > 0 else "error",
            "detail": f"{artefacts} artefacts (profiles, CodeSystems, ValueSets)",
        },
        {
            "id": "cds",
            "label": "CDS Hooks service",
            "status": "ok",
            "detail": "patient-view · oah-exposure-advisory (informational only)",
        },
        {
            "id": "weather",
            "label": "Open-Meteo weather",
            "status": weather_state["status"],
            "detail": weather_state["detail"],
        },
    ]
    degraded = any(c["status"] in ("error", "degraded") for c in components)
    return {
        "status": "degraded" if degraded else "operational",
        "server_time_utc": _now_iso(),
        "engine": ENGINE_VERSION,
        "components": components,
        "self_test": self_test,
        "weather": weather_state,
        "scope_note": "Counters are process-local: they reset on restart and are per worker.",
        **METRICS.snapshot(),
    }
