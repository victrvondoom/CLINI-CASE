"""FHIR R4-shaped, native-resource exchange with explicit draft-profile checks.

The installed fhir.resources library validates R4B base shapes, NOT R4 profiles.
Our pinned OAH constraint checks are additional and intentionally labelled partial.
Imports are staged as unverified evidence; provenance is not a digital signature.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from typing import Any

from fhir.resources.R4B.bundle import Bundle

from app.onehealth.models import ANALYTES, Analyte, ExposureHistory, ExposureRecord, LabSample

OAH_COMMIT = "b907cf0869b59d82d9138b3d147fca66f333d911"
OAH = "http://hl7.eu/fhir/ig/oah/StructureDefinition/"
OAH_CODE_SYSTEM = "http://hl7.eu/fhir/ig/oah/CodeSystem/temporarySystem-oah-eu"
OAH_INDICATORS_VALUE_SET = (
    "http://hl7.eu/fhir/ig/oah/ValueSet/oah-indicators-no-health-oah-vs"
)
OAH_PROFILES = {
    "Location": OAH + "location-oah",
    "Specimen": OAH + "specimen-oah",
    "Observation": OAH + "observation-indicators-oah",
}
SYSTEM = "https://github.com/victrvondoom/CLINI-CASE/fhir/CodeSystem/one-health"
IDENTIFIER = "https://github.com/victrvondoom/CLINI-CASE/identifier/"
CONTRACT = "clincase-one-health-1"
ANALYTE_LABELS = {
    "total_arsenic": "Total arsenic",
    "inorganic_arsenic": "Inorganic arsenic",
    "dissolved_arsenic": "Arsenic dissolved",
}
STANDARDS = {
    "target": "FHIR R4 4.0.1",
    "oah_package": "hl7.eu.fhir.oah#0.1.0-ci-build",
    "oah_commit": OAH_COMMIT,
    "oah_publication_status": "draft CI build; not an authorized publication",
    "oah_profiles": OAH_PROFILES,
    "oah_indicator_value_set": OAH_INDICATORS_VALUE_SET,
    "oah_specimen_type_value_set": "http://hl7.eu/fhir/ig/oah/ValueSet/specimen-type-oah-vs",
    "verified_oah_analyte": {
        "system": OAH_CODE_SYSTEM,
        "code": "arsenic-dissolved",
        "display": "Arsenic dissolved",
    },
    "source": f"https://github.com/hl7-eu/oah/tree/{OAH_COMMIT}/input/fsh/profiles",
    "validation_scope": "R4B base-model validation + selected pinned OAH R4 constraints + ClinCase exchange contract",
    "full_hl7_profile_validation": False,
    "notice": "Pinned CI-build alignment only, not an authorized OAH publication or HL7 certification. Only dissolved arsenic has a verified OAH terminology coding; total/inorganic arsenic remain local text concepts. Full profile, invariant, and terminology validation is not established.",
}


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()


def coding(code: str) -> dict[str, Any]:
    return {"coding": [{"system": SYSTEM, "code": code}]}


def analyte_concept(concept: str) -> dict[str, Any]:
    """Encode only the one analyte concept verified in the pinned OAH guide."""
    if concept == "dissolved_arsenic":
        return {
            "coding": [
                {
                    "system": OAH_CODE_SYSTEM,
                    "code": "arsenic-dissolved",
                    "display": "Arsenic dissolved",
                }
            ],
            "text": "Arsenic dissolved",
        }
    if concept in ("total_arsenic", "inorganic_arsenic"):
        # These are supported internal concepts, but the pinned OAH guide has no
        # verified matching code. Text preserves meaning without asserting one.
        return {"text": ANALYTE_LABELS[concept]}
    raise ValueError("Unsupported analyte concept")


def _decode_analyte(codeable: Any) -> Analyte:
    if not isinstance(codeable, dict):
        raise ValueError("Observation analyte code is missing")
    codings = codeable.get("coding") or []
    if not codings:
        matches = [
            concept for concept in ANALYTES if codeable.get("text") == ANALYTE_LABELS[concept]
        ]
        if len(matches) == 1 and matches[0] in ("total_arsenic", "inorganic_arsenic"):
            return matches[0]
        raise ValueError("Analyte has no supported terminology mapping or recognized local text")
    if len(codings) != 1:
        raise ValueError("Analyte must have exactly one supported coding")
    item = codings[0]
    if (
        item.get("system") == OAH_CODE_SYSTEM
        and item.get("code") == "arsenic-dissolved"
        and item.get("display") in (None, "Arsenic dissolved")
    ):
        return "dissolved_arsenic"
    # Read legacy internally coded bundles, but never generate these as OAH codes.
    # Compare by equality so an untrusted non-string code is rejected, never hashed.
    if item.get("system") == SYSTEM:
        for concept in ANALYTES:
            if item.get("code") == concept:
                return concept
    raise ValueError("Analyte terminology code is not supported by the pinned OAH contract")


def _ref(kind: str, rid: str) -> dict[str, Any]:
    return {"reference": f"{kind}/{rid}"}


def export(record: ExposureRecord) -> dict[str, Any]:
    r = record
    s = r.sample
    resources: list[dict[str, Any]] = [
        {
            "resourceType": "Location",
            "id": "waterbody",
            "meta": {"profile": [OAH + "location-oah"]},
            "identifier": [{"system": IDENTIFIER + "waterbody", "value": r.waterbody_id}],
            "name": r.waterbody_name,
            "mode": "instance",
        },
        {
            "resourceType": "Location",
            "id": "sample-site",
            "meta": {"profile": [OAH + "location-oah"]},
            "identifier": [{"system": IDENTIFIER + "sample-site", "value": s.sample_id}],
            "name": s.location_name,
            "mode": "instance",
            # The Location.role value set does not define these environmental
            # sample kinds; retain the source concept as text, not a false code.
            "type": [{"text": s.kind}],
        },
        {"resourceType": "Organization", "id": "laboratory", "name": s.laboratory},
        {"resourceType": "PractitionerRole", "id": "collector", "code": [{"text": s.collector}]},
        {
            "resourceType": "Specimen",
            "id": "sample",
            "meta": {"profile": [OAH + "specimen-oah"]},
            "identifier": [{"system": IDENTIFIER + "sample", "value": s.sample_id}],
            "subject": _ref("Location", "sample-site"),
            "type": {
                "coding": [
                    {
                        "system": "http://snomed.info/sct",
                        "code": "11713004",
                        "display": "Water",
                    }
                ],
                "text": "Water sample",
            },
            "collection": {
                "collector": _ref("PractitionerRole", "collector"),
                "collectedDateTime": s.collected_at.isoformat(),
            },
        },
        {
            "resourceType": "Observation",
            "id": "lab-result",
            "meta": {"profile": [OAH + "observation-indicators-oah"]},
            "identifier": [
                {"system": IDENTIFIER + "laboratory-report", "value": s.report_reference}
            ],
            # final describes the submitted lab report, not our independent verification.
            "status": "final",
            "code": analyte_concept(s.analyte),
            "subject": _ref("Location", "sample-site"),
            "specimen": _ref("Specimen", "sample"),
            "effectiveDateTime": s.collected_at.isoformat(),
            "issued": s.reported_at.isoformat(),
            "performer": [_ref("Organization", "laboratory")],
            "method": {"text": s.method},
            "valueQuantity": {
                "value": s.value,
                "unit": s.unit,
                "system": "http://unitsofmeasure.org",
                "code": s.unit,
                **({"comparator": "<"} if s.qualifier == "lt" else {}),
            },
        },
        {
            "resourceType": "Task",
            "id": "environmental-followup",
            "status": r.followup_status.replace("_", "-"),
            "intent": "proposal",
            "code": coding("environmental-retest"),
            "focus": _ref("Location", "sample-site"),
            "description": "Investigate the water source and document a retest. No patient details in this task.",
            **(
                {
                    "output": [
                        {
                            "type": coding("followup-report"),
                            "valueString": r.followup_evidence_reference,
                        }
                    ]
                }
                if r.followup_evidence_reference
                else {}
            ),
        },
    ]
    items = []

    def item(key: str, value: Any) -> None:
        if value is None:
            return
        kind = "Boolean" if isinstance(value, bool) else "String"
        items.append({"linkId": key, "answer": [{"value" + kind: value}]})

    for key, value in {
        "observation_id": r.observation_id,
        "lab_verified": r.lab_verified,
        "review": r.review,
        "case_id": r.case_id,
        "created_at": r.created_at.isoformat(),
        "followup_evidence_reference": r.followup_evidence_reference,
    }.items():
        item(key, value)
    h = r.history
    if h:
        resources += [
            {
                "resourceType": "Patient",
                "id": "linked-patient",
                "identifier": [{"system": IDENTIFIER + "patient", "value": h.patient_id}],
            },
            {
                "resourceType": "Consent",
                "id": "exposure-consent",
                "status": "inactive" if r.consent_withdrawn or not h.consent_recorded else "active",
                "scope": {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/consentscope",
                            "code": "patient-privacy",
                        }
                    ]
                },
                "category": [coding("exposure-evidence-sharing")],
                "patient": _ref("Patient", "linked-patient"),
                "sourceAttachment": {"title": h.consent_reference},
                "policyRule": {
                    "text": "Recorded local consent; receiver must reconfirm permission"
                },
            },
            {
                "resourceType": "Task",
                "id": "clinical-review",
                "status": {
                    "pending": "requested",
                    "reviewed": "completed",
                    "rejected": "cancelled",
                    "more_information": "on-hold",
                }[r.review],
                "intent": "proposal",
                "code": coding("exposure-clinical-review"),
                "for": _ref("Patient", "linked-patient"),
                "focus": _ref("Observation", "lab-result"),
                "description": "Review exposure relevance; no disease prediction or treatment order.",
            },
        ]
        for key, value in h.model_dump(mode="json").items():
            item("exposure." + key, value)
        item("consent_withdrawn", r.consent_withdrawn)
    resources.append(
        {
            "resourceType": "QuestionnaireResponse",
            "id": "exposure-history",
            "status": "completed",
            "item": items,
            **({"subject": _ref("Patient", "linked-patient")} if h else {}),
        }
    )
    for index, event in enumerate(r.audit):
        aid = f"actor-{index}"
        resources.extend(
            [
                {
                    "resourceType": "Practitioner",
                    "id": aid,
                    "identifier": [{"system": IDENTIFIER + "reviewer", "value": event.actor_id}],
                },
                {
                    "resourceType": "Provenance",
                    "id": f"audit-{index}",
                    "target": [_ref("QuestionnaireResponse", "exposure-history")],
                    "recorded": event.at.isoformat(),
                    "activity": coding(event.action),
                    "reason": [{"text": event.note}],
                    "agent": [{"who": _ref("Practitioner", aid)}],
                },
            ]
        )
    return {
        "resourceType": "Bundle",
        "id": r.id,
        "type": "collection",
        "timestamp": r.created_at.isoformat(),
        "identifier": {"system": IDENTIFIER + "exposure", "value": r.id},
        "meta": {
            "versionId": str(r.version),
            "tag": [
                {"system": SYSTEM, "code": CONTRACT},
                {"system": SYSTEM, "code": "synthetic" if r.synthetic else "non-synthetic"},
            ],
        },
        "entry": [
            {
                "fullUrl": f"https://clincase.invalid/fhir/{x['resourceType']}/{x['id']}",
                "resource": x,
            }
            for x in resources
        ],
    }


def _resources(bundle: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Index resources by FHIR identity and fullUrl, never by a demo-specific id."""
    result: dict[str, dict[str, Any]] = {}
    for entry in bundle["entry"]:
        resource = entry["resource"]
        result[f"{resource['resourceType']}/{resource['id']}"] = resource
        if entry.get("fullUrl"):
            result[entry["fullUrl"]] = resource
    return result


def _role_resource(
    resources: dict[str, dict[str, Any]],
    resource_type: str,
    predicate: Callable[[dict[str, Any]], bool],
    role: str,
) -> dict[str, Any]:
    matches = [
        value
        for value in {id(item): item for item in resources.values()}.values()
        if value.get("resourceType") == resource_type and predicate(value)
    ]
    if len(matches) != 1:
        raise ValueError(f"Expected one unambiguous {role} {resource_type}; found {len(matches)}")
    return matches[0]


def _profiled(resource: dict[str, Any], profile: str) -> bool:
    return OAH + profile in resource.get("meta", {}).get("profile", [])


def _identifier_role(resource: dict[str, Any], role: str) -> bool:
    return any(
        item.get("system") == IDENTIFIER + role
        for item in resource.get("identifier", [])
    )


def _resolve(resources: dict[str, dict[str, Any]], reference: Any, expected: str) -> dict[str, Any]:
    if not isinstance(reference, dict) or not isinstance(reference.get("reference"), str):
        raise ValueError(f"Missing {expected} reference")
    resource = resources.get(reference["reference"])
    if not resource or resource.get("resourceType") != expected:
        raise ValueError(f"Unresolved {expected} reference")
    return resource


def _exchange_resources(bundle: dict[str, Any]) -> dict[str, Any]:
    """Resolve this gateway's supported semantic roles through profiles and references."""
    resources = _resources(bundle)
    observation = _role_resource(
        resources,
        "Observation",
        lambda r: _profiled(r, "observation-indicators-oah")
        and _identifier_role(r, "laboratory-report"),
        "laboratory result",
    )
    specimen = _resolve(resources, observation.get("specimen"), "Specimen")
    site = _resolve(resources, observation.get("subject"), "Location")
    if site != _resolve(resources, specimen.get("subject"), "Location"):
        raise ValueError("Observation and Specimen resolve to different sampling locations")
    waterbody = _role_resource(
        resources,
        "Location",
        lambda r: _profiled(r, "location-oah") and _identifier_role(r, "waterbody"),
        "waterbody",
    )
    performers = observation.get("performer") or []
    if len(performers) != 1:
        raise ValueError("Expected one laboratory performer")
    laboratory = _resolve(resources, performers[0], "Organization")
    role = _resolve(
        resources,
        specimen.get("collection", {}).get("collector"),
        "PractitionerRole",
    )
    questionnaire = _role_resource(
        resources,
        "QuestionnaireResponse",
        lambda r: any(
            item.get("linkId") == "observation_id" for item in r.get("item", [])
        ),
        "source questionnaire",
    )
    consent_rows = [
        r
        for r in {id(item): item for item in resources.values()}.values()
        if r.get("resourceType") == "Consent"
        and any(
            coding.get("system") == SYSTEM and coding.get("code") == "exposure-evidence-sharing"
            for category in r.get("category", [])
            for coding in category.get("coding", [])
        )
    ]
    consent = consent_rows[0] if len(consent_rows) == 1 else None
    patient = _resolve(resources, consent.get("patient"), "Patient") if consent else None
    tasks = [
        r
        for r in {id(item): item for item in resources.values()}.values()
        if r.get("resourceType") == "Task"
    ]
    review_tasks = [
        r
        for r in tasks
        if any(
            c.get("system") == SYSTEM and c.get("code") == "exposure-clinical-review"
            for c in r.get("code", {}).get("coding", [])
        )
    ]
    followup_tasks = [
        r
        for r in tasks
        if any(
            c.get("system") == SYSTEM and c.get("code") == "environmental-retest"
            for c in r.get("code", {}).get("coding", [])
        )
    ]
    provenance = [
        r
        for r in {id(item): item for item in resources.values()}.values()
        if r.get("resourceType") == "Provenance"
        and any(
            _resolve(resources, target, "QuestionnaireResponse") == questionnaire
            for target in r.get("target", [])
        )
    ]
    return {
        "index": resources,
        "observation": observation,
        "specimen": specimen,
        "site": site,
        "waterbody": waterbody,
        "laboratory": laboratory,
        "role": role,
        "questionnaire": questionnaire,
        "consent": consent,
        "patient": patient,
        "review_tasks": review_tasks,
        "followup_tasks": followup_tasks,
        "provenance": provenance,
    }


def read_evidence(bundle: dict[str, Any]) -> dict[str, Any]:
    """Decode native lab and questionnaire fields. Never return local trust state."""
    selected = _exchange_resources(bundle)
    resources = selected["index"]
    o = selected["observation"]
    site = selected["site"]
    specimen = selected["specimen"]
    answers = {}
    for i in selected["questionnaire"]["item"]:
        if i["linkId"] in answers:
            raise ValueError("Duplicate questionnaire answer")
        if len(i.get("answer", [])) != 1 or len(i["answer"][0]) != 1:
            raise ValueError("Each exchange-contract question requires one unambiguous answer")
        if not set(i["answer"][0]) <= {"valueString", "valueBoolean"}:
            raise ValueError("Unsupported questionnaire answer type")
        answers[i["linkId"]] = next(iter(i["answer"][0].values()))
    sample = LabSample(
        sample_id=specimen["identifier"][0]["value"],
        location_name=site["name"],
        kind=(
            site["type"][0].get("text")
            or (site["type"][0].get("coding") or [{}])[0].get("code")
        ),
        laboratory=selected["laboratory"]["name"],
        collector=selected["role"]["code"][0]["text"],
        report_reference=o["identifier"][0]["value"],
        method=o["method"]["text"],
        collected_at=o["effectiveDateTime"],
        reported_at=o["issued"],
        analyte=_decode_analyte(o.get("code")),
        value=o["valueQuantity"]["value"],
        unit=o["valueQuantity"]["code"],
        qualifier="lt" if o["valueQuantity"].get("comparator") == "<" else "eq",
    )
    history_data = {
        k.removeprefix("exposure."): v for k, v in answers.items() if k.startswith("exposure.")
    }
    history = ExposureHistory.model_validate(history_data) if history_data else None
    return {
        "sample": sample.model_dump(mode="json"),
        "history": history.model_dump(mode="json") if history else None,
        "source_observation_id": answers["observation_id"],
        "claimed_review": answers.get("review", "pending"),
        "consent_withdrawn": answers.get("consent_withdrawn", False),
        "waterbody_name": selected["waterbody"]["name"],
        "provenance": [
            {
                "action": x["activity"]["coding"][0]["code"],
                "at": x["recorded"],
                "actor_id": _resolve(
                    resources, x["agent"][0]["who"], "Practitioner"
                )["identifier"][0]["value"],
                "note": x["reason"][0]["text"],
            }
            for x in selected["provenance"]
        ],
    }


def validate(bundle: dict[str, Any]) -> dict[str, Any]:
    issues: list[str] = []
    try:
        if len(json.dumps(bundle)) > 500_000:
            raise ValueError("Bundle exceeds 500 KB exchange limit")
        Bundle.parse_obj(bundle)
        if bundle.get("type") != "collection":
            raise ValueError(
                "Only collection bundles are accepted; no executable transaction imports"
            )
        if {"system": SYSTEM, "code": CONTRACT} not in bundle.get("meta", {}).get("tag", []):
            raise ValueError("Unsupported exchange contract")
        demo_tags = [
            t
            for t in bundle["meta"]["tag"]
            if t.get("system") == SYSTEM and t.get("code") in ("synthetic", "non-synthetic")
        ]
        if len(demo_tags) != 1:
            raise ValueError("Exactly one synthetic/non-synthetic classification is required")
        identity_resources = {
            f"{e['resource']['resourceType']}/{e['resource']['id']}": e["resource"]
            for e in bundle["entry"]
        }
        if len(identity_resources) != len(bundle["entry"]):
            raise ValueError("Duplicate resource identity")
        resources = _resources(bundle)
        urls = [e["fullUrl"] for e in bundle["entry"] if e.get("fullUrl")]
        if len(urls) != len(set(urls)):
            raise ValueError("Duplicate fullUrl")

        def references(node: Any) -> None:
            if isinstance(node, dict):
                if "reference" in node and node["reference"] not in resources:
                    raise ValueError("Unresolved or external resource reference")
                for value in node.values():
                    references(value)
            elif isinstance(node, list):
                for value in node:
                    references(value)

        references(bundle)
        selected = _exchange_resources(bundle)
        for loc in (selected["waterbody"], selected["site"]):
            if not loc.get("identifier") or not loc.get("name") or loc.get("mode") != "instance":
                raise ValueError("OAH Location requires identifier, name and instance mode")
            if loc.get("position") and not {"longitude", "latitude"} <= loc["position"].keys():
                raise ValueError("OAH coordinates require latitude and longitude")
        obs = selected["observation"]
        if (
            obs.get("status") != "final"
            or not obs.get("performer")
            or not obs.get("effectiveDateTime")
            or _resolve(resources, obs.get("subject"), "Location") != selected["site"]
        ):
            raise ValueError(
                "OAH indicator requires final status, location subject, effective time and performer"
            )
        quantity = obs["valueQuantity"]
        if (
            quantity.get("system") != "http://unitsofmeasure.org"
            or quantity.get("comparator") not in (None, "<")
            or quantity.get("unit") != quantity.get("code")
        ):
            raise ValueError("Unsupported or inconsistent quantity units/comparator")
        _decode_analyte(obs.get("code"))
        sp = selected["specimen"]
        if (
            _resolve(resources, sp.get("subject"), "Location") != selected["site"]
            or _resolve(
                resources, sp.get("collection", {}).get("collector"), "PractitionerRole"
            ) != selected["role"]
            or sp["collection"].get("bodySite")
        ):
            raise ValueError(
                "OAH specimen requires location subject and collector role; no bodySite"
            )
        if sp["collection"]["collectedDateTime"] != obs["effectiveDateTime"]:
            raise ValueError("Sample and observation collection dates differ")
        evidence = read_evidence(bundle)
        h = evidence["history"]
        selected = _exchange_resources(bundle)
        observation = selected["observation"]
        if (
            observation.get("status") != "final"
            or not observation.get("performer")
            or not observation.get("effectiveDateTime")
            or observation.get("subject") is None
        ):
            raise ValueError(
                "OAH indicator requires final status, location subject, effective time and performer"
            )
        if not selected["waterbody"].get("name") or not selected["site"].get("name"):
            raise ValueError("OAH Location requires identifier, name and profile")
        if h and selected["patient"]["identifier"][0]["value"] != h["patient_id"]:
            raise ValueError("Patient identity mismatch between resources")
        if h:
            consent = selected["consent"]
            expected_consent = (
                "active"
                if h["consent_recorded"] and not evidence["consent_withdrawn"]
                else "inactive"
            )
            if (
                consent["status"] != expected_consent
                or _resolve(resources, consent["patient"], "Patient") != selected["patient"]
                or consent["sourceAttachment"]["title"] != h["consent_reference"]
            ):
                raise ValueError("Consent disagrees with the exposure interview")
            if len(selected["review_tasks"]) != 1:
                raise ValueError("Expected one clinical review task")
            task = selected["review_tasks"][0]
            expected_review = {
                "pending": "requested",
                "reviewed": "completed",
                "rejected": "cancelled",
                "more_information": "on-hold",
            }[evidence["claimed_review"]]
            if task["status"] != expected_review or _resolve(
                resources, task["for"], "Patient"
            ) != selected["patient"]:
                raise ValueError("Clinical task and interview review state disagree")
    except Exception as exc:  # noqa: BLE001 - return a bounded OperationOutcome, never model internals
        issues.append(str(exc)[:500])
    return {
        "valid": not issues,
        "sha256": digest(bundle),
        "standards": STANDARDS,
        "operation_outcome": {
            "resourceType": "OperationOutcome",
            "issue": [{"severity": "error", "code": "invalid", "diagnostics": i} for i in issues]
            or [
                {
                    "severity": "information",
                    "code": "informational",
                    "diagnostics": "Selected draft constraints and exchange contract passed; not full HL7 validation.",
                }
            ],
        },
    }
