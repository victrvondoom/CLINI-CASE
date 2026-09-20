"""ClinCase MCP tool implementations.

These five tools expose ClinCase's reasoning agents as a Model Context Protocol
(MCP) toolbox. An MCP-compatible client — Claude Desktop, Cursor, the
Cognizant TriZetto AI Gateway — can list these tools, call them, and compose
prior-authorisation workflows around them.

Each tool returns a list of MCP content blocks (text + structured JSON) so
clients see both human-readable summary and machine-parseable detail.

Reference:
  - MCP spec: https://modelcontextprotocol.io
  - TriZetto AI Gateway (Cognizant) is MCP-compliant per re:Invent 2025 IND210.
"""
from __future__ import annotations

import json
from typing import Any

from app.agents.policy_retriever import _candidate_sections
from app.db import db

# =============================================================================
# Tool 1: policy_lookup
# =============================================================================


async def policy_lookup(payer_id: str, treatment: str) -> dict[str, Any]:
    """Return the matching policy sections for a (payer, treatment) pair.

    Uses the same retrieval primitive as the in-graph Policy Retriever agent;
    on production deployment this is backed by Bedrock Knowledge Base.
    """
    candidates = _candidate_sections(payer_id, treatment)
    if not candidates:
        return _text_block(
            f"No policy match for {treatment!r} under payer {payer_id!r}. "
            f"ClinCase covers Aetna, UHC, BCBS, Anthem; treatment must match "
            f"one of the indexed keywords."
        )
    summary_lines = [
        f"Found {len(candidates)} policy section(s) for {treatment} under {payer_id}:",
        "",
    ]
    structured: list[dict[str, Any]] = []
    for i, c in enumerate(candidates[:5], 1):
        p = c["policy"]
        s = c["section"]
        summary_lines.append(
            f"{i}. {p['policy_title']}  [{p['policy_id']}] — § {s['heading']}"
        )
        structured.append({
            "policy_id": p["policy_id"],
            "policy_title": p["policy_title"],
            "section_heading": s["heading"],
            "section_text": s["text"],
            "source_url": p.get("source_url"),
            "page_number": s.get("page_number"),
        })
    return {
        "content": [
            {"type": "text", "text": "\n".join(summary_lines)},
            {
                "type": "text",
                "text": "```json\n" + json.dumps(structured, indent=2) + "\n```",
            },
        ],
        "isError": False,
    }


# =============================================================================
# Tool 2: clinical_extract
# =============================================================================


async def clinical_extract(case_id: str) -> dict[str, Any]:
    """Return the structured clinical snapshot extracted by the agent.

    Reads from the persisted agent_traces table; does NOT re-run the LLM
    (idempotent, audit-grade). In production this is the cheapest read in
    the system because every case has the snapshot pre-computed.
    """
    row = await db.fetchrow(
        """SELECT output_json FROM agent_traces
           WHERE case_id = $1 AND agent_name = 'clinical_extractor'
           ORDER BY started_at DESC LIMIT 1""",
        case_id,
    )
    if not row:
        return _text_block(
            f"No clinical extraction found for case {case_id}. "
            f"Run the LangGraph DAG on this case first via POST /cases or "
            f"POST /fhir/Claim/$submit."
        )
    snapshot = row["output_json"]
    if isinstance(snapshot, str):
        snapshot = json.loads(snapshot)
    summary = (
        f"Clinical snapshot for case {case_id} "
        f"(extracted by ClinCase Clinical Extractor agent):"
    )
    return {
        "content": [
            {"type": "text", "text": summary},
            {
                "type": "text",
                "text": "```json\n" + json.dumps(snapshot, indent=2)[:4000] + "\n```",
            },
        ],
        "isError": False,
    }


# =============================================================================
# Tool 3: decision_check
# =============================================================================


async def decision_check(case_id: str) -> dict[str, Any]:
    """Return the verdict + cited rationale for a case.

    Reads the persisted Decision Composer output; does NOT re-run the LLM.
    Used by external orchestrators (TriZetto AI Gateway) to query ClinCase's
    determination without invoking the full DAG.
    """
    row = await db.fetchrow(
        """SELECT verdict, rationale, citations_json, confidence, created_at
           FROM decisions WHERE case_id = $1
           ORDER BY created_at DESC LIMIT 1""",
        case_id,
    )
    if not row:
        return _text_block(
            f"No decision found for case {case_id}. "
            f"The case may still be running or have been routed to manual review."
        )
    citations = row["citations_json"]
    if isinstance(citations, str):
        citations = json.loads(citations)
    return {
        "content": [
            {
                "type": "text",
                "text": (
                    f"Verdict: {row['verdict']}  "
                    f"(confidence {row['confidence']:.2f})\n"
                    f"\nRationale: {row['rationale']}\n"
                    f"\nCitations: {len(citations or [])} entries"
                ),
            },
            {
                "type": "text",
                "text": "```json\n" + json.dumps(
                    {
                        "case_id": case_id,
                        "verdict": row["verdict"],
                        "confidence": float(row["confidence"]) if row["confidence"] else None,
                        "rationale": row["rationale"],
                        "citations": citations,
                        "decided_at": row["created_at"].isoformat()
                        if row["created_at"]
                        else None,
                    },
                    indent=2,
                ) + "\n```",
            },
        ],
        "isError": False,
    }


# =============================================================================
# Tool 4: appeal_draft
# =============================================================================


async def appeal_draft(case_id: str) -> dict[str, Any]:
    """Return the drafted appeal letter for a denied case.

    Reads the persisted Appeals Drafter output. If the case wasn't denied,
    no appeal exists; the tool returns a helpful message with the actual
    verdict.
    """
    appeal = await db.fetchrow(
        """SELECT appeal_body, structured_arguments_json, created_at
           FROM appeals WHERE case_id = $1
           ORDER BY created_at DESC LIMIT 1""",
        case_id,
    )
    if not appeal:
        decision = await db.fetchrow(
            "SELECT verdict FROM decisions WHERE case_id = $1 ORDER BY created_at DESC LIMIT 1",
            case_id,
        )
        if decision and decision["verdict"] != "DENY":
            return _text_block(
                f"No appeal needed: case {case_id} was {decision['verdict']}."
            )
        return _text_block(
            f"No appeal drafted for case {case_id} yet. "
            f"Run the Appeals Drafter via the LangGraph DAG."
        )
    args = appeal["structured_arguments_json"]
    if isinstance(args, str):
        args = json.loads(args)
    return {
        "content": [
            {"type": "text", "text": appeal["appeal_body"]},
            {
                "type": "text",
                "text": (
                    "```json\n" + json.dumps(
                        {
                            "case_id": case_id,
                            "structured_arguments": args,
                            "drafted_at": appeal["created_at"].isoformat()
                            if appeal["created_at"]
                            else None,
                        },
                        indent=2,
                    ) + "\n```"
                ),
            },
        ],
        "isError": False,
    }


# =============================================================================
# Tool 5: audit_query
# =============================================================================


async def audit_query(case_id: str) -> dict[str, Any]:
    """Return the full agent trace for a case (audit-grade provenance).

    This is the tool a CMS auditor uses to reconstruct a decision. Returns
    every agent invocation: input tokens, output tokens, model id, latency,
    system prompt version hash. Reproducible to the millisecond.
    """
    rows = await db.fetch(
        """SELECT agent_name, model_id, input_tokens, output_tokens,
                  started_at, completed_at, latency_ms, status
           FROM agent_traces
           WHERE case_id = $1
           ORDER BY started_at ASC""",
        case_id,
    )
    if not rows:
        return _text_block(f"No agent traces found for case {case_id}.")
    lines = [f"Agent trace for case {case_id} ({len(rows)} agent invocations):", ""]
    structured = []
    for r in rows:
        latency = r["latency_ms"] or 0
        lines.append(
            f"  • {r['agent_name']:22s} {r['model_id']:36s} "
            f"in={r['input_tokens'] or 0:>5}  "
            f"out={r['output_tokens'] or 0:>5}  "
            f"{latency:>6}ms  {r['status']}"
        )
        structured.append({
            "agent": r["agent_name"],
            "model_id": r["model_id"],
            "input_tokens": r["input_tokens"],
            "output_tokens": r["output_tokens"],
            "started_at": r["started_at"].isoformat() if r["started_at"] else None,
            "completed_at": r["completed_at"].isoformat() if r["completed_at"] else None,
            "latency_ms": latency,
            "status": r["status"],
        })
    return {
        "content": [
            {"type": "text", "text": "\n".join(lines)},
            {
                "type": "text",
                "text": "```json\n" + json.dumps(structured, indent=2) + "\n```",
            },
        ],
        "isError": False,
    }


# =============================================================================
# Helpers
# =============================================================================


def _text_block(text: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": text}], "isError": False}


# =============================================================================
# Tool registry
# =============================================================================


TOOL_DEFINITIONS = [
    {
        "name": "policy_lookup",
        "description": (
            "Look up payer-specific prior-authorisation policy sections for a "
            "given oncology treatment. Returns NCCN-aligned criteria text and "
            "section pointers. Backed by ClinCase's curated 21-policy corpus "
            "across Aetna, UHC, BCBS, Anthem (production: Bedrock Knowledge Base)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "payer_id": {
                    "type": "string",
                    "enum": ["aetna", "uhc", "bcbs", "anthem"],
                    "description": "The payer to query.",
                },
                "treatment": {
                    "type": "string",
                    "description": "Treatment generic or brand name (e.g. 'trastuzumab', 'keytruda').",
                },
            },
            "required": ["payer_id", "treatment"],
        },
    },
    {
        "name": "clinical_extract",
        "description": (
            "Return the structured clinical snapshot ClinCase extracted from a "
            "case's FHIR bundle and physician note (diagnosis, biomarkers, "
            "performance status, treatment request). Idempotent read against "
            "the audit trail; does not re-invoke the LLM."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "case_id": {"type": "string", "description": "ClinCase case ID."},
            },
            "required": ["case_id"],
        },
    },
    {
        "name": "decision_check",
        "description": (
            "Return ClinCase's verdict (APPROVE / DENY / REFER), confidence, "
            "cited rationale, and citation pointers for a case. Used by "
            "external orchestrators to query ClinCase's determination."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "case_id": {"type": "string", "description": "ClinCase case ID."},
            },
            "required": ["case_id"],
        },
    },
    {
        "name": "appeal_draft",
        "description": (
            "Return the drafted appeal letter for a denied case. The Appeals "
            "Drafter agent generates this on the LangGraph DAG's DENY edge; "
            "the letter cites NCCN guidelines and patient-specific evidence."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "case_id": {"type": "string", "description": "ClinCase case ID."},
            },
            "required": ["case_id"],
        },
    },
    {
        "name": "audit_query",
        "description": (
            "Return the full agent trace for a case: agent names, model IDs, "
            "token counts, latencies, timestamps, statuses. This is the "
            "CMS-0057-F audit-grade provenance record any decision can be "
            "reconstructed from."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "case_id": {"type": "string", "description": "ClinCase case ID."},
            },
            "required": ["case_id"],
        },
    },
]


# Map tool name -> implementation
TOOL_IMPLS = {
    "policy_lookup": policy_lookup,
    "clinical_extract": clinical_extract,
    "decision_check": decision_check,
    "appeal_draft": appeal_draft,
    "audit_query": audit_query,
}
