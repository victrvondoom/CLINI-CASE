# ClinCase — Architecture Diagrams

ASCII for grep-ability + Mermaid for visual rendering. Both are derived from the canonical 5-layer model in [`ops/architecture/TARGET_ARCHITECTURE.md`](../ops/architecture/TARGET_ARCHITECTURE.md).

---

## ASCII — 5-layer overview

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         1.  EXPERIENCE LAYER                             │
│                                                                          │
│   React 18 SPA · TypeScript strict · Tailwind · SSE for live trace       │
│   17 routes incl. /dashboard /cases /roi /compliance /industrialize      │
│                    /architecture                                         │
│   Role-aware (coordinator / reviewer / admin)                            │
└─────────────────────────────────┬────────────────────────────────────────┘
                                  │  HTTPS · JWT · Idempotency-Key
                                  ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                  2.  ORCHESTRATION & POLICY ENGINE                       │
│                                                                          │
│   FastAPI · LangGraph 7-agent DAG · BudgetTracker · review_gate (HITL)   │
│   case_jobs queue (Postgres SKIP LOCKED) · per-org quotas · response     │
│   cache · idempotent submits · 22 sub-agents                             │
└─────┬────────────────────┬────────────────────┬─────────────────┬───────┘
      │                    │                    │                 │
      ▼                    ▼                    ▼                 ▼
┌──────────────┐   ┌────────────────┐   ┌─────────────────┐  ┌─────────────┐
│ 3. CONTEXT   │   │ 4. GENAI       │   │ 5. TELEMETRY    │  │ External    │
│    RETRIEVAL │   │    GATEWAY     │   │    & GOVERNANCE │  │ INTEGRATIONS│
│              │   │                │   │                 │  │             │
│ Bedrock KB   │   │ LLMClient ABC  │   │ TraceSink ABC   │  │ TriZetto AI │
│ Amazon Q Biz │   │ Bedrock client │   │ Prometheus /met │  │  Gateway    │
│ S3 Vectors   │   │ Anthropic API  │   │ Postgres audit  │  │  (Facets v3 │
│ Policy corpus│   │ ModelRouter    │   │ Compliance      │  │  + QNXT v2) │
│ Citation     │   │  (Sonnet/Haiku │   │  scorecard      │  │             │
│  resolver    │   │  escalation)   │   │ Evidence Pack   │  │ MCP server  │
│ FHIR R4      │   │ Bedrock        │   │  (SHA-256       │  │  (5 tools)  │
│  validator   │   │  Guardrails    │   │  tamper-evident)│  │             │
│              │   │  per-tenant    │   │ Responsible AI  │  │ FHIR PAS    │
│              │   │ Budget+token   │   │  model card     │  │  endpoint   │
│              │   │  ceilings      │   │ SLO+error budg. │  │             │
└──────┬───────┘   └────────┬───────┘   └────────┬────────┘  └─────────────┘
       │                    │                    │
       ▼                    ▼                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                          AWS Foundation                                  │
│                                                                          │
│  Bedrock (Claude Sonnet 4.6 + Haiku 4.5) · Bedrock Knowledge Base ·      │
│  Bedrock Guardrails · AgentCore Runtime · Amazon Q Business · RDS Aurora │
│  Global · S3 + KMS multi-region · ALB + WAF · IAM Identity Center · X-Ray│
│  + CloudWatch · SNS → PagerDuty · IRSA · NetworkPolicy (VPC-only egress) │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## ASCII — agentic workflow shape

```
USER GOAL    → AGENT NETWORK              → ACTIONS              → OUTCOME
"Decide PA   → 7 parents + 22 sub-agents  → 5 typed actions      → APPROVE/DENY/REFER
 for         →   under GenAI Gateway      → A1 persist_decision  → time-to-decision 52s
 trastuzumab →   under BudgetTracker      → A2 route_to_review   → cost $0.25
 on patient  →   under review_gate (HITL) → A3 submit_to_TriZetto→ Evidence Pack +
 X under     →                            → A4 draft_appeal      →  bundle SHA-256
 Aetna"      →                            → A5 notify_patient    → CMS-0057-F audit-ready
```

---

## Mermaid — request lifecycle

```mermaid
sequenceDiagram
    participant Coordinator
    participant API as FastAPI
    participant Queue as case_jobs (Postgres SKIP LOCKED)
    participant Worker
    participant DAG as LangGraph 7-agent DAG
    participant Gateway as GenAI Gateway
    participant Bedrock
    participant TriZetto as TriZetto AI Gateway

    Coordinator->>API: POST /run-async (Idempotency-Key)
    API->>Queue: enqueue(case_id, payload)
    API-->>Coordinator: 202 + job_id

    Worker->>Queue: claim_next() [SKIP LOCKED]
    Queue-->>Worker: case_jobs row
    Worker->>DAG: run(ClinCaseState)

    loop for each agent (7 parents)
        DAG->>Gateway: complete(system, user, model_id)
        Gateway->>Gateway: tenant policy + quota check
        Gateway->>Gateway: content-safety pre-check
        Gateway->>Bedrock: InvokeModel (with per-tenant Guardrail)
        Bedrock-->>Gateway: response
        Gateway->>Gateway: write llm_invocations row
        Gateway-->>DAG: LLMResponse
    end

    alt confidence < HITL_CONFIDENCE_THRESHOLD
        DAG->>Worker: paused_for_review (status=awaiting_review)
        Worker->>API: SSE event hitl_pause
        Coordinator->>API: POST /resume {verdict, note}
    else otherwise
        DAG-->>Worker: ClinCaseState (decision + appeal + comm)
    end

    Worker->>API: persist decision row + agent_runs rows
    Coordinator->>API: POST /integrations/trizetto/submit
    API->>TriZetto: Facets v3 + QNXT v2 envelope (SHA-256)
    TriZetto-->>API: gateway_id + fanout_targets
    Coordinator->>API: GET /cases/{id}/evidence-pack
    API-->>Coordinator: JSON bundle + bundle_sha256
```

---

## Mermaid — 5-layer block diagram

```mermaid
flowchart TB
    UI[Layer 1: Experience<br/>React 18 + Vite + TypeScript<br/>17 routes · SSE trace · RBAC]
    OPE[Layer 2: Orchestration & Policy Engine<br/>FastAPI · LangGraph DAG · BudgetTracker<br/>review_gate HITL · case_jobs queue]
    CR[Layer 3: Context Retrieval Service<br/>Bedrock KB / Amazon Q Business / S3 Vectors<br/>policy_retriever orchestrator]
    GW[Layer 4: GenAI Gateway<br/>per-tenant model allowlist · 24h quota<br/>content-safety · llm_invocations audit]
    TG[Layer 5: Telemetry & Governance<br/>Prometheus /metrics · 7 SLOs<br/>Evidence Pack · Responsible AI card]
    EXT[External Integrations<br/>TriZetto Gateway · MCP server · FHIR PAS]
    AWS[AWS Foundation<br/>Bedrock + Sonnet 4.6 + Haiku 4.5<br/>AgentCore · Aurora Global · KMS multi-region]

    UI --> OPE
    OPE --> CR
    OPE --> GW
    OPE --> TG
    OPE --> EXT
    CR --> AWS
    GW --> AWS
    TG --> AWS
    EXT --> AWS
```

---

## Mermaid — agent DAG topology

```mermaid
flowchart LR
    A[Clinical Extractor<br/>3 sub-agents] --> B[Policy Retriever<br/>4 sub-agents]
    B --> C[Necessity Reasoner<br/>3 sub-agents]
    C -- confidence < 0.75 --> RG[review_gate HITL<br/>terminal · resume via API]
    C -- confidence >= 0.75 --> D[Decision Composer<br/>3 sub-agents]
    D -- verdict == DENY --> E[Denial Forecaster<br/>3 sub-agents]
    E --> F[Appeals Drafter<br/>3 sub-agents · reflection]
    F --> G[Patient Communicator<br/>3 sub-agents]
    D -- verdict in APPROVE/REFER --> G
```

---

---

## Where these diagrams appear

- **`/architecture` page** in the running app — same data live-introspected
- **README.md** — the same 5-layer ASCII at the top
