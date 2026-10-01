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
