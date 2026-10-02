"""Project an interop job and its bound evidence into the ten-stage CLINI-CASE journey.

Pure and read-only. Every status is derived from state the existing gateway and One Health
services already persisted; nothing here can advance a workflow. Completed stages cite the
logged event that proves them, so the UI can show *why* a stage is complete.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Literal

from app.interop.models import TARGETS
from app.onehealth import fhir

StageStatus = Literal["complete", "ready", "waiting", "blocked", "failed"]

STAGES: tuple[tuple[str, str, str], ...] = (
    ("ingest", "Ingest", "Track 7 gateway intake (JSON, CSV, FHIR, synthetic lab, reviewed evidence)"),
    ("understand", "Understand", "Gateway schema discovery"),
    ("map", "Map", "Deterministic mapping with optional governed AI suggestions"),
    ("review", "Review", "Human review gate"),
    ("standardize", "Standardize", "OAH/FHIR R4 generation"),
    ("validate", "Validate", "Exchange-contract validation"),
    ("exchange", "Exchange", "Independent System B over HTTP"),
    ("verify", "Verify", "Semantic round trip and Evidence Passport"),
    ("clinical_context", "Clinical context", "One Health evidence and consented clinical capabilities"),
    ("follow_up", "Follow-up", "Environmental follow-up and laboratory retest"),
)


def _short(digest: str | None) -> str | None:
    return digest[:12] if digest else None


def _proof(job: dict[str, Any], *types: str, limit: int = 1) -> list[dict[str, Any]]:
    """The newest logged events of the given types, as stage evidence."""
    found = [e for e in reversed(job.get("events") or []) if e.get("event_type") in types]
    return [
        {
            "event_type": e["event_type"],
            "timestamp": e["timestamp"],
            "actor": e["actor"],
            "status": e["status"],
            "correlation_id": e["correlation_id"],
        }
        for e in found[:limit]
    ]


def _stage(
    stage_id: str,
    status: StageStatus,
    summary: str,
    *,
    facts: list[tuple[str, Any]] | None = None,
    evidence: list[dict[str, Any]] | None = None,
    next_action: tuple[str, str] | None = None,
    links: list[tuple[str, str]] | None = None,
    detail: dict[str, Any] | None = None,
) -> dict[str, Any]:
    index, (_, label, owner) = next(
        (i, s) for i, s in enumerate(STAGES) if s[0] == stage_id
    )
    return {
        "id": stage_id,
        "index": index + 1,
        "label": label,
        "owner": owner,
        "status": status,
        "summary": summary,
        "facts": [{"label": k, "value": v} for k, v in (facts or []) if v is not None],
        "evidence": evidence or [],
        "next_action": {"id": next_action[0], "label": next_action[1]} if next_action else None,
        "links": [{"label": k, "href": v} for k, v in (links or [])],
        "detail": detail or {},
    }


def project(job: dict[str, Any], evidence: dict[str, Any] | None = None) -> dict[str, Any]:
    """Compose stages from an interop job view and, when bound, its One Health journey."""
    source = job["source"]
    schema = job.get("schema") or {}
    metrics = job.get("metrics") or {}
    mappings: list[dict[str, Any]] = job.get("mappings") or []
    bundle: dict[str, Any] | None = job.get("bundle")
    validation: dict[str, Any] | None = job.get("validation")
    withdrawn = job.get("consent_status") == "WITHDRAWN"
    from_evidence = bool(_proof(job, "reviewed_evidence_exchange_created"))
    workbench = ("Open in interop workbench", f"/interop?job={job['id']}")
    stages: list[dict[str, Any]] = []

    def done() -> bool:
        """Whether the previously appended stage is complete (the next stage's gate)."""
        return bool(stages) and stages[-1]["status"] == "complete"

    # 1 Ingest -----------------------------------------------------------------------
    stages.append(
        _stage(
            "ingest",
            "complete",
            f"{source['source_system']} · record {source['original_record_id']}",
            facts=[
                ("Format", str(source.get("format", "json")).upper()),
                ("Classification", "Synthetic" if source.get("synthetic") else "Non-synthetic"),
                ("Fields received", metrics.get("fields_detected")),
            ],
            evidence=_proof(job, "source_received", "reviewed_evidence_exchange_created"),
        )
    )

    # 2 Understand -------------------------------------------------------------------
    fields = schema.get("fields") or []
    stages.append(
        _stage(
            "understand",
            "complete" if fields else "failed",
            f"{len(fields)} source fields discovered"
            if fields
            else "No readable fields were found in the source",
            facts=[
                ("Fields", len(fields)),
                ("Required targets not yet mapped", len(schema.get("missing_required_fields") or [])),
                ("Ambiguous fields", ", ".join(schema.get("ambiguities") or []) or "None"),
            ],
            evidence=_proof(job, "schema_discovered"),
            detail={
                "fields": fields,
                "missing_required_fields": schema.get("missing_required_fields") or [],
                "ambiguities": schema.get("ambiguities") or [],
            },
        )
    )

    # 3 Map --------------------------------------------------------------------------
    mapping_rows = [
        {
            k: m.get(k)
            for k in (
                "source_field",
                "target",
                "fhir_target",
                "confidence",
                "origin",
                "decision",
                "concept",
                "terminology_status",
                "reason",
                "reviewer",
            )
        }
        for m in mappings
    ]
    firewall = job.get("semantic_firewall") or {}
    if from_evidence:
        stages.append(
            _stage(
                "map",
                "complete",
                "Not required: the source is a reviewed One Health evidence record",
                evidence=_proof(job, "reviewed_evidence_exchange_created"),
            )
        )
    elif mappings:
        stages.append(
            _stage(
                "map",
                "complete",
                f"{metrics.get('fields_mapped', 0)} of {len(mappings)} fields have a proposed target",
                facts=[
                    ("Mode", job.get("mapping_mode")),
                    ("Model status", job.get("ai_status")),
                    ("AI authority", firewall.get("ai_authority")),
                ],
                evidence=_proof(job, "mappings_proposed"),
                detail={"mappings": mapping_rows, "semantic_firewall": firewall},
            )
        )
    else:
        stages.append(
            _stage(
                "map",
                "ready" if done() else "waiting",
                "Propose field mappings: deterministic, or governed AI suggestions a reviewer must approve",
                next_action=("map", "Propose mappings"),
            )
        )

    # 4 Review -----------------------------------------------------------------------
    pending = [m for m in mappings if m.get("decision") == "pending"]
    missing = schema.get("missing_required_fields") or []
    review_detail = {"mappings": mapping_rows, "targets": TARGETS, "semantic_firewall": firewall}
    if from_evidence:
        stages.append(
            _stage(
                "review",
                "complete",
                "Reviewed when the evidence record was verified",
                evidence=_proof(job, "reviewed_evidence_exchange_created"),
            )
        )
    elif not mappings:
        stages.append(_stage("review", "waiting", "Waiting for proposed mappings"))
    elif pending:
        stages.append(
            _stage(
                "review",
                "ready",
                f"{len(pending)} mapping decision(s) await a reviewer",
                facts=[("Ambiguous fields", ", ".join(firewall.get("ambiguous_fields") or []) or "None")],
                next_action=("review", "Review mappings"),
                detail=review_detail,
            )
        )
    elif missing:
        stages.append(
            _stage(
                "review",
                "blocked",
                "Required targets are still unmapped: " + ", ".join(missing),
                next_action=("review", "Revisit mapping decisions"),
                links=[workbench],
                detail=review_detail,
            )
        )
    else:
        decided = Counter(m.get("decision") for m in mappings)
        stages.append(
            _stage(
                "review",
                "complete",
                f"{decided['accepted']} accepted · {decided['rejected']} rejected by a reviewer",
                evidence=_proof(job, "mapping_accepted", "mapping_rejected", limit=3),
                detail=review_detail,
            )
        )

    # 5 Standardize ------------------------------------------------------------------
    if bundle:
        types = Counter(e["resource"]["resourceType"] for e in bundle.get("entry", []))
        stages.append(
            _stage(
                "standardize",
                "complete",
                f"{metrics.get('resources_generated', 0)} FHIR R4 resources generated",
                facts=[
                    ("Bundle SHA-256", _short(fhir.digest(bundle))),
                    ("Resources", ", ".join(f"{t} ×{n}" for t, n in sorted(types.items()))),
                ],
                evidence=_proof(job, "bundle_generated", "reviewed_evidence_exchange_created"),
                detail={"resource_types": dict(types)},
            )
        )
    elif withdrawn:
        stages.append(_stage("standardize", "blocked", "Sharing withdrawn; exchange artefacts are hidden"))
    else:
        stages.append(
            _stage(
                "standardize",
                "ready" if done() else "waiting",
                "Generate the OAH/FHIR collection Bundle from approved mappings",
                next_action=("generate", "Generate OAH/FHIR bundle"),
            )
        )

    # 6 Validate ---------------------------------------------------------------------
    current_digest = fhir.digest(bundle) if bundle else None
    if not bundle:
        stages.append(_stage("validate", "blocked" if withdrawn else "waiting", "Waiting for a bundle"))
    elif not validation:
        stages.append(
            _stage("validate", "ready", "Validate the generated bundle", next_action=("validate", "Validate bundle"))
        )
    else:
        issues = [
            i for i in validation.get("operation_outcome", {}).get("issue", []) if i.get("severity") == "error"
        ]
        standards = validation.get("standards") or {}
        validation_detail = {
            "issues": validation.get("operation_outcome", {}).get("issue", []),
            "checks": validation.get("checks", []),
            "standards": standards,
        }
        if validation.get("sha256") != current_digest:
            stages.append(
                _stage(
                    "validate",
                    "ready",
                    "The last validation covered a different payload; validate the generated bundle",
                    next_action=("validate", "Validate generated bundle"),
                    detail=validation_detail,
                )
            )
        elif not validation.get("valid"):
            stages.append(
                _stage(
                    "validate",
                    "failed",
                    issues[0]["diagnostics"] if issues else "Validation failed",
                    links=[workbench],
                    detail=validation_detail,
                )
            )
        else:
            stages.append(
                _stage(
                    "validate",
                    "complete",
                    f"{metrics.get('checks_passed', 0)} exchange checks passed",
                    facts=[
                        ("Scope", standards.get("validation_scope")),
                        (
                            "Full HL7 profile validation",
                            "No (partial contract validation)"
                            if standards.get("full_hl7_profile_validation") is False
                            else None,
                        ),
                    ],
                    evidence=_proof(job, "validation_passed"),
                    detail=validation_detail,
                )
            )

    # 7 Exchange ---------------------------------------------------------------------
    all_transfers: list[dict[str, Any]] = job.get("transfers") or []
    transfers = [t for t in all_transfers if not t.get("challenge")]
    challenges = [t for t in all_transfers if t.get("challenge")]
    delivered = next(
        (
            t
            for t in reversed(transfers)
            if t.get("status") == "delivered" and t.get("sha256") == current_digest
        ),
        None,
    )
    latest = next((t for t in reversed(transfers) if t.get("sha256") == current_digest), None)
    transfer_detail = {
        "transfers": [
            {
                "id": t.get("id"),
                "status": t.get("status"),
                "sha256": _short(t.get("sha256")),
                "correlation_id": t.get("correlation_id"),
                "error": t.get("error"),
                "resources_acknowledged": (t.get("acknowledgement") or {}).get("resources_acknowledged"),
                "processing_ms": (t.get("acknowledgement") or {}).get("processing_ms"),
            }
            for t in transfers
        ],
        "challenges": [
            {"id": t.get("id"), "status": t.get("status"), "receiver_http": t.get("receiver_http")}
            for t in challenges
        ],
    }
    rejected_challenges = sum(t.get("status") == "rejected" for t in challenges)
    if delivered:
        ack = delivered.get("acknowledgement") or {}
        stages.append(
            _stage(
                "exchange",
                "complete",
                f"System B acknowledged {ack.get('resources_acknowledged', 0)} resources over HTTP",
                facts=[
                    ("Correlation ID", delivered.get("correlation_id")),
                    ("Receiver reassigned resource IDs", "Yes" if ack.get("resource_ids_reassigned") else "No"),
                    ("Invalid packages rejected by System B", rejected_challenges or None),
                ],
                evidence=_proof(job, "transfer_delivered"),
                detail=transfer_detail,
            )
        )
    elif latest and latest.get("status") in ("failed", "rejected"):
        stages.append(
            _stage(
                "exchange",
                "failed",
                latest.get("error") or "System B did not accept the package",
                next_action=("transfer", "Retry transfer"),
                evidence=_proof(job, "transfer_failed", "transfer_rejected"),
                detail=transfer_detail,
            )
        )
    elif latest and latest.get("status") == "processing":
        # A transfer persisted as processing never received an outcome (e.g. interrupted).
        stages.append(
            _stage(
                "exchange",
                "ready",
                "A previous transfer did not record an outcome; retry the transfer",
                next_action=("transfer", "Retry transfer"),
                detail=transfer_detail,
            )
        )
    else:
        stages.append(
            _stage(
                "exchange",
                "ready" if done() else "waiting",
                "Send the validated bundle to the independent System B receiver",
                next_action=("transfer", "Send to System B"),
                detail=transfer_detail,
            )
        )

    # 8 Verify -----------------------------------------------------------------------
    roundtrip = (delivered or {}).get("roundtrip")
    integrity = job.get("passport_integrity") or {}
    passport_facts: list[tuple[str, Any]] = [
        ("Evidence Passport", integrity.get("status")),
        ("Passport revisions", integrity.get("revision_count")),
        ("Passport head", _short(integrity.get("head"))),
    ]
    if roundtrip:
        verify_detail = {"roundtrip_fields": roundtrip.get("fields", []), "passport": integrity}
        verified = roundtrip.get("status") == "passed" and integrity.get("valid") is True
        stages.append(
            _stage(
                "verify",
                "complete" if verified else "failed",
                f"{roundtrip.get('fields_preserved')}/{roundtrip.get('fields_total')} semantic fields "
                "preserved after System B reassigned resource IDs"
                if verified
                else "Round trip or Evidence Passport verification failed",
                facts=[
                    ("Fields preserved", f"{roundtrip.get('fields_preserved')}/{roundtrip.get('fields_total')}"),
                    ("Resource IDs reassigned", "Yes" if roundtrip.get("resource_ids_reassigned") else "No"),
                    ("Source SHA-256", _short(roundtrip.get("source_sha256"))),
                    ("Returned SHA-256", _short(roundtrip.get("returned_sha256"))),
                    *passport_facts,
                ],
                evidence=_proof(job, "return_exchange_validated"),
                next_action=("export_passport", "Export Evidence Passport"),
                detail=verify_detail,
            )
        )
    else:
        stages.append(
            _stage(
                "verify",
                "ready" if done() else "waiting",
                "Return the bundle from System B and verify semantic preservation",
                facts=passport_facts,
                next_action=("return", "Return and verify round trip"),
                detail={"passport": integrity},
            )
        )

    # 9 Clinical context -------------------------------------------------------------
    record = (evidence or {}).get("record")
    if not job.get("exposure_id"):
        stages.append(
            _stage(
                "clinical_context",
                "ready" if done() else "waiting",
                "Bind this verified exchange to a One Health evidence record to open consented clinical context",
                next_action=("bind", "Bind to One Health evidence"),
            )
        )
    elif not record:
        stages.append(
            _stage("clinical_context", "blocked", "The bound evidence record is not available in this organisation")
        )
    else:
        consent = evidence["consent_status"] if evidence else "NOT_ESTABLISHED"
        connections = (evidence or {}).get("connections") or []
        open_links = [c for c in connections if c.get("href")]
        evidence_link = ("Open evidence review", f"/onehealth?record={record['id']}")
        context_facts: list[tuple[str, Any]] = [
            ("Evidence record", record["id"]),
            ("Laboratory verified", "Yes" if record.get("lab_verified") else "No"),
            ("Clinical review", str(record.get("review", "")).replace("_", " ")),
            ("Consent", consent.replace("_", " ").lower()),
            ("Linked case", record.get("case_id") or None),
            ("Evidence level", ((record.get("epistemic_ceiling") or {}).get("level") or "").replace("_", " ") or None),
        ]
        context_detail = {
            "connections": connections,
            "epistemic_ceiling": record.get("epistemic_ceiling"),
            "assessment_gates": (record.get("assessment") or {}).get("gates", []),
        }
        if consent == "WITHDRAWN":
            status: StageStatus = "blocked"
            summary = "Consent withdrawn: clinical sharing is disabled; history is retained"
        elif consent == "ACTIVE":
            status = "complete"
            summary = f"{len(open_links)} of {len(connections)} capabilities connected under recorded consent"
        else:
            status = "ready"
            summary = (
                f"Evidence bound; {len(open_links)} of {len(connections)} capabilities open. "
                "Record laboratory verification, consent and clinical review to open patient-linked context"
            )
        stages.append(
            _stage(
                "clinical_context",
                status,
                summary,
                facts=context_facts,
                evidence=_proof(job, "onehealth_evidence_bound", "reviewed_evidence_exchange_created"),
                next_action=None if status == "complete" else ("open_evidence", "Open evidence review"),
                links=[evidence_link],
                detail=context_detail,
            )
        )

    # 10 Follow-up -------------------------------------------------------------------
    if not record:
        stages.append(_stage("follow_up", "waiting", "Available once evidence is bound"))
    else:
        comparison = (evidence or {}).get("retest_comparison")
        followup = record.get("followup_status") or "requested"
        successor = record.get("successor_id")
        follow_links = [("Open evidence review", f"/onehealth?record={record['id']}")]
        if successor:
            follow_links.append(("Open linked retest", f"/onehealth?record={successor}"))
        stages.append(
            _stage(
                "follow_up",
                "complete" if successor or followup == "completed" else "ready",
                "Laboratory retest recorded; the original measurement is retained"
                if successor
                else f"Environmental follow-up {followup.replace('_', ' ')}",
                facts=[
                    ("Follow-up status", followup.replace("_", " ")),
                    ("Retest of", record.get("retest_of")),
                    ("Successor retest", successor),
                    ("Follow-up evidence", record.get("followup_evidence_reference")),
                ],
                next_action=None if successor else ("open_evidence", "Record follow-up or retest"),
                links=follow_links,
                detail={"retest_comparison": comparison},
            )
        )

    current = next((s["id"] for s in stages if s["status"] != "complete"), None)
    events = job.get("events") or []
    return {
        "job_id": job["id"],
        "job_version": job["version"],
        "exposure_id": job.get("exposure_id"),
        "exposure_version": record.get("version") if record else None,
        "source": {
            "system": source["source_system"],
            "record_id": source["original_record_id"],
            "format": source.get("format", "json"),
            "synthetic": bool(source.get("synthetic")),
        },
        "consent_status": job.get("consent_status") or (evidence or {}).get("consent_status"),
        "trust_states": job.get("trust_states") or [],
        "current_stage": current,
        "progress": {"complete": sum(s["status"] == "complete" for s in stages), "total": len(stages)},
        "last_activity": events[-1]["timestamp"] if events else None,
        "stages": stages,
    }


def summary(projected: dict[str, Any]) -> dict[str, Any]:
    """Compact list-row form of a projection."""
    current = next((s for s in projected["stages"] if s["id"] == projected["current_stage"]), None)
    return {
        "job_id": projected["job_id"],
        "source": projected["source"],
        "exposure_id": projected["exposure_id"],
        "current_stage": projected["current_stage"],
        "current_status": current["status"] if current else "complete",
        "current_summary": current["summary"] if current else "Journey complete",
        "progress": projected["progress"],
        "last_activity": projected["last_activity"],
    }
