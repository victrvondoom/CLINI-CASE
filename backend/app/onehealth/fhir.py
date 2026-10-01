"""FHIR R4-shaped, native-resource exchange with explicit draft-profile checks.

The installed fhir.resources library validates R4B base shapes, NOT R4 profiles.
Our pinned OAH constraint checks are additional and intentionally labelled partial.
Imports are staged as unverified evidence; provenance is not a digital signature.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from fhir.resources.R4B.bundle import Bundle

from app.onehealth.models import ExposureHistory, ExposureRecord, LabSample

OAH_COMMIT = "b907cf0869b59d82d9138b3d147fca66f333d911"
OAH = "http://hl7.eu/fhir/ig/oah/StructureDefinition/"
SYSTEM = "https://github.com/victrvondoom/CLINI-CASE/fhir/CodeSystem/one-health"
IDENTIFIER = "https://github.com/victrvondoom/CLINI-CASE/identifier/"
CONTRACT = "clincase-one-health-1"
STANDARDS = {
    "target": "FHIR R4 4.0.1",
    "oah_package": "hl7.eu.fhir.oah#0.1.0-ci-build",
    "oah_commit": OAH_COMMIT,
    "source": f"https://github.com/hl7-eu/oah/tree/{OAH_COMMIT}/input/fsh/profiles",
    "validation_scope": "R4B base-model validation + selected pinned OAH R4 constraints + ClinCase exchange contract",
    "full_hl7_profile_validation": False,
    "notice": "Draft alignment, not HL7 certification. Local arsenic and workflow codes need receiver agreement. Full R4 terminology/invariant validation remains required before deployment.",
}


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()


def coding(code: str) -> dict[str, Any]:
    return {"coding": [{"system": SYSTEM, "code": code}]}


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
            "type": [coding(s.kind)],
        },
        {"resourceType": "Organization", "id": "laboratory", "name": s.laboratory},
        {"resourceType": "PractitionerRole", "id": "collector", "code": [{"text": s.collector}]},
        {
            "resourceType": "Specimen",
            "id": "sample",
            "meta": {"profile": [OAH + "specimen-oah"]},
            "identifier": [{"system": IDENTIFIER + "sample", "value": s.sample_id}],
            "subject": _ref("Location", "sample-site"),
            "type": {"text": "Water sample"},
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
            "code": coding(s.analyte),
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
    return {
        f"{e['resource']['resourceType']}/{e['resource']['id']}": e["resource"]
        for e in bundle["entry"]
    }


def read_evidence(bundle: dict[str, Any]) -> dict[str, Any]:
    """Decode native lab and questionnaire fields. Never return local trust state."""
    resources = _resources(bundle)
    o = resources["Observation/lab-result"]
    site = resources["Location/sample-site"]
    specimen = resources["Specimen/sample"]
    answers = {}
    for i in resources["QuestionnaireResponse/exposure-history"]["item"]:
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
        kind=site["type"][0]["coding"][0]["code"],
        laboratory=resources["Organization/laboratory"]["name"],
        collector=resources["PractitionerRole/collector"]["code"][0]["text"],
        report_reference=o["identifier"][0]["value"],
        method=o["method"]["text"],
        collected_at=o["effectiveDateTime"],
        reported_at=o["issued"],
        analyte=o["code"]["coding"][0]["code"],
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
        "provenance": [
            {
                "action": x["activity"]["coding"][0]["code"],
                "at": x["recorded"],
                "actor_id": resources[x["agent"][0]["who"]["reference"]]["identifier"][0]["value"],
                "note": x["reason"][0]["text"],
            }
            for x in resources.values()
            if x["resourceType"] == "Provenance"
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
        resources = _resources(bundle)
        if len(resources) != len(bundle["entry"]):
            raise ValueError("Duplicate resource identity")
        urls = [e.get("fullUrl") for e in bundle["entry"]]
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
        for key in ("Location/waterbody", "Location/sample-site"):
            loc = resources[key]
            if not loc.get("identifier") or not loc.get("name") or loc.get("mode") != "instance":
                raise ValueError("OAH Location requires identifier, name and instance mode")
            if loc.get("position") and not {"longitude", "latitude"} <= loc["position"].keys():
                raise ValueError("OAH coordinates require latitude and longitude")
        obs = resources["Observation/lab-result"]
        if (
            obs.get("status") != "final"
            or not obs.get("performer")
            or not obs.get("effectiveDateTime")
            or obs.get("subject") != _ref("Location", "sample-site")
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
        if obs["code"]["coding"][0]["system"] != SYSTEM:
            raise ValueError("Analyte code system is not supported")
        sp = resources["Specimen/sample"]
        if (
            sp.get("subject") != _ref("Location", "sample-site")
            or sp.get("collection", {}).get("collector") != _ref("PractitionerRole", "collector")
            or sp["collection"].get("bodySite")
        ):
            raise ValueError(
                "OAH specimen requires location subject and collector role; no bodySite"
            )
        if sp["collection"]["collectedDateTime"] != obs["effectiveDateTime"]:
            raise ValueError("Sample and observation collection dates differ")
        evidence = read_evidence(bundle)
        h = evidence["history"]
        if h and resources["Patient/linked-patient"]["identifier"][0]["value"] != h["patient_id"]:
            raise ValueError("Patient identity mismatch between resources")
        if h:
            consent = resources["Consent/exposure-consent"]
            expected_consent = (
                "active"
                if h["consent_recorded"] and not evidence["consent_withdrawn"]
                else "inactive"
            )
            if (
                consent["status"] != expected_consent
                or consent["patient"] != _ref("Patient", "linked-patient")
                or consent["sourceAttachment"]["title"] != h["consent_reference"]
            ):
                raise ValueError("Consent disagrees with the exposure interview")
            task = resources["Task/clinical-review"]
            expected_review = {
                "pending": "requested",
                "reviewed": "completed",
                "rejected": "cancelled",
                "more_information": "on-hold",
            }[evidence["claimed_review"]]
            if task["status"] != expected_review or task["for"] != _ref(
                "Patient", "linked-patient"
            ):
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
