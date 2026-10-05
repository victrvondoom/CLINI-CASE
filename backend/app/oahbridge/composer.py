"""
FHIR R4 Resource Composer for OneAquaHealth Semantic Interoperability Bridge.
Constructs canonical, validated HL7 FHIR R4 resources implementing all frozen
informatics audit rules.
"""

import base64
import json
from datetime import UTC, datetime
from typing import Any

from .models import CompositeEvidenceResult, ScenarioDefinition


def create_location_resource(scenario: ScenarioDefinition) -> dict[str, Any]:
    """
    Constructs FHIR R4 Location with HL7-maintained draft extension:
    http://hl7.org/fhir/StructureDefinition/location-boundary-geojson
    """
    geojson_str = json.dumps(scenario.spatial_zone.geojson_polygon)
    geojson_b64 = base64.b64encode(geojson_str.encode("utf-8")).decode("utf-8")

    return {
        "resourceType": "Location",
        "id": scenario.spatial_zone.site_id,
        "status": "active",
        "name": f"{scenario.spatial_zone.site_name} ({scenario.city})",
        "description": f"Urban aquatic surveillance reach in {scenario.river_system} system. Recreational classification: {scenario.spatial_zone.recreational_use_category}.",
        "mode": "instance",
        "type": [
            {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/v3-EntityCode",
                        "code": "RIV",
                        "display": "River / Stream"
                    }
                ]
            }
        ],
        "extension": [
            {
                "url": "http://hl7.org/fhir/StructureDefinition/location-boundary-geojson",
                "valueAttachment": {
                    "contentType": "application/geo+json",
                    "data": geojson_b64,
                    "title": f"GeoJSON Spatial Boundary - {scenario.spatial_zone.site_name}"
                }
            }
        ],
        "position": {
            "longitude": scenario.spatial_zone.geojson_polygon["coordinates"][0][0][0],
            "latitude": scenario.spatial_zone.geojson_polygon["coordinates"][0][0][1]
        }
    }


def create_hazard_observation_resource(
    scenario: ScenarioDefinition,
    evidence: CompositeEvidenceResult
) -> dict[str, Any]:
    """
    Constructs FHIR R4 Hazard Observation.
    - Observation.method: Physical/algorithmic technique (http://oneaquahealth.eu/fhir/cs/observation-technique)
    - oah-evidence-status extension: valueCodeableConcept (http://oneaquahealth.eu/fhir/cs/evidence-status)
    - component: exposure-pathway
    """
    obs_id = f"oah-hazard-{scenario.scenario_id}"

    return {
        "resourceType": "Observation",
        "id": obs_id,
        "status": "final",
        "extension": [
            {
                "url": "http://oneaquahealth.eu/fhir/StructureDefinition/oah-evidence-status",
                "valueCodeableConcept": {
                    "coding": [
                        {
                            "system": "http://oneaquahealth.eu/fhir/cs/evidence-status",
                            "code": evidence.epistemic_status,
                            "display": evidence.epistemic_display
                        }
                    ]
                }
            }
        ],
        "code": {
            "coding": [
                {
                    "system": "http://oneaquahealth.eu/fhir/cs/hazard-type",
                    "code": scenario.hazard_code,
                    "display": scenario.hazard_display
                }
            ],
            "text": scenario.hazard_display
        },
        "subject": {
            "reference": f"Location/{scenario.spatial_zone.site_id}",
            "display": scenario.spatial_zone.site_name
        },
        "effectiveDateTime": datetime.now(UTC).isoformat(),
        "method": {
            "coding": [
                {
                    "system": "http://oneaquahealth.eu/fhir/cs/observation-technique",
                    "code": scenario.ascertainment_technique,
                    "display": scenario.ascertainment_display
                }
            ]
        },
        "component": [
            {
                "code": {
                    "coding": [
                        {
                            "system": "http://oneaquahealth.eu/fhir/cs/semantic-component",
                            "code": "exposure-pathway",
                            "display": "Exposure Pathway"
                        }
                    ]
                },
                "valueCodeableConcept": {
                    "coding": [
                        {
                            "system": "http://oneaquahealth.eu/fhir/cs/exposure-pathway",
                            "code": scenario.exposure_pathway_code,
                            "display": scenario.exposure_pathway_display
                        }
                    ]
                }
            }
        ]
    }


def create_evidence_support_observation_resource(
    scenario: ScenarioDefinition,
    evidence: CompositeEvidenceResult,
    hazard_obs_id: str
) -> dict[str, Any]:
    """
    Constructs Standalone Evidence Support Observation.
    - code: evidence-support-score (http://oneaquahealth.eu/fhir/cs/assessment-metrics)
    - valueDecimal: 0.00 - 1.00
    - focus: Reference(Observation/hazard)
    - component: sensor-corroboration, citizen-agreement, temporal-consistency
    """
    score_id = f"oah-evidence-support-{scenario.scenario_id}"

    return {
        "resourceType": "Observation",
        "id": score_id,
        "status": "final",
        "focus": [
            {
                "reference": f"Observation/{hazard_obs_id}",
                "display": f"Target Environmental Hazard ({scenario.hazard_display})"
            }
        ],
        "code": {
            "coding": [
                {
                    "system": "http://oneaquahealth.eu/fhir/cs/assessment-metrics",
                    "code": "evidence-support-score",
                    "display": "Environmental Evidence Support Score"
                }
            ],
            "text": "Multi-Source Environmental Evidence Support Score"
        },
        "valueDecimal": float(evidence.score),
        "note": [
            {
                "text": evidence.disclaimer
            }
        ],
        "component": [
            {
                "code": {
                    "coding": [
                        {
                            "system": "http://oneaquahealth.eu/fhir/cs/assessment-metrics",
                            "code": "sensor-corroboration",
                            "display": "Sensor Corroboration"
                        }
                    ]
                },
                "valueDecimal": float(evidence.sub_scores.sensor_corroboration)
            },
            {
                "code": {
                    "coding": [
                        {
                            "system": "http://oneaquahealth.eu/fhir/cs/assessment-metrics",
                            "code": "citizen-agreement",
                            "display": "Citizen Agreement"
                        }
                    ]
                },
                "valueDecimal": float(evidence.sub_scores.citizen_agreement)
            },
            {
                "code": {
                    "coding": [
                        {
                            "system": "http://oneaquahealth.eu/fhir/cs/assessment-metrics",
                            "code": "temporal-consistency",
                            "display": "Temporal Consistency"
                        }
                    ]
                },
                "valueDecimal": float(evidence.sub_scores.temporal_consistency)
            }
        ]
    }


def create_group_resource(scenario: ScenarioDefinition) -> dict[str, Any]:
    """
    Constructs FHIR R4 Definitional Group (actual = false).
    Represents the population potentially exposed based on geographic and activity criteria.
    """
    group_id = f"oah-cohort-{scenario.scenario_id}"

    return {
        "resourceType": "Group",
        "id": group_id,
        "type": "person",
        "actual": False,
        "name": f"Definitional Cohort: {scenario.spatial_zone.site_name} Aquatic Exposure Zone",
        "quantity": scenario.spatial_zone.estimated_exposed_population,
        "characteristic": [
            {
                "code": {
                    "coding": [
                        {
                            "system": "http://oneaquahealth.eu/fhir/cs/semantic-component",
                            "code": "spatial-exposure-zone",
                            "display": "Spatial Exposure Zone"
                        }
                    ]
                },
                "valueReference": {
                    "reference": f"Location/{scenario.spatial_zone.site_id}",
                    "display": f"{scenario.spatial_zone.site_name} ({scenario.city})"
                },
                "exclude": False
            },
            {
                "code": {
                    "coding": [
                        {
                            "system": "http://oneaquahealth.eu/fhir/cs/exposure-pathway",
                            "code": scenario.exposure_pathway_code,
                            "display": scenario.exposure_pathway_display
                        }
                    ]
                },
                "valueCodeableConcept": {
                    "coding": [
                        {
                            "system": "http://oneaquahealth.eu/fhir/cs/exposure-pathway",
                            "code": scenario.exposure_pathway_code,
                            "display": scenario.exposure_pathway_display
                        }
                    ]
                },
                "exclude": False
            }
        ]
    }


def create_risk_assessment_resource(
    scenario: ScenarioDefinition,
    group_id: str,
    evidence_score_id: str,
    hazard_obs_id: str
) -> dict[str, Any]:
    """
    Constructs FHIR R4 RiskAssessment.
    - subject: Reference(Group/...)
    - basis: Reference(Observation/evidence-support-id), Reference(Observation/hazard-id)
    - method: oah-environmental-exposure-assessment
    - prediction.outcome: SNOMED CT concept (CodeableConcept)
    - prediction.qualitativeRisk: HL7 risk-probability (CodeableConcept)
    """
    risk_id = f"oah-risk-{scenario.scenario_id}"

    return {
        "resourceType": "RiskAssessment",
        "id": risk_id,
        "status": "final",
        "subject": {
            "reference": f"Group/{group_id}",
            "display": f"Definitional Cohort ({scenario.spatial_zone.site_name})"
        },
        "basis": [
            {
                "reference": f"Observation/{evidence_score_id}",
                "display": "Environmental Evidence Support Score Observation"
            },
            {
                "reference": f"Observation/{hazard_obs_id}",
                "display": f"Environmental Hazard Observation ({scenario.hazard_display})"
            }
        ],
        "method": {
            "coding": [
                {
                    "system": "http://oneaquahealth.eu/fhir/cs/assessment-method",
                    "code": "oah-environmental-exposure-assessment",
                    "display": "OAH Environmental Exposure Risk Assessment"
                }
            ]
        },
        "occurrenceDateTime": datetime.now(UTC).isoformat(),
        "prediction": [
            {
                "outcome": {
                    "coding": [
                        {
                            "system": "http://snomed.info/sct",
                            "code": scenario.snomed_outcome_code,
                            "display": scenario.snomed_outcome_display
                        }
                    ],
                    "text": scenario.snomed_outcome_display
                },
                "qualitativeRisk": {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/risk-probability",
                            "code": scenario.qualitative_risk,
                            "display": scenario.qualitative_risk.capitalize()
                        }
                    ]
                },
                "rationale": scenario.risk_summary
            }
        ]
    }


def create_provenance_resource(
    scenario: ScenarioDefinition,
    target_ids: list[str]
) -> dict[str, Any]:
    """
    Constructs FHIR R4 Provenance documenting agents, sensors, and source entities.
    """
    prov_id = f"oah-prov-{scenario.scenario_id}"

    return {
        "resourceType": "Provenance",
        "id": prov_id,
        "target": [{"reference": tid} for tid in target_ids],
        "recorded": datetime.now(UTC).isoformat(),
        "reason": [
            {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/v3-ActReason",
                        "code": "PUBHLTH",
                        "display": "Public Health Surveillance"
                    }
                ]
            }
        ],
        "agent": [
            {
                "type": {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/provenance-participant-type",
                            "code": "author",
                            "display": "Author / Synthesizer"
                        }
                    ]
                },
                "who": {
                    "display": "OneAquaHealth Semantic Interoperability Bridge (OAH-Bridge Engine v0.1)"
                }
            }
        ],
        "entity": [
            {
                "role": "source",
                "what": {
                    "reference": f"Location/{scenario.spatial_zone.site_id}",
                    "display": f"{scenario.spatial_zone.site_name} GIS Boundary"
                }
            }
        ]
    }


def create_flag_resource(
    scenario: ScenarioDefinition,
    group_id: str,
    risk_id: str
) -> dict[str, Any]:
    """
    Constructs FHIR R4 Flag for operational Public Health surveillance interface.
    """
    flag_id = f"oah-flag-{scenario.scenario_id}"

    return {
        "resourceType": "Flag",
        "id": flag_id,
        "status": "active",
        "category": [
            {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/flag-category",
                        "code": "env",
                        "display": "Environmental Alert"
                    }
                ]
            }
        ],
        "code": {
            "coding": [
                {
                    "system": "http://oneaquahealth.eu/fhir/cs/hazard-type",
                    "code": scenario.hazard_code,
                    "display": scenario.hazard_display
                }
            ],
            "text": f"SURVEILLANCE ALERT: {scenario.hazard_display} in {scenario.spatial_zone.site_name}. Exposure risk: {scenario.qualitative_risk.upper()}."
        },
        "subject": {
            "reference": f"Group/{group_id}",
            "display": f"Definitional Cohort ({scenario.spatial_zone.site_name})"
        },
        "period": {
            "start": datetime.now(UTC).isoformat()
        }
    }


def create_communication_request_resource(
    scenario: ScenarioDefinition,
    risk_id: str
) -> dict[str, Any]:
    """
    Constructs FHIR R4 CommunicationRequest for dispatching environmental health inspection.
    """
    comm_id = f"oah-comm-{scenario.scenario_id}"

    return {
        "resourceType": "CommunicationRequest",
        "id": comm_id,
        "status": "active",
        "priority": "urgent",
        "category": [
            {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/communication-category",
                        "code": "alert",
                        "display": "Alert"
                    }
                ]
            }
        ],
        "about": [
            {
                "reference": f"RiskAssessment/{risk_id}",
                "display": "Associated Environmental Exposure RiskAssessment"
            }
        ],
        "payload": [
            {
                "contentString": f"Automated OAH-Bridge Dispatch: Deploy field inspection team to {scenario.spatial_zone.site_name} ({scenario.city}) for confirmatory laboratory grab sampling and advisory posting regarding {scenario.hazard_display}."
            }
        ],
        "authoredOn": datetime.now(UTC).isoformat()
    }


def compose_scenario_bundle(
    scenario: ScenarioDefinition,
    evidence: CompositeEvidenceResult,
    *,
    fhir_base: str = "http://localhost:8000/api/fhir"
) -> dict[str, Any]:
    """
    Composes complete FHIR R4 Bundle containing the scientific knowledge artifacts
    and downstream workflow artifacts.
    """
    location = create_location_resource(scenario)
    hazard_obs = create_hazard_observation_resource(scenario, evidence)
    evidence_obs = create_evidence_support_observation_resource(scenario, evidence, hazard_obs["id"])
    group = create_group_resource(scenario)
    risk_assmt = create_risk_assessment_resource(scenario, group["id"], evidence_obs["id"], hazard_obs["id"])
    flag = create_flag_resource(scenario, group["id"], risk_assmt["id"])
    comm_req = create_communication_request_resource(scenario, risk_assmt["id"])

    target_refs = [
        f"Location/{location['id']}",
        f"Observation/{hazard_obs['id']}",
        f"Observation/{evidence_obs['id']}",
        f"Group/{group['id']}",
        f"RiskAssessment/{risk_assmt['id']}"
    ]
    prov = create_provenance_resource(scenario, target_refs)

    resources = [
        location,
        hazard_obs,
        evidence_obs,
        group,
        risk_assmt,
        prov,
        flag,
        comm_req
    ]

    bundle_id = f"oah-bundle-{scenario.scenario_id}"
    entries = []
    for r in resources:
        entries.append({
            "fullUrl": f"{fhir_base.rstrip('/')}/{r['resourceType']}/{r['id']}",
            "resource": r
        })

    return {
        "resourceType": "Bundle",
        "id": bundle_id,
        "type": "collection",
        "timestamp": datetime.now(UTC).isoformat(),
        "total": len(entries),
        "entry": entries
    }
