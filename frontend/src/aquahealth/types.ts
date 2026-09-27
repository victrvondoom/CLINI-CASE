// AquaHealth types — mirrors backend/app/aquahealth/models.py.
// Kept in its own folder (like src/oncotwin/) so nothing in the existing
// ClinCase type surface changes.

/** Four-state answer. `unknown`/`not_available` are never treated as evidence. */
export type Presence = "observed" | "not_observed" | "unknown" | "not_available";

export type EcosystemStatus =
  | "healthy_signal"
  | "watch"
  | "potential_stress"
  | "critical_signal"
  | "insufficient_data";

export type Confidence = "low" | "medium" | "high";
export type DataQuality = "good" | "limited" | "insufficient";

export type DataSource =
  | "citizen_observation"
  | "sensor"
  | "imported_dataset"
  | "demonstration_data";

export type VerificationState =
  | "unverified"
  | "ai_assisted"
  | "human_reviewed"
  | "verified";

export type ReviewDecision =
  | "accepted"
  | "modified"
  | "rejected"
  | "more_info_requested";

export type ReviewStatus = "pending_review" | "in_review" | "completed";

export type Clarity = "clear" | "slightly_cloudy" | "cloudy" | "opaque" | "unknown";

export type WaterbodyKind =
  | "stream"
  | "river"
  | "lake"
  | "pond"
  | "canal"
  | "wetland"
  | "other";

export interface GeoPoint {
  latitude: number;
  longitude: number;
}

export interface Measurements {
  ph: number | null;
  water_temperature_c: number | null;
  turbidity_ntu: number | null;
  dissolved_oxygen_mgl: number | null;
}

export interface WaterAppearance {
  floating_waste: Presence;
  foam: Presence;
  algae: Presence;
  oily_film: Presence;
  unusual_colour: Presence;
  unusual_odour: Presence;
  colour_note: string | null;
  clarity: Clarity;
}

export interface Biodiversity {
  fish: Presence;
  birds: Presence;
  insects: Presence;
  aquatic_plants: Presence;
  macroinvertebrates: Presence;
  dead_organisms: Presence;
  unusual_organisms: Presence;
  note: string | null;
}

export interface EnvironmentalContextFields {
  recent_rainfall: Presence;
  flooding: Presence;
  drought: Presence;
  construction: Presence;
  waste_accumulation: Presence;
  suspected_discharge: Presence;
  unusual_activity: Presence;
  note: string | null;
}

export interface PhotoAILabel {
  label: string;
  confidence: Confidence;
  note: string | null;
}

export interface PhotoEvidence {
  id: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  caption: string | null;
  uri: string | null;
  ai_labels: PhotoAILabel[];
  ai_disclaimer: string;
  human_confirmed: boolean | null;
  created_at: string;
}

/** One traceable observation supporting a finding. */
export interface Evidence {
  field: string;
  label: string;
  value: string;
  interpretation: string;
}

/** The explainability contract: finding + evidence + confidence + next step. */
export interface AgentFinding {
  agent: string;
  finding: string;
  evidence: Evidence[];
  confidence: Confidence;
  data_quality: DataQuality;
  uncertainty: string | null;
  recommended_next_step: string | null;
}

export interface EarlyWarning {
  active: boolean;
  headline: string;
  reason: string;
  confidence: Confidence;
  recommended_next_step: string;
  notice: string;
}

export interface EnvironmentalAssessment {
  id: string;
  observation_id: string;
  run_id: string;
  created_at: string;
  status: EcosystemStatus;
  status_reason: string;
  confidence: Confidence;
  data_quality: DataQuality;
  completeness: number;
  findings: AgentFinding[];
  one_health_note: string | null;
  early_warning: EarlyWarning | null;
  human_verification: "required" | "reviewed";
  disclaimer: string;
}

export interface HumanReview {
  id: string;
  observation_id: string;
  decision: ReviewDecision;
  reviewer_id: string;
  reviewer_label: string;
  comment: string | null;
  corrected_status: EcosystemStatus | null;
  rejected_findings: string[];
  reviewed_at: string;
}

export interface Observation {
  id: string;
  reference: string;
  organization_id: string;
  waterbody_id: string;
  waterbody_name: string;
  location: GeoPoint | null;
  locality: string | null;
  observed_at: string;
  created_at: string;
  observer_id: string | null;
  observer_label: string | null;
  observer_note: string | null;
  appearance: WaterAppearance;
  biodiversity: Biodiversity;
  context: EnvironmentalContextFields;
  measurements: Measurements;
  photos: PhotoEvidence[];
  source: DataSource;
  is_demo: boolean;
  verification: VerificationState;
  review_status: ReviewStatus;
  assessment: EnvironmentalAssessment | null;
  review: HumanReview | null;
  case_type: "ENVIRONMENTAL_OBSERVATION";
}

export interface ObservationSummary {
  id: string;
  reference: string;
  waterbody_id: string;
  waterbody_name: string;
  location: GeoPoint | null;
  observed_at: string;
  status: EcosystemStatus;
  confidence: Confidence;
  data_quality: DataQuality;
  source: DataSource;
  verification: VerificationState;
  review_status: ReviewStatus;
  is_demo: boolean;
  headline: string | null;
}

export interface DashboardOverview {
  waterbody_count: number;
  observation_count: number;
  awaiting_review: number;
  demo_observation_count: number;
  status_distribution: Record<string, number>;
  confidence_distribution: Record<string, number>;
  data_quality_distribution: Record<string, number>;
  source_distribution: Record<string, number>;
  recent: ObservationSummary[];
  active_warnings: ObservationSummary[];
}

export interface Badge {
  code: string;
  label: string;
  description: string;
  earned: boolean;
  progress: number;
  target: number;
}

export interface CommunityStats {
  observations_contributed: number;
  waterbodies_explored: number;
  reviewed_contributions: number;
  community_observers: number;
  community_observations: number;
  badges: Badge[];
  note: string;
}

export interface WaterbodyRow {
  id: string;
  name: string;
  kind: WaterbodyKind;
  locality: string | null;
  latitude: number | null;
  longitude: number | null;
  is_demo: boolean;
  observation_count: number;
  latest_status: EcosystemStatus | null;
  latest_observed_at: string | null;
}

export interface MapPoint {
  observation_id: string;
  reference: string;
  waterbody_id: string;
  waterbody_name: string;
  latitude: number;
  longitude: number;
  observed_at: string;
  status: EcosystemStatus;
  confidence: Confidence;
  review_status: ReviewStatus;
  verification: VerificationState;
  source: DataSource;
  is_demo: boolean;
  summary: string | null;
}

export interface StatusCatalogEntry {
  status: EcosystemStatus;
  label: string;
  meaning: string;
}

export interface MapView {
  points: MapPoint[];
  waterbodies: Array<{
    id: string;
    name: string;
    kind: WaterbodyKind;
    locality: string | null;
    latitude: number | null;
    longitude: number | null;
    is_demo: boolean;
  }>;
  statuses: StatusCatalogEntry[];
}

export interface TrendPoint {
  date: string;
  observations: number;
  adverse_signals: number;
  biodiversity_positives: number;
  mean_dissolved_oxygen_mgl: number | null;
  mean_turbidity_ntu: number | null;
}

export interface TrendsResponse {
  sufficient: boolean;
  message: string | null;
  window_days: number;
  observation_count: number;
  series: TrendPoint[];
  status_history: Array<{
    date: string;
    reference: string;
    status: EcosystemStatus;
    waterbody_name: string;
  }>;
  note?: string;
}

export interface OneHealthLayer {
  layer: "ecosystem" | "animal" | "community";
  label: string;
  signal_count: number;
  signals: Record<string, number>;
  description: string;
}

export interface OneHealthPathway {
  observation_id: string;
  reference: string;
  waterbody_name: string;
  observed_at: string;
  finding: string;
  confidence: Confidence;
  evidence: Evidence[];
  uncertainty: string | null;
  status: EcosystemStatus;
}

export interface OneHealthView {
  chain: OneHealthLayer[];
  pathways: OneHealthPathway[];
  disclaimer: string;
}

export interface ReviewQueue {
  total: number;
  observations: ObservationSummary[];
  decisions: Array<{ value: ReviewDecision; label: string }>;
}

export interface FormSchema {
  presence_options: Array<{ value: Presence; label: string }>;
  guidance: string;
  sections: Array<{
    key: "appearance" | "biodiversity" | "context";
    label: string;
    fields: Array<{ code: string; label: string }>;
  }>;
  clarity_options: Array<{ value: Clarity; label: string }>;
  measurements: Array<{
    code: keyof Measurements;
    label: string;
    unit: string;
    min: number;
    max: number;
  }>;
  measurement_note: string;
  waterbody_kinds: WaterbodyKind[];
}

export interface AquaMeta {
  module: string;
  version: string;
  parent_product: string;
  summary: string;
  case_type: string;
  disclaimers: {
    status: string;
    ai: string;
    interoperability: string;
  };
  statuses: StatusCatalogEntry[];
  presence_values: Array<{ value: Presence; informative: boolean }>;
  data_sources: DataSource[];
  verification_states: VerificationState[];
}

export interface AgentManifest {
  module: string;
  deterministic: boolean;
  n_agents: number;
  note: string;
  agents: Array<{
    name: string;
    role: string;
    description: string;
    uses_llm: boolean;
  }>;
}

/** Request body for creating an observation. */
export interface ObservationCreate {
  waterbody_id?: string | null;
  waterbody_name?: string | null;
  waterbody_kind?: WaterbodyKind;
  locality?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  observed_at?: string | null;
  observer_note?: string | null;
  appearance?: Partial<WaterAppearance>;
  biodiversity?: Partial<Biodiversity>;
  context?: Partial<EnvironmentalContextFields>;
  measurements?: Partial<Measurements>;
  photos?: Array<Partial<PhotoEvidence>>;
}
