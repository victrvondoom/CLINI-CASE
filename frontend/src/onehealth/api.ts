import { authHeader, clearAuth } from "../lib/auth";

export interface LabSample {
  sample_id: string;
  location_name: string;
  kind: "stream" | "source_water" | "drinking_water";
  laboratory: string;
  collector: string;
  report_reference: string;
  method: string;
  collected_at: string;
  reported_at: string;
  analyte: "total_arsenic" | "inorganic_arsenic" | "dissolved_arsenic";
  value: number;
  unit: "ug/L" | "mg/L";
  qualifier: "eq" | "lt";
}
export interface ExposureHistory {
  patient_id: string;
  consent_reference: string;
  consent_recorded: boolean;
  route: "drinking" | "other" | "unknown";
  pathway_confirmed: boolean;
  pathway_evidence: string;
  treatment_context: string;
  started_on: string;
  ended_on: string;
}
export interface ExposureRecord {
  id: string;
  version: number;
  observation_id: string;
  waterbody_name: string;
  synthetic: boolean;
  created_at: string;
  sample: LabSample;
  history: ExposureHistory | null;
  lab_verified: boolean;
  consent_withdrawn: boolean;
  review: "pending" | "reviewed" | "more_information" | "rejected";
  followup_status: "requested" | "in_progress" | "completed";
  case_id: string | null;
  followup_evidence_reference?: string | null;
  audit: { action: string; actor_id: string; at: string; note: string }[];
  assessment: {
    state: string;
    eligible_for_review: boolean;
    concentration_ug_l: number;
    comparison: string;
    gates: { id: string; label: string; passed: boolean }[];
    reference: { value: number; unit: string; name: string; url: string };
    meaning: string;
    notice: string;
    clinical_context: Record<string, string>;
  };
  ablation: { removed: string; eligible_for_review: boolean; state: string }[];
  source_bundle_sha256: string | null;
  persistence: string;
  gateway_job_id?: string | null;
  retest_of?: string | null;
  successor_id?: string | null;
  epistemic_ceiling?: {
    level: string;
    allowed: string;
    missing_gates: string[];
    not_allowed: string[];
  };
  trust_states?: string[];
  passport_integrity?: {
    status: string;
    valid: boolean;
    revision_count?: number;
    head?: string;
  };
}
export interface Standards {
  target: string;
  oah_package: string;
  oah_commit: string;
  source: string;
  validation_scope: string;
  full_hl7_profile_validation: boolean;
  notice: string;
}
export interface Validation {
  valid: boolean;
  sha256: string;
  standards: Standards;
  operation_outcome: { issue: { severity: string; diagnostics: string }[] };
  roundtrip?: {
    sample_preserved: boolean;
    history_preserved: boolean;
    trust_policy: string;
  };
  import_policy?: string;
}
export interface Meta {
  product: string;
  primary_track: string;
  supporting_track: string;
  standards: Standards;
  persistence: string;
  notice: string;
}
export interface Patient {
  id: string;
  label: string;
  synthetic: boolean;
}
export interface EnvironmentalTask {
  id: string;
  waterbody_name: string;
  observation_id: string;
  status: "requested" | "in_progress" | "completed";
  synthetic: boolean;
  action: string;
}
export interface CaseCandidate {
  id: string;
  patient_initials: string;
  treatment: string;
  status: string;
}

async function request<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`/api/v1/onehealth${path}`, {
    method: body === undefined ? "GET" : "POST",
    headers: { "Content-Type": "application/json", ...authHeader() },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  if (res.status === 401) {
    clearAuth();
    throw new Error("Session expired. Sign in again.");
  }
  const data = await res.json();
  if (!res.ok)
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : JSON.stringify(data.detail),
    );
  return data as T;
}
export const onehealth = {
  journey: (id: string) =>
    request<Journey>(`/exposures/${encodeURIComponent(id)}/journey`),
  passport: (id: string) =>
    request<unknown>(`/exposures/${encodeURIComponent(id)}/passport`),
  meta: () => request<Meta>("/meta"),
  patients: () => request<{ patients: Patient[] }>("/patients"),
  environmentalTasks: () =>
    request<{ tasks: EnvironmentalTask[] }>("/environmental-tasks"),
  caseCandidates: () =>
    request<{ available: boolean; reason?: string; cases: CaseCandidate[] }>(
      "/case-candidates",
    ),
  list: (filter?: { patient_id?: string; case_id?: string }) =>
    request<{ records: ExposureRecord[]; persistence: string }>(
      `/exposures?${new URLSearchParams(filter)}`,
    ),
  get: (id: string) =>
    request<ExposureRecord>(`/exposures/${encodeURIComponent(id)}`),
  create: (observation_id: string, sample: LabSample) =>
    request<ExposureRecord>("/exposures", { observation_id, sample }),
  demo: () => request<ExposureRecord>("/demo", {}),
  action: (
    record: ExposureRecord,
    action: string,
    payload: Record<string, unknown>,
  ) =>
    request<ExposureRecord>(`/exposures/${record.id}/${action}`, {
      ...payload,
      expected_version: record.version,
    }),
  export: (id: string) =>
    request<{ bundle: Record<string, unknown>; validation: Validation }>(
      `/exposures/${id}/fhir`,
    ),
  validate: (bundle: unknown) =>
    request<Validation>("/exchange/validate", { bundle }),
  import: (bundle: unknown, observation_id: string) =>
    request<ExposureRecord>("/exchange/import", { bundle, observation_id }),
};

export interface Journey {
  record: ExposureRecord;
  connections: {
    capability: string;
    href: string | null;
    binding: string | null;
  }[];
  consent_status: string;
  retest_comparison: {
    previous_record_id: string;
    comparable: boolean;
    change_ug_l: number | null;
    meaning: string;
  } | null;
}
