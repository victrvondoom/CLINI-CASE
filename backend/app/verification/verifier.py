"""Independent evidence-based verification of a composed Decision (Phase 7).

The verifier never reads the composer's rationale. It re-derives the verdict the criterion-level evidence
supports (deterministic, no LLM) and checks that every clinical citation resolves to the submitted FHIR
bundle. `compare()` then decides whether the two disagree; disagreement/conflict is escalated to a human
through the reserved pause kinds (`verification_disagreement`, `evidence_conflict`).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

from app.models import Decision, NecessityAssessment

VERIFIER_VERSION = "1"


@dataclass
class Verification:
    verifier_version: str
    composer_verdict: str
    independent_verdict: str
    agrees: bool
    dangling_citations: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    pause_kind: str | None = None  # set when a human must look

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def derive_verdict(assessment: NecessityAssessment) -> str:
    """Verdict the criteria support: any unresolved criterion -> REFER; any failure -> DENY; else APPROVE."""
    verdict = "APPROVE"
    for c in assessment.criteria:
        if c.status == "AMBIGUOUS":
            return "REFER"
        failed = (c.criterion_type == "inclusion" and c.status == "NOT_MET") or (
            c.criterion_type == "exclusion" and c.status == "MET"
        )
        if failed:
            verdict = "DENY"
    if not assessment.criteria:
        return "REFER"
    return verdict


def _bundle_ids(bundle: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    for e in bundle.get("entry", []) or []:
        rid = (e.get("resource") or {}).get("id")
        if rid:
            ids.add(str(rid))
    return ids


def verify(
    decision: Decision, assessment: NecessityAssessment | None, fhir_bundle: dict[str, Any]
) -> Verification:
    if assessment is None:
        return Verification(
            VERIFIER_VERSION, decision.verdict, "REFER", False,
            issues=["no necessity assessment to verify against"], pause_kind="evidence_conflict",
        )  # fmt: skip
    independent = derive_verdict(assessment)
    ids = _bundle_ids(fhir_bundle)
    dangling = [
        c.pointer for c in decision.citations if c.kind == "clinical" and c.pointer not in ids
    ]
    issues: list[str] = []
    if decision.verdict != "REFER" and not decision.citations:
        issues.append("decisive verdict carries no citations")
    agrees = independent == decision.verdict
    if not agrees:
        issues.append(f"composer={decision.verdict} but criteria support {independent}")
    if dangling:
        issues.append(f"{len(dangling)} clinical citation(s) do not resolve to the FHIR bundle")
    pause = (
        "verification_disagreement"
        if not agrees
        else ("evidence_conflict" if dangling or issues else None)
    )
    return Verification(
        VERIFIER_VERSION, decision.verdict, independent, agrees, dangling, issues, pause
    )


async def persist(v: Verification, *, case_id: str, run_id: str | None, ciid: str | None) -> None:
    from app.db import db

    await db.execute(
        """INSERT INTO decision_verifications
              (case_id, run_id, case_intelligence_id, verifier_version, composer_verdict,
               independent_verdict, agrees, pause_kind, detail_json)
           VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9::jsonb)""",
        case_id, run_id, ciid, v.verifier_version, v.composer_verdict, v.independent_verdict,
        v.agrees, v.pause_kind, json.dumps(v.to_dict()),
    )  # fmt: skip
