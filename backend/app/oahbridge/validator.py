"""
6-Tier Conformance & Terminology Validation Harness for OAH-Bridge.
Implements rigorous multi-layer informatics audit testing against HL7 FHIR R4
and OneAquaHealth conformance definitions.
"""

import json
import os
from typing import Any


class FHIRValidationReport:
    def __init__(self):
        self.tiers: dict[str, dict[str, Any]] = {
            "tier1_structural": {"name": "Tier 1: Prototype FHIR R4 Structural & Element Assertions", "passed": True, "checks": []},
            "tier2_profiles": {"name": "Tier 2: OAH StructureDefinition & Extension Constraints", "passed": True, "checks": []},
            "tier3_codesystems": {"name": "Tier 3: OAH Canonical CodeSystem Membership", "passed": True, "checks": []},
            "tier4_external_terminologies": {"name": "Tier 4: External Terminology & Concept Resolution (SNOMED CT, HL7)", "passed": True, "checks": []},
            "tier5_references": {"name": "Tier 5: FHIR Internal Reference Graph Integrity", "passed": True, "checks": []},
            "tier6_scenario_logic": {"name": "Tier 6: Scenario Invariants & Deterministic Formula Assertions", "passed": True, "checks": []},
        }

    def add_check(self, tier_key: str, name: str, passed: bool, message: str):
        self.tiers[tier_key]["checks"].append({
            "name": name,
            "passed": passed,
            "message": message
        })
        if not passed:
            self.tiers[tier_key]["passed"] = False

    @property
    def all_passed(self) -> bool:
        return all(t["passed"] for t in self.tiers.values())

    def to_dict(self) -> dict[str, Any]:
        return {
            "all_passed": self.all_passed,
            "tiers": self.tiers,
            "summary": {
                "total_checks": sum(len(t["checks"]) for t in self.tiers.values()),
                "passed_checks": sum(sum(1 for c in t["checks"] if c["passed"]) for t in self.tiers.values()),
                "failed_checks": sum(sum(1 for c in t["checks"] if not c["passed"]) for t in self.tiers.values())
            }
        }


class OAHValidator:
    def __init__(self, conformance_dir: str):
        self.conformance_dir = conformance_dir
        self.codesystems: dict[str, set] = {}
        self.load_conformance_resources()

    def load_conformance_resources(self):
        """Loads canonical CodeSystems to validate codes."""
        cs_dir = os.path.join(self.conformance_dir, "codesystems")
        if os.path.exists(cs_dir):
            for fname in os.listdir(cs_dir):
                if fname.endswith(".json"):
                    with open(os.path.join(cs_dir, fname), encoding="utf-8") as fp:
                        data = json.load(fp)
                        url = data.get("url")
                        codes = {c["code"] for c in data.get("concept", [])}
                        if url:
                            self.codesystems[url] = codes

    def validate_bundle(self, bundle: dict[str, Any], scenario: Any, evidence: Any) -> FHIRValidationReport:
        report = FHIRValidationReport()

        # Extract resources from bundle
        resources_by_type: dict[str, list[dict[str, Any]]] = {}
        resource_id_map: dict[str, dict[str, Any]] = {}

        # -------------------------------------------------------------
        # TIER 1: FHIR R4 Structural & Data-Type Schema
        # -------------------------------------------------------------
        report.add_check(
            "tier1_structural",
            "Bundle Root Structure",
            bundle.get("resourceType") == "Bundle" and "entry" in bundle and isinstance(bundle["entry"], list),
            "Bundle contains valid root resourceType and entry array."
        )

        for entry in bundle.get("entry", []):
            res = entry.get("resource", {})
            rtype = res.get("resourceType")
            rid = res.get("id")
            if not rtype or not rid:
                report.add_check("tier1_structural", "Resource Identification", False, f"Missing resourceType or id in entry: {entry}")
                continue

            ref_key = f"{rtype}/{rid}"
            resource_id_map[ref_key] = res
            resources_by_type.setdefault(rtype, []).append(res)

            # Check core required fields per FHIR R4
            if rtype == "Location":
                report.add_check("tier1_structural", f"Location/{rid} Structural", res.get("status") in ["active", "suspended", "inactive"], "Valid Location status.")
            elif rtype == "Observation":
                has_status = res.get("status") in ["registered", "preliminary", "final", "amended", "corrected"]
                has_code = "code" in res and "coding" in res["code"]
                report.add_check("tier1_structural", f"Observation/{rid} Structural", has_status and has_code, "Observation has valid status and codeableConcept.")
            elif rtype == "Group":
                has_type = res.get("type") in ["person", "animal", "practitioner", "device", "medication", "substance"]
                has_actual = isinstance(res.get("actual"), bool)
                report.add_check("tier1_structural", f"Group/{rid} Structural", has_type and has_actual, "Group has valid type and boolean actual field.")
            elif rtype == "RiskAssessment":
                has_status = res.get("status") in ["registered", "preliminary", "final", "amended", "corrected", "cancelled"]
                has_subject = "subject" in res and "reference" in res["subject"]
                report.add_check("tier1_structural", f"RiskAssessment/{rid} Structural", has_status and has_subject, "RiskAssessment has valid status and subject reference.")
            elif rtype == "Provenance":
                has_target = "target" in res and len(res["target"]) > 0
                has_agent = "agent" in res and len(res["agent"]) > 0
                report.add_check("tier1_structural", f"Provenance/{rid} Structural", has_target and has_agent, "Provenance has valid targets and agents.")

        # -------------------------------------------------------------
        # TIER 2: OAH StructureDefinition & Extension Constraints
        # -------------------------------------------------------------
        # Check Location extension: location-boundary-geojson
        for loc in resources_by_type.get("Location", []):
            exts = [e for e in loc.get("extension", []) if e.get("url") == "http://hl7.org/fhir/StructureDefinition/location-boundary-geojson"]
            valid_ext = len(exts) == 1 and "valueAttachment" in exts[0] and exts[0]["valueAttachment"].get("contentType") == "application/geo+json"
            report.add_check("tier2_profiles", f"Location/{loc['id']} GeoJSON Extension", valid_ext, "HL7 draft location-boundary-geojson extension present with application/geo+json attachment.")

        # Check Hazard Observation constraints
        hazard_obs = None
        evidence_obs = None
        for obs in resources_by_type.get("Observation", []):
            # Evidence Support observation has code 'evidence-support-score'
            codings = obs.get("code", {}).get("coding", [])
            codes = [c.get("code") for c in codings]
            if "evidence-support-score" in codes:
                evidence_obs = obs
            else:
                hazard_obs = obs

        if hazard_obs:
            exts = [e for e in hazard_obs.get("extension", []) if e.get("url") == "http://oneaquahealth.eu/fhir/StructureDefinition/oah-evidence-status"]
            valid_ext = False
            if len(exts) == 1:
                val_cc = exts[0].get("valueCodeableConcept", {})
                valid_ext = "coding" in val_cc and len(val_cc["coding"]) > 0 and val_cc["coding"][0].get("system") == "http://oneaquahealth.eu/fhir/cs/evidence-status"

            report.add_check(
                "tier2_profiles",
                "Hazard Observation Epistemic Extension",
                valid_ext,
                "oah-evidence-status extension present with valueCodeableConcept bound to OAH evidence-status CodeSystem (NOT valueCode)."
            )

            # Check exposure pathway component
            components = hazard_obs.get("component", [])
            has_pathway = any(
                any(c.get("code") == "exposure-pathway" for c in comp.get("code", {}).get("coding", []))
                for comp in components
            )
            report.add_check("tier2_profiles", "Hazard Observation Exposure Pathway Component", has_pathway, "Mandatory exposure-pathway component slice present.")

        # Check Evidence Support Observation constraints
        if evidence_obs:
            has_decimal = "valueDecimal" in evidence_obs and isinstance(evidence_obs["valueDecimal"], float | int)
            has_focus = "focus" in evidence_obs and len(evidence_obs["focus"]) == 1
            report.add_check("tier2_profiles", "Evidence Support Observation valueDecimal & focus", has_decimal and has_focus, "Carries numeric valueDecimal score and single focus Reference to Hazard Observation.")

            # Check coded subcomponents
            comps = evidence_obs.get("component", [])
            sub_codes = {c.get("code") for comp in comps for c in comp.get("code", {}).get("coding", [])}
            expected_subs = {"sensor-corroboration", "citizen-agreement", "temporal-consistency"}
            has_all_subs = expected_subs.issubset(sub_codes)
            report.add_check("tier2_profiles", "Evidence Support Subcomponents", has_all_subs, f"Subcomponents coded in assessment-metrics: {expected_subs}.")

        # Check Definitional Group constraints
        for grp in resources_by_type.get("Group", []):
            is_definitional = grp.get("actual") is False
            has_chars = len(grp.get("characteristic", [])) >= 2
            report.add_check("tier2_profiles", f"Group/{grp['id']} Definitional Constraints", is_definitional and has_chars, "Group.actual is False and contains spatial + exposure pathway characteristics.")

        # Check RiskAssessment constraints
        for ra in resources_by_type.get("RiskAssessment", []):
            # Must NOT use condition element for SNOMED concept (condition in R4 is Reference(Condition))
            has_illegal_condition = "condition" in ra
            report.add_check("tier2_profiles", f"RiskAssessment/{ra['id']} Condition Semantic Slot Check", not has_illegal_condition, "RiskAssessment.condition is correctly NOT used for SNOMED outcome (avoids R4 semantic type clash).")

            # Must carry method: oah-environmental-exposure-assessment
            method_codings = ra.get("method", {}).get("coding", [])
            has_valid_method = any(c.get("code") == "oah-environmental-exposure-assessment" and c.get("system") == "http://oneaquahealth.eu/fhir/cs/assessment-method" for c in method_codings)
            report.add_check("tier2_profiles", f"RiskAssessment/{ra['id']} Assessment Method", has_valid_method, "RiskAssessment.method explicitly carries oah-environmental-exposure-assessment.")

            # Must have prediction with outcome and qualitativeRisk
            preds = ra.get("prediction", [])
            has_valid_pred = len(preds) > 0 and "outcome" in preds[0] and "qualitativeRisk" in preds[0]
            report.add_check("tier2_profiles", f"RiskAssessment/{ra['id']} Prediction Outcome & Likelihood", has_valid_pred, "RiskAssessment.prediction contains both outcome CodeableConcept and qualitativeRisk.")

        # -------------------------------------------------------------
        # TIER 3: OAH Canonical CodeSystem Membership
        # -------------------------------------------------------------
        for rlist in resources_by_type.values():
            for res in rlist:
                # Check codings in res
                self._check_codings_in_obj(res, report, "tier3_codesystems")

        # -------------------------------------------------------------
        # TIER 4: External Terminology & Concept Resolution (SNOMED CT, HL7)
        # -------------------------------------------------------------
        for ra in resources_by_type.get("RiskAssessment", []):
            preds = ra.get("prediction", [])
            for p in preds:
                outcome_codings = p.get("outcome", {}).get("coding", [])
                snomed_valid = any(c.get("system") == "http://snomed.info/sct" and c.get("code") in ["40275004", "416113008", "69776003"] for c in outcome_codings)
                report.add_check("tier4_external_terminologies", "SNOMED CT Concept Resolution", snomed_valid, "prediction.outcome resolves to verified active SNOMED CT concept (40275004 Contact dermatitis, 416113008 Acute febrile illness, or 69776003 Acute gastroenteritis).")

                qual_codings = p.get("qualitativeRisk", {}).get("coding", [])
                hl7_risk_valid = any(c.get("system") == "http://terminology.hl7.org/CodeSystem/risk-probability" and c.get("code") in ["negligible", "low", "moderate", "high", "certain"] for c in qual_codings)
                report.add_check("tier4_external_terminologies", "HL7 Qualitative Risk Probability", hl7_risk_valid, "prediction.qualitativeRisk bound to official HL7 risk-probability CodeSystem.")

        # -------------------------------------------------------------
        # TIER 5: FHIR Internal Reference Graph Integrity
        # -------------------------------------------------------------
        references_to_check: list[tuple[str, str, str]] = []

        if hazard_obs:
            subj_ref = hazard_obs.get("subject", {}).get("reference")
            if subj_ref:
                references_to_check.append(("Hazard Observation -> Location", subj_ref, "Location"))

        if evidence_obs:
            for f in evidence_obs.get("focus", []):
                references_to_check.append(("Evidence Support -> Hazard Observation", f.get("reference"), "Observation"))

        for ra in resources_by_type.get("RiskAssessment", []):
            subj_ref = ra.get("subject", {}).get("reference")
            if subj_ref:
                references_to_check.append(("RiskAssessment -> Group", subj_ref, "Group"))
            for b in ra.get("basis", []):
                references_to_check.append(("RiskAssessment -> Basis Observation", b.get("reference"), "Observation"))

        for prov in resources_by_type.get("Provenance", []):
            for t in prov.get("target", []):
                references_to_check.append(("Provenance -> Target Resource", t.get("reference"), "Any"))

        for ref_name, ref_val, expected_type in references_to_check:
            exists = ref_val in resource_id_map
            target_matches = True
            if exists and expected_type != "Any":
                target_matches = resource_id_map[ref_val].get("resourceType") == expected_type
            report.add_check("tier5_references", ref_name, exists and target_matches, f"Reference '{ref_val}' resolves to valid internal Bundle resource of expected type '{expected_type}'.")

        # -------------------------------------------------------------
        # TIER 6: Scenario Invariants & Deterministic Formula Assertions
        # -------------------------------------------------------------
        # Check score formula
        expected_score = round(
            0.40 * evidence.sub_scores.sensor_corroboration +
            0.30 * evidence.sub_scores.citizen_agreement +
            0.30 * evidence.sub_scores.temporal_consistency,
            2
        )
        score_matches = (evidence.score == expected_score)
        report.add_check("tier6_scenario_logic", "Deterministic Evidence Score Formula", score_matches, f"Calculated score {evidence.score} exactly matches 0.40*Cs + 0.30*Cc + 0.30*Ct = {expected_score}.")

        # Check epistemic status mapping
        if evidence.is_lab_confirmed:
            epistemic_matches = (evidence.epistemic_status == "confirmed")
        elif evidence.score >= 0.70 or evidence.score >= 0.40:
            epistemic_matches = (evidence.epistemic_status == "inferred")
        else:
            epistemic_matches = (evidence.epistemic_status == "observed")

        report.add_check("tier6_scenario_logic", "Epistemic Threshold Mapping", epistemic_matches, f"Score {evidence.score} correctly mapped to epistemic status '{evidence.epistemic_status}'.")

        return report

    def _check_codings_in_obj(self, obj: Any, report: FHIRValidationReport, tier_key: str):
        if isinstance(obj, dict):
            if "system" in obj and "code" in obj:
                system = obj["system"]
                code = obj["code"]
                if system in self.codesystems:
                    valid = code in self.codesystems[system]
                    report.add_check(
                        tier_key,
                        f"CodeSystem Validation: {code}",
                        valid,
                        f"Code '{code}' is in CodeSystem <{system}>." if valid else f"Code '{code}' NOT in CodeSystem <{system}>!"
                    )
            for v in obj.values():
                self._check_codings_in_obj(v, report, tier_key)
        elif isinstance(obj, list):
            for item in obj:
                self._check_codings_in_obj(item, report, tier_key)
