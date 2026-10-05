"""
Synthetic Demonstration Scenarios for OneAquaHealth Semantic Interoperability Bridge.
Grounded in OneAquaHealth research-city geography and ecosystem context:
- Coimbra (Mondego River Basin)
- Toulouse (Garonne Urban Aquatic System)
- Post-Storm Urban Stormwater Runoff

DISCLAIMER:
DEMONSTRATION DATA — NOT LIVE PUBLIC-HEALTH SURVEILLANCE.
"""

from .models import (
    CitizenReport,
    LabAssay,
    ModelInference,
    ScenarioDefinition,
    SensorReading,
    SpatialExposureZone,
)
from .scoring import compute_composite_evidence


def get_coimbra_scenario() -> ScenarioDefinition:
    """
    Scenario 1: Coimbra Pilot (Mondego Basin - Parque Verde do Mondego)
    Suspected Cyanobacterial Proliferation during summer stagnation.
    Demonstrates: Multi-source sensor + citizen corroboration yielding Evidence Support 0.86.
    """
    zone = SpatialExposureZone(
        site_id="oah-site-coimbra-04",
        site_name="Parque Verde do Mondego Reach",
        city="Coimbra",
        river_system="Mondego River",
        recreational_use_category="recreational-water-contact",
        estimated_exposed_population=1850,
        buffer_meters=350.0,
        geojson_polygon={
            "type": "Polygon",
            "coordinates": [
                [
                    [-8.4312, 40.2015],
                    [-8.4258, 40.2038],
                    [-8.4235, 40.2052],
                    [-8.4248, 40.2071],
                    [-8.4305, 40.2050],
                    [-8.4328, 40.2030],
                    [-8.4312, 40.2015]
                ]
            ]
        }
    )

    citizen_reports = [
        CitizenReport(
            report_id="cr-coimbra-101",
            timestamp="2026-10-01T14:30:00Z",
            site_id="oah-site-coimbra-04",
            observer_type="citizen-scientist",
            sighting_type="surface-scum",
            severity_rating=4,
            description="Thick greenish scum and blue-green paint-like streaks observed along riverbank steps near pedestrian bridge.",
            coordinates=[-8.4285, 40.2035]
        ),
        CitizenReport(
            report_id="cr-coimbra-102",
            timestamp="2026-10-01T16:15:00Z",
            site_id="oah-site-coimbra-04",
            observer_type="recreational-kayaker",
            sighting_type="water-discoloration",
            severity_rating=4,
            description="Noticeable earthy/musty odor and reduced water clarity while launching kayak at water sports pontoon.",
            coordinates=[-8.4271, 40.2042]
        ),
        CitizenReport(
            report_id="cr-coimbra-103",
            timestamp="2026-10-02T09:45:00Z",
            site_id="oah-site-coimbra-04",
            observer_type="field-volunteer",
            sighting_type="surface-scum",
            severity_rating=3,
            description="Accumulation of scum persisted overnight in sheltered eddy behind river island.",
            coordinates=[-8.4290, 40.2031]
        )
    ]

    sensor_readings = [
        SensorReading("sr-coimbra-201", "2026-10-01T12:00:00Z", "oah-site-coimbra-04", "water-temperature", 24.8, "degC", 19.5, True),
        SensorReading("sr-coimbra-202", "2026-10-01T12:00:00Z", "oah-site-coimbra-04", "chlorophyll-a", 38.6, "ug/L", 10.0, True),
        SensorReading("sr-coimbra-203", "2026-10-01T12:00:00Z", "oah-site-coimbra-04", "dissolved-oxygen", 11.4, "mg/L", 8.0, True),  # Daytime supersaturation
        SensorReading("sr-coimbra-204", "2026-10-01T12:00:00Z", "oah-site-coimbra-04", "pH", 8.8, "pH", 7.4, True),
        SensorReading("sr-coimbra-205", "2026-10-02T06:00:00Z", "oah-site-coimbra-04", "chlorophyll-a", 42.1, "ug/L", 10.0, True)
    ]

    return ScenarioDefinition(
        scenario_id="coimbra-cyanobacteria",
        title="Coimbra Mondego Reach — Suspected Cyanobacterial Proliferation",
        city="Coimbra",
        river_system="Mondego River Basin",
        grounding_statement="Synthetic demonstration scenario grounded in OneAquaHealth research-city geography (Coimbra / Mondego River).",
        hazard_code="cyanobacteria-proliferation",
        hazard_display="Suspected Cyanobacterial Proliferation",
        exposure_pathway_code="recreational-contact",
        exposure_pathway_display="Recreational Water Contact",
        snomed_outcome_code="40275004",
        snomed_outcome_display="Contact dermatitis",
        snomed_preferred_term="Contact dermatitis",
        qualitative_risk="moderate",
        risk_summary="Multi-source environmental evidence corroboration indicates active cyanobacterial surface proliferation along urban recreational reach. Primary dermal and mucosal exposure during water recreation represents moderate acute contact dermatitis risk.",
        ascertainment_technique="in-situ-sensor-probe",
        ascertainment_display="In-situ Sensor Telemetry Probe & Citizen Corroboration",
        spatial_zone=zone,
        citizen_reports=citizen_reports,
        sensor_readings=sensor_readings
    )


def get_toulouse_scenario() -> ScenarioDefinition:
    """
    Scenario 2: Toulouse Pilot (Garonne Urban Reach - Île du Ramier)
    Diptera Mosquito Vector Surge modeled by DipteraCAST inference.
    Demonstrates: Model inference ascertainment and vector-borne exposure pathway.
    """
    zone = SpatialExposureZone(
        site_id="oah-site-toulouse-02",
        site_name="Île du Ramier Urban Aquatic Margin",
        city="Toulouse",
        river_system="Garonne River",
        recreational_use_category="urban-riparian-park",
        estimated_exposed_population=3200,
        buffer_meters=500.0,
        geojson_polygon={
            "type": "Polygon",
            "coordinates": [
                [
                    [1.4310, 43.5820],
                    [1.4395, 43.5850],
                    [1.4420, 43.5895],
                    [1.4380, 43.5930],
                    [1.4330, 43.5910],
                    [1.4290, 43.5860],
                    [1.4310, 43.5820]
                ]
            ]
        }
    )

    citizen_reports = [
        CitizenReport(
            report_id="cr-toulouse-301",
            timestamp="2026-10-01T18:00:00Z",
            site_id="oah-site-toulouse-02",
            observer_type="urban-park-visitor",
            sighting_type="larval-cluster",
            severity_rating=4,
            description="Dense mosquito swarm and standing water breeding clusters along backwater drainage channel.",
            coordinates=[1.4355, 43.5870]
        ),
        CitizenReport(
            report_id="cr-toulouse-302",
            timestamp="2026-10-02T08:30:00Z",
            site_id="oah-site-toulouse-02",
            observer_type="citizen-scientist",
            sighting_type="mosquito-nuisance",
            severity_rating=4,
            description="Persistent daytime biting activity along riparian walking path.",
            coordinates=[1.4370, 43.5885]
        )
    ]

    sensor_readings = [
        SensorReading("sr-toulouse-401", "2026-10-01T15:00:00Z", "oah-site-toulouse-02", "water-temperature", 22.3, "degC", 18.0, True),
        SensorReading("sr-toulouse-402", "2026-10-01T15:00:00Z", "oah-site-toulouse-02", "stagnation-index", 0.82, "ratio", 0.3, True)
    ]

    model_inferences = [
        ModelInference(
            model_name="DipteraCAST-EcoSurv",
            version="2.4.1",
            timestamp="2026-10-02T07:00:00Z",
            site_id="oah-site-toulouse-02",
            predicted_hazard="diptera-vector-surge",
            confidence=0.88,
            ecological_factors={"riparian_stagnation": 0.85, "degree_days": 182, "canopy_cover": 0.65}
        )
    ]

    return ScenarioDefinition(
        scenario_id="toulouse-diptera",
        title="Toulouse Garonne Margin — Diptera Vector Proliferation Surge",
        city="Toulouse",
        river_system="Garonne Urban River System",
        grounding_statement="Synthetic demonstration scenario grounded in OneAquaHealth research-city geography (Toulouse / Garonne River).",
        hazard_code="diptera-vector-surge",
        hazard_display="Diptera Vector Proliferation Surge",
        exposure_pathway_code="vector-borne-bite",
        exposure_pathway_display="Vector-Borne Arthropod Bite",
        snomed_outcome_code="416113008",
        snomed_outcome_display="Acute febrile illness",
        snomed_preferred_term="Disorder characterized by fever",
        qualitative_risk="high",
        risk_summary="DipteraCAST algorithmic model synthesis and citizen biting reports indicate acute ecological surge in disease-vector diptera along riparian park margins. Vector-bite exposure pathway carries elevated risk of acute febrile illness requiring differential clinical history taking.",
        ascertainment_technique="predictive-model-inference",
        ascertainment_display="Predictive Algorithmic Model Inference (DipteraCAST)",
        spatial_zone=zone,
        citizen_reports=citizen_reports,
        sensor_readings=sensor_readings,
        model_inferences=model_inferences
    )


def get_storm_surge_scenario() -> ScenarioDefinition:
    """
    Scenario 3: Synthetic Storm Runoff (Post-Storm Enteropathogen Alert)
    Demonstrates: Simulated reference-laboratory assay override yielding Epistemic Status: confirmed.
    """
    zone = SpatialExposureZone(
        site_id="oah-site-mondego-downstream",
        site_name="Mondego Estuary Transition Zone",
        city="Figueira da Foz / Coimbra Sub-basin",
        river_system="Mondego Lower Basin",
        recreational_use_category="recreational-water-contact",
        estimated_exposed_population=950,
        buffer_meters=600.0,
        geojson_polygon={
            "type": "Polygon",
            "coordinates": [
                [
                    [-8.8500, 40.1450],
                    [-8.8400, 40.1480],
                    [-8.8350, 40.1550],
                    [-8.8450, 40.1580],
                    [-8.8550, 40.1520],
                    [-8.8500, 40.1450]
                ]
            ]
        }
    )

    citizen_reports = [
        CitizenReport(
            report_id="cr-storm-501",
            timestamp="2026-10-01T05:30:00Z",
            site_id="oah-site-mondego-downstream",
            observer_type="citizen-scientist",
            sighting_type="surface-scum",
            severity_rating=4,
            description="Combined sewer overflow plume with turbid dark runoff visible entering estuary margin.",
            coordinates=[-8.8450, 40.1500]
        ),
        CitizenReport(
            report_id="cr-storm-502",
            timestamp="2026-10-01T07:15:00Z",
            site_id="oah-site-mondego-downstream",
            observer_type="recreational-swimmer",
            sighting_type="water-discoloration",
            severity_rating=3,
            description="Strong sewage and organic decomposition odor along beach margin near breakwater.",
            coordinates=[-8.8420, 40.1510]
        )
    ]

    sensor_readings = [
        SensorReading("sr-storm-501", "2026-10-01T04:00:00Z", "oah-site-mondego-downstream", "turbidity", 85.0, "NTU", 12.0, True),
        SensorReading("sr-storm-502", "2026-10-01T04:00:00Z", "oah-site-mondego-downstream", "electrical-conductivity", 650.0, "uS/cm", 250.0, True)
    ]

    lab_assays = [
        LabAssay(
            sample_id="lab-mondego-992",
            timestamp="2026-10-02T10:00:00Z",
            site_id="oah-site-mondego-downstream",
            analyte="Escherichia coli",
            concentration=2400.0,
            unit="CFU/100mL",
            regulatory_threshold=500.0,
            confirmed_positive=True,
            laboratory_name="Simulated Reference Laboratory (Synthetic Scenario)"
        )
    ]

    return ScenarioDefinition(
        scenario_id="mondego-storm-surge",
        title="Lower Mondego — Post-Storm Runoff Enteropathogen Surge",
        city="Figueira da Foz / Coimbra",
        river_system="Mondego River Basin",
        grounding_statement="Synthetic demonstration scenario grounded in OneAquaHealth research-city lower basin geography.",
        hazard_code="enteropathogen-surge",
        hazard_display="Post-Surge Enteropathogen Contamination",
        exposure_pathway_code="recreational-contact",
        exposure_pathway_display="Recreational Water Contact",
        snomed_outcome_code="69776003",
        snomed_outcome_display="Acute gastroenteritis",
        snomed_preferred_term="Acute gastroenteritis",
        qualitative_risk="high",
        risk_summary="Simulated reference-laboratory assay indicates E. coli concentration (2400 CFU/100mL) substantially exceeding EU Bathing Water recreational thresholds following combined storm runoff. Primary water recreation carries high acute waterborne gastroenteritis risk context.",
        ascertainment_technique="laboratory-chemical-assay",
        ascertainment_display="Simulated Reference-Laboratory Microbial Assay Override",
        spatial_zone=zone,
        citizen_reports=citizen_reports,
        sensor_readings=sensor_readings,
        lab_assays=lab_assays
    )


SCENARIOS = {
    "coimbra-cyanobacteria": get_coimbra_scenario,
    "toulouse-diptera": get_toulouse_scenario,
    "mondego-storm-surge": get_storm_surge_scenario
}


def load_scenario_and_compute(scenario_id: str):
    """
    Loads scenario, dynamically computes deterministic evidence score directly from raw inputs,
    and returns scenario definition and computed evidence.
    """
    if scenario_id not in SCENARIOS:
        raise ValueError(f"Unknown scenario ID: {scenario_id}. Available: {list(SCENARIOS.keys())}")

    scenario = SCENARIOS[scenario_id]()

    # Dynamically compute deterministic evidence score and sub-scores directly from scenario inputs
    evidence = compute_composite_evidence(
        readings=scenario.sensor_readings,
        reports=scenario.citizen_reports,
        lab_assays=scenario.lab_assays
    )

    return scenario, evidence
