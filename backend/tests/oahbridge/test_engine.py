"""OAH-Bridge engine tests.

The first sections are OneAquaHealth-Bridge's own tests (MIT), ported with package imports
so the ported engine is held to the same assertions as upstream. The service section covers
the CLINI-CASE orchestration layer.
"""

from __future__ import annotations

import json

import pytest

from app.oahbridge import service
from app.oahbridge.composer import compose_scenario_bundle
from app.oahbridge.models import LabAssay
from app.oahbridge.scenarios import SCENARIOS, get_coimbra_scenario, load_scenario_and_compute
from app.oahbridge.scoring import (
    WEIGHT_CITIZEN,
    WEIGHT_SENSOR,
    WEIGHT_TEMPORAL,
    EvidenceSubScores,
    compute_composite_evidence,
)
from app.oahbridge.spatial import (
    build_definitional_cohort_characteristics,
    evaluate_patient_exposure_intersection,
    point_in_polygon,
)

COIMBRA = "coimbra-cyanobacteria"
INSIDE_COIMBRA = (-8.4285, 40.2035)
OUTSIDE_COIMBRA = (-8.6000, 40.3500)


# --- scoring (upstream tests/test_scoring.py) ------------------------------


def test_fixed_weights_sum_to_one():
    assert WEIGHT_SENSOR == 0.40
    assert WEIGHT_CITIZEN == 0.30
    assert WEIGHT_TEMPORAL == 0.30
    assert pytest.approx(WEIGHT_SENSOR + WEIGHT_CITIZEN + WEIGHT_TEMPORAL, 0.001) == 1.00


def test_coimbra_score_calibration():
    result = compute_composite_evidence(
        sub_scores=EvidenceSubScores(
            sensor_corroboration=0.90, citizen_agreement=0.75, temporal_consistency=0.92
        )
    )
    assert result.score == 0.86
    assert result.epistemic_status == "inferred"
    assert "Modeled Inference" in result.epistemic_display
    assert result.methodology_version == "v0.1-prototype"
    assert "Not clinically validated" in result.disclaimer


def test_laboratory_confirmation_override():
    lab = LabAssay(
        sample_id="lab-01",
        timestamp="2026-10-02T10:00:00Z",
        site_id="site-01",
        analyte="Microcystin-LR",
        concentration=15.0,
        unit="ug/L",
        regulatory_threshold=1.0,
        confirmed_positive=True,
        laboratory_name="Reference Lab",
    )
    result = compute_composite_evidence(
        sub_scores=EvidenceSubScores(
            sensor_corroboration=0.85, citizen_agreement=0.70, temporal_consistency=0.88
        ),
        lab_assays=[lab],
    )
    assert result.score == 0.81
    assert result.epistemic_status == "confirmed"
    assert result.is_lab_confirmed is True


def test_low_score_epistemic_classification():
    result = compute_composite_evidence(
        sub_scores=EvidenceSubScores(
            sensor_corroboration=0.20, citizen_agreement=0.30, temporal_consistency=0.20
        )
    )
    assert result.score == 0.23
    assert result.epistemic_status == "observed"


# --- spatial (upstream tests/test_spatial.py, tests/test_cds_hooks.py) -----


def test_point_in_polygon_inside_and_outside():
    square = [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0], [0.0, 0.0]]
    assert point_in_polygon((5.0, 5.0), square) is True
    assert point_in_polygon((15.0, 15.0), square) is False
    assert point_in_polygon((-1.0, 5.0), square) is False


def test_coimbra_patient_exposure_intersection():
    zone = get_coimbra_scenario().spatial_zone
    inside = evaluate_patient_exposure_intersection(INSIDE_COIMBRA, zone)
    assert inside["intersects"] is True
    assert inside["city"] == "Coimbra"
    assert inside["site_id"] == "oah-site-coimbra-04"
    assert evaluate_patient_exposure_intersection(OUTSIDE_COIMBRA, zone)["intersects"] is False


def test_definitional_cohort_characteristics_structure():
    chars = build_definitional_cohort_characteristics(get_coimbra_scenario().spatial_zone)
    assert len(chars) == 2
    assert chars[0]["valueReference"]["reference"] == "Location/oah-site-coimbra-04"
    assert chars[0]["exclude"] is False
    assert chars[1]["valueCodeableConcept"]["coding"][0]["code"] == "recreational-contact"
    assert chars[1]["exclude"] is False


# --- composer (upstream tests/test_composer.py) ----------------------------


def _bundle(scenario_id: str = COIMBRA, **kwargs):
    scenario, evidence = load_scenario_and_compute(scenario_id)
    return compose_scenario_bundle(scenario, evidence, **kwargs)


def _resources(bundle, resource_type):
    return [e["resource"] for e in bundle["entry"] if e["resource"]["resourceType"] == resource_type]


def test_bundle_composition_resource_types():
    bundle = _bundle()
    assert bundle["resourceType"] == "Bundle"
    assert bundle["type"] == "collection"
    assert bundle["total"] == 8
    assert {e["resource"]["resourceType"] for e in bundle["entry"]} == {
        "Location",
        "Observation",
        "Group",
        "RiskAssessment",
        "Provenance",
        "Flag",
        "CommunicationRequest",
    }


def test_hazard_observation_semantics():
    hazard = [
        o
        for o in _resources(_bundle(), "Observation")
        if o["code"]["coding"][0]["code"] != "evidence-support-score"
    ][0]
    assert hazard["method"]["coding"][0]["system"] == "http://oneaquahealth.eu/fhir/cs/observation-technique"
    assert hazard["method"]["coding"][0]["code"] == "in-situ-sensor-probe"
    ext = [e for e in hazard["extension"] if "oah-evidence-status" in e["url"]][0]
    assert ext["valueCodeableConcept"]["coding"][0]["system"] == "http://oneaquahealth.eu/fhir/cs/evidence-status"
    assert ext["valueCodeableConcept"]["coding"][0]["code"] == "inferred"


def test_evidence_support_observation_semantics():
    support = [
        o
        for o in _resources(_bundle(), "Observation")
        if o["code"]["coding"][0]["code"] == "evidence-support-score"
    ][0]
    assert support["valueDecimal"] == 0.86
    assert len(support["focus"]) == 1
    assert "Observation/oah-hazard-coimbra-cyanobacteria" in support["focus"][0]["reference"]
    assert len(support["component"]) == 3


def test_risk_assessment_semantics():
    ra = _resources(_bundle(), "RiskAssessment")[0]
    assert "Group/" in ra["subject"]["reference"]
    assert any("oah-evidence-support" in b["reference"] for b in ra["basis"])
    assert "condition" not in ra
    assert ra["method"]["coding"][0]["code"] == "oah-environmental-exposure-assessment"
    prediction = ra["prediction"][0]
    assert prediction["outcome"]["coding"][0]["system"] == "http://snomed.info/sct"
    assert prediction["outcome"]["coding"][0]["code"] == "40275004"
    assert prediction["qualitativeRisk"]["coding"][0]["code"] == "moderate"


def test_full_url_uses_supplied_fhir_base():
    bundle = _bundle(fhir_base="https://example.test/api/oah-bridge/fhir/")
    assert bundle["entry"][0]["fullUrl"] == (
        "https://example.test/api/oah-bridge/fhir/Location/oah-site-coimbra-04"
    )


# --- validation pipeline (upstream tests/test_validation_pipeline.py) ------


@pytest.mark.parametrize("scenario_id", list(SCENARIOS))
def test_validation_all_scenarios_pass(scenario_id):
    scenario, evidence = load_scenario_and_compute(scenario_id)
    report = service.get_validator().validate_bundle(
        compose_scenario_bundle(scenario, evidence), scenario, evidence
    )
    failed = [
        c["name"] for tier in report.tiers.values() for c in tier["checks"] if not c["passed"]
    ]
    assert report.all_passed is True, failed


def test_validator_detects_illegal_risk_condition():
    scenario, evidence = load_scenario_and_compute(COIMBRA)
    bundle = compose_scenario_bundle(scenario, evidence)
    for resource in _resources(bundle, "RiskAssessment"):
        resource["condition"] = {"coding": [{"system": "http://snomed.info/sct", "code": "40275004"}]}
    report = service.get_validator().validate_bundle(bundle, scenario, evidence)
    assert report.all_passed is False
    assert report.tiers["tier2_profiles"]["passed"] is False


def test_validator_detects_unknown_oah_code():
    scenario, evidence = load_scenario_and_compute(COIMBRA)
    bundle = compose_scenario_bundle(scenario, evidence)
    _resources(bundle, "RiskAssessment")[0]["method"]["coding"][0]["code"] = "made-up-method"
    report = service.get_validator().validate_bundle(bundle, scenario, evidence)
    assert report.tiers["tier3_codesystems"]["passed"] is False


def test_snomed_ct_terminology_manifest_resolution():
    manifest = json.loads(
        (service.CONFORMANCE_DIR / "terminology_manifest.json").read_text(encoding="utf-8")
    )
    concepts = {c["code"]: c for c in manifest["concepts"]}
    expected = {
        "coimbra-cyanobacteria": "40275004",
        "toulouse-diptera": "416113008",
        "mondego-storm-surge": "69776003",
    }
    for scenario_id, code in expected.items():
        scenario, _ = load_scenario_and_compute(scenario_id)
        assert scenario.snomed_outcome_code == code
        assert concepts[code]["validation_status"] == "VERIFIED_ACTIVE"
        assert scenario_id in concepts[code]["scenarios"]


# --- CLINI-CASE orchestration layer ----------------------------------------


def test_scores_match_upstream_engine():
    """The split, timed corroboration must equal upstream load_scenario_and_compute."""
    for scenario_id in SCENARIOS:
        _, upstream = load_scenario_and_compute(scenario_id)
        ours = service._corroborate(service._load(scenario_id))
        assert ours.score == upstream.score
        assert ours.epistemic_status == upstream.epistemic_status
        assert ours.sub_scores == upstream.sub_scores


def test_list_scenarios_exposes_globe_geometry():
    rows = {row["id"]: row for row in service.list_scenarios()}
    assert set(rows) == set(SCENARIOS)
    coimbra = rows[COIMBRA]
    assert coimbra["evidence_score"] == 0.86
    assert coimbra["epistemic_status"] == "inferred"
    assert coimbra["synthetic"] is True
    assert coimbra["site"]["polygon"][0] == coimbra["site"]["polygon"][-1]
    centroid = coimbra["site"]["centroid"]
    assert point_in_polygon((centroid["longitude"], centroid["latitude"]), coimbra["site"]["polygon"])
    assert rows["mondego-storm-surge"]["epistemic_status"] == "confirmed"


def test_run_pipeline_reports_real_stage_timings():
    result = service.run_pipeline(COIMBRA, fhir_base="https://example.test/fhir")
    assert set(result["run"]["timings_ms"]) == {"ingest", "corroborate", "compose", "validate"}
    assert all(v >= 0 for v in result["run"]["timings_ms"].values())
    assert result["run"]["total_ms"] >= result["run"]["timings_ms"]["validate"]
    assert len(result["steps"]) == 8
    assert {s["stage"] for s in result["steps"]} == {"ingest", "corroborate", "compose", "validate"}
    assert result["validation_report"]["all_passed"] is True
    assert result["validation_report"]["summary"]["total_checks"] == 44
    assert result["scenario"]["clinical_encounter"]["synthetic"] is True
    assert result["bundle"]["entry"][0]["fullUrl"].startswith("https://example.test/fhir/")


def test_unknown_scenario_is_rejected_not_defaulted():
    with pytest.raises(service.UnknownScenarioError):
        service.run_pipeline("atlantis-kraken", fhir_base="https://example.test/fhir")


def test_cds_advisory_inside_and_outside_zone():
    inside = service.evaluate_exposure_advisory(COIMBRA, INSIDE_COIMBRA, fhir_base="https://e.test/fhir")
    assert len(inside["cards"]) == 1
    card = inside["cards"][0]
    assert card["summary"] == "Environmental exposure context available"
    assert card["indicator"] == "info"
    assert "Contact dermatitis" in card["detail"]
    assert card["links"][0]["url"] == "https://e.test/fhir/RiskAssessment?scenario=coimbra-cyanobacteria"
    assert inside["location_source"] == "request"

    outside = service.evaluate_exposure_advisory(COIMBRA, OUTSIDE_COIMBRA, fhir_base="https://e.test/fhir")
    assert outside["cards"] == []


def test_cds_advisory_without_coordinates_says_it_used_the_demo_patient():
    result = service.evaluate_exposure_advisory(COIMBRA, None, fhir_base="https://e.test/fhir")
    assert result["location_source"].startswith("scenario-default")
    assert result["intersection_evaluation"]["patient_coordinates"] == list(
        service.DEFAULT_PATIENT_COORDS[COIMBRA]
    )


def test_cds_cards_never_carry_diagnosis_or_treatment_language():
    for scenario_id in SCENARIOS:
        result = service.evaluate_exposure_advisory(scenario_id, None, fhir_base="https://e.test/fhir")
        for card in result["cards"]:
            assert card["indicator"] == "info"
            text = json.dumps(card).lower()
            for banned in ("diagnosed with", "prescribe", "administer", "treatment:"):
                assert banned not in text


def test_fhir_search_applies_oah_parameters():
    hits = service.fhir_search(
        "Observation", COIMBRA, hazard="cyanobacteria-proliferation", location=None, fhir_base="https://e.test/fhir"
    )
    assert hits["type"] == "searchset"
    assert hits["total"] == 1
    assert hits["entry"][0]["resource"]["code"]["coding"][0]["code"] == "cyanobacteria-proliferation"

    none = service.fhir_search(
        "Observation", COIMBRA, hazard="no-such-hazard", location=None, fhir_base="https://e.test/fhir"
    )
    assert none["total"] == 0

    bundle = service.fhir_search("Bundle", COIMBRA, hazard=None, location=None, fhir_base="https://e.test/fhir")
    assert bundle["type"] == "collection"
    assert bundle["total"] == 8


def test_capability_statement_points_at_this_server():
    cap = service.capability_statement(fhir_base="https://e.test/api/oah-bridge/fhir/")
    assert cap["resourceType"] == "CapabilityStatement"
    assert cap["fhirVersion"] == "4.0.1"
    assert cap["implementation"]["url"] == "https://e.test/api/oah-bridge/fhir"
    # the cached original is not mutated
    assert service.capability_statement(fhir_base="https://other.test/fhir")["implementation"]["url"] == (
        "https://other.test/fhir"
    )


def test_conformance_pack_is_complete():
    pack = service.conformance_items()
    assert pack["total"] >= 12
    types = {item["resourceType"] for item in pack["items"]}
    assert {"CodeSystem", "ValueSet", "StructureDefinition", "CapabilityStatement"} <= types


def test_monitor_snapshot_reports_components_and_counters():
    before = service.METRICS.snapshot()["counters"]["pipeline_runs"]
    service.run_pipeline(COIMBRA, fhir_base="https://e.test/fhir")
    snapshot = service.monitor_snapshot()
    assert snapshot["counters"]["pipeline_runs"] == before + 1
    ids = {c["id"]: c["status"] for c in snapshot["components"]}
    assert set(ids) == {"engine", "validator", "conformance", "cds", "weather"}
    assert ids["engine"] == ids["validator"] == ids["conformance"] == "ok"
    assert snapshot["self_test"]["passed"] is True
    assert snapshot["recent_runs"][0]["scenario"] == COIMBRA
