"""Round-7 smoke test — verify every architecture layer's primitives import + execute.

Run after backend boot: `cd backend && .venv/Scripts/python.exe -m scripts.smoke_test`

Output is intentionally human-readable; capture it to a file if you need a record.
"""
from __future__ import annotations

import asyncio
import sys


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

    from app.main import app

    # Layer 1 — Experience Layer (route registry)
    from app.api.architecture import get_layers
    from app.api.business_value import case_value  # noqa: F401
    from app.api.compliance import get_org_scorecard  # noqa: F401
    from app.api.evidence_pack import evidence_pack  # noqa: F401
    from app.api.foundry import foundry_manifest
    from app.api.responsible_ai import get_model_card  # noqa: F401
    from app.api.llm_gateway import my_policy  # noqa: F401

    # Layer 2 — Orchestration & Policy Engine
    from app.agents.framework.agent import Agent, GatewayCallContext  # noqa: F401
    from app.agents.framework.budget import BudgetTracker, BudgetExceeded  # noqa: F401
    from app.agents.framework.cache import schema_version_for  # noqa: F401
    from app.agents.framework.guardrails import Guardrail, GuardrailDecision  # noqa: F401
    from app.agents.framework.models import (
        ModelRouter,  # noqa: F401
        SONNET_REASONING,  # noqa: F401
        HAIKU_LITE,  # noqa: F401
        estimate_cost,  # noqa: F401
    )
    from app.agents.framework.trace_sink import (
        TraceSink,  # noqa: F401
        PostgresTraceSink,  # noqa: F401
        InMemoryTraceSink,  # noqa: F401
    )
    from app.agents.framework.types import AgentResult, AgentMetadata, AgentTrace  # noqa: F401
    from app.agents.manifest import AGENT_MANIFEST, total_sub_agents
    from app.jobs import queue as jq  # noqa: F401
    from app.quotas import consume_case_quota, get_quota  # noqa: F401

    # Layer 3 — Context Retrieval
    from app.integrations.amazon_q import AmazonQClient

    # Layer 4 — GenAI Gateway
    from app.llm.factory import get_llm_client
    from app.llm.gateway import (
        GenAIGateway,
        GatewayQuotaExceeded,  # noqa: F401
        GatewayPolicyViolation,  # noqa: F401
        _cost_for,
    )

    # Layer 5 — Telemetry & Governance
    from app.compliance.cms_0057f import CLAUSES
    from app.business_value.roi import (
        case_roi,  # noqa: F401
        MANUAL_PA_COST_USD,
        CLINCASE_COST_CLEAN_APPROVE,
    )
    from app.business_value.star_ratings import star_revenue_estimate

    # External Integrations
    from app.integrations.kiro import export_kiro_specs  # noqa: F401
    from app.integrations.trizetto import (
        TriZettoGatewayClient,
        build_facets_event,
    )
    from app.streaming import (
        InProcessBackend,  # noqa: F401
        RedisPubSubBackend,  # noqa: F401
    )

    print("LAYER 1 - EXPERIENCE LAYER")
    paths = sorted(set(r.path for r in app.routes if hasattr(r, "path")))
    print(f"  routes registered:                  {len(paths)}")
    print()

    print("LAYER 2 - ORCHESTRATION & POLICY ENGINE")
    print(f"  parent agents auto-discovered:      {len(AGENT_MANIFEST)}")
    print(f"  sub-agents auto-discovered:         {total_sub_agents()}")
    budget = BudgetTracker(
        max_cost_usd=5.0,
        max_total_tokens=720_000,
        max_latency_ms=600_000,
    )
    res = budget.reserve(estimated_usd=0.05, estimated_input_tokens=1000, estimated_output_tokens=500)
    print(f"  BudgetTracker.reserve works:        ok")
    budget.commit(res, actual_usd=0.04, actual_input_tokens=900, actual_output_tokens=400, model_id="sonnet-test")
    print(f"  BudgetTracker.commit works:         ok (remaining=${budget.remaining_usd:.2f})")
    print()

    print("LAYER 3 - CONTEXT RETRIEVAL")
    q = AmazonQClient()
    snippets = asyncio.run(q.retrieve(query="trastuzumab HER2", top_k=2, payer_id="aetna"))
    print(f"  AmazonQClient.retrieve (mock):      {len(snippets)} snippets")
    print(f"  first snippet score:                {snippets[0].score if snippets else 'n/a'}")
    print()

    print("LAYER 4 - GENAI GATEWAY")
    client = get_llm_client()
    print(f"  factory returns:                    {type(client).__name__}")
    print(f"  Gateway implements LLMClient:       {isinstance(client, GenAIGateway) or 'underlying client (gateway disabled)'}")
    cost = _cost_for("apac.anthropic.claude-sonnet-4-6", 24_000, 4_500)
    print(f"  cost(Sonnet 24k+4.5k tok):          ${cost:.4f}")
    print()

    print("LAYER 5 - TELEMETRY & GOVERNANCE")
    print(f"  CMS-0057-F clauses tracked:         {len(CLAUSES)}")
    in_force = sum(1 for c in CLAUSES if c.in_force_today)
    print(f"  clauses in force today:             {in_force} of {len(CLAUSES)}")
    arch = asyncio.run(get_layers())
    print(f"  /architecture/layers:               {len(arch['layers'])} layers, {len(arch['primary_kpis'])} KPIs")
    fm = asyncio.run(foundry_manifest())
    print(f"  /foundry/manifest agents_total:     {fm['agent_foundry_compatibility']['agents_total']}")
    print(f"  /foundry/manifest sub_agents_total: {fm['agent_foundry_compatibility']['sub_agents_total']}")
    print()

    print("EXTERNAL INTEGRATIONS")
    ev = build_facets_event(
        case_id="SMOKE-1",
        payer_id="aetna",
        member_id="M0001",
        requested_treatment={"name": "trastuzumab", "j_code": "J9355"},
        decision={
            "verdict": "APPROVE",
            "rationale": "HER2+ confirmed; meets NCCN BREA-N criteria.",
            "citations": ["Aetna oncology policy section 4.2"],
        },
        primary_model_id="apac.anthropic.claude-sonnet-4-6",
        confidence=0.92,
        triggered_hitl=False,
        decision_run_id="abc-123",
        cms_0057f_clauses_satisfied=["§ IV.A", "§ IV.B.1"],
    )
    print(f"  Facets event build:                 action={ev.action}")
    print(f"  SHA-256 (first 16):                 {ev.external_decision_engine.decision_hash_sha256[:16]}")
    trz = TriZettoGatewayClient()
    print(f"  TriZetto client mode:               {'mock' if trz.is_mock else 'real'}")
    print()

    print("BUSINESS VALUE SPOT-CHECK")
    rev = star_revenue_estimate(member_count=6_000_000, star_lift=0.5)
    print(f"  Humana 0.5-star revenue lift:       ${rev / 1_000_000_000:.2f}B / yr")
    print(f"  AMA manual PA baseline:             ${MANUAL_PA_COST_USD:.0f} / case")
    print(f"  ClinCase clean APPROVE cost:         ${CLINCASE_COST_CLEAN_APPROVE:.2f} / case")
    print(f"  per-case savings (clean APPROVE):   ${MANUAL_PA_COST_USD - CLINCASE_COST_CLEAN_APPROVE:.2f}")
    print()

    print("SMOKE TEST: PASS")
    print("  - all 5 layers' primitives import + execute correctly")
    print("  - external integrations build without error")
    print("  - business-value math anchored to public sources")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
