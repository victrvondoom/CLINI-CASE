"""OpenLineage emitter — agent-run + RAG-retrieval data lineage.

For ML retraining + auditor "show me what data this decision was based on,"
every agent run + every RAG retrieval is an OpenLineage event linking
input datasets to output datasets via a job + run.

OpenLineage is the de-facto standard (CNCF sandbox, used by Airbnb / Netflix
/ Astronomer / Marquez). The shape:

  event = {
    "eventType":  "START" | "COMPLETE" | "FAIL",
    "eventTime":  ISO-8601,
    "run":   { "runId": uuid, "facets": {...} },
    "job":   { "namespace": "clincase", "name": "agent.policy_retriever", "facets": {...} },
    "inputs":  [ {namespace, name, facets: {schema, dataSource, ...}} ],
    "outputs": [ {namespace, name, facets: {...}} ],
    "producer": "https://github.com/victrvondoom/CLINI-CASE/v0.1.0",
  }

Today (round-11) we emit to a logger (default) or POST to
`OPENLINEAGE_URL` (e.g., a Marquez endpoint or a Kafka REST proxy).
Production wiring lands at the first customer that runs Marquez.

Pairs with: ops/architecture/DATA_LINEAGE.md
"""
from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime
from typing import Any

import structlog

log = structlog.get_logger()

_OPENLINEAGE_URL = os.getenv("OPENLINEAGE_URL", "").strip()
_OPENLINEAGE_NAMESPACE = os.getenv("OPENLINEAGE_NAMESPACE", "clincase")
_PRODUCER = "https://github.com/victrvondoom/CLINI-CASE/v0.1.0"


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


async def _post(event: dict[str, Any]) -> None:
    """Best-effort POST to the OpenLineage endpoint. Logs on every failure
    but never raises — lineage MUST NOT break the agent path."""
    if not _OPENLINEAGE_URL:
        return
    try:
        import httpx  # type: ignore[import-not-found]
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.post(
                _OPENLINEAGE_URL,
                json=event,
                headers={"Content-Type": "application/json"},
            )
            if resp.status_code >= 300:
                log.warning("openlineage.post.non_2xx", status=resp.status_code)
    except Exception as e:  # noqa: BLE001
        log.warning("openlineage.post.failed", error=str(e))


# =============================================================================
# Public API — emit_agent_run / emit_rag_retrieval
# =============================================================================


async def emit_agent_run(
    *,
    agent_name: str,
    run_id: str,
    case_id: str,
    organization_id: str,
    event_type: str,                              # "START" | "COMPLETE" | "FAIL"
    inputs: list[dict[str, Any]] | None = None,
    outputs: list[dict[str, Any]] | None = None,
    error: str | None = None,
) -> None:
    """Emit an OpenLineage event for an agent run."""
    facets: dict[str, Any] = {
        "case_id": {"_producer": _PRODUCER, "_schemaURL": "https://clincase.com/lineage/case-id-facet/v1.json", "case_id": case_id},
        "organization_id": {"_producer": _PRODUCER, "organization_id": organization_id},
    }
    if error:
        facets["errorMessage"] = {
            "_producer": _PRODUCER,
            "message": error,
            "programmingLanguage": "python",
        }
    event: dict[str, Any] = {
        "eventType": event_type,
        "eventTime": _now_iso(),
        "producer": _PRODUCER,
        "run": {
            "runId": run_id,
            "facets": facets,
        },
        "job": {
            "namespace": _OPENLINEAGE_NAMESPACE,
            "name": f"agent.{agent_name}",
            "facets": {
                "documentation": {
                    "_producer": _PRODUCER,
                    "description": f"ClinCase agent: {agent_name}",
                },
            },
        },
        "inputs": inputs or [{"namespace": _OPENLINEAGE_NAMESPACE, "name": f"case.{case_id}"}],
        "outputs": outputs or [],
    }
    log.info("openlineage.emit", agent=agent_name, run_id=run_id, event_type=event_type)
    await _post(event)


async def emit_rag_retrieval(
    *,
    run_id: str,
    case_id: str,
    organization_id: str,
    backend: str,                  # "bedrock_kb" | "amazon_q" | "file_corpus"
    query: str,
    retrieved_doc_ids: list[str],
    score_top1: float | None = None,
) -> None:
    """Emit an OpenLineage event for a RAG retrieval. Each retrieved document
    is a lineage input → the case_decision is the lineage output."""
    inputs = [
        {
            "namespace": _OPENLINEAGE_NAMESPACE,
            "name": f"corpus.{backend}.doc.{doc_id}",
        }
        for doc_id in retrieved_doc_ids
    ]
    outputs = [
        {
            "namespace": _OPENLINEAGE_NAMESPACE,
            "name": f"case.{case_id}.retrieval",
            "facets": {
                "topQueryFacet": {
                    "_producer": _PRODUCER,
                    "query": query[:500],
                    "score_top1": score_top1,
                },
            },
        },
    ]
    await emit_agent_run(
        agent_name="rag_retrieval",
        run_id=run_id,
        case_id=case_id,
        organization_id=organization_id,
        event_type="COMPLETE",
        inputs=inputs,
        outputs=outputs,
    )


def lineage_snapshot() -> dict[str, Any]:
    """Snapshot for /capabilities + /architecture descriptor."""
    return {
        "openlineage_url_configured": bool(_OPENLINEAGE_URL),
        "namespace": _OPENLINEAGE_NAMESPACE,
        "producer": _PRODUCER,
        "spec_version": "OpenLineage 1.x",
        "emit_targets": ["agent_run", "rag_retrieval"],
        "downstream_compatibility": ["Marquez", "DataHub", "OpenMetadata", "Kafka REST proxy"],
    }


# Convenience for callers that don't have a run_id handy yet
def new_run_id() -> str:
    return str(uuid.uuid4())
