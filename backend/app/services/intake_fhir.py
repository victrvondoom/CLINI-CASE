"""Conservative document-to-FHIR shaping before clinical extraction.

Only explicitly labeled facts become resources. Missing facts stay missing;
this adapter neither interprets biomarkers nor makes coverage decisions.
"""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from typing import Any

from app.models.intake import DocumentClassification, ExtractedField, IntakeResult, OCRResult

_SOURCE_EXTENSION = "urn:clincase:source-document"
_LABELS = {
    "patient": r"patient(?:\s*\(initials\)|\s+initials|\s+name)?",
    "identifier": r"mrn|medical record (?:number|id)|patient id",
    "age_sex": r"age\s*/\s*sex",
    "diagnosis": r"(?:primary\s+)?diagnosis(?:\s*\(icd[- ]?10\))?",
    "icd10": r"icd[- ]?10(?:\s+code)?",
    "stage": r"(?:cancer\s+|liver disease\s+)?stage",
    "treatment": r"drug|requested treatment|requested medication",
    "j_code": r"hcpcs\s*/\s*j[- ]code|j[- ]code|hcpcs(?:\s+code)?",
    "dose": r"dose|dosage",
    "HER2 IHC": r"her[- ]?2(?:\s+ihc)?",
    "HER2 FISH": r"her[- ]?2\s+fish",
    "ER": r"er|estrogen receptor",
    "PR": r"pr|progesterone receptor",
    "Ki-67": r"ki[- ]?67",
    "ECOG": r"ecog(?:\s+performance status)?",
    "LVEF": r"lvef(?:\s*\([^\n:]*\))?",
    "histology": r"histology",
    "pathology_confirmation": r"pathologic diagnosis confirmed",
    "cardiac_history": r"cardiac history",
    "genotype": r"genotype",
    "HCV RNA": r"hcv rna(?:\s+quantitative)?",
}
_MISSING = re.compile(r"^(?:unknown|not (?:documented|available)|n/?a|pending)\b", re.I)
_ICD10 = re.compile(r"\b([A-Z]\d{2}(?:\.[A-Z0-9]{1,4})?)\b", re.I)


def clinical_document_text(text: str) -> str:
    """Remove demo verdict instructions while preserving the clinical record."""
    return re.sub(r"__VERDICT_HINT_[A-Z_]+__", "", text).strip(" \r\n\t")


def bundle_from_note(initials: str, note: str) -> dict[str, Any]:
    """Compatibility for older upload callers; requires an actual diagnosis."""
    result = IntakeResult(
        classification=DocumentClassification(
            document_type="typed_print", confidence=1.0, rationale="User-supplied clinical note"
        ),
        ocr=OCRResult(
            engine="plain_text",
            full_text=f"Patient initials: {initials}\n{note}",
            extracted_fields=[],
            overall_confidence=1.0,
        ),
        clinical_snapshot_partial={},
        audit={"document_sha256": hashlib.sha256(note.encode()).hexdigest()},
    )
    return shape_intake(result).fhir_bundle


def shape_intake(result: IntakeResult) -> IntakeResult:
    """Add an auditable case payload to every document-format response."""
    text = clinical_document_text(result.ocr.full_text)
    values: dict[str, str] = {}
    fields: list[ExtractedField] = []
    conflicts: list[str] = []
    for name, label in _LABELS.items():
        pattern = re.compile(rf"^[ \t]*(?:{label})[ \t]*:[ \t]*(?:\n[ \t]*)?([^\n]+)", re.I | re.M)
        matches = [m for m in pattern.finditer(text) if not _MISSING.match(m.group(1).strip())]
        matches = [m for m in matches if not m.group(1).strip().endswith(":")]
        if not matches:
            continue
        distinct = {re.sub(r"\s+", " ", m.group(1).strip()).lower() for m in matches}
        if len(distinct) > 1:
            conflicts.append(name)
            continue
        match = matches[0]
        value = re.sub(r"</?b>", "", match.group(1).strip(), flags=re.I)
        values[name] = value
        fields.append(
            ExtractedField(
                name=name,
                value=value,
                confidence=result.ocr.overall_confidence,
                source_excerpt=match.group(0).strip(),
                page=(1 + text[: match.start()].count("\f"))
                if result.ocr.pages == 1 or "\f" in text
                else None,
            )
        )

    # PA request headings sometimes provide the requested drug instead of a
    # separate Drug field. An arbitrary mention elsewhere is never sufficient.
    if "treatment" not in values and "treatment" not in conflicts:
        match = re.search(r"^([^\n:]+?)\s+\((J\d{4})\)\s+for\s+[^\n]+$", text, re.I | re.M)
        if match:
            values["treatment"] = match.group(1).strip()
            values.setdefault("j_code", match.group(2).upper())
            fields.append(
                ExtractedField(
                    name="treatment",
                    value=values["treatment"],
                    confidence=result.ocr.overall_confidence,
                    source_excerpt=match.group(0),
                    page=(1 + text[: match.start()].count("\f"))
                    if result.ocr.pages == 1 or "\f" in text
                    else None,
                )
            )

    digest = str(result.audit.get("document_sha256") or hashlib.sha256(text.encode()).hexdigest())
    suffix = digest[:16]
    patient_id = f"intake-patient-{suffix}"
    document_id = f"intake-document-{suffix}"
    condition_id = f"intake-condition-{suffix}"
    patient_ref = {"reference": f"Patient/{patient_id}"}
    source_extension = [
        {
            "url": _SOURCE_EXTENSION,
            "valueReference": {"reference": f"DocumentReference/{document_id}"},
        }
    ]
    resources: list[dict[str, Any]] = []
    patient_value = values.get("patient")
    has_patient = bool(patient_value or values.get("identifier"))
    initials = None
    snapshot = dict(result.clinical_snapshot_partial)
    if has_patient:
        patient: dict[str, Any] = {
            "resourceType": "Patient",
            "id": patient_id,
            "extension": source_extension,
        }
        if patient_value:
            patient["name"] = [{"text": patient_value}]
            initials = (
                patient_value
                if re.fullmatch(r"[A-Z. ]{1,16}", patient_value)
                else ".".join(w[0].upper() for w in patient_value.split() if w) + "."
            )
        if values.get("identifier"):
            patient["identifier"] = [
                {"type": {"text": "Medical record number"}, "value": values["identifier"]}
            ]
        age_sex = re.match(
            r"(\d{1,3})\s*(?:y|years?)?\s*/\s*(male|female|other|unknown)\b",
            values.get("age_sex", ""),
            re.I,
        )
        if age_sex:
            patient["gender"] = age_sex.group(2).lower()
            snapshot["patient_sex"] = patient["gender"]
            age = int(age_sex.group(1))
            if 0 <= age <= 130:
                snapshot["patient_age"] = age
                resources.append(
                    {
                        "resourceType": "Observation",
                        "id": f"intake-age-{suffix}",
                        "status": "final",
                        "code": {"text": "Age at document submission"},
                        "subject": patient_ref,
                        "extension": source_extension,
                        "valueQuantity": {
                            "value": age,
                            "unit": "years",
                            "system": "http://unitsofmeasure.org",
                            "code": "a",
                        },
                    }
                )
        resources.insert(0, patient)

    diagnosis = values.get("diagnosis") or values.get("icd10")
    if has_patient and diagnosis:
        condition: dict[str, Any] = {
            "resourceType": "Condition",
            "id": condition_id,
            "subject": patient_ref,
            "code": {"text": diagnosis},
            "extension": source_extension,
        }
        code_match = _ICD10.search(values.get("icd10") or diagnosis)
        partial: dict[str, Any] = {"description": diagnosis, "source_resource_id": condition_id}
        if code_match:
            icd = code_match.group(1).upper()
            # The source does not distinguish WHO ICD-10 from ICD-10-CM.
            # Preserve its code without asserting a terminology system.
            condition["code"]["coding"] = [{"code": icd}]
            partial["icd10_code"] = icd
        if values.get("stage"):
            condition["stage"] = [{"summary": {"text": values["stage"]}}]
            partial["stage"] = values["stage"]
        for key in ("histology", "pathology_confirmation", "cardiac_history"):
            if values.get(key):
                condition.setdefault("note", []).append({"text": f"{key}: {values[key]}"})
        resources.append(condition)
        snapshot["primary_diagnosis"] = partial

    treatment = {"name": values["treatment"]} if values.get("treatment") else {}
    if values.get("j_code"):
        j_match = re.search(r"\bJ\d{4}\b", values["j_code"], re.I)
        if j_match:
            treatment["j_code"] = j_match.group(0).upper()
    if values.get("dose"):
        treatment["dose"] = values["dose"]
    if treatment.get("name"):
        snapshot["requested_treatment"] = treatment
        if has_patient:
            resources.append(
                {
                    "resourceType": "MedicationRequest",
                    "id": f"intake-medication-{suffix}",
                    "status": "draft",
                    "intent": "proposal",
                    "subject": patient_ref,
                    "medicationCodeableConcept": {"text": treatment["name"]},
                    "extension": source_extension,
                    **(
                        {"dosageInstruction": [{"text": treatment["dose"]}]}
                        if "dose" in treatment
                        else {}
                    ),
                }
            )
    if has_patient:
        for name in (
            "HER2 IHC",
            "HER2 FISH",
            "ER",
            "PR",
            "Ki-67",
            "ECOG",
            "LVEF",
            "genotype",
            "HCV RNA",
        ):
            if name in values:
                observation: dict[str, Any] = {
                    "resourceType": "Observation",
                    "id": f"intake-observation-{len(resources)}-{suffix}",
                    "status": "final",
                    "code": {"text": name},
                    "subject": patient_ref,
                    "extension": source_extension,
                }
                if re.search(
                    r"\b(?:not (?:yet )?performed|pending|awaiting)\b", values[name], re.I
                ):
                    observation.update(
                        {"status": "registered", "dataAbsentReason": {"text": values[name]}}
                    )
                else:
                    observation["valueString"] = values[name]
                resources.append(observation)

    if text:
        document: dict[str, Any] = {
            "resourceType": "DocumentReference",
            "id": document_id,
            "status": "current",
            "identifier": [{"system": "urn:clincase:sha256", "value": digest}],
            "content": [{"attachment": {"url": f"urn:sha256:{digest}"}}],
        }
        if has_patient:
            document["subject"] = patient_ref
        targets = [{"reference": f"{r['resourceType']}/{r['id']}"} for r in resources]
        resources.append(document)
        if targets:
            resources.append(
                {
                    "resourceType": "Provenance",
                    "id": f"intake-provenance-{suffix}",
                    "target": targets,
                    "recorded": datetime.now(UTC).isoformat(),
                    "agent": [{"who": {"display": "ClinCase deterministic document intake"}}],
                    "entity": [
                        {
                            "role": "source",
                            "what": {"reference": f"DocumentReference/{document_id}"},
                        }
                    ],
                }
            )
    missing = []
    if not has_patient:
        missing.append("patient")
    if not diagnosis:
        missing.append("primary_diagnosis")
    if not treatment.get("name"):
        missing.append("requested_treatment")
    if (
        not text
        or result.ocr.overall_confidence < 0.70
        or "non-clinical-content" in result.risk_flags
    ):
        missing.append("readable_clinical_document")
    if conflicts:
        missing.append("conflicting_document_fields")
    flags = list(result.risk_flags)
    if missing:
        flags.append("incomplete-clinical-document")
    audit = {
        **result.audit,
        "fhir_mapping": "explicit-document-fields-v1",
        "source_fields": [f.model_dump() for f in fields],
        "conflicting_fields": conflicts,
        "mapping_notice": "Document-derived facts require verification; no terminology certification is claimed.",
    }
    return result.model_copy(
        update={
            "fhir_bundle": {
                "resourceType": "Bundle",
                "type": "collection",
                "entry": [{"resource": r} for r in resources],
            },
            "requested_treatment": treatment,
            "patient_initials": initials,
            "clinical_snapshot_partial": snapshot,
            "missing_fields": missing,
            "case_ready": not missing,
            "risk_flags": list(dict.fromkeys(flags)),
            "requires_human_review": result.requires_human_review or bool(missing),
            "ocr": result.ocr.model_copy(
                update={"full_text": text, "extracted_fields": result.ocr.extracted_fields + fields}
            ),
            "audit": audit,
        }
    )
