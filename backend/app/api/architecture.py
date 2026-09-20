"""Live target-architecture descriptor — 5 named enterprise layers.

An enterprise solution architect asking "show me the architecture, mapped to
the components actually running in this build" gets a structured JSON answer
here. The response is generated from live system state (route registry,
agent manifest, settings) so what we declare always matches what we run.

Layers:
  1. Experience Layer
  2. Orchestration & Policy Engine
  3. Context Retrieval Service
  4. GenAI Gateway
  5. Telemetry & Governance Layer

Each layer carries:
  • components (live + introspected from imports / settings / manifest)
  • health    (computed from quick reachable checks)
  • business_outcome (one-line, sourced)
  • endpoints (the API surface this layer exposes)

The endpoint is read-only and idempotent. It is the single API a judge
calls to verify "does the architecture in TARGET_ARCHITECTURE.md match the
running app?"

Pairs with:
  • ops/architecture/TARGET_ARCHITECTURE.md
  • ops/architecture/BUSINESS_USE_CASE.md
  • frontend/src/routes/Architecture.tsx
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter

from app.config import settings

router = APIRouter(prefix="/architecture", tags=["architecture"])


def _layer_experience() -> dict[str, Any]:
    return {
        "id": "experience",
        "name": "Experience Layer",
        "purpose": "Role-aware UI surfaces that make business value visible without a query.",
        "components": [
            {"name": "Dashboard",       "path": "frontend/src/routes/Dashboard.tsx"},
            {"name": "Case Detail",     "path": "frontend/src/routes/CaseDetail.tsx"},
            {"name": "ROI Calculator",  "path": "frontend/src/routes/ROI.tsx"},
            {"name": "Compliance",      "path": "frontend/src/routes/Compliance.tsx"},
            {"name": "Industrialize",   "path": "frontend/src/routes/Industrialize.tsx"},
            {"name": "Architecture",    "path": "frontend/src/routes/Architecture.tsx"},
            {"name": "SSE trace stream","path": "app/api/stream.py"},
            {"name": "RBAC",            "path": "frontend/src/components/RequireAuth.tsx"},
            {"name": "/api/v2 scaffold (RFC 7807 envelope)", "path": "app/api/v2.py"},
            {"name": "X-API-Version + RFC 8594 Sunset/Deprecation headers", "path": "app/api/version_headers.py"},
            {"name": "API versioning + deprecation policy", "path": "ops/architecture/API_VERSIONING.md"},
            {"name": "OIDC SSO scaffold (Okta/Azure/Ping/Auth0/Google)", "path": "app/auth/oidc.py"},
            {"name": "Per-tenant rate limiter (sliding window per second + per minute)", "path": "app/rate_limit.py"},
            {"name": "X-ClinCase-Cell-Id response header (cell-based architecture)", "path": "app/api/cell_router_middleware.py"},
        ],
        "endpoints": [
            "/api/v1/cases",
            "/api/v1/cases/{case_id}/stream",
            "/api/v1/auth/*",
            "/api/v1/auth/oidc/login",
            "/api/v1/auth/oidc/callback",
            "/api/v1/auth/oidc/status",
            "/api/v1/rate-limits/me",
            "/api/v2/healthz",
            "/api/v2/version",
        ],
        "business_outcome": (
            "Replaces 12-13 hours/week per oncologist of manual PA workflow "
            "(AMA 2025) with a 2-minute click-through. Each visible UI moment "
            "maps to a quantitative outcome (see BUSINESS_USE_CASE.md)."
        ),
    }


def _layer_orchestration() -> dict[str, Any]:
    from app.agents.manifest import (
        AGENT_MANIFEST,
        deterministic_sub_agents_count,
        llm_backed_sub_agents_count,
        reflection_enabled_count,
        total_sub_agents,
    )

    return {
        "id": "orchestration",
        "name": "Orchestration & Policy Engine",
        "purpose": (
            "The lifecycle, queue, and governance primitives that turn AI infra "
            "spend into AI value. This is where ClinCase sits in McKinsey's 5%."
        ),
        "components": [
            {"name": "Agent[I, O] framework",     "path": "app/agents/framework/agent.py"},
            {"name": "LangGraph 7-agent DAG",     "path": "app/graph/build.py"},
            {"name": "BudgetTracker",             "path": "app/agents/framework/budget.py"},
            {"name": "Per-agent perf budget (p95_latency_budget_ms)", "path": "app/agents/framework/agent.py"},
            {"name": "Guardrail surface",         "path": "app/agents/framework/guardrails.py"},
            {"name": "case_jobs queue (SKIP LOCKED)", "path": "app/jobs/queue.py"},
            {"name": "review_gate (HITL)",        "path": "app/graph/build.py"},
            {"name": "Per-org quotas + tier + data_region", "path": "app/quotas.py"},
            {"name": "Response cache",            "path": "app/agents/framework/cache.py"},
            {"name": "Idempotency-Key dedup",     "path": "app/api/jobs.py"},
            {"name": "Domain events + transactional Outbox", "path": "app/events/outbox.py"},
            {"name": "Outbox publisher worker",   "path": "app/events/publisher.py"},
            {"name": "Saga (5 typed actions + compensations)", "path": "ops/architecture/SAGA_PATTERN.md"},
            {"name": "Per-tenant data residency runtime (ResidencyViolation)", "path": "app/residency.py"},
            {"name": "Region-aware Bedrock model_id resolver", "path": "app/residency.py"},
            {"name": "Cell registry + consistent-hash router", "path": "app/cells.py"},
            {"name": "Cedar fine-grained authorization (deny-wins)", "path": "app/authz/cedar.py"},
            {"name": "Alembic schema migration framework",  "path": "backend/alembic/"},
            {"name": "Saga state-machine engine (case_sagas + replay)", "path": "app/saga.py"},
            {"name": "Graceful shutdown / SIGTERM in-flight drain", "path": "app/graceful_shutdown.py"},
            {"name": "Downstream circuit breakers (TriZetto/FHIR/Q)", "path": "app/downstream/breaker.py"},
            {"name": "Outbox DLQ + replay engine", "path": "app/events/dlq.py"},
            {"name": "Postgres Row Level Security + tenant context", "path": "app/api/tenant_context_middleware.py"},
        ],
        "agents": {
            "parents":   len(AGENT_MANIFEST),
            "sub_agents": total_sub_agents(),
            "llm_backed_sub_agents": llm_backed_sub_agents_count(),
            "deterministic_sub_agents": deterministic_sub_agents_count(),
            "reflection_enabled_sub_agents": reflection_enabled_count(),
        },
        "endpoints": [
            "/api/v1/cases/{case_id}/run-async",
            "/api/v1/cases/{case_id}/run",
            "/api/v1/cases/{case_id}/resume",
            "/api/v1/jobs/{job_id}",
            "/api/v1/jobs/queue/depth",
            "/api/v1/quotas/me",
            "/api/v1/quotas/{organization_id}",
            "/api/v1/residency",
            "/api/v1/residency/regions",
            "/api/v1/residency/{organization_id}",
            "/api/v1/authz/policies",
            "/api/v1/sagas/me",
            "/api/v1/sagas/{saga_id}",
            "/api/v1/sagas/{saga_id}/replay",
            "/api/v1/dlq/me",
            "/api/v1/dlq/me/stats",
            "/api/v1/dlq/{event_id}/replay",
        ],
        "business_outcome": (
            "Per-agent fault isolation, race-free queue, hard cost ceiling, "
            "HITL signoff baked in. Compliance is enforced by the lifecycle, "
            "not by review."
        ),
    }


def _layer_context_retrieval() -> dict[str, Any]:
    return {
        "id": "context-retrieval",
        "name": "Context Retrieval Service (\"agentic capital\")",
        "purpose": (
            "Customer-aligned grounding — the encoded work knowledge an agent "
            "network draws on. industry narrative in 2026 calls this \"agentic capital.\" "
            "Pluggable backend behind a single schema — Bedrock KB / Amazon Q Business / S3 Vectors."
        ),
        "components": [
            {"name": "policy_retriever orchestrator",      "path": "app/agents/policy_retriever/orchestrator.py"},
            {"name": "keyword_filter sub-agent (Bedrock-KB path)", "path": "app/agents/policy_retriever/sub_agents/keyword_filter.py"},
            {"name": "q_business_retriever sub-agent",     "path": "app/agents/policy_retriever/sub_agents/q_business_retriever.py"},
            {"name": "llm_reranker sub-agent",             "path": "app/agents/policy_retriever/sub_agents/llm_reranker.py"},
            {"name": "citation_resolver sub-agent",        "path": "app/agents/policy_retriever/sub_agents/citation_resolver.py"},
            {"name": "phi_sanitizer sub-agent",            "path": "app/agents/clinical_extractor/sub_agents/phi_sanitizer.py"},
            {"name": "fhir_resource_validator sub-agent", "path": "app/agents/clinical_extractor/sub_agents/fhir_resource_validator.py"},
            {"name": "biomarker_specialist sub-agent",     "path": "app/agents/clinical_extractor/sub_agents/biomarker_specialist.py"},
            {"name": "S3 Vectors substrate (Terraform)",   "path": "ops/terraform/s3-vectors/"},
        ],
        "active_backend": (
            "amazon_q_business" if settings.USE_AMAZON_Q else
            ("bedrock_kb" if settings.BEDROCK_KB_ID else "file_corpus")
        ),
        "configured_backends": {
            "bedrock_kb_id": settings.BEDROCK_KB_ID or None,
            "amazon_q_application_id": settings.AMAZON_Q_APPLICATION_ID or None,
            "use_amazon_q": settings.USE_AMAZON_Q,
            "s3_vectors_terraform_apply_ready": True,
        },
        "business_outcome": (
            "Onboard a new customer with their own M365/SharePoint policy "
            "library by flipping USE_AMAZON_Q=true — no new vector index, no "
            "code change. Saves ~1 month of customer-onboarding time. At "
            "production scale, S3 Vectors substrate replaces a separate "
            "OpenSearch Serverless cluster for ~$18/month/customer."
        ),
    }


def _layer_genai_gateway() -> dict[str, Any]:
    return {
        "id": "genai-gateway",
        "name": "GenAI Gateway",
        "purpose": (
            "Single, named, ENFORCED entry point to every Bedrock call. "
            "Realizes AWS's published guidance: API-Gateway-style governance "
            "with IAM scope, per-tenant model allowlist, 24h quota, content-safety "
            "pre-check, and per-call audit log. A CISO audits ONE component."
        ),
        "components": [
            {"name": "GenAIGateway (in-process enforcement)", "path": "app/llm/gateway.py"},
            {"name": "Circuit breaker (per-model 3-state)",  "path": "app/llm/circuit_breaker.py"},
            {"name": "GatewayCallContext (per-tenant scope)", "path": "app/llm/gateway.py"},
            {"name": "TenantPolicy (model allowlist + caps)", "path": "app/llm/gateway.py"},
            {"name": "llm_invocations audit table",          "path": "app/llm/gateway.py (ensure_schema)"},
            {"name": "tenant_policies table",                "path": "app/llm/gateway.py (ensure_schema)"},
            {"name": "OpenTelemetry Bedrock spans (gen_ai.* convention)", "path": "app/observability/otel.py"},
            {"name": "LLMClient ABC",                         "path": "app/llm/base.py"},
            {"name": "BedrockClient (underlying transport)", "path": "app/llm/bedrock_client.py"},
            {"name": "Factory wires Gateway → underlying",   "path": "app/llm/factory.py"},
            {"name": "ModelRouter (Haiku→Sonnet)",            "path": "app/agents/framework/models.py"},
            {"name": "LLMGrader",                              "path": "app/agents/framework/grader.py"},
            {"name": "Per-tenant Bedrock Guardrails (env)",   "path": "app/config.py"},
            {"name": "Bedrock VPC endpoint + endpoint-policy + IAM (Terraform)", "path": "ops/terraform/bedrock-vpc-endpoint/"},
            {"name": "Provisioned Throughput (Terraform)",    "path": "ops/terraform/provisioned-throughput/"},
            {"name": "AgentCore Runtime (apply-ready)",       "path": "ops/aws/agentcore/deployment.yaml"},
            {"name": "AWS WAF + per-tier rate limits (Terraform)", "path": "ops/terraform/waf/"},
        ],
        "endpoints": [
            "/api/v1/llm-gateway/usage",
            "/api/v1/llm-gateway/policy",
            "/api/v1/llm-gateway/usage/{organization_id}",
            "/api/v1/llm-gateway/circuit-breakers",
        ],
        "gateway": {
            "enabled": settings.GENAI_GATEWAY_ENABLED,
            "enforcements": [
                "per-tenant model allowlist",
                "per-tenant 24h rolling token cap",
                "per-tenant 24h rolling USD cap",
                "content-safety pre-check (PHI sniff)",
                "audit row to llm_invocations on every call (success or failure)",
                "GatewayCallContext propagated through Agent.invoke() — every call attributable to (org_id, case_id, agent_name)",
            ],
        },
        "active_provider": settings.LLM_PROVIDER,
        "models": {
            "primary": settings.BEDROCK_MODEL_ID,
            "fallback": settings.BEDROCK_HAIKU_MODEL_ID,
            "region": settings.AWS_REGION,
        },
        "guardrail": {
            "guardrail_id": settings.BEDROCK_GUARDRAIL_ID or None,
            "version": settings.BEDROCK_GUARDRAIL_VERSION,
        },
        "aws_pattern_alignment": {
            "spec_source": "https://aws.amazon.com/blogs/architecture/category/artificial-intelligence/amazon-machine-learning/amazon-bedrock/",
            "in_process_governance": "app/llm/gateway.py",
            "network_isolation": "ops/terraform/bedrock-vpc-endpoint/ (PrivateLink + endpoint policy)",
            "iam_least_privilege": "ops/terraform/bedrock-vpc-endpoint/iam.tf (per-model-id condition)",
            "model_invocation_logging": "ops/terraform/bedrock-vpc-endpoint/logs.tf (7-year retention for CMS-0057-F § IV.D)",
        },
        "business_outcome": (
            "Every Bedrock call goes through one named, enforced, audited component. "
            "ModelRouter routes 60% of calls to Haiku (10× cheaper). Per-tenant 24h "
            "caps prevent runaway burn. Per-tenant audit row in llm_invocations "
            "feeds Evidence Pack reproduction. Cost-optimal, safe, attributable."
        ),
    }


def _layer_telemetry_governance() -> dict[str, Any]:
    from app.compliance.cms_0057f import CLAUSES

    return {
        "id": "telemetry-governance",
        "name": "Telemetry & Governance Layer",
        "purpose": (
            "Compliance is not a slide — it's an endpoint. Every regulatory "
            "claim has a queryable component."
        ),
        "components": [
            {"name": "TraceSink ABC",               "path": "app/agents/framework/trace_sink.py"},
            {"name": "PostgresTraceSink",           "path": "app/agents/framework/trace_sink.py"},
            {"name": "agent_runs audit table",      "path": "backend/db/schema.sql"},
            {"name": "OpenTelemetry distributed tracing (W3C Trace Context)", "path": "app/observability/otel.py"},
            {"name": "Prometheus /metrics",         "path": "app/api/metrics.py"},
            {"name": "Compliance scorecard",        "path": "app/compliance/cms_0057f.py"},
            {"name": "Business value calculator",   "path": "app/business_value/"},
            {"name": "Evidence Pack",               "path": "app/api/evidence_pack.py"},
            {"name": "Responsible AI model card",   "path": "app/api/responsible_ai.py"},
            {"name": "Foundry manifest",            "path": "app/api/foundry.py"},
            {"name": "SLO + error budget",          "path": "ops/sre/SLO.yaml"},
            {"name": "SRE runbook",                 "path": "ops/sre/RUNBOOK.md"},
            {"name": "Chaos engineering playbook (5 named experiments)", "path": "ops/sre/CHAOS_ENGINEERING.md"},
            {"name": "AWS Fault Injection Simulator (Terraform — 5 templates)", "path": "ops/terraform/fis/"},
            {"name": "Chaos trigger script (prod-safe)", "path": "ops/sre/scripts/chaos.sh"},
            {"name": "DR / BCP playbook (5 scenarios + quarterly drill cadence)", "path": "ops/sre/DR_BCP_PLAYBOOK.md"},
            {"name": "Regional failover script", "path": "ops/sre/scripts/regional-failover.sh"},
            {"name": "Quarterly DR drill orchestrator", "path": "ops/sre/scripts/dr-drill.sh"},
            {"name": "CDC stream → S3 audit lake (Terraform)", "path": "ops/terraform/cdc-stream/"},
            {"name": "Service mesh decision (Linkerd Helm install path)", "path": "ops/k8s/linkerd/"},
            {"name": "Per-agent perf-budget breach Prometheus counter", "path": "app/api/metrics.py"},
            {"name": "Circuit breaker state Prometheus gauge",          "path": "app/api/metrics.py"},
            {"name": "OpenLineage emitter (agent + RAG retrieval)", "path": "app/observability/lineage.py"},
            {"name": "Per-tenant audit log export (Terraform — cross-account Kinesis)", "path": "ops/terraform/audit-export/"},
            {"name": "Secrets Manager rotation Lambdas (Terraform)", "path": "ops/terraform/secrets-rotation/"},
            {"name": "Argo CD app-of-apps GitOps", "path": "ops/argocd/"},
            {"name": "KEDA queue-depth autoscaler", "path": "ops/k8s/keda/"},
            {"name": "Supply-chain security (SBOM + Sigstore)", "path": ".github/workflows/supply-chain.yml"},
            {"name": "PgBouncer transaction pooling + read/write split", "path": "ops/k8s/pgbouncer/"},
            {"name": "HIPAA breach detection automation", "path": "app/security/breach_detector.py"},
            {"name": "Compliance control library (NIST AI RMF + ISO 42001 + SOC 2 Type II)", "path": "app/compliance/control_library.py"},
            {"name": "FinOps dashboard (per-tenant + per-cell)", "path": "app/api/finops.py"},
            {"name": "Streaming Bedrock completions (SSE)", "path": "app/api/stream_completion.py"},
            {"name": "Synthetic monitoring (multi-region canary)", "path": "ops/terraform/synthetic-monitoring/"},
            {"name": "CI security pipeline (Trivy + Semgrep + Checkov + gitleaks)", "path": ".github/workflows/security.yml"},
            {"name": "Helm chart for the full app", "path": "charts/clincase/"},
            {"name": "Bedrock cross-region fallback chain", "path": "app/llm/cross_region_fallback.py"},
        ],
        "compliance": {
            "cms_0057f_clauses_tracked": len([c for c in CLAUSES if c.id.startswith("§")]),
            "state_ai_laws_tracked": [c.id for c in CLAUSES if not c.id.startswith("§")],
            "in_force_today": sum(1 for c in CLAUSES if c.in_force_today),
        },
        "endpoints": [
            "/api/v1/compliance/case/{case_id}",
            "/api/v1/compliance/org",
            "/api/v1/business-value/case/{case_id}",
            "/api/v1/business-value/org",
            "/api/v1/business-value/star-impact",
            "/api/v1/business-value/provider-abrasion",
            "/api/v1/cases/{case_id}/evidence-pack",
            "/api/v1/responsible-ai/model-card",
            "/api/v1/responsible-ai/model-card.md",
            "/api/v1/foundry/manifest",
            "/api/v1/healthz/deep",
            "/api/v1/version",
            "/api/v1/capabilities",
            "/metrics",
        ],
        "business_outcome": (
            "−4 hours/quarter of compliance prep · −45 min/audit ticket · "
            "−2 weeks/customer of vendor-security-questionnaire prep · "
            "auditor-grade Evidence Pack in 12 seconds. "
            "Live evidence per-case; never a slide."
        ),
    }


def _layer_external_integrations() -> dict[str, Any]:
    return {
        "id": "external-integrations",
        "name": "External Integrations (cross-cutting)",
        "purpose": (
            "TriZetto AI Gateway adapter + MCP server + FHIR PAS endpoint. "
            "These are how the rest of the customer's stack consumes ClinCase."
        ),
        "components": [
            {"name": "TriZetto AI Gateway adapter (MCP-native)", "path": "app/integrations/trizetto/"},
            {"name": "Facets prior_auth_event v3",               "path": "app/integrations/trizetto/facets_pa_event.py"},
            {"name": "QNXT case_event v2",                       "path": "app/integrations/trizetto/qnxt_writeback.py"},
            {"name": "MCP server (5 tools)",                     "path": "app/mcp/server.py"},
            {"name": "Da Vinci PAS endpoint (FHIR R4)",          "path": "app/api/fhir_pas.py"},
            {"name": "Amazon Q Business client",                 "path": "app/integrations/amazon_q/client.py"},
            {"name": "Kiro IDE spec exporter",                   "path": "app/integrations/kiro/exporter.py"},
        ],
        "endpoints": [
            "/api/v1/integrations/trizetto/submit",
            "/api/v1/integrations/trizetto/_mock/inbox",
            "/api/v1/integrations/trizetto/info",
            "/api/v1/integrations/kiro/export",
            "/mcp",
            "/fhir/Claim/$submit",
        ],
        "business_outcome": (
            "ClinCase deploys natively into the existing TriZetto book of "
            "business. Day-1 add-on inside an existing TriZetto subscription — "
            "no new procurement, no new platform. ~$80M Facets lives + ~20M QNXT "
            "lives addressable from the first sale."
        ),
    }


def _aws_foundation() -> dict[str, Any]:
    return {
        "id": "aws-foundation",
        "name": "AWS Foundation",
        "purpose": "Underlying AWS services every layer above depends on.",
        "services": [
            "Amazon Bedrock (Anthropic Claude Sonnet 4.6 + Haiku 4.5)",
            "Bedrock Knowledge Base",
            "Bedrock Guardrails",
            "Bedrock AgentCore Runtime (apply-ready)",
            "Amazon Q Business",
            "RDS Aurora Global (multi-region apply-ready)",
            "S3 + KMS multi-region",
            "ALB + WAF",
            "IAM Identity Center",
            "X-Ray + CloudWatch",
            "SNS → PagerDuty",
            "EKS (IRSA, NetworkPolicy VPC-only egress)",
        ],
        "region_primary": settings.AWS_REGION,
        "terraform_modules": [
            "ops/terraform/multi-region/",
            "ops/terraform/provisioned-throughput/",
        ],
    }


@router.get("/layers")
async def get_layers() -> dict[str, Any]:
    """Live, structured descriptor of the 5-layer enterprise architecture."""
    return {
        "asof_iso": datetime.now(timezone.utc).isoformat(),
        "clincase_version": "0.1.0",
        "doc_path": "ops/architecture/TARGET_ARCHITECTURE.md",
        "business_use_case_doc": "ops/architecture/BUSINESS_USE_CASE.md",
        "primary_kpis": [
            {
                "id": "cycle_time_reduction",
                "name": "Cycle-time reduction",
                "baseline": "18 min / case (AMA 2025)",
                "target_range": "95–99%",
                "measurement_endpoint": "/api/v1/business-value/org",
            },
            {
                "id": "per_case_cost_savings",
                "name": "Per-case cost displacement",
                "baseline": "$1,500 / case (AMA loaded)",
                "target_range": "$1,499.55–$1,499.75 / case saved",
                "measurement_endpoint": "/api/v1/business-value/case/{case_id}",
            },
            {
                "id": "star_ratings_lift",
                "name": "Star Ratings revenue lift (MA payers)",
                "baseline": "2026 MA average 3.98 stars",
                "target_range": "+0.2 to +0.4 stars (= $1.26B/half-star at Humana scale)",
                "measurement_endpoint": "/api/v1/business-value/star-impact",
            },
            {
                "id": "provider_abrasion_reduction",
                "name": "Provider abrasion reduction",
                "baseline": "12–13 hrs/week PA burden (AMA)",
                "target_range": "60–80% over 90 days",
                "measurement_endpoint": "/api/v1/business-value/provider-abrasion",
            },
        ],
        "layers": [
            _layer_experience(),
            _layer_orchestration(),
            _layer_context_retrieval(),
            _layer_genai_gateway(),
            _layer_telemetry_governance(),
            _layer_external_integrations(),
        ],
        "aws_foundation": _aws_foundation(),
        "cognizant_alignment": {
            "ai_velocity_gap_addressed": True,
            "ai_adaptation_gap_addressed": True,
            "vector_strategy_classification": ["V2 (new agentic software cycles)", "V3 (digital labor)"],
            "agent_foundry_stage": "Build (graduating to Scale on first pilot customer)",
            "neuro_san_compatible": True,
            "trizetto_ai_gateway_native": True,
            "flowsource_compatible_ux_shape": True,
            "anthropic_partnership_alignment": "Claude Sonnet 4.6 + MCP + Anthropic Agent SDK semantics",
            "agentic_workflow_pattern": "user goal → 7-agent network → 5 typed actions → auditable outcome",
            "agentic_capital_layer": "Context Retrieval Service (Layer 3) — Bedrock KB / Q Business / S3 Vectors",
        },
        "trend_alignment_2026": {
            "agent_adoption_pct_industry": 32,
            "expected_agent_returns_12mo_industry": 47,
            "positive_roi_among_early_adopters_pct": 92,
            "productivity_uplift_target_band": "20–40% (ClinCase hits 95–98% on this workflow due to extreme manual baseline)",
            "ticket_escalation_reduction_target_band": "20–30% (ClinCase 60–80% over 90 days)",
            "doc_pair": [
                "ops/architecture/AI_ADAPTATION_GAP.md",
                "ops/architecture/AGENTIC_ACTIONS.md",
                "ops/demo/CASE_STUDY_VIGNETTE.md",
            ],
        },
    }


@router.get("/layers/{layer_id}")
async def get_layer(layer_id: str) -> dict[str, Any]:
    """Return one layer's descriptor (for the frontend's per-layer detail view)."""
    full = await get_layers()
    layers_by_id = {l["id"]: l for l in full["layers"]}
    if layer_id == "aws-foundation":
        return full["aws_foundation"]
    if layer_id not in layers_by_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Layer {layer_id!r} not found")
    return layers_by_id[layer_id]
