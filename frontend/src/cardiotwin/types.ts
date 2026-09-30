// CardioTwin API types. Mirrors backend/app/cardiotwin (model.py `predict()` payload).

export type VesselId = "LAD" | "LCX" | "RCA";
export type TargetId = "CAD" | VesselId;
export type Band = "low" | "intermediate" | "elevated";
export type Confidence = "low" | "moderate" | "high";
export type FeatureValue = number | string | null;
export type PatientValues = Record<string, FeatureValue>;

export const VESSELS: VesselId[] = ["LAD", "LCX", "RCA"];
export const TARGETS: TargetId[] = ["CAD", "LAD", "LCX", "RCA"];

export const VESSEL_NAMES: Record<VesselId, string> = {
  LAD: "Left anterior descending",
  LCX: "Left circumflex",
  RCA: "Right coronary artery",
};

export interface TargetPrediction {
  target: TargetId;
  name: string;
  probability: number;
  model_probability: number;
  calibrated: boolean;
  calibration_method: string;
  interval_80: [number, number];
  ensemble_sd: number;
  operating_point: number;
  above_operating_point: boolean;
  band: Band;
  confidence: Confidence;
  held_out_auc: number;
  held_out_auc_ci95: [number, number];
  consistency_adjusted?: boolean;
  unadjusted_probability?: number;
}

export interface FeatureContribution {
  feature: string;
  label: string;
  group: string;
  value: number | string;
  unit: string;
  imputed: boolean;
  contribution: number;
  direction: "raises" | "lowers" | "neutral";
  share: number;
  cohort_percentile?: number;
  cohort_median?: number;
  reference_status?: "below" | "within" | "above";
  reference_range?: [number | null, number | null];
}

export interface Explanation {
  baseline_logit: number;
  sum_check_logit: number;
  features: FeatureContribution[];
}

export interface Representativeness {
  status: "representative" | "borderline" | "outside";
  distance_squared: number;
  percentile_of_training: number;
  borderline_above: number;
  outside_above: number;
  out_of_range_features: { feature: string; value: number; training_min: number; training_max: number }[];
}

export interface Warning {
  code: string;
  severity: "info" | "medium" | "high";
  message: string;
}

export interface VesselViz {
  id: VesselId;
  probability: number;
  band: Band;
  confidence: Confidence;
  halo: number;
}

export interface Prediction {
  cad: TargetPrediction;
  vessels: Record<VesselId, TargetPrediction>;
  explanations: Record<TargetId, Explanation>;
  representativeness: Representativeness;
  feature_completeness: { provided: number; total: number; fraction: number; imputed: string[] };
  warnings: Warning[];
  visualization: {
    encoding: Record<string, string>;
    vessels: Record<VesselId, VesselViz>;
    cad_probability: number;
  };
  provenance: {
    model_id: string;
    version: string;
    artifact_sha256: string;
    integrity_verified: boolean;
    dataset_sha256: string;
    trained_on: string;
    prediction_timestamp: string;
    input_sha256: string;
    scenario_id: string | null;
    leakage_audit: string;
    calibration: Record<string, string>;
  };
  safety_notice: string;
  claims: { is: string; is_not: string };
}

export interface FeatureSpec {
  name: string;
  label: string;
  group: string;
  kind: "binary" | "numeric" | "ordinal" | "categorical";
  unit: string;
  min: number | null;
  max: number | null;
  ref_low: number | null;
  ref_high: number | null;
  options: string[];
  core: boolean;
  note: string;
}

export interface FeatureCatalog {
  groups: { id: string; label: string }[];
  features: FeatureSpec[];
}

export interface Scenario {
  id: string;
  title: string;
  description: string;
  patient: PatientValues;
  source: "dataset_sample" | "synthetic";
  dataset_row?: number;
  reference_labels?: Record<string, string>;
  out_of_fold_probabilities?: Record<TargetId, number>;
  perturbation?: Record<string, number | string>;
}

export interface CounterfactualResult {
  changes: { feature: string; label: string; before: number | string; after: number | string; unit: string; was_imputed: boolean }[];
  targets: Record<TargetId, { before: number; after: number; delta: number; within_model_uncertainty: boolean; baseline_ensemble_sd: number }>;
  baseline: Prediction;
  perturbed: Prediction;
  label: string;
}

export interface Overview {
  name: string;
  tagline: string;
  cardiotwin_version: string;
  model: { model_id: string; version: string; artifact_sha256: string; integrity_verified: boolean; dataset_sha256: string; trained_on: string };
  headline_metrics: Record<TargetId, { roc_auc: number; roc_auc_ci95: [number, number]; pr_auc: number; brier: number; ece: number; prevalence: number }>;
  safety_notice: string;
}

// The evaluation report is large and read-only; the page narrows fields it needs.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type EvaluationReport = Record<string, any>;
