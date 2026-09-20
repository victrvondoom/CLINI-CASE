"""Formal compliance control library — NIST AI RMF + ISO 42001 + SOC 2 Type II.

Round-9 had narrative compliance docs. Auditor's first ask is:
  "Show me your control library — for each control, what's the implementing
   evidence in your codebase / infrastructure?"

This module is the structured answer. Each control:
  • framework + clause id (e.g. NIST AI RMF "GOVERN-1.1")
  • description (the auditor's rubric in plain English)
  • implementation pointers (concrete files / endpoints / Terraform)
  • status (in-place | partial | not-applicable | deferred)
  • last_verified_date

Surfaced as JSON at:
  GET  /api/v1/compliance/control-library
  GET  /api/v1/compliance/control-library/{framework}
  GET  /api/v1/compliance/control-library/{framework}/{clause_id}

Pairs with: ops/compliance/CONTROL_LIBRARY.md
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class Control:
    framework: str        # 'NIST_AI_RMF' | 'ISO_42001' | 'SOC2_TYPE2' | 'HIPAA' | 'CMS_0057F'
    clause_id: str        # framework-specific
    title: str
    description: str
    status: str           # 'in_place' | 'partial' | 'not_applicable' | 'deferred'
    implementation_evidence: tuple[str, ...] = ()
    last_verified_date: str = "2026-05-03"
    notes: str = ""


# =============================================================================
# NIST AI Risk Management Framework 1.0 (https://www.nist.gov/itl/ai-risk-management-framework)
# =============================================================================
NIST_AI_RMF: tuple[Control, ...] = (
    Control(
        framework="NIST_AI_RMF", clause_id="GOVERN-1.1",
        title="Legal/regulatory requirements involving AI are understood, managed, and documented",
        description="The organization tracks which regulations apply (CMS-0057-F, CA SB-1120, EU AI Act, HIPAA) and how they map to the AI system.",
        status="in_place",
        implementation_evidence=(
            "app/compliance/cms_0057f.py — CMS 8 clauses tracked",
            "ops/architecture/AI_ADAPTATION_GAP.md — EU AI Act high-risk classification",
            "ops/sre/DR_BCP_PLAYBOOK.md — HIPAA Breach Notification Rule mapping",
        ),
    ),
    Control(
        framework="NIST_AI_RMF", clause_id="GOVERN-1.2",
        title="Roles and responsibilities for AI risk management are documented and clear",
        description="Owner per agent, owner per layer, escalation path documented.",
        status="in_place",
        implementation_evidence=(
            "ops/sre/RUNBOOK.md — incident escalation matrix",
            "ops/sre/CHAOS_ENGINEERING.md — quarterly drill ownership",
            "frontend/src/components/Sidenav.tsx — role-based UI surfaces",
        ),
    ),
    Control(
        framework="NIST_AI_RMF", clause_id="MAP-1.1",
        title="Context in which AI system will be deployed is understood and documented",
        description="The deployment, operational, and intended-use context is captured.",
        status="in_place",
        implementation_evidence=(
            "ops/architecture/BUSINESS_USE_CASE.md",
            "PROPOSAL.md § 1-5 (problem framing)",
            "app/api/foundry.py — agents_manifest with intended_use",
        ),
    ),
    Control(
        framework="NIST_AI_RMF", clause_id="MAP-2.3",
        title="Data sources are documented and provenance is tracked",
        description="Lineage from input data → model output is auditable.",
        status="in_place",
        implementation_evidence=(
            "app/observability/lineage.py — OpenLineage emitter (round 11)",
            "ops/architecture/DATA_LINEAGE.md",
            "ops/terraform/cdc-stream/ — DMS CDC into S3 audit lake (round 9)",
        ),
    ),
    Control(
        framework="NIST_AI_RMF", clause_id="MEASURE-2.1",
        title="Test sets, metrics, and model performance are documented",
        description="Per-agent eval suite + business-value metrics are auditable.",
        status="in_place",
        implementation_evidence=(
            "app/api/eval.py — per-agent eval rollups",
            "app/api/responsible_ai.py — model card endpoint",
            "tests/fixtures/ — contract tests",
        ),
    ),
    Control(
        framework="NIST_AI_RMF", clause_id="MEASURE-2.6",
        title="The AI system is evaluated for safety, security, resilience",
        description="Resilience proven via chaos engineering + DR drills.",
        status="in_place",
        implementation_evidence=(
            "ops/sre/CHAOS_ENGINEERING.md — 5 named experiments",
            "ops/terraform/fis/ — apply-ready AWS FIS module (round 10)",
            "ops/sre/scripts/chaos.sh + dr-drill.sh",
        ),
    ),
    Control(
        framework="NIST_AI_RMF", clause_id="MANAGE-1.3",
        title="High-risk AI uses have documented risk controls",
        description="HITL signoff, hard cost ceiling, denial guardrail.",
        status="in_place",
        implementation_evidence=(
            "app/graph/build.py — review_gate (HITL)",
            "app/agents/framework/budget.py — BudgetTracker",
            "app/agents/framework/guardrails.py",
        ),
    ),
    Control(
        framework="NIST_AI_RMF", clause_id="MANAGE-4.1",
        title="Mechanisms exist to deactivate the AI system when warranted",
        description="Kill-switch + tenant-level disable + tier-cap.",
        status="in_place",
        implementation_evidence=(
            "app/llm/circuit_breaker.py — auto-disable per Bedrock model on failures",
            "app/llm/gateway.py — TenantPolicy.allowed_model_ids allowlist",
            "ops/sre/scripts/regional-failover.sh",
        ),
    ),
)

# =============================================================================
# ISO/IEC 42001:2023 — AI Management System
# =============================================================================
ISO_42001: tuple[Control, ...] = (
    Control(
        framework="ISO_42001", clause_id="A.5.2",
        title="AI Policy",
        description="Organization has a documented AI policy aligned with strategy.",
        status="in_place",
        implementation_evidence=(
            "PROPOSAL.md — overall design and AI use",
            "ops/architecture/AI_ADAPTATION_GAP.md",
            "ROADMAP.md",
        ),
    ),
    Control(
        framework="ISO_42001", clause_id="A.6.2",
        title="Roles, responsibilities, and authorities for AI management",
        description="Clear ownership for AI risk decisions.",
        status="in_place",
        implementation_evidence=(
            "ops/sre/RUNBOOK.md",
            "frontend/src/components/RequireAuth.tsx — RBAC",
            "ops/architecture/AUTHZ_CEDAR.md — fine-grained authorization (round 11)",
        ),
    ),
    Control(
        framework="ISO_42001", clause_id="A.7.4",
        title="AI system impact assessment",
        description="Documented assessment of AI system's impact on individuals.",
        status="in_place",
        implementation_evidence=(
            "ops/architecture/BUSINESS_USE_CASE.md",
            "app/api/responsible_ai.py — model card",
            "ops/architecture/AGENTIC_ACTIONS.md — what each agent does + does NOT do",
        ),
    ),
    Control(
        framework="ISO_42001", clause_id="A.8.2",
        title="AI system requirements",
        description="Functional + non-functional requirements documented.",
        status="in_place",
        implementation_evidence=(
            "ops/architecture/TARGET_ARCHITECTURE.md",
            "ops/sre/SLO.yaml — 9 SLOs (rounds 9, 10)",
            "PROPOSAL.md § 6-25 (functional requirements)",
        ),
    ),
    Control(
        framework="ISO_42001", clause_id="A.9.3",
        title="Performance evaluation",
        description="Metrics, monitoring, and audit results documented.",
        status="in_place",
        implementation_evidence=(
            "app/api/metrics.py — Prometheus + perf-budget counter",
            "app/api/business_value.py",
            "app/api/eval.py",
        ),
    ),
    Control(
        framework="ISO_42001", clause_id="A.10.4",
        title="Improvement",
        description="Continual improvement loop with documented action items.",
        status="in_place",
        implementation_evidence=(
            "ops/sre/dr-results/ — quarterly drill summaries (template via dr-drill.sh)",
            "ops/sre/chaos-results/ — quarterly chaos summaries",
            "CHANGELOG.md",
        ),
    ),
)

# =============================================================================
# SOC 2 Type II — Trust Services Criteria
# (https://www.aicpa-cima.com/topic/audit-assurance/audit-and-assurance-greater-than-soc-2)
# =============================================================================
SOC2_TYPE2: tuple[Control, ...] = (
    Control(
        framework="SOC2_TYPE2", clause_id="CC1.1",
        title="Control Environment — Integrity and Ethical Values",
        description="Code of conduct + acceptable-use policy.",
        status="in_place",
        implementation_evidence=("CONTRIBUTING.md", "SECURITY.md", "CLAUDE.md"),
    ),
    Control(
        framework="SOC2_TYPE2", clause_id="CC2.1",
        title="Communication — Information Quality",
        description="Information used by personnel is high-quality and timely.",
        status="in_place",
        implementation_evidence=(
            "app/api/architecture.py — live architecture descriptor",
            "ops/sre/RUNBOOK.md",
            "app/observability/otel.py — distributed tracing",
        ),
    ),
    Control(
        framework="SOC2_TYPE2", clause_id="CC6.1",
        title="Logical Access — Access Controls",
        description="Access is restricted by role and need-to-know.",
        status="in_place",
        implementation_evidence=(
            "app/auth/ — JWT + role gates",
            "app/authz/cedar.py — fine-grained ABAC (round 11)",
            "ops/architecture/ROW_LEVEL_SECURITY.md (round 12)",
        ),
    ),
    Control(
        framework="SOC2_TYPE2", clause_id="CC6.6",
        title="System boundaries are designed and documented",
        description="Boundaries between cloud + on-prem + customer + vendor are explicit.",
        status="in_place",
        implementation_evidence=(
            "ops/architecture/TARGET_ARCHITECTURE.md",
            "ops/architecture/CELL_BASED_ARCHITECTURE.md (round 11)",
            "ops/terraform/bedrock-vpc-endpoint/ — network boundary",
        ),
    ),
    Control(
        framework="SOC2_TYPE2", clause_id="CC7.2",
        title="Anomalies are identified and analyzed",
        description="Real-time anomaly detection with documented response.",
        status="in_place",
        implementation_evidence=(
            "app/security/breach_detector.py (round 12)",
            "app/llm/circuit_breaker.py",
            "app/downstream/breaker.py (round 12)",
        ),
    ),
    Control(
        framework="SOC2_TYPE2", clause_id="CC7.3",
        title="Incidents are responded to and remediated",
        description="Documented incident response runbook + escalation.",
        status="in_place",
        implementation_evidence=(
            "ops/sre/RUNBOOK.md",
            "ops/sre/DR_BCP_PLAYBOOK.md",
            "ops/sre/scripts/regional-failover.sh + chaos.sh + dr-drill.sh",
        ),
    ),
    Control(
        framework="SOC2_TYPE2", clause_id="CC8.1",
        title="Change Management",
        description="Changes go through documented change management.",
        status="in_place",
        implementation_evidence=(
            "ops/argocd/ — GitOps (round 11)",
            "backend/alembic/ — schema migrations (round 11)",
            ".github/workflows/security.yml — security gates (round 12)",
        ),
    ),
    Control(
        framework="SOC2_TYPE2", clause_id="A1.2",
        title="Availability — Capacity",
        description="Capacity is planned to meet commitments.",
        status="in_place",
        implementation_evidence=(
            "ops/k8s/keda/ (round 11) — queue-depth autoscaler",
            "ops/sre/SLO.yaml — error budget tracking",
            "ops/sre/LOAD_TEST_RESULTS.md",
        ),
    ),
    Control(
        framework="SOC2_TYPE2", clause_id="C1.1",
        title="Confidentiality of customer data",
        description="Customer data is encrypted, segregated, deleted on request.",
        status="in_place",
        implementation_evidence=(
            "ops/architecture/DATA_RESIDENCY.md (round 9)",
            "ops/architecture/ROW_LEVEL_SECURITY.md (round 12)",
            "ops/terraform/secrets-rotation/ (round 11)",
        ),
    ),
)

# =============================================================================
# Public API
# =============================================================================


def all_controls() -> list[Control]:
    return list(NIST_AI_RMF) + list(ISO_42001) + list(SOC2_TYPE2)


def by_framework(framework: str) -> list[Control]:
    return [c for c in all_controls() if c.framework.lower() == framework.lower()]


def get(framework: str, clause_id: str) -> Control | None:
    for c in all_controls():
        if c.framework.lower() == framework.lower() and c.clause_id == clause_id:
            return c
    return None


def summary() -> dict[str, Any]:
    by_fw: dict[str, dict[str, int]] = {}
    for c in all_controls():
        by_fw.setdefault(c.framework, {"in_place": 0, "partial": 0, "deferred": 0, "not_applicable": 0, "total": 0})
        by_fw[c.framework][c.status] = by_fw[c.framework].get(c.status, 0) + 1
        by_fw[c.framework]["total"] += 1
    return {
        "frameworks_tracked": list(by_fw.keys()),
        "total_controls": len(all_controls()),
        "by_framework": by_fw,
    }


def to_dict(c: Control) -> dict[str, Any]:
    d = asdict(c)
    d["implementation_evidence"] = list(d["implementation_evidence"])
    return d
