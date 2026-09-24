// Types for the OncoTwin 2.0 payloads (/api/v1/oncotwin — intelligence, command center, what-if, research, ops).
// Deep, fully-dynamic blobs (e.g. model cards, benchmark tables) are typed as Json.
import type { Profile, Tier } from "./types";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type Json = any;

export type Severity = "normal" | "attention" | "alert";

export interface Dim {
  status: string;
  severity: Severity;
  basis: string;
  fields: Json;
  confidence: number | null;
  data_quality: string | string[];
  sources: { type: string; ids?: string[]; code?: string }[];
  pending?: { status: string; note: string; consecutive_days: number };
}

export interface TwinState {
  day: number;
  as_of_time: string;
  dimensions: Record<string, Dim>;
  sha256: string;
}

export interface Transition {
  day: number;
  at: string;
  dimension: string;
  label: string;
  previous: string;
  new: string;
  direction: "worsening" | "improving" | "change";
  severity: Severity;
  reason: string;
  basis: string;
  sources: { type: string; ids?: string[] }[];
  confidence: number | null;
  data_quality: string | string[];
}

export interface GNode {
  id: string;
  group: string;
  label: string;
  status: string;
  severity: Severity;
  basis: string;
  evidence: Json[];
  detail: Json;
}

export interface GEdge {
  source: string;
  target: string;
  kind: "clinical" | "temporal" | "data" | "model";
  label: string;
  weight: number | null;
}

export interface Graph {
  nodes: GNode[];
  edges: GEdge[];
  edge_kinds: Record<string, string>;
  groups: string[];
  counts: Record<string, number>;
  note: string;
}

export interface Intel {
  as_of_day: number;
  live_day: number;
  n_days: number;
  is_replay: boolean;
  synthetic_notice: string;
  patient: Profile;
  prediction: Json;
  state: TwinState;
  transitions_recent: Transition[];
  what_changed: Json;
  change_points: Json;
  trajectory: Json;
  memory: Json;
  correlation: Json;
  conflicts: Json[];
  consistency: Json;
  uncertainty: Json;
  readiness: Json;
  horizons: Json;
  why_now: Json;
  show_your_work: Json;
  graph: Graph;
  evidence: Json;
  review: string[];
  facts: Json;
  triage: { category: string; data_quality_reasons: string[] };
  interventions: Json[];
}

export interface CCRow {
  patient: Profile;
  live_day: number;
  n_days: number;
  category: string;
  category_reasons: string[];
  tier: Tier;
  risk: number;
  risk_p10: number;
  risk_p90: number;
  risk_series: { day: number; risk: number; tier: Tier }[];
  readiness: { score: number; label: string; limiting_factor: string };
  data_quality: string;
  trajectory: string;
  pattern: string;
  top_change: Json | null;
  n_changes_3d: number;
  change_point: { day: number; kind: string } | null;
  conflicts: string[];
  consistency: string;
  open_alerts: number;
  why_now: string;
}

export interface CommandCenter {
  categories: string[];
  counts: Record<string, number>;
  patients: CCRow[];
  drift: Json;
  ledger: Json;
  note: string;
}

export interface ScenarioParams {
  label?: string;
  adherence?: number;
  gcsf_tomorrow?: boolean;
  antibiotics_start_day_offset?: number;
  antibiotics_days?: number;
  iv_hydration_day_offsets?: number[];
  oral_hydration_coaching?: boolean;
  activity_program?: boolean;
  next_dose_scale?: number;
  delay_next_dose_days?: number;
  gcsf_with_next_cycle?: boolean;
  new_infection?: boolean;
}

export interface WhatIf {
  as_of_day: number;
  risk: number;
  tier: Tier;
  simulation: Json;
  observed: { day: number; risk: number; risk_p10: number; risk_p90: number; tier: Tier }[];
  data_used: Json;
  label: string;
}

export interface Counterfactual {
  disclaimer: string;
  anchor_day: number;
  live_day: number;
  scenario: Json;
  data_used: Json;
  days: {
    day: number;
    observed_risk: number | null;
    observed_tier: Tier | null;
    simulated_median: number;
    simulated_p10: number;
    simulated_p90: number;
    simulated_event_probability_cumulative: number;
    observed_within_band: boolean | null;
  }[];
  signals: Record<string, {
    label: string; unit: string; days: number[]; observed: (number | null)[];
    simulated_median: number[]; simulated_p10: number[]; simulated_p90: number[];
  }>;
  observed_interventions: { day: number; display: string; id: string }[];
  observed_outcomes: { day: number; display: string }[];
  band_coverage: number | null;
  first_divergence: Json;
  summary: string;
  synthetic_truth: Json;
}
