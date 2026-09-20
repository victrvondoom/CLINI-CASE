/* ============================================================
   DOC 4 — ClinCase Code Files Explained (every file's role)
   ============================================================ */
const fs = require('fs');
const path = require('path');
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, LevelFormat, HeadingLevel,
  BorderStyle, WidthType, ShadingType, PageBreak, PageNumber,
} = require('docx');

const OUT = path.join(__dirname, 'ClinCase_04_Code_Files_Explained.docx');
const PAGE = { width: 11906, height: 16838 };
const MARGIN = { top: 1440, right: 1200, bottom: 1440, left: 1200 };
const CONTENT_W = 9506;
const BORDER = { style: BorderStyle.SINGLE, size: 4, color: 'CCCCCC' };
const BORDERS = { top: BORDER, bottom: BORDER, left: BORDER, right: BORDER };

const H1 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1, spacing: { before: 320, after: 160 }, children: [new TextRun({ text: t, bold: true, size: 32, color: '0F172A' })] });
const H2 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_2, spacing: { before: 240, after: 120 }, children: [new TextRun({ text: t, bold: true, size: 26, color: '1E293B' })] });
const H3 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_3, spacing: { before: 200, after: 80 }, children: [new TextRun({ text: t, bold: true, size: 22, color: '4F46E5' })] });
const PARA = (t, opts = {}) => new Paragraph({ spacing: { after: 100 }, children: [new TextRun({ text: t, size: 22, ...opts })] });
const BULLET = (t) => new Paragraph({ numbering: { reference: 'bullets', level: 0 }, spacing: { after: 60 }, children: [new TextRun({ text: t, size: 22 })] });
const PB = () => new Paragraph({ children: [new PageBreak()] });
const SPACER = () => new Paragraph({ spacing: { after: 100 }, children: [new TextRun('')] });

const FILE = (path, role, what, why) => [
  new Paragraph({ spacing: { before: 180, after: 40 }, children: [new TextRun({ text: path, bold: true, color: '4F46E5', size: 21, font: 'Consolas' })] }),
  new Paragraph({ spacing: { after: 50 }, children: [new TextRun({ text: 'Role: ', bold: true, color: '0F172A', size: 21 }), new TextRun({ text: role, size: 21 })] }),
  new Paragraph({ spacing: { after: 50 }, children: [new TextRun({ text: 'What it does: ', bold: true, color: '0F172A', size: 21 }), new TextRun({ text: what, size: 21 })] }),
  new Paragraph({ spacing: { after: 100 }, children: [new TextRun({ text: 'Why we built it: ', bold: true, color: '0F172A', size: 21 }), new TextRun({ text: why, size: 21 })] }),
];

const CALLOUT = (label, body, accent = '4F46E5', bg = 'EEF2FF') => new Table({
  width: { size: CONTENT_W, type: WidthType.DXA },
  columnWidths: [CONTENT_W],
  rows: [new TableRow({
    children: [new TableCell({
      borders: { top: { style: BorderStyle.SINGLE, size: 16, color: accent }, bottom: BORDER, left: BORDER, right: BORDER },
      width: { size: CONTENT_W, type: WidthType.DXA },
      shading: { fill: bg, type: ShadingType.CLEAR },
      margins: { top: 120, bottom: 120, left: 200, right: 200 },
      children: [
        new Paragraph({ spacing: { after: 60 }, children: [new TextRun({ text: label, bold: true, color: accent, size: 20 })] }),
        new Paragraph({ children: [new TextRun({ text: body, size: 22 })] }),
      ],
    })],
  })],
});

const c = [];

// COVER
c.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 2400, after: 200 }, children: [new TextRun({ text: 'CLINCASE', bold: true, size: 56, color: '4F46E5' })] }));
c.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 600 }, children: [new TextRun({ text: 'Code Files Explained — Every File\'s Role', size: 26, color: '475569' })] }));
c.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 400 }, children: [new TextRun({ text: '187 Python files + 56 TypeScript routes + components, organised into 12 logical groups', italics: true, size: 22, color: '64748B' })] }));
c.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 }, children: [new TextRun({ text: 'Document 4 of 7 · the 2026 hackathon', size: 22, color: '64748B' })] }));
c.push(PB());

// Intro
c.push(H1('How to read this document'));
c.push(PARA('ClinCase has hundreds of files. You do not need to memorise each one. You need to understand the GROUPS and where each group fits.'));
c.push(PARA('We have organised every code file into 12 groups. For each group, we explain:'));
c.push(BULLET('What the group does (in one sentence)'));
c.push(BULLET('Where it lives in the repo'));
c.push(BULLET('The key files inside (with role + purpose)'));
c.push(BULLET('How it connects to the rest of the system'));
c.push(SPACER());
c.push(CALLOUT('Memorise the groups, not the files', 'You will be asked "where does X happen?" — answering with the group name (e.g., "in the Agent Plane, specifically the Necessity Reasoner") is enough. The file-level detail is for follow-up.'));
c.push(PB());

// =============================================================
// GROUP 1 — AGENT FRAMEWORK
// =============================================================
c.push(H1('Group 1 — Agent Framework (the foundation)'));
c.push(PARA('Where: backend/app/agents/framework/ · 10 files'));
c.push(PARA('Purpose: The shared infrastructure every agent uses. Like a "base class" for all 7 parent agents and 22 sub-agents.'));
c.push(SPACER());

c.push(...FILE('framework/agent.py',
  'The base Agent class that every ClinCase agent inherits from.',
  'Defines the contract: every agent has a name, an input_schema (Pydantic), an output_schema (Pydantic), a system_prompt, a primary_model, and a run() method.',
  'Without this, every agent would re-implement the boilerplate (validation, retry, grading). With it, building a new agent is just: subclass Agent + write a prompt.'));

c.push(...FILE('framework/models.py',
  'Defines the LLM model "specs" — Sonnet for reasoning, Haiku for grading, etc.',
  'Has constants like SONNET_REASONING (max_tokens=3000), HAIKU_GRADER (max_tokens=1500), SONNET_LONG_JSON (max_tokens=8000). Each agent picks one.',
  'Centralised model selection. When AWS adds a new model, we add one line here and all agents can use it. Saves us from changing every agent file.'));

c.push(...FILE('framework/grader.py',
  'A small AI that scores other AI outputs.',
  'Takes an agent\'s output, runs it through Haiku 4.5 with a grading prompt, returns a 5-field GraderScore (schema_correctness, clinical_faithfulness, citation_completeness, feedback, overall score).',
  'The grader is what stops hallucinations. Below 0.80 score = retry. This is one of our biggest reliability differentiators.'));

c.push(...FILE('framework/guardrails.py',
  'Pre-flight and post-flight checks for every agent call.',
  'TokenBudgetGuardrail (rejects huge inputs), SchemaGuardrail (validates output JSON), PHIGuardrail (re-checks no PHI leaked).',
  'Defence-in-depth. Even if the LLM goes rogue, guardrails catch problems at the boundary.'));

c.push(...FILE('framework/trace_sink.py',
  'Records every agent invocation to the audit_ledger and agent_runs tables.',
  'Every agent call writes: timestamp, agent name, model used, tokens in/out, latency, hash chain entry.',
  'The audit ledger is built on this. Without trace_sink, we could not prove what happened in any given case.'));

c.push(...FILE('framework/budget.py',
  'Tracks per-tenant LLM cost.',
  'Aggregates llm_invocations rows by tenant + month. Returns "you have $X spent of your $Y budget".',
  'Multi-tenant cost awareness. Enterprise clients get per-team usage tracking.'));

c.push(...FILE('framework/cache.py',
  'Caches identical LLM calls.',
  'If the same prompt + same model is called twice in 24 hours, returns the cached response instead of calling Bedrock again.',
  'Saves money during testing. Disabled in production for compliance reasons (audit log must show every actual call).'));

c.push(...FILE('framework/context.py',
  'Holds per-request context (case_id, tenant_id, JWT).',
  'Python contextvar that propagates through async functions without explicit passing.',
  'Lets us write clean function signatures while still accessing case_id from anywhere (e.g., the audit ledger writer).'));

c.push(...FILE('framework/types.py',
  'Shared Pydantic types used across multiple agents.',
  'AgentInput, AgentOutput, GraderScore, AgentResult, RetryPolicy.',
  'DRY — define once, use everywhere. If we change AgentResult, every agent updates automatically.'));

c.push(...FILE('framework/__init__.py',
  'The public interface of the framework module.',
  'Re-exports Agent, ModelSpec, all guardrails, the grader, etc.',
  'Lets agents do "from app.agents.framework import Agent" instead of deep imports.'));
c.push(PB());

// =============================================================
// GROUP 2 — THE 7 PARENT AGENTS
// =============================================================
c.push(H1('Group 2 — The 7 Parent Agents (the brains)'));
c.push(PARA('Where: backend/app/agents/{clinical_extractor, policy_retriever, necessity_reasoner, decision_composer, denial_forecaster, appeals_drafter, patient_communicator}/'));
c.push(PARA('Each parent agent is a folder containing: orchestrator.py (the main entrypoint), schemas.py (Pydantic models), node.py (LangGraph integration), and sub_agents/ (specialist children).'));
c.push(SPACER());

c.push(H2('clinical_extractor/ — Reads FHIR, makes a Snapshot'));
c.push(...FILE('clinical_extractor/orchestrator.py',
  'The entry point of the Clinical Extractor agent.',
  'Reads a FHIR R4 Bundle, calls the 3 sub-agents (biomarker_specialist, phi_sanitizer, fhir_resource_validator) in sequence, returns a ClinicalSnapshot.',
  'Without this, every downstream agent would re-read FHIR. The Snapshot is much smaller and easier to reason about.'));

c.push(...FILE('clinical_extractor/schemas.py',
  'Pydantic models for inputs and outputs.',
  'Defines ClinicalSnapshot (with biomarkers, diagnosis, performance_status, etc.), FHIRBundle input.',
  'Strict typing means malformed input fails fast at the boundary, not deep inside the LLM.'));

c.push(...FILE('clinical_extractor/sub_agents/biomarker_specialist.py',
  'Pulls biomarker observations from FHIR.',
  'Looks for HER2, ER, PR, Ki-67, LVEF, etc. Normalises units. Returns typed list.',
  'Biomarker logic is complex (different LOINC codes for the same test). Centralising it here means one place to update when a new biomarker is added.'));

c.push(...FILE('clinical_extractor/sub_agents/phi_sanitizer.py',
  'Strips Protected Health Information BEFORE any LLM call.',
  'Removes name, DOB, MRN, address, phone. Replaces with patient initials + hashed identifiers.',
  'HIPAA-compliant by architecture. PHI never enters the LLM context window.'));

c.push(...FILE('clinical_extractor/sub_agents/fhir_resource_validator.py',
  'Checks the input is real FHIR R4 (not garbage).',
  'Validates Bundle structure, resource references, required fields per USCDI v3.',
  'Reject malformed input fast — saves LLM cost on cases that would fail anyway.'));

c.push(SPACER());
c.push(H2('policy_retriever/ — Finds the right payer policy'));
c.push(...FILE('policy_retriever/orchestrator.py',
  'Main entry — retrieves the top 5 most relevant policy excerpts for a case.',
  'Fans out to 4 sub-agents: keyword_filter, q_business_retriever, llm_reranker, citation_resolver.',
  'Hybrid retrieval (keyword + semantic + LLM rerank) is more accurate than any single method.'));

c.push(...FILE('policy_retriever/sub_agents/keyword_filter.py',
  'Quick filter on payer + drug + indication.',
  'Cuts thousands of policies down to ~50 candidates in <100ms.',
  'Without this, we would semantic-search across thousands. Pre-filter saves Q Business cost.'));

c.push(...FILE('policy_retriever/sub_agents/q_business_retriever.py',
  'AWS Q Business semantic search.',
  'Embeds the case and finds the closest 10 policy sections.',
  'Q Business is the partner\'s standard retrieval engine. Using it = fitting their stack.'));

c.push(...FILE('policy_retriever/sub_agents/llm_reranker.py',
  'Final rerank by Claude Sonnet.',
  'Reads the top 10 candidates and picks the best 5 by actual relevance to the case.',
  'Semantic search returns "similar" results, but similarity ≠ relevance. The LLM reranker fixes this.'));

c.push(...FILE('policy_retriever/sub_agents/citation_resolver.py',
  'Generates the canonical citation pointer.',
  'Maps a policy excerpt to "policy/aetna-0123#4.1" format.',
  'Stable pointers = auditors can re-fetch any cited section years later.'));

c.push(SPACER());
c.push(H2('necessity_reasoner/ — The hardest part'));
c.push(...FILE('necessity_reasoner/orchestrator.py',
  'Coordinates per-criterion checking.',
  'Calls criterion_splitter, then fans out evidence_matcher in parallel (one call per criterion), then confidence_calibrator.',
  'Parallel fan-out is what makes ClinCase fast. 8 criteria checked in parallel, not sequentially.'));

c.push(...FILE('necessity_reasoner/sub_agents/criterion_splitter.py',
  'Breaks payer policy into atomic, individually-checkable criteria.',
  'Reads 5 policy excerpts, outputs 8 atomic criteria like "HER2-positive (IHC 3+ or FISH ≥ 2.0)".',
  'You cannot check a compound criterion. Splitting first makes evidence_matcher\'s job tractable.'));

c.push(...FILE('necessity_reasoner/sub_agents/evidence_matcher.py',
  'For ONE atomic criterion, decides MET / NOT_MET / AMBIGUOUS.',
  'Reads the criterion + ClinicalSnapshot, returns status with cited evidence.',
  'This is the single most-called agent in ClinCase (8x per case parallel). Most expensive in cost, most critical in accuracy.'));

c.push(...FILE('necessity_reasoner/sub_agents/confidence_calibrator.py',
  'Aggregates all criterion results into one confidence score.',
  'If any criterion AMBIGUOUS, lowers confidence. If all MET, high confidence.',
  'Single-number summary for the verdict_synthesizer to make a clean APPROVE/REFER/DENY decision.'));

c.push(SPACER());
c.push(H2('decision_composer/ — Build the final verdict'));
c.push(...FILE('decision_composer/sub_agents/verdict_synthesizer.py',
  'Deterministic logic — no LLM call.',
  'If all inclusion MET + no exclusion triggered = APPROVE. If any inclusion NOT_MET = DENY. If AMBIGUOUS = REFER.',
  'Verdicts must be reproducible. We do not let the LLM decide — the LLM produces evidence, the deterministic synthesizer produces the verdict.'));

c.push(...FILE('decision_composer/sub_agents/rationale_writer.py',
  'Composes a 2-4 sentence executive rationale.',
  'Reads the assessment + verdict, writes a doctor-readable explanation citing snapshot fields and policy phrases.',
  'A verdict alone is not enough — the doctor needs to understand why. The rationale is what they read first.'));

c.push(...FILE('decision_composer/sub_agents/citation_linker.py',
  'Builds the final citation chain.',
  'For every claim in the rationale, attaches a stable pointer (FHIR resource ID or policy section).',
  'Citations are what make the verdict auditable. Without them, the doctor (and the auditor) cannot verify.'));

c.push(SPACER());
c.push(H2('denial_forecaster/ — Predict payer behaviour'));
c.push(...FILE('denial_forecaster/sub_agents/probability_estimator.py',
  'Predicts payer denial probability (0.0 to 1.0).',
  'Reads our verdict + the case + the payer policy, estimates how likely the payer will agree with us.',
  'Even when we APPROVE, the payer might still deny. Pre-warning the doctor saves another fax cycle.'));

c.push(...FILE('denial_forecaster/sub_agents/reason_predictor.py',
  'Predicts the top 3 reasons the payer might cite for denial.',
  'Returns ranked list with policy section pointers.',
  'Pre-stages counter-arguments for the appeals drafter. Faster appeal letter when needed.'));

c.push(...FILE('denial_forecaster/sub_agents/appeal_path_recommender.py',
  'If denial probability ≥ 0.35, picks the appeal angle.',
  'Returns one of: biomarker_evidence, guideline_alignment, prior_therapy_failure, etc.',
  'Different appeals work differently. Picking the right angle = higher overturn probability.'));

c.push(SPACER());
c.push(H2('appeals_drafter/ — The killer feature'));
c.push(...FILE('appeals_drafter/sub_agents/counter_evidence_finder.py',
  'Finds clinical evidence that contests likely denial reasons.',
  'Reads denial_forecaster output, mines the snapshot for counter-evidence.',
  'A blank-page appeal letter is hard. Pre-finding counter-evidence = faster, more accurate letter.'));

c.push(...FILE('appeals_drafter/sub_agents/nccn_reference_specialist.py',
  'Pulls NCCN guideline references that support the treatment.',
  'Returns canonical NCCN section pointers.',
  'NCCN is the gold standard. Citing it lifts the appeal letter from "physician opinion" to "guideline-aligned".'));

c.push(...FILE('appeals_drafter/sub_agents/letter_composer.py',
  'Writes the final 5-paragraph formal appeal letter.',
  'Combines counter-evidence + NCCN refs + structured arguments + standard CMS-0057-F § IV.E 14-day clause.',
  'The letter is the most important artifact in the entire system. It must read as a real physician letter — formal, cited, defensible.'));

c.push(SPACER());
c.push(H2('patient_communicator/ — Patient-facing output'));
c.push(...FILE('patient_communicator/sub_agents/action_step_writer.py',
  'Lists 3 concrete next steps for the patient.',
  'Reads the verdict, writes "what to do next" in patient language.',
  'Patients do not understand "REFER". They understand "schedule an echo on Tuesday".'));

c.push(...FILE('patient_communicator/sub_agents/empathy_layer.py',
  'Rewrites the action steps in warm, supportive tone.',
  'Uses Sonnet 4.6 with a "patient voice" prompt. Never includes PHI.',
  'A clinical decision delivered coldly causes anxiety. The empathy layer prevents that.'));

c.push(...FILE('patient_communicator/sub_agents/reading_level_tuner.py',
  'Deterministic post-processor (no LLM).',
  'Calculates Flesch-Kincaid grade level, rewrites sentences if above 6th grade.',
  'Health literacy in the US is at 6th-grade average. Anything higher fails real patients.'));

c.push(PB());

// =============================================================
// GROUP 3 — API LAYER
// =============================================================
c.push(H1('Group 3 — API Layer (FastAPI endpoints)'));
c.push(PARA('Where: backend/app/api/ · ~30 files'));
c.push(PARA('Purpose: HTTP endpoints exposed to the frontend. Each file is one logical group of endpoints.'));
c.push(SPACER());

c.push(...FILE('api/cases.py',
  'The main case lifecycle endpoints.',
  'POST /cases (create), GET /cases (list), GET /cases/{id} (detail), POST /cases/{id}/run-async (start pipeline), GET /cases/{id}/stream (SSE).',
  'The frontend\'s primary integration point. Most user actions hit this file.'));

c.push(...FILE('api/auth.py',
  'Login, logout, JWT issuance.',
  'POST /auth/login (returns JWT), POST /auth/logout, GET /auth/me (current user).',
  'Without auth, every API would be public. Authentication is the first layer of defence.'));

c.push(...FILE('api/healthz.py',
  'Liveness + readiness probes for Kubernetes/ECS.',
  'GET /healthz returns 200 if FastAPI is alive; GET /readyz returns 200 if Postgres + Bedrock are reachable.',
  'AWS load balancer uses these to route traffic. Without them, ECS would not know when to start sending requests.'));

c.push(...FILE('api/architecture.py',
  'Returns the 6-layer architecture spec for the frontend Architecture page.',
  'GET /architecture returns the layer descriptors and their components.',
  'The frontend Architecture.tsx page reads this. Lets us update layer descriptions without redeploying frontend.'));

c.push(...FILE('api/compliance.py',
  'CMS-0057-F compliance endpoints.',
  'GET /compliance/case/{id} returns the per-case compliance report. GET /compliance/org returns the org scorecard.',
  'Required for the Compliance page UI. Auditors will eventually pull these endpoints directly.'));

c.push(...FILE('api/business_value.py',
  'ROI math endpoints.',
  'GET /business-value/case/{id} returns per-case savings. GET /business-value/org returns aggregate.',
  'Powers the ROI page. Lets non-technical buyers see hard numbers, not promises.'));

c.push(...FILE('api/eval.py',
  'Agent evaluation harness endpoints.',
  'POST /eval/run executes the eval suite against a model version. Returns per-agent grader scores.',
  'When Sonnet updates to 5.0, we run /eval to verify parity before rolling out.'));

c.push(...FILE('api/llm_gateway.py',
  'LLM provider routing + cost ledger.',
  'GET /llm-gateway/usage returns per-tenant token + cost summary. POST /llm-gateway/route picks the cheapest provider.',
  'Multi-provider abstraction lives here. Lets us flip Bedrock ↔ Anthropic with one env var.'));

c.push(...FILE('api/fhir_bulk.py',
  'CMS-0057-F FHIR Bulk Data $export ingestion.',
  'POST /fhir-bulk handles NDJSON bundles, parallel queue runner.',
  'Required for hospital systems that batch-submit cases overnight. Regulatory hit (mandate fixture).'));

c.push(...FILE('api/evidence_pack.py',
  'Quarterly evidence pack download.',
  'GET /cases/{id}/evidence-pack returns a signed JSON bundle with the full case + audit trail.',
  'Auditor\'s "first ask". The pack is the legal evidence that the case was decided correctly.'));

c.push(SPACER());
c.push(PARA('Other API files (briefly):', { bold: true }));
c.push(BULLET('agents_manifest.py — exposes the 7-agent graph to the frontend Agents page'));
c.push(BULLET('demo.py — demo-fixture seed endpoints (load APPROVE / REFER / DENY)'));
c.push(BULLET('eval.py — evaluation harness for the model card'));
c.push(BULLET('finops.py — financial-ops dashboards (cost per agent, per tenant)'));
c.push(BULLET('foundry.py — the Agent Foundry manifest endpoint'));
c.push(BULLET('rate_limit_middleware.py — per-user request limits'));
c.push(BULLET('idempotency_middleware.py — prevents duplicate POST submissions'));
c.push(BULLET('cell_router_middleware.py — multi-tenant cell routing'));
c.push(BULLET('jobs.py — background job status'));
c.push(BULLET('dlq.py — dead-letter queue (failed cases that need manual triage)'));
c.push(BULLET('kiro.py — Kiro IDE integration endpoints'));
c.push(BULLET('quotas.py — per-tenant quotas (cases/month limits)'));
c.push(BULLET('metrics.py — Prometheus-style metrics for monitoring'));
c.push(BULLET('privacy.py — PHI redaction receipt endpoints'));
c.push(BULLET('prompts.py — fetch agent prompts (read-only — for the Agents page)'));
c.push(BULLET('compliance_controls.py — list of 23 CMS-0057-F sub-controls'));
c.push(PB());

// =============================================================
// GROUP 4 — MODELS, GRAPH, WORKER, LLM
// =============================================================
c.push(H1('Group 4 — Models, Graph, Worker, LLM (the supporting layers)'));

c.push(H2('app/models/ — Pydantic data shapes'));
c.push(PARA('Where: backend/app/models/ · ~15 files'));
c.push(PARA('Purpose: All Pydantic schemas for case lifecycle. Defines what data flows between layers.'));
c.push(BULLET('clinical.py — ClinicalSnapshot, Biomarker, Diagnosis, etc.'));
c.push(BULLET('policy.py — PolicyExcerpt, PolicyVersion, Citation'));
c.push(BULLET('necessity.py — AtomicCriterion, EvidenceMatch, NecessityAssessment'));
c.push(BULLET('decision.py — Verdict, Decision, Citation, RiskFlag'));
c.push(BULLET('appeal.py — AppealLetter, StructuredArgument, AppealRecommendation'));
c.push(BULLET('forecast.py — DenialForecast, AppealStrategy, DenialReason'));
c.push(BULLET('case.py — Case, CaseStatus, CaseLifecycle'));
c.push(BULLET('audit.py — AuditEvent, HashChainEntry'));
c.push(BULLET('telemetry.py — AgentRun, LLMInvocation, TraceEvent'));
c.push(SPACER());

c.push(H2('app/graph/ — LangGraph orchestration'));
c.push(PARA('Where: backend/app/graph/ · ~5 files'));
c.push(PARA('Purpose: Wires the 7 agents into one DAG.'));
c.push(...FILE('graph/state.py',
  'The global state object passed between agents.',
  'Single Pydantic class with all fields any agent might write to (snapshot, excerpts, assessment, decision, forecast, appeal).',
  'Type-safe state passing. Each agent reads what it needs, writes its output, passes the state on.'));
c.push(...FILE('graph/build.py',
  'The DAG construction code.',
  'Wires nodes (agents) and edges (conditions). Defines that decision_composer always fires after necessity_reasoner. Defines that appeals_drafter only fires on DENY or high-prob denial.',
  'This is where "if DENY then draft appeal" is encoded. Changes here = changes to the workflow.'));

c.push(SPACER());
c.push(H2('app/llm/ — Provider abstraction'));
c.push(PARA('Where: backend/app/llm/ · ~6 files'));
c.push(PARA('Purpose: Talk to LLMs without caring about the provider.'));
c.push(...FILE('llm/client.py',
  'The abstract LLMClient interface.',
  'Defines complete(), embed(), and stream() methods. Every concrete client implements these.',
  'Provider-agnostic agents. We can swap Bedrock for Anthropic for OpenRouter without changing any agent code.'));
c.push(...FILE('llm/bedrock_client.py',
  'AWS Bedrock implementation.',
  'Wraps boto3 bedrock-runtime client. Handles Sonnet 4.6 + Haiku 4.5 calls.',
  'Production LLM client. HIPAA-eligible. Region-pinned to ap-south-1 (Mumbai) for latency.'));
c.push(...FILE('llm/anthropic_client.py',
  'Direct Anthropic API implementation.',
  'Wraps the official anthropic Python SDK.',
  'Fallback when Bedrock is unavailable. Same models, different API surface.'));
c.push(...FILE('llm/openrouter_client.py',
  'OpenRouter implementation.',
  'Routes calls to OpenRouter, which proxies to multiple providers.',
  'Development-only client. Lets us test agents without burning Bedrock credits.'));

c.push(SPACER());
c.push(H2('app/workers/ — Background job processing'));
c.push(PARA('Where: backend/app/workers/ · ~3 files'));
c.push(PARA('Purpose: Process cases asynchronously after API submission.'));
c.push(...FILE('workers/case_runner.py',
  'The main worker loop.',
  'Polls the case_jobs queue. For each queued case, runs the full LangGraph pipeline. Updates status to done/dead.',
  'Long-running pipelines (60+ seconds) cannot block the HTTP request. The worker handles them in the background.'));

c.push(SPACER());
c.push(H2('app/streaming/ — SSE event bus'));
c.push(PARA('Where: backend/app/streaming/ · ~3 files'));
c.push(...FILE('streaming/publisher.py',
  'Publishes trace events to a Redis-like in-memory pubsub.',
  'When an agent fires, calls publisher.publish(case_id, event).',
  'Streams agent progress to the frontend in real-time. Without this, the user sees a spinner.'));
c.push(...FILE('streaming/sse_handler.py',
  'FastAPI SSE response handler.',
  'GET /cases/{id}/stream subscribes the browser. Each event becomes an SSE message.',
  'Bridges the publisher to the browser. Standard SSE protocol — no special client required.'));
c.push(PB());

// =============================================================
// GROUP 5 — DATABASE
// =============================================================
c.push(H1('Group 5 — Database (Postgres + RLS)'));
c.push(PARA('Where: backend/app/db/ + backend/migrations/ · ~10 files'));
c.push(...FILE('db/session.py',
  'Postgres connection pool.',
  'AsyncPG-based. Per-request connection from the pool. Auto-injects tenant_id from JWT into every query.',
  'Async DB calls do not block the event loop. RLS enforcement is automatic.'));
c.push(...FILE('migrations/0001_initial.sql',
  'Initial schema — cases, decisions, agent_runs, llm_invocations, audit_ledger, etc.',
  'Creates 12 tables, 36 indexes, 8 RLS policies, 4 hash-chain triggers.',
  'Single source of truth for the data model. New env = run this script + you have a working DB.'));
c.push(...FILE('migrations/0002_rls_policies.sql',
  'Row-level security policies for tenant isolation.',
  'Each table gets a policy: SELECT/UPDATE/DELETE only where tenant_id = current_setting(\'app.tenant_id\').',
  'Tenant A cannot see Tenant B\'s rows even if a bug routes them to the same query. Enforced at the kernel.'));
c.push(...FILE('migrations/0003_audit_ledger.sql',
  'Hash-chained audit_ledger table + verify_chain() function.',
  'INSERT trigger computes SHA-256 of (prev_hash + this_row_payload). UPDATE/DELETE rejected.',
  'Tamper-evident. Auditors verify the entire chain in <1 second with one SQL call.'));
c.push(PB());

// =============================================================
// GROUP 6-12 — Frontend, Tests, Prompts, Synthea, Specs, Docs, Ops
// =============================================================
c.push(H1('Group 6 — Frontend (React + Vite + TypeScript)'));
c.push(PARA('Where: frontend/src/ · ~75 files (20 routes + 36 components + lib)'));
c.push(PARA('20 routes = 20 pages. 36 components = reusable UI atoms. lib/ = API client + types + SSE wrapper.'));
c.push(SPACER());

c.push(H2('Key route files (frontend/src/routes/)'));
c.push(BULLET('Dashboard.tsx — landing page with KPIs + recent cases ribbon + agent health'));
c.push(BULLET('Cases.tsx — case list table with filters + 12 synthetic rows'));
c.push(BULLET('CaseDetail.tsx — full case view: snapshot + decision + citations + appeal + audit'));
c.push(BULLET('Compare.tsx — multi-payer arbitration (Novelty #1)'));
c.push(BULLET('PolicyDiff.tsx — policy diff viewer (Novelty #2)'));
c.push(BULLET('Agents.tsx — 5-agent DAG meta-view (Novelty #3)'));
c.push(BULLET('Architecture.tsx — 6-layer architecture descriptor'));
c.push(BULLET('Compliance.tsx — CMS-0057-F scorecard'));
c.push(BULLET('Industrialize.tsx — Agent Foundry manifest + model card'));
c.push(BULLET('ROI.tsx — interactive ROI calculator with member-count slider'));
c.push(SPACER());

c.push(H2('Key component files (frontend/src/components/)'));
c.push(BULLET('AppShell.tsx — top bar + sidenav + page wrapper'));
c.push(BULLET('Sidenav.tsx — left navigation with workspace / knowledge / analytics groups'));
c.push(BULLET('AgentCard.tsx — visual card showing one agent + its sub-agents + stats'));
c.push(BULLET('CitationChip.tsx — color-coded clinical/policy citation pill'));
c.push(BULLET('DecisionBadge.tsx — large APPROVE/REFER/DENY verdict display'));
c.push(BULLET('ReasoningTracePanel.tsx — live SSE-streamed agent trace timeline'));
c.push(BULLET('AppealLetterEditor.tsx — formatted letter view + edit + sign'));
c.push(BULLET('AuditLogViewer.tsx — collapsible per-event audit log'));
c.push(BULLET('PHIBanner.tsx — animated banner showing PHI redaction events'));
c.push(BULLET('TrustBadgeRow.tsx — HIPAA / FHIR R4 / USCDI v3 / Bedrock-ready chips'));
c.push(PB());

c.push(H1('Group 7 — Prompts (the agent instructions)'));
c.push(PARA('Where: backend/app/prompts/ · 22 files'));
c.push(PARA('Each agent has its system prompt as a .txt file. Stored separately from code so we can edit without redeploying.'));
c.push(SPACER());
c.push(BULLET('clinical_extractor/ — biomarker_specialist.txt, fhir_resource_validator.txt, phi_sanitizer.txt'));
c.push(BULLET('policy_retriever/ — keyword_filter.txt, llm_reranker.txt, citation_resolver.txt, q_business_retriever.txt'));
c.push(BULLET('necessity_reasoner/ — criterion_splitter.txt, evidence_matcher.txt, confidence_calibrator.txt'));
c.push(BULLET('decision_composer/ — verdict_synthesizer.txt, rationale_writer.txt, citation_linker.txt'));
c.push(BULLET('denial_forecaster/ — probability_estimator.txt, reason_predictor.txt, appeal_path_recommender.txt'));
c.push(BULLET('appeals_drafter/ — counter_evidence_finder.txt, nccn_reference_specialist.txt, letter_composer.txt'));
c.push(BULLET('patient_communicator/ — action_step_writer.txt, empathy_layer.txt'));
c.push(SPACER());

c.push(H1('Group 8 — Synthea Demo Data'));
c.push(PARA('Where: backend/app/synthea/seeds/ · 3 fixtures'));
c.push(BULLET('her2_positive_approve.json — HER2+ all met → APPROVE'));
c.push(BULLET('her2_positive_refer.json — HER2+ missing LVEF → REFER'));
c.push(BULLET('her2_negative_deny.json — HER2- mismatch → DENY (auto-appeal)'));
c.push(PARA('Synthea is the open-source synthetic patient generator. Real-feeling FHIR R4 bundles, zero real PHI.'));
c.push(SPACER());

c.push(H1('Group 9 — Tests'));
c.push(PARA('Where: backend/tests/ · ~60 files'));
c.push(BULLET('tests/agents/ — contract tests per agent (one per parent + sub)'));
c.push(BULLET('tests/integration/ — full-pipeline tests for each demo fixture'));
c.push(BULLET('tests/api/ — endpoint tests for each API file'));
c.push(BULLET('tests/db/ — RLS isolation tests + hash chain verification tests'));
c.push(SPACER());

c.push(H1('Group 10 — Operations & Docs'));
c.push(PARA('Where: backend/Makefile + ClinCase/ops/'));
c.push(BULLET('Makefile — `make demo` boots the system in 5 minutes'));
c.push(BULLET('ops/demo/ — pitch deck, demo-day checklist, anticipated Q&A, ROI calc'));
c.push(BULLET('ops/demo/standalone/ — zero-backend HTML showcase (the QR target)'));
c.push(BULLET('ops/demo/print/ — 5 printable docs (booklet, compliance, ROI fold, architecture poster, brochure)'));
c.push(BULLET('ops/demo/docs/ — these 7 documentation files'));
c.push(SPACER());

c.push(H1('Group 11 — Configs & Specs'));
c.push(BULLET('.kiro/specs/ — Kiro IDE spec files (architecture, agents, contracts)'));
c.push(BULLET('pyproject.toml — Python deps + ruff/mypy config'));
c.push(BULLET('package.json (frontend) — Node deps for Vite build'));
c.push(BULLET('tsconfig.json — TypeScript strict settings'));
c.push(BULLET('docker-compose.yml — local dev stack (Postgres + worker + API)'));
c.push(BULLET('.env.example — config template (no secrets)'));
c.push(SPACER());

c.push(H1('Group 12 — Memory of how we got here'));
c.push(BULLET('CLINCASE_PROPOSAL.md — strategic source of truth'));
c.push(BULLET('PROPOSAL.md (engineering) — full Pydantic + DDL spec'));
c.push(BULLET('CLAUDE.md — coding conventions for AI-assisted development'));
c.push(BULLET('CHANGELOG.md — version history'));
c.push(SPACER());

c.push(CALLOUT('Quick-reference: Most-asked file mapping',
  '"Where is the audit ledger?" → migrations/0003_audit_ledger.sql + framework/trace_sink.py. ' +
  '"Where do you call the LLM?" → llm/bedrock_client.py via llm/client.py interface. ' +
  '"Where does the verdict come from?" → decision_composer/sub_agents/verdict_synthesizer.py (deterministic). ' +
  '"Where is PHI removed?" → clinical_extractor/sub_agents/phi_sanitizer.py.',
  '4F46E5', 'EEF2FF'));

c.push(SPACER());
c.push(H1('That is every file group. You can defend it all.'));
c.push(PARA('When asked "show me where you do X", you have the answer. The architecture is so cleanly separated that knowing the GROUP is enough — the FILE is one Ctrl-F away.'));

const doc = new Document({
  styles: {
    default: { document: { run: { font: 'Calibri', size: 22 } } },
    paragraphStyles: [
      { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { size: 32, bold: true, font: 'Calibri', color: '0F172A' }, paragraph: { spacing: { before: 320, after: 160 }, outlineLevel: 0 } },
      { id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { size: 26, bold: true, font: 'Calibri', color: '1E293B' }, paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 1 } },
      { id: 'Heading3', name: 'Heading 3', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { size: 22, bold: true, font: 'Calibri', color: '4F46E5' }, paragraph: { spacing: { before: 200, after: 80 }, outlineLevel: 2 } },
    ],
  },
  numbering: { config: [{ reference: 'bullets', levels: [{ level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] }] },
  sections: [{
    properties: { page: { size: PAGE, margin: MARGIN } },
    headers: { default: new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [new TextRun({ text: 'ClinCase · Code Files Explained · Doc 4 of 7', size: 18, color: '94A3B8' })] })] }) },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: 'Page ', size: 18, color: '94A3B8' }), new TextRun({ children: [PageNumber.CURRENT], size: 18, color: '94A3B8' }), new TextRun({ text: ' · Team AeroFyta', size: 18, color: '94A3B8' })] })] }) },
    children: c,
  }],
});

Packer.toBuffer(doc).then(buf => { fs.writeFileSync(OUT, buf); console.log('Wrote', OUT, '(' + buf.length + ' bytes)'); });
