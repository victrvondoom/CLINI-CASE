// AquaHealth API client — same auth + 401 behaviour as lib/api.ts and
// oncotwin/api.ts. Reuses ClinCase's existing auth helpers rather than
// introducing a second token mechanism.
import { authHeader, clearAuth } from "../lib/auth";
import type {
  AgentManifest,
  AquaMeta,
  CommunityStats,
  DashboardOverview,
  EcosystemStatus,
  FormSchema,
  MapView,
  Observation,
  ObservationCreate,
  ObservationSummary,
  OneHealthView,
  ReviewDecision,
  ReviewQueue,
  ReviewStatus,
  TrendsResponse,
  Track3Evaluation,
  WaterbodyRow,
} from "./types";

const BASE = "/api/v1/aquahealth";

export class AquaHealthError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...authHeader() },
  });
  if (res.status === 401) {
    clearAuth();
    window.location.href = "/login";
    throw new AquaHealthError(401, "Session expired");
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    const detail =
      typeof body?.detail === "string"
        ? body.detail
        : JSON.stringify(body?.detail ?? body);
    throw new AquaHealthError(res.status, detail || `Request failed (${res.status})`);
  }
  return res.json() as Promise<T>;
}

export interface ListObservationsParams {
  waterbodyId?: string;
  reviewStatus?: ReviewStatus;
  status?: EcosystemStatus;
  includeDemo?: boolean;
  limit?: number;
  offset?: number;
}

export interface ObservationListResponse {
  total: number;
  limit: number;
  offset: number;
  observations: ObservationSummary[];
}

export interface ReviewPayload {
  decision: ReviewDecision;
  comment?: string | null;
  corrected_status?: EcosystemStatus | null;
  rejected_findings?: string[];
}

export const aqua = {
  meta: () => request<AquaMeta>("/meta"),

  formSchema: () => request<FormSchema>("/form-schema"),

  agentManifest: () => request<AgentManifest>("/agents/manifest"),

  evaluation: () => request<Track3Evaluation>("/evaluation"),

  overview: () => request<DashboardOverview>("/overview"),

  map: () => request<MapView>("/map"),

  trends: (waterbodyId?: string, days = 90) => {
    const qs = new URLSearchParams({ days: String(days) });
    if (waterbodyId) qs.set("waterbody_id", waterbodyId);
    return request<TrendsResponse>(`/trends?${qs.toString()}`);
  },

  oneHealth: () => request<OneHealthView>("/one-health"),

  community: () => request<CommunityStats>("/community"),

  waterbodies: () =>
    request<{ waterbodies: WaterbodyRow[]; total: number }>("/waterbodies"),

  listObservations: (params: ListObservationsParams = {}) => {
    const qs = new URLSearchParams();
    if (params.waterbodyId) qs.set("waterbody_id", params.waterbodyId);
    if (params.reviewStatus) qs.set("review_status", params.reviewStatus);
    if (params.status) qs.set("status", params.status);
    if (params.includeDemo !== undefined) {
      qs.set("include_demo", String(params.includeDemo));
    }
    qs.set("limit", String(params.limit ?? 50));
    qs.set("offset", String(params.offset ?? 0));
    return request<ObservationListResponse>(`/observations?${qs.toString()}`);
  },

  getObservation: (id: string) => request<Observation>(`/observations/${id}`),

  createObservation: (payload: ObservationCreate) =>
    request<Observation>("/observations", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  reassess: (id: string) =>
    request<Observation>(`/observations/${id}/reassess`, { method: "POST" }),

  reviewQueue: () => request<ReviewQueue>("/review/queue"),

  review: (id: string, payload: ReviewPayload) =>
    request<Observation>(`/observations/${id}/review`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  exportObservation: (id: string, format: "prototype" | "fhir" = "prototype") =>
    request<Record<string, unknown>>(`/observations/${id}/export?format=${format}`),

  exportBundle: (waterbodyId?: string) => {
    const qs = new URLSearchParams();
    if (waterbodyId) qs.set("waterbody_id", waterbodyId);
    const suffix = qs.toString() ? `?${qs.toString()}` : "";
    return request<Record<string, unknown>>(`/export/bundle${suffix}`);
  },

  exportCatalog: () => request<Record<string, unknown>>("/export/catalog"),

  seedDemo: (force = false) =>
    request<{
      seeded: boolean;
      reason?: string;
      observations: number;
      waterbodies: number;
      banner: string;
    }>(`/demo/seed?force=${force}`, { method: "POST" }),

  resetDemo: () =>
    request<{ cleared: boolean; observations_removed: number }>("/demo/reset", {
      method: "POST",
    }),
};
