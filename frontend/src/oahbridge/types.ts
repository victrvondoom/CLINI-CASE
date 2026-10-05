// OAH-Bridge API types — mirror backend/app/oahbridge/service.py and weather.py.
// Every scenario is synthetic demonstration data; responses say so (`synthetic: true`).

export type EpistemicStatus = "observed" | "inferred" | "confirmed";

export interface LonLat {
  longitude: number;
  latitude: number;
}

// ---------------------------------------------------------------------------
// Scenario catalogue (GET /scenarios) — globe pins and exposure zones
// ---------------------------------------------------------------------------

export interface ScenarioSite {
  id: string;
  name: string;
  centroid: LonLat;
  /** Closed GeoJSON ring, [longitude, latitude] pairs; first point repeats last. */
  polygon: [number, number][];
  buffer_meters: number;
  estimated_exposed_population: number;
  recreational_use_category: string;
}

export interface CitizenPoint {
  id: string;
  longitude: number;
  latitude: number;
  sighting: string;
  severity: number;
}

export interface ScenarioSummary {
  id: string;
  title: string;
  city: string;
  river_system: string;
  hazard_code: string;
  hazard_display: string;
  evidence_score: number;
  epistemic_status: EpistemicStatus;
  epistemic_display: string;
  is_lab_confirmed: boolean;
  qualitative_risk: string;
  snomed_outcome_code: string;
  snomed_outcome_display: string;
  snomed_outcome: string;
  grounding_statement: string;
  synthetic: boolean;
  site: ScenarioSite;
  citizen_points: CitizenPoint[];
  default_patient: LonLat | null;
  sub_scores: SubScores;
  exposure_pathway_display: string;
  snomed_preferred_term: string;
  /** Latest reading per sensor parameter, lab assays and model confidence, from the engine. */
  key_inputs: {
    kind: "sensor" | "lab" | "model";
    label: string;
    value: number;
    unit: string;
    exceeded: boolean | null;
  }[];
}

// ---------------------------------------------------------------------------
// Demo run (GET /demo/run?scenario=) — the 8-step decision chain
// ---------------------------------------------------------------------------

export interface SubScores {
  sensor_corroboration: number;
  citizen_agreement: number;
  temporal_consistency: number;
}

export interface SensorReadingRow {
  id: string;
  timestamp: string;
  parameter: string;
  value: number;
  unit: string;
  baseline: number;
  exceeded: boolean;
}

export interface CitizenReportRow {
  id: string;
  timestamp: string;
  sighting: string;
  severity: number;
  description: string;
  observer: string;
  longitude: number;
  latitude: number;
}

export interface LabAssayRow {
  id: string;
  timestamp: string;
  analyte: string;
  concentration: number;
  unit: string;
  threshold: number;
  laboratory: string;
  confirmed: boolean;
}

export interface ModelInferenceRow {
  model: string;
  version: string;
  timestamp: string;
  predicted_hazard: string;
  confidence: number;
  ecological_factors: Record<string, number | string>;
}

/** Synthetic emergency-department persona used to demonstrate the CDS Hooks card. Not a real person. */
export interface ClinicalEncounter {
  facility: string;
  bay: string;
  patient_name: string;
  triage: string;
  reason: string;
  location_context: string;
  snomed_outcome: string;
  clinical_consideration: string;
  doc_text: string;
  dispatch_target: string;
  dispatch_action: string;
  dossier_ref: string;
  dispatch_id: string;
  synthetic: boolean;
}

export interface ScenarioDetail {
  id: string;
  title: string;
  city: string;
  river_system: string;
  site_id: string;
  site_name: string;
  grounding_statement: string;
  hazard_code: string;
  hazard_display: string;
  evidence_score: number;
  epistemic_status: EpistemicStatus;
  epistemic_display: string;
  is_lab_confirmed: boolean;
  methodology_version: string;
  weights: { sensor: number; citizen: number; temporal: number };
  disclaimer: string;
  sub_scores: SubScores;
  estimated_exposed_population: number;
  buffer_meters: number;
  recreational_use_category: string;
  qualitative_risk: string;
  risk_summary: string;
  exposure_pathway_code: string;
  exposure_pathway_display: string;
  ascertainment_technique: string;
  ascertainment_display: string;
  snomed_outcome_code: string;
  snomed_outcome_display: string;
  snomed_preferred_term: string;
  snomed_outcome: string;
  sensor_readings: SensorReadingRow[];
  citizen_reports: CitizenReportRow[];
  lab_assays: LabAssayRow[];
  model_inferences: ModelInferenceRow[];
  clinical_encounter: ClinicalEncounter;
  synthetic: boolean;
}

export type PipelineStage = "ingest" | "corroborate" | "compose" | "validate";

export interface PipelineStep {
  step: number;
  stage: PipelineStage;
  title: string;
  detail: string;
  status: "COMPLETED" | "PASSED" | "FAILED";
}

export interface ValidationCheck {
  name: string;
  passed: boolean;
  message: string;
}

export interface ValidationTier {
  name: string;
  passed: boolean;
  checks: ValidationCheck[];
}

export interface ValidationReport {
  all_passed: boolean;
  /** Keys in run order: tier1_structural … tier6_scenario_logic. */
  tiers: Record<string, ValidationTier>;
  summary: { total_checks: number; passed_checks: number; failed_checks: number };
}

export interface FhirResource {
  resourceType: string;
  id?: string;
  [key: string]: unknown;
}

export interface FhirBundleEntry {
  fullUrl?: string;
  resource: FhirResource;
}

export interface FhirBundle {
  resourceType: "Bundle";
  id?: string;
  type: string;
  timestamp?: string;
  total: number;
  entry: FhirBundleEntry[];
}

export interface PipelineRun {
  id: string;
  ran_at: string;
  engine: string;
  /** Measured engine time per stage, milliseconds. */
  timings_ms: Record<PipelineStage, number>;
  total_ms: number;
}

export interface DemoRunResponse {
  run: PipelineRun;
  scenario: ScenarioDetail;
  steps: PipelineStep[];
  validation_report: ValidationReport;
  bundle: FhirBundle;
}

// ---------------------------------------------------------------------------
// CDS Hooks 1.0 (POST /cds-services/oah-exposure-advisory)
// ---------------------------------------------------------------------------

export interface CdsCard {
  summary: string;
  indicator: "info" | "warning" | "critical";
  detail: string;
  source: { label: string; url: string };
  suggestions: { label: string; actions: { type: string; description: string }[] }[];
  links: { label: string; url: string; type: string }[];
}

export interface CdsResponse {
  cards: CdsCard[];
  intersection_evaluation: {
    intersects: boolean;
    site_id: string;
    site_name: string;
    city: string;
    river_system: string;
    recreational_use_category: string;
    /** [longitude, latitude] */
    patient_coordinates: [number, number];
  };
  /** "request", or "scenario-default (synthetic demo patient)" when no coordinates were sent. */
  location_source: string;
}

export interface CdsDiscovery {
  services: { hook: string; name: string; description: string; id: string; prefetch: Record<string, string> }[];
}

// ---------------------------------------------------------------------------
// Conformance and terminology
// ---------------------------------------------------------------------------

export interface ConformanceItem {
  resourceType: string | null;
  id: string | null;
  url: string | null;
  title: string | null;
  status: string | null;
  version: string | null;
  description: string | null;
  raw: Record<string, unknown>;
}

export interface ConformancePack {
  total: number;
  items: ConformanceItem[];
}

export interface TerminologyConcept {
  code: string;
  preferred_term: string;
  display_label: string;
  display: string;
  fully_specified_name: string;
  hierarchy: string;
  status: string;
  pinned_release: string;
  verification_source: string;
  reference_url: string;
  validation_status: string;
  scenarios: string[];
  clinical_rationale: string;
}

export interface TerminologyManifest {
  system: string;
  name: string;
  version: string;
  pinned_release: string;
  publisher: string;
  verified_concepts_count: number;
  concepts: TerminologyConcept[];
  canonical_codesystems_verified?: unknown;
  external_standards_verified?: unknown;
}

// ---------------------------------------------------------------------------
// Weather (GET /weather?lat=&lon=) — Open-Meteo, context only
// ---------------------------------------------------------------------------

export type WeatherMode = "live" | "cached" | "unavailable";

export interface WeatherCurrent {
  time_local: string;
  time_utc: string | null;
  temperature_c: number | null;
  apparent_temperature_c: number | null;
  relative_humidity: number | null;
  precipitation_mm: number | null;
  rain_mm: number | null;
  weather_code: number | null;
  summary: string;
  cloud_cover: number | null;
  wind_speed_kmh: number | null;
  /** Meteorological: the direction the wind blows FROM, degrees clockwise from north. */
  wind_direction_deg: number | null;
  is_day: number | null;
}

export interface WeatherHour {
  time_local: string;
  time_utc: string | null;
  temperature_c: number | null;
  precipitation_mm: number | null;
  precipitation_probability: number | null;
  weather_code: number | null;
  summary: string;
  cloud_cover: number | null;
  wind_speed_kmh: number | null;
  wind_direction_deg: number | null;
  is_day: number | null;
}

export interface WeatherDay {
  date: string;
  weather_code: number | null;
  summary: string;
  temperature_max_c: number | null;
  temperature_min_c: number | null;
  precipitation_sum_mm: number | null;
}

export interface ContextSignal {
  code: string;
  label: string;
  detail: string;
  relevant_hazards: string[];
  epistemic_state: "context";
  caveat: string;
}

export interface WeatherResponse {
  mode: WeatherMode;
  /** True when Open-Meteo failed and the last good response is being shown. */
  stale: boolean;
  source: string;
  attribution: string;
  fetched_at: string | null;
  age_seconds: number | null;
  request: { latitude: number; longitude: number; precision: string };
  note: string | null;
  location?: {
    latitude: number | null;
    longitude: number | null;
    elevation_m: number | null;
    /** IANA time zone of the point, from Open-Meteo. */
    timezone: string;
    timezone_abbreviation: string | null;
    utc_offset_seconds: number;
  };
  current?: WeatherCurrent;
  rainfall?: { last_24h_mm: number | null; last_72h_mm: number | null; last_7d_mm: number | null };
  forecast_hourly?: WeatherHour[];
  forecast_daily?: WeatherDay[];
  context_signals?: ContextSignal[];
}

// ---------------------------------------------------------------------------
// Live system monitor (GET /monitor)
// ---------------------------------------------------------------------------

export type ComponentStatus = "ok" | "idle" | "degraded" | "error";

export interface MonitorComponent {
  id: string;
  label: string;
  status: ComponentStatus;
  detail: string;
}

export interface MonitorRecentRun {
  id: string;
  scenario: string;
  ran_at: string;
  total_ms: number;
  passed: boolean;
  checks: string;
}

export interface MonitorSnapshot {
  status: "operational" | "degraded";
  server_time_utc: string;
  engine: string;
  components: MonitorComponent[];
  self_test: {
    ran_at: string;
    duration_ms: number;
    passed: boolean;
    results: { scenario: string; passed: boolean; checks: string }[];
    error: string | null;
  };
  weather: {
    status: ComponentStatus;
    detail: string;
    cached_points: number;
    upstream_calls: number;
    upstream_failures: number;
    cache_hits: number;
    last_ok_at: string | null;
    last_error: string | null;
    last_error_at: string | null;
  };
  scope_note: string;
  started_at: string;
  uptime_seconds: number;
  counters: {
    pipeline_runs: number;
    pipeline_runs_passed: number;
    pipeline_runs_failed: number;
    cds_evaluations: number;
    cds_cards_issued: number;
  };
  recent_runs: MonitorRecentRun[];
}
