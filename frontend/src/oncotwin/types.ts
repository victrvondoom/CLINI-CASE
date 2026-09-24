// Types for the /api/v1/oncotwin payloads (the subset the UI consumes).

export type Tier = "NORMAL" | "WATCH" | "EARLY WARNING" | "HIGH PRIORITY" | "IN ACUTE CARE";

export interface Profile {
  patient_id: string;
  label: string;
  age: number;
  sex: string;
  cancer: string;
  icd10: string;
  stage: string;
  biomarkers: Record<string, string>;
  regimen_code: string;
  payer_id: string;
  archetype: string;
  narrative: string;
  diabetic: boolean;
  synthetic: boolean;
  ecog: number;
}

export interface PatientSummary {
  patient: Profile;
  live_day: number;
  n_days: number;
  tier: Tier;
  risk: number;
  risk_p10: number;
  risk_p90: number;
  pattern: string;
  in_acute_care: boolean;
  risk_series: { day: number; risk: number; tier: Tier }[];
  open_alerts: number;
}

export interface Contributor {
  group: string;
  label: string;
  logit: number;
  direction: string;
  features?: { feature: string; logit: number }[];
}

export interface ChangedSignal {
  signal: string;
  label: string;
  value: number;
  unit: string;
  day: number;
  baseline_median: number;
  baseline_low: number;
  baseline_high: number;
  z_adverse: number;
  slope3_per_day: number;
  text: string;
  observation_id: string | null;
}

export interface RuleFired {
  rule: string;
  tier: string;
  text: string;
  basis: string;
}

export interface Evidence {
  tier: Tier;
  headline: string;
  what_changed: ChangedSignal[];
  why: string;
  compared_with: string;
  period: { start_day: number | null; days: number; text: string; risk_at_start?: number; risk_now?: number };
  contributors: Contributor[];
  review: string[];
  evidence: { observation_id: string; signal: string; day: number; value: number; unit: string }[];
  rules_fired: RuleFired[];
  references: { id: string; text: string; source: string }[];
  decision_support_notice: string;
}

export interface Confidence {
  score: number;
  label: "high" | "moderate" | "low";
  components: {
    input_completeness_7d: number;
    input_freshness: number;
    baseline_adequacy: number;
    model_agreement: number;
    bootstrap_interval_width: number;
  };
  stale_signals: string[];
  formula: string;
}

export interface ModelVersion {
  model_id: string;
  version: string;
  artifact_sha256: string;
  integrity_verified: boolean;
  outcome_id: string;
  horizon_days: number;
}

export interface Prediction {
  outcome_id: string;
  outcome: string;
  horizon_days: number;
  risk: number;
  risk_p10: number;
  risk_p90: number;
  tier: Tier;
  previous_tier: Tier;
  probability_tier: Tier;
  rule_tier: Tier;
  escalated: boolean;
  rules_fired: RuleFired[];
  thresholds: { watch: number; early_warning: number; high_priority: number };
  contributors: Contributor[];
  confidence: Confidence;
  logit_check: { intercept: number; sum_contributions: number; logit: number; probability_from_logit: number };
  model: ModelVersion;
}

export interface BaselineDisplay {
  signal: string;
  label: string;
  unit: string;
  median: number;
  low: number;
  high: number;
  n_days: number;
  established: boolean;
  adverse_direction: "up" | "down";
  population_reference: { low: number; high: number; note: string } | null;
}

export interface SignalQuality {
  completeness_7d: number;
  last_day: number | null;
  last_effective: string | null;
  hours_since_last: number | null;
  fresh: boolean;
  freshness: number;
}

export interface SignalPanel {
  label: string;
  unit: string;
  code_system: string;
  code: string;
  device: string;
  adverse_direction: "up" | "down";
  category: string;
  days: number[];
  values: (number | null)[];
  baseline: BaselineDisplay | null;
  quality: SignalQuality | null;
  forecast: { days: number[]; median: number[]; p10: number[]; p90: number[] } | null;
}

export interface AncProjection {
  available: boolean;
  nadir_median?: number;
  nadir_p10?: number;
  nadir_p90?: number;
  nadir_day_median?: number;
  p_below_0_5_within_48h?: number;
  trajectory_median?: number[];
  trajectory_p10?: number[];
  trajectory_p90?: number[];
  trajectory_start_day?: number;
  reason?: string;
}

export interface AncPanel {
  label: string;
  unit: string;
  labs: { day: number; value: number; observation_id: string }[];
  twin_estimate: { day: number; mean: number; p10: number; p90: number }[];
  projection: AncProjection;
}

export interface TwinCard {
  patient: { id: string; label: string; age: number; sex: string; cancer: string; stage: string;
             biomarkers: Record<string, string>; payer_id: string; synthetic: boolean; archetype: string };
  current_state: { tier: Tier; care_setting: string; dominant_latent_load: string; dominant_latent_value: number;
                   as_of_day: number; as_of_time: string };
  baseline: { window: { start_day: number; end_day: number }; adequacy: number; kind: string };
  trajectory: { pattern: string; signals_adverse: string[]; signals_rising: string[] };
  risk: { probability: number; p10: number; p90: number; horizon_days: number; outcome_id: string;
          confidence: string; confidence_score: number };
  treatment: {
    regimen: string; regimen_name: string; cycle: number; day_of_cycle: number | null; next_dose_day: number | null;
    gcsf_this_cycle: boolean; nadir_window: boolean; anc_estimate: { mean: number; p10: number; p90: number; source: string };
  };
  symptoms: { symptom_score: number | null; symptom_baseline: number; symptom_change_3d: number | null; recovery_index: number | null };
  wearables: { model_signals_fresh: number; model_signals_total: number; completeness_7d: number; active_quality_flags: number };
  predicted_changes: { risk_day7_median: number; event_probability_7d: number; anc_nadir_projection: number | null; source: string } | null;
  recommended_review: string[];
}

export interface QualityFlag {
  kind: string;
  signal: string;
  days: number[];
  message: string;
  severity: string;
  observation_ids: string[];
}

export interface HistorySnap {
  day: number;
  risk: number;
  risk_p10: number;
  risk_p90: number;
  tier: Tier;
  raw_tier: Tier;
  in_acute_care: boolean;
}

export interface KeyMoment {
  day: number;
  kind: string;
  text: string;
}

export interface AlertSummary {
  id: string;
  patient_id: string;
  patient_label: string;
  as_of_day: number;
  twin_time: string;
  created_at: string;
  tier: Tier;
  previous_tier: Tier;
  risk: number;
  risk_p10: number;
  risk_p90: number;
  headline: string;
  status: "open" | "accepted" | "dismissed" | "investigating";
  n_actions: number;
  handoff_case_id: string | null;
}

export interface Handoff {
  case_id: string;
  created_at: string;
  created_by: string;
  requested_treatment: { name: string; hcpcs_code?: string; dose?: string; intent?: string };
  requested_treatment_rationale: string;
  policy_preview: { policy_id: string; policy_title: string; section_heading: string; page_number: number | null; excerpt: string }[];
  policy_preview_note: string;
  package_sha256: string;
  bundle_resource_count: number;
  physician_note_draft: string;
  next_step: string;
}

export interface AlertAction {
  action: string;
  note: string | null;
  user_email: string;
  role: string;
  at: string;
  ledger_entry_id: string;
}

export interface AlertDetail extends AlertSummary {
  evidence: Evidence;
  actions: AlertAction[];
  handoff: Handoff | null;
  provenance: { input_sha256: string; n_inputs: number };
}

export interface LatentPoint {
  day: number;
  infection: number;
  dehydration: number;
  fatigue: number;
}

export interface Dashboard {
  synthetic_notice: string;
  patient: Profile;
  live_day: number;
  as_of_day: number;
  n_days: number;
  is_replay: boolean;
  card: TwinCard;
  state: {
    as_of_time: string;
    baseline_state: { window: { start_day: number; end_day: number }; kind: string; adequacy: number; method: string;
                      signals: Record<string, BaselineDisplay> };
    cancer_treatment_state: {
      diagnosis: { text: string; icd10: string; stage: string };
      biomarkers: Record<string, string>;
      regimen: { code: string; name: string; cycle_days: number; myelosuppression_tier: string; tier_basis: string };
      cycle_number: number;
      day_of_cycle: number | null;
      last_dose_day: number | null;
      next_planned_dose_day: number | null;
      gcsf_this_cycle: boolean;
      in_expected_nadir_window: boolean;
      neutrophil: {
        twin_estimate_today: { mean: number; p10: number; p90: number; source: string };
        last_lab: { value: number; day: number } | null;
        fitted_sensitivity: { relative_sensitivity_mean: number; relative_sensitivity_p10: number; relative_sensitivity_p90: number } | null;
        baseline_anc: { value: number; source: string };
        projection: AncProjection;
      };
      performance_status_ecog: number;
    };
    physiological_state: {
      latent_loads: Record<string, { label: string; value: number; event_threshold: number | null }>;
      observation_model_fit_r2: number | null;
      method: string;
    };
    symptom_recovery_state: TwinCard["symptoms"];
    adherence_state: { supportive_medication_7d: number; scheduled_doses_7d: number; missed_doses_7d: number; applicable: boolean };
    care_setting: string;
    data_quality: { flags: QualityFlag[]; signals: Record<string, SignalQuality> };
  };
  trajectory: {
    pattern: string;
    signals_adverse: string[];
    signals_rising: string[];
    n_concordant: number;
    anomaly_score: number;
    sudden_changes: string[];
    drift_alarms: string[];
    analysed_as: string;
    signals: Record<string, { label: string; z_adverse: number | null; slope3_per_day: number | null; persistence_days: number;
                              cusum_alarm: boolean; sudden_jump: boolean; status: string; z_history: (number | null)[] }>;
  };
  prediction: Prediction;
  evidence: Evidence;
  signals: Record<string, SignalPanel | AncPanel>;
  risk_timeline: HistorySnap[];
  risk_forecast: { days: number[]; median: number[]; p10: number[]; p90: number[]; event_probability_cumulative: number[] } | null;
  latent_timeline: LatentPoint[];
  latent_forecast: { days: number[]; infection: number[]; dehydration: number[]; fatigue: number[] } | null;
  key_moments: KeyMoment[];
  alerts: AlertSummary[];
  provenance: { input_sha256: string; n_inputs: number; feature_window_days: [number, number]; model: ModelVersion; oncotwin_version: string };
  injections: { kind: string; label: string; effective_from_day: number; past_data_unchanged: boolean }[];
}

export interface Scenario {
  key: string;
  label: string;
  description: string;
  assumptions: string[];
  days: number[];
  risk: { median: number[]; p10: number[]; p90: number[] };
  event_probability_cumulative: number[];
  event_probability_7d: number;
  risk_day7_median: number;
  anc: { median: number[]; p10: number[]; p90: number[] };
  latent: Record<string, number[]>;
  delta_vs_current: { event_probability_7d: number; risk_day7_median: number };
  doses_in_horizon: Record<string, number>;
  gcsf_in_horizon: number[];
}

export interface Simulation {
  as_of_day: number;
  horizon_days: number;
  n_runs: number;
  disclaimer: string;
  method: string;
  initial_state: Record<string, number>;
  scenarios: Record<string, Scenario>;
}

export interface TimelineItem {
  day: number;
  time: string;
  lane: string;
  title: string;
  detail: Record<string, unknown> | null;
  severity: "info" | "warning" | "high";
  fhir: { resourceType: string; id: string } | null;
  source: string;
}

export interface LedgerEntry {
  id: string;
  seq: number;
  kind: string;
  patient_id: string | null;
  actor: string;
  created_at: string;
  payload: Record<string, unknown>;
  prev_hash: string;
  hash: string;
  persisted?: boolean;
}

export interface WhyResponse {
  alert: AlertDetail;
  answer: string;
  thresholds_crossed: string[];
  rules_fired: string[];
  history_window: HistorySnap[];
  ledger_entries: LedgerEntry[];
  chain_verification: { valid: boolean; entries: number; tip?: string; broken_at_seq?: number };
}

export interface EventLevel {
  events: number;
  events_detected: number;
  sensitivity: number | null;
  median_lead_time_days: number | null;
  lead_time_days_iqr: [number, number] | null;
  false_alert_onsets_per_100_patient_days: number;
  patient_days: number;
}

export interface ModelCard {
  model_id: string;
  version: string;
  artifact_sha256: string;
  integrity_verified: boolean;
  algorithm: string;
  outcome: { id: string; name: string; definition: string; horizon_days: number; label_rule: string; measure_basis: string };
  features: { name: string; coef_standardised: number }[];
  metrics: {
    data: string;
    day_level: Record<string, number>;
    event_level: Record<string, EventLevel>;
    calibration_test: { mean_predicted: number; observed_rate: number; n: number }[];
  };
  comparators: Record<string, { definition: string; test_auroc?: number; early_warning_or_higher?: EventLevel } & Partial<EventLevel>>;
  training: Record<string, string | number>;
  limitations: string[];
}

export interface Overview {
  tagline: string;
  outcome: ModelCard["outcome"];
  model: ModelVersion;
  headline_metrics: { data: string; day_level: Record<string, number>; event_level: Record<string, EventLevel>;
                      comparators: ModelCard["comparators"] };
  open_alerts: number;
  ledger: { valid: boolean; entries: number };
  decision_support_notice: string;
}
