/**
 * Unified evidence journey client.
 *
 * State comes from the server-side projection (`GET /api/v1/journey/...`), which composes the
 * existing interop job and its bound One Health evidence. Actions call the EXISTING gateway
 * endpoints; the server enforces every rule (roles, tenancy, consent, versions). The client
 * never invents progress — after each action it re-reads the projection.
 */
import { authHeader, clearAuth } from "../lib/auth";
import { interop, type Job } from "../interop/api";

export type StageStatus = "complete" | "ready" | "waiting" | "blocked" | "failed";
export type StageId =
  | "ingest"
  | "understand"
  | "map"
  | "review"
  | "standardize"
  | "validate"
  | "exchange"
  | "verify"
  | "clinical_context"
  | "follow_up";
export type ActionId =
  | "map"
  | "review"
  | "generate"
  | "validate"
  | "transfer"
  | "return"
  | "bind"
  | "export_passport"
  | "open_evidence";

export interface StageEvidence {
  event_type: string;
  timestamp: string;
  actor: string;
  status: string;
  correlation_id: string;
}

export interface MappingRow {
  source_field: string;
  target: string | null;
  fhir_target: string | null;
  confidence: number;
  origin: string;
  decision: "pending" | "accepted" | "rejected";
  concept: string | null;
  terminology_status: string;
  reason: string;
  reviewer: string | null;
}

export interface Connection {
  capability: string;
  href: string | null;
  binding: string | null;
}

export interface StageDetail {
  fields?: { name: string; detected_type: string }[];
  missing_required_fields?: string[];
  ambiguities?: string[];
  mappings?: MappingRow[];
  targets?: Record<string, string>;
  semantic_firewall?: {
    status?: string;
    ai_authority?: string;
    ai_input?: string;
    ambiguous_fields?: string[];
    blocked_inferences?: string[];
  };
  resource_types?: Record<string, number>;
  issues?: { severity: string; diagnostics: string; code?: string }[];
  checks?: { name: string; passed: boolean | null }[];
  standards?: { validation_scope?: string; notice?: string; target?: string; oah_package?: string };
  transfers?: {
    id: string;
    status: string;
    sha256: string | null;
    correlation_id: string | null;
    error: string | null;
    resources_acknowledged: number | null;
    processing_ms: number | null;
  }[];
  challenges?: { id: string; status: string; receiver_http: number | null }[];
  roundtrip_fields?: { field: string; preserved: boolean }[];
  passport?: { valid?: boolean; status?: string; revision_count?: number; head?: string };
  connections?: Connection[];
  epistemic_ceiling?: { level: string; allowed: string; not_allowed: string[]; missing_gates?: string[] } | null;
  assessment_gates?: { id: string; label: string; passed: boolean }[];
  retest_comparison?: {
    previous_record_id: string;
    comparable: boolean;
    change_ug_l: number | null;
    meaning: string;
  } | null;
}

export interface Stage {
  id: StageId;
  index: number;
  label: string;
  owner: string;
  status: StageStatus;
  summary: string;
  facts: { label: string; value: string | number }[];
  evidence: StageEvidence[];
  next_action: { id: ActionId; label: string } | null;
  links: { label: string; href: string }[];
  detail: StageDetail;
}

export interface JourneyView {
  job_id: string;
  job_version: number;
  exposure_id: string | null;
  exposure_version: number | null;
  source: { system: string; record_id: string; format: string; synthetic: boolean };
  consent_status: string | null;
  trust_states: string[];
  current_stage: StageId | null;
  progress: { complete: number; total: number };
  last_activity: string | null;
  stages: Stage[];
}

export interface JourneySummary {
  job_id: string;
  source: JourneyView["source"];
  exposure_id: string | null;
  current_stage: StageId | null;
  current_status: StageStatus;
  current_summary: string;
  progress: JourneyView["progress"];
  last_activity: string | null;
}

export interface JourneyList {
  journeys: JourneySummary[];
  persistence: string;
  stages: { id: StageId; label: string; owner: string }[];
}

export const STAGE_ORDER: StageId[] = [
  "ingest",
  "understand",
  "map",
  "review",
  "standardize",
  "validate",
  "exchange",
  "verify",
  "clinical_context",
  "follow_up",
];

export function isStageId(value: string | undefined): value is StageId {
  return !!value && (STAGE_ORDER as string[]).includes(value);
}

async function request<T>(path: string): Promise<T> {
  const res = await fetch(`/api/v1/journey${path}`, { headers: authHeader() });
  if (res.status === 401) {
    clearAuth();
    throw new Error("Session expired. Sign in again.");
  }
  if (res.status === 403) throw new Error("The evidence journey needs a reviewer or admin role.");
  if (res.status === 404) throw new Error("This journey was not found in your organisation.");
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const detail = data && typeof data.detail === "string" ? data.detail : `Request failed (${res.status})`;
    throw new Error(detail);
  }
  return data as T;
}

export const journeyApi = {
  list: () => request<JourneyList>(""),
  get: (jobId: string) => request<JourneyView>(`/${encodeURIComponent(jobId)}`),
};

function command(view: JourneyView) {
  return { job_id: view.job_id, expected_version: view.job_version };
}

/** Thin wrappers over the existing gateway endpoints. The server enforces every rule. */
export const journeyActions = {
  startDemo: (variant: "dissolved" | "ambiguous") => interop<Job>(`/demo?variant=${variant}`, {}),
  importSource: (source: {
    source_system: string;
    original_record_id: string;
    format: "json" | "csv" | "fhir";
    payload: Record<string, unknown> | string;
    synthetic: boolean;
  }) => interop<Job>("/import", source),
  map: (view: JourneyView, useAi = false) => interop<Job>("/map", { ...command(view), use_ai: useAi }),
  decide: (
    view: JourneyView,
    row: MappingRow,
    decision: "approve" | "reject",
    target: string | null,
    concept: string | null,
  ) =>
    interop<Job>(`/mappings/${encodeURIComponent(view.job_id)}/${decision}`, {
      ...command(view),
      source_field: row.source_field,
      target,
      ...(concept ? { concept } : {}),
    }),
  generate: (view: JourneyView) => interop<Job>("/generate-fhir", command(view)),
  /** Re-validate exactly the generated bundle (read it, then validate it at its current version). */
  validate: async (view: JourneyView) => {
    const job = await interop<Job>(`/jobs/${encodeURIComponent(view.job_id)}`);
    if (!job.bundle) throw new Error("Generate a bundle before validating.");
    return interop<Job>("/validate", { job_id: job.id, expected_version: job.version, bundle: job.bundle });
  },
  transfer: (view: JourneyView) => interop<Job>("/transfer", { ...command(view), receiver: "clinical" }),
  returnTrip: (view: JourneyView) => interop<{ job: Job }>("/return", command(view)),
  bind: (view: JourneyView) => interop<Job>("/bind-evidence", command(view)),
  passport: (view: JourneyView) => interop<unknown>(`/passport/${encodeURIComponent(view.job_id)}/export`),
};
