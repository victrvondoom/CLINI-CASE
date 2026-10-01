// TypeScript mirror of backend Pydantic models.
// Source of truth: backend/app/models/*.py — keep in sync.

// --- ClinicalSnapshot ---
export interface Diagnosis {
  icd10_code: string;
  description: string;
  stage: string | null;
  onset_date: string | null;
  source_resource_id: string;
}

export interface PriorTherapy {
  therapy_name: string;
  start_date: string | null;
  end_date: string | null;
  response: string | null;
  source_resource_id: string | null;
}

export interface Biomarker {
  name: string;
  value: string;
  test_date: string | null;
  source_resource_id: string | null;
}

export interface Comorbidity {
  icd10_code: string;
  description: string;
}

export interface RequestedTreatment {
  name: string;
  hcpcs_code: string | null;
  j_code: string | null;
  dose: string | null;
  frequency: string | null;
  intent: string | null;
}

export interface ClinicalSnapshot {
  patient_age: number | null;
  patient_sex: string | null;
  primary_diagnosis: Diagnosis;
  additional_diagnoses: Diagnosis[];
  prior_therapies: PriorTherapy[];
  biomarkers: Biomarker[];
  comorbidities: Comorbidity[];
  performance_status: string | null;
  requested_treatment: RequestedTreatment;
  free_text_summary: string;
}

// --- PolicyExcerpt ---
export interface PolicyExcerpt {
  payer_id: string;
  policy_id: string;
  policy_title: string;
  section_heading: string;
  excerpt_text: string;
  source_url: string | null;
  page_number: number | null;
  relevance_score: number;
}

// --- NecessityAssessment ---
export type CriterionStatus = "MET" | "NOT_MET" | "AMBIGUOUS";
export type CriterionType = "inclusion" | "exclusion";

export interface CriterionAssessment {
  criterion_text: string;
  criterion_type: CriterionType;
  policy_excerpt_index: number;
  status: CriterionStatus;
  supporting_evidence: string[];
  missing_evidence: string | null;
  confidence: number;
  rationale: string;
}

export interface NecessityAssessment {
  criteria: CriterionAssessment[];
  overall_confidence: number;
  summary: string;
}

// --- Decision ---
export type Verdict = "APPROVE" | "DENY" | "REFER";

// ClinCase citation kinds (round 14 expansion).
// Backward compatible: existing data with kind="clinical" or "policy" still validates.
// New kinds align with how real payer denial / approval letters cite authority:
//   compendium  — NCCN, AHFS, Lexi-Drugs, Clinical Pharmacology, DrugDex
//   fda_label   — FDA-approved drug label (Highlights of Prescribing Information)
//   guideline   — ASCO, ESMO, ASH, ACS, NCCN-Guidelines (vs NCCN compendium)
export type CitationKind = "clinical" | "policy" | "compendium" | "fda_label" | "guideline";

export interface Citation {
  kind: CitationKind;
  text: string;
  pointer: string;
}

export interface Decision {
  verdict: Verdict;
  rationale: string;
  citations: Citation[];
  confidence: number;
  risk_flags: string[];
}

// --- AppealDraft ---
export interface AppealArgument {
  contested_criterion: string;
  payer_position: string;
  counter_position: string;
  cited_evidence: string[];
  cited_policy_text: string;
  cited_guideline: string;
}

export interface AppealDraft {
  patient_initials: string;
  payer_id: string;
  requested_treatment: string;
  denial_date: string;
  appeal_body: string;
  structured_arguments: AppealArgument[];
  attachments_referenced: string[];
  requested_action: string;
}

// --- DenialForecast (6th agent: Denial Forecaster) ---
export interface DenialReason {
  rank: number;
  text: string;
  policy_section_pointer: string;
  likelihood: number;
}

export type AppealAngle =
  | "biomarker_evidence"
  | "guideline_alignment"
  | "prior_therapy_failure"
  | "step_therapy_completed"
  | "medical_necessity_letter"
  | "documentation_gap_resolved";

export interface AppealStrategy {
  primary_angle: AppealAngle;
  rationale: string;
  expected_overturn_probability: number;
}

export interface DenialForecast {
  denial_probability: number;
  confidence: number;
  top_reasons: DenialReason[];
  appeal_strategy: AppealStrategy | null;
  summary: string;
}

// --- PatientCommunication (7th agent: Patient Communicator) ---
export interface PatientNextStep {
  step_number: number;
  text: string;
  timing: "today" | "this_week" | "this_month" | "after_decision";
}

export interface PatientCommunication {
  headline: string;
  body: string;
  next_steps: PatientNextStep[];
  tone: "reassuring" | "neutral" | "urgent";
  reading_level_grade: number;
  contains_phi: boolean;
}

// --- API responses ---
export interface DemoFixture {
  name: string;
  label: string;
  description: string;
  patient_initials: string;
  physician_note: string;
  requested_treatment: { name: string; j_code: string };
  payer_id: string;
  expected_verdict: Verdict;
}

export interface RunResult {
  case_id: string;
  clinical_snapshot: ClinicalSnapshot | null;
  policy_excerpts: PolicyExcerpt[];
  necessity_assessment: NecessityAssessment | null;
  decision: Decision | null;
  denial_forecast: DenialForecast | null;
  appeal_draft: AppealDraft | null;
  patient_communication: PatientCommunication | null;
  paused_for_review?: boolean;
  pause_reason?: string | null;
}

export interface AgentRun {
  id: number;
  agent_name: string;
  started_at: string;
  finished_at: string | null;
  latency_ms: number | null;
  model_id: string | null;
  input_tokens: number | null;
  output_tokens: number | null;
  error_text: string | null;
}

// --- SSE event types (from app/streaming.py) ---
export interface AgentStartedEvent {
  type: "agent_started";
  agent_name: string;
  ts: number;
}

export interface AgentFinishedEvent {
  type: "agent_finished";
  agent_name: string;
  output: Record<string, unknown>;
  latency_ms: number;
  model_id: string | null;
  ts: number;
}

export interface AgentErrorEvent {
  type: "agent_error";
  agent_name: string;
  error: string;
  ts: number;
}

export interface DoneEvent {
  type: "done";
  case_id?: string;
  ts: number;
}

export type TraceEvent =
  | AgentStartedEvent
  | AgentFinishedEvent
  | AgentErrorEvent
  | DoneEvent;

// ---- Cohort analytics (GET /cohorts) -------------------------------------------------------
export interface CohortInsight {
  id: string;
  accent: "amber" | "blue" | "violet" | "green";
  metric: string;
  metric_label: string;
  title: string;
  detail: string;
  link: { label: string; to: string };
}

export interface CohortReport {
  window_days: number;
  generated_at: string;
  total_cases: number;
  decided_cases: number;
  pending_cases: number;
  verdicts: { APPROVE: number; DENY: number; REFER: number };
  approval_by_payer: { payer: string; decided: number; approve: number; deny: number; refer: number; rate: number | null }[];
  time_to_decision: {
    buckets: { bucket: string; count: number }[];
    timed_cases: number;
    median_seconds: number | null;
    p90_seconds: number | null;
  };
  verdict_by_treatment: { treatment: string; approve: number; deny: number; refer: number }[];
  status_counts: Record<string, number>;
  insights: CohortInsight[];
  min_group_size: number;
}

// ---- Reviewer queue (GET /reviewer/queue) --------------------------------------------------
export interface ReviewQueueItem {
  case_id: string;
  patient: string;
  treatment: string;
  payer: "aetna" | "uhc" | "bcbs" | "anthem" | string;
  status: string;
  priority: "high" | "medium" | "low";
  reason: string;
  missing_evidence: string | null;
  unresolved_criteria: number;
  confidence: number | null;
  age_minutes: number;
  referred_at: string;
}

export interface ReviewQueueReport {
  generated_at: string;
  total: number;
  priority_rule: string;
  counts: { high: number; medium: number; low: number };
  items: ReviewQueueItem[];
}

// ---- Policy catalog (GET /policy-catalog[/{id}]) -------------------------------------------
export interface PolicyCatalogItem {
  payer_id: string;
  policy_id: string;
  title: string;
  treatment_keywords: string[];
  source_url: string | null;
  section_count: number;
  word_count: number;
  recent_change_at: string | null;
  has_recent_change: boolean;
}

export interface PolicyCatalog {
  n: number;
  payers: string[];
  n_with_recent_change: number;
  snapshot: { taken_at: string; version: string };
  policies: PolicyCatalogItem[];
}

export interface PolicyChange {
  payer: string;
  treatment: string;
  policy_id: string;
  version_old: string;
  version_new: string;
  changed_at: string;
  summary: string;
  diff: { action: "added" | "removed" | "modified"; section: string; text: string }[];
  in_flight_pas_affected?: number;
}

export interface PolicyDetail extends PolicyCatalogItem {
  sections: { heading: string | null; page_number: number | null; word_count: number; text: string }[];
  diffs: PolicyChange[];
  related: { payer_id: string; policy_id: string; title: string }[];
  snapshot: { taken_at: string; version: string; note: string };
  open_cases: { case_id: string; patient: string; treatment: string; status: string; created_at: string }[];
  open_cases_available: boolean;
}

// ---- Multi-payer comparison (GET /cases/{id}/compare) --------------------------------------
export interface PayerColumn {
  payer_id: "aetna" | "uhc" | "bcbs" | "anthem" | string;
  name: string;
  is_this_case: boolean;
  policy: { policy_id: string; title: string; source_url: string | null; section_count: number; has_recent_change: boolean } | null;
  case: { case_id: string; status: string; created_at: string } | null;
  decision: { verdict: "APPROVE" | "DENY" | "REFER"; confidence: number; rationale: string | null; decided_at: string } | null;
  state: "decided" | "in_progress" | "not_started" | "no_policy";
  can_create: boolean;
}

export interface CaseComparison {
  case_id: string;
  treatment: string;
  j_code: string | null;
  patient: string;
  payer_id: string;
  payers: PayerColumn[];
  recommendation: { primary: string | null; fallback: string | null; summary: string };
  method: string;
}

/** GET /cases/{id}/twin — derived, auditable view of one case's whole life. */
export interface TwinEvidence {
  evidence_id: string;
  kind: string;
  pointer: string;
  text: string | null;
  fhir_resource_type: string | null;
  resolved: boolean | null;
  policy_version: string | null;
  section: string | null;
  first_seen_agent: string | null;
  model_id: string | null;
  recorded_at: string | null;
}
export interface TwinStage {
  stage: string;
  actor: "agent" | "human" | "system";
  offset_ms: number | null;
  duration_ms: number | null;
  status: "ok" | "error" | "running" | "waiting";
}
export interface TwinRun {
  run_id: string | null;
  attempt_no: number;
  trigger: "initial" | "rerun" | "resume" | "legacy";
  parent_run_id: string | null;
  status: "queued" | "running" | "paused" | "completed" | "failed" | "cancelled" | null;
  trace_id: string | null;
  job_attempts: number[];
  agent_rows: number;
  agent_errors: number;
  verdict: string | null;
  human_actions: number;
}
export interface CaseTwin {
  case_intelligence_id: string;
  case_id: string;
  identity: { case_intelligence_id: string; stored: boolean; matches_derived: boolean };
  runs: TwinRun[];
  headline_run_id: string | null;
  patient_fhir: { resource_counts: Record<string, number> };
  authorization: { status: string; payer_id: string; treatment: string };
  policy: { criteria_total: number; criteria_met: number; criteria_ambiguous: number; criteria_not_met: number };
  evidence: TwinEvidence[];
  agent_history: { agent: string; latency_ms: number | null; model_id: string | null; error: string | null }[];
  human_decisions: { reviewer_id: string; action: string; at: string | null }[];
  infrastructure_events: { event: string; at?: string | null; worker?: string | null; attempts?: number; error?: string | null }[];
  trace: {
    stages: TwinStage[];
    totals: { agent_ms: number; human_wait_ms: number | null; input_tokens: number; output_tokens: number; estimated_cost_usd: number };
  };
  outcome: { status: string; final: boolean; last_verdict: string | null; appeal_drafted: boolean };
  integrity: { dangling_citations: string[]; citations_total: number; all_clinical_citations_resolve: boolean };
  twin_sha256: string;
  generated_at: string;
}
