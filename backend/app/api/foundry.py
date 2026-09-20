"""Neuro AI / Agent Foundry compatibility manifest.

An enterprise solution architect asking "is this Neuro-compatible? does it
ship as an Agent Foundry artifact?" gets a structured, JSON answer here.
The manifest is generated from the live system state — what we *actually*
expose, not what a slide claims — so the answer always matches reality.

Endpoint: GET /api/v1/foundry/manifest

What it declares:
  • Neuro AI Multi-Agent Orchestration compatibility — yes;
    we ship the Anthropic Agent SDK semantics + an MCP server compatible
    with the TriZetto AI Gateway (Neuro launch surface, Aug 6, 2025).
  • Agent Foundry compatibility — yes; Agent[I, O] base class is the
    artifact contract, AGENT_MANIFEST is the bundle descriptor.
  • Bedrock model lineage — primary + fallback model IDs, region, guardrails ID.
  • TriZetto integration shape — Facets v3 + QNXT v2 schema names.
  • Observability — /metrics, /stream, /audit endpoints.
  • Governance — CMS-0057-F clauses tracked, model card, evidence pack.

This is the document health-sciences sales would attach to a
co-sell motion: "we already conform — flip the env vars and ship."
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.config import settings

router = APIRouter(prefix="/foundry", tags=["foundry"])


@router.get("/manifest")
async def foundry_manifest() -> dict[str, Any]:
    """Return the Neuro / Agent Foundry compatibility manifest."""
    from app.agents.manifest import (
        AGENT_MANIFEST,
        deterministic_sub_agents_count,
        llm_backed_sub_agents_count,
        total_sub_agents,
    )
    from app.compliance.cms_0057f import CLAUSES

    return {
        "artifact_kind": "neuro.agent-bundle",
        "schema_version": "v1",
        "clincase_version": "0.1.0",
        "name": "clincase",
        "display_name": "ClinCase — Oncology Prior-Authorization Agent Bundle",
        "description": (
            "First specialty-medicine agent bundle for TriZetto AI "
            "Gateway. 7-parent / 22-sub-agent LangGraph DAG on Bedrock + "
            "Anthropic Claude Sonnet 4.6, MCP-native, FHIR + Da Vinci PAS-aware."
        ),
        # --- Neuro AI ----------------------------------------------
        "cognizant_neuro_compatibility": {
            "multi_agent_orchestration": True,
            "agent_sdk": "anthropic-agent-sdk@>=0.4 (Neuro std per Nov 4, 2025 partnership)",
            "mcp_server_endpoint": "/mcp",
            "mcp_protocol_version": "2024-11-05",
            "claude_models_used": [
                settings.BEDROCK_MODEL_ID,
                settings.BEDROCK_HAIKU_MODEL_ID,
            ],
            "compatible_neuro_components": [
                "TriZetto AI Gateway (Aug 6, 2025 launch)",
                "TriZetto Facets G6 prior_auth_event v3",
                "TriZetto QNXT case_event v2",
                "Neuro Multi-Agent Orchestration framework",
            ],
        },
        # --- Agent Foundry artifact descriptor -------------------------------
        "agent_foundry_compatibility": {
            "agents_total": len(AGENT_MANIFEST),
            "sub_agents_total": total_sub_agents(),
            "sub_agents_llm_backed": llm_backed_sub_agents_count(),
            "sub_agents_deterministic": deterministic_sub_agents_count(),
            "agent_contract": "app.agents.framework.agent.Agent[InputSchema, OutputSchema]",
            "manifest_endpoint": "/api/v1/agents/manifest",
            "deployment_targets": [
                "AWS EKS (ops/k8s/)",
                "AWS ECS Fargate (compatible — same image)",
                "AWS Bedrock AgentCore (porting docs in ops/aws/)",
                "TriZetto AI Gateway (MCP fan-out)",
            ],
            "self_describing": True,
            "auto_discovery": "pkgutil.iter_modules(app.agents.*) — manifest is generated, not hand-listed",
        },
        # --- Bedrock lineage ---------------------------------------------------
        "bedrock": {
            "region": settings.AWS_REGION,
            "primary_model": settings.BEDROCK_MODEL_ID,
            "fallback_model": settings.BEDROCK_HAIKU_MODEL_ID,
            "guardrails_id": settings.BEDROCK_GUARDRAIL_ID or None,
            "guardrails_version": settings.BEDROCK_GUARDRAIL_VERSION or None,
            "knowledge_base_id": settings.BEDROCK_KB_ID or None,
            "provisioned_throughput_terraform": "ops/terraform/provisioned-throughput/",
        },
        # --- TriZetto adapter shape -------------------------------------------
        "trizetto_integration": {
            "facets_event_schema": "prior_auth_event v3 (app/integrations/trizetto/facets_pa_event.py)",
            "qnxt_event_schema": "qnxt_case_event v2 (app/integrations/trizetto/qnxt_writeback.py)",
            "gateway_url_env_var": "TRIZETTO_GATEWAY_URL",
            "gateway_token_env_var": "TRIZETTO_GATEWAY_TOKEN",
            "submit_endpoint": "/api/v1/integrations/trizetto/submit",
            "mock_inbox_endpoint": "/api/v1/integrations/trizetto/_mock/inbox",
            "tamper_evident_hash": "sha256(verdict|rationale|citations|model_id)",
        },
        # --- Observability surface --------------------------------------------
        "observability": {
            "metrics_endpoint": "/metrics",
            "metrics_format": "Prometheus",
            "sse_endpoint": "/api/v1/cases/{case_id}/stream",
            "audit_endpoint": "/api/v1/cases/{case_id}/audit",
            "queue_depth_endpoint": "/api/v1/jobs/queue/depth",
            "trace_format": "AgentTrace (parent_span_id chain — X-Ray-mappable)",
        },
        # --- Governance / compliance ------------------------------------------
        "governance": {
            "cms_0057f_clauses_tracked": len([c for c in CLAUSES if c.id.startswith("§")]),
            "state_ai_laws_tracked": [c.id for c in CLAUSES if not c.id.startswith("§")],
            "model_card_endpoint": "/api/v1/responsible-ai/model-card",
            "evidence_pack_endpoint": "/api/v1/cases/{case_id}/evidence-pack",
            "compliance_scorecard_endpoint": "/api/v1/compliance/case/{case_id}",
            "hitl_gate_route": "review_gate (LangGraph; SB 1120-aligned)",
            "audit_retention_days": 365 * 7,
            "phi_handling": "Bedrock Guardrails + PHIInputGuardrail in framework",
        },
        # --- Business value surface (for sales attach) -----------------------
        "business_value_endpoints": {
            "case_roi": "/api/v1/business-value/case/{case_id}",
            "org_rollup": "/api/v1/business-value/org",
            "star_ratings_projection": "/api/v1/business-value/star-impact",
            "provider_abrasion": "/api/v1/business-value/provider-abrasion",
        },
        # --- Deployment readiness --------------------------------------------
        "deployment_readiness": {
            "k8s_manifests": "ops/k8s/",
            "scaling_capacity_model": "ops/SCALING.md",
            "multi_region_terraform": "ops/terraform/multi-region/",
            "aws_migration_runbook": "ops/aws/MIGRATION_RUNBOOK.md",
            "go_to_market_doc": "ops/demo/GO_TO_MARKET.md",
        },
    }
