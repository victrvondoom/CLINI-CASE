import { authHeader, clearAuth } from "../lib/auth";
import type { Validation, ExposureRecord } from "../onehealth/api";
export interface Mapping {
  source_field: string;
  target: string | null;
  fhir_target: string | null;
  confidence: number;
  origin: string;
  decision: string;
  concept: string | null;
  terminology_status: string;
  reason: string;
  reviewer: string | null;
}
export interface Job {
  schema: {
    missing_required_fields: string[];
    ambiguities: string[];
    fields: { name: string; detected_type: string }[];
  };
  id: string;
  version: number;
  source: {
    source_system: string;
    original_record_id: string;
    payload: unknown;
  };
  fields: Record<string, unknown>;
  mappings: Mapping[];
  ai_status: string;
  mapping_version: number;
  bundle: Record<string, unknown> | null;
  validation:
    | (Omit<Validation, "roundtrip"> & {
        checks: { name: string; passed: boolean | null }[];
        roundtrip?: {
          fields_preserved: number;
          fields_total: number;
          sample_preserved: boolean;
          history_preserved?: boolean;
          trust_policy?: string;
        };
      })
    | null;
  metrics: Record<string, number>;
  assessment: ExposureRecord["assessment"] | null;
  transfers: {
    id: string;
    sha256: string;
    status: string;
    error?: string;
    acknowledgement?: {
      resources_acknowledged: number;
      representation: unknown;
    };
  }[];
  events: {
    timestamp: string;
    event_type: string;
    actor: string;
    status: string;
    correlation_id: string;
    provenance: unknown;
  }[];
}
export async function interop<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`/api/v1/interop${path}`, {
    method: body === undefined ? "GET" : "POST",
    headers: { "Content-Type": "application/json", ...authHeader() },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  if (res.status === 401) clearAuth();
  const data = await res.json();
  if (res.status === 429)
    throw new Error(
      `Rate limit reached. Retry in ${res.headers.get("Retry-After") || "a few"} seconds.`,
    );
  if (!res.ok)
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : JSON.stringify(data.detail ?? data.error ?? data),
    );
  return data as T;
}
