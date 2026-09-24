// OncoTwin API client — same auth + 401 behaviour as lib/api.ts.
import { authHeader, clearAuth } from "../lib/auth";
import type {
  AlertDetail,
  Dashboard,
  Handoff,
  HistorySnap,
  KeyMoment,
  LedgerEntry,
  ModelCard,
  Overview,
  PatientSummary,
  Simulation,
  TimelineItem,
  WhyResponse,
} from "./types";
import type { CommandCenter, Counterfactual, Intel, Json, ScenarioParams, WhatIf } from "./types2";

const BASE = "/api/v1/oncotwin";

export class OncoTwinError extends Error {
  constructor(public status: number, message: string) {
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
    throw new OncoTwinError(401, "Session expired");
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    const detail = typeof body?.detail === "string" ? body.detail : JSON.stringify(body?.detail ?? body);
    throw new OncoTwinError(res.status, detail || `Request failed (${res.status})`);
  }
  return (await res.json()) as T;
}

function post<T>(path: string, body: unknown = {}): Promise<T> {
  return request<T>(path, { method: "POST", body: JSON.stringify(body) });
}

export type InjectionKind = "infection" | "dehydration" | "nonadherence";
export type AlertActionKind = "accept" | "dismiss" | "investigate";

export const ot = {
  overview: () => request<Overview>("/overview"),
  model: () => request<ModelCard>("/model"),
  patients: () => request<{ patients: PatientSummary[] }>("/patients"),
  dashboard: (pid: string, asOfDay?: number) =>
    request<Dashboard>(`/patients/${pid}${asOfDay ? `?as_of_day=${asOfDay}` : ""}`),
  replay: (pid: string) =>
    request<{ snapshots: HistorySnap[]; key_moments: KeyMoment[]; live_day: number }>(`/patients/${pid}/replay`),
  timeline: (pid: string, asOfDay?: number) =>
    request<{ items: TimelineItem[]; lanes: string[]; as_of_day: number }>(
      `/patients/${pid}/timeline${asOfDay ? `?as_of_day=${asOfDay}` : ""}`),
  fhir: (pid: string, asOfDay?: number) =>
    request<{ entry: { resource: { resourceType: string; id: string } & Record<string, unknown> }[] }>(
      `/patients/${pid}/fhir?include_daily=false${asOfDay ? `&as_of_day=${asOfDay}` : ""}`),
  simulate: (pid: string, asOfDay?: number) =>
    post<{ simulation: Simulation; as_of_day: number }>(`/patients/${pid}/simulate`, asOfDay ? { as_of_day: asOfDay } : {}),
  advance: (pid: string, days: number) =>
    post<{ live_day: number; evaluations: { as_of_day: number; tier: string; risk: number }[]; alerts: string[] }>(
      `/patients/${pid}/advance`, { days }),
  evaluate: (pid: string) => post<{ tier: string; risk: number; alert: AlertDetail | null }>(`/patients/${pid}/evaluate`),
  inject: (pid: string, kind: InjectionKind) =>
    post<{ injection: { label: string; effective_from_day: number; past_data_unchanged: boolean } }>(
      `/patients/${pid}/inject`, { kind }),
  alert: (id: string) => request<AlertDetail>(`/alerts/${id}`),
  why: (id: string) => request<WhyResponse>(`/alerts/${id}/why`),
  act: (id: string, action: AlertActionKind, note: string) =>
    post<{ alert: AlertDetail }>(`/alerts/${id}/action`, { action, note }),
  handoff: (id: string) => post<{ handoff: Handoff; already_handed_off: boolean }>(`/alerts/${id}/handoff`, {}),
  audit: (pid?: string) =>
    request<{ entries: LedgerEntry[]; total: number; verification: { valid: boolean; entries: number; tip?: string } }>(
      `/audit${pid ? `?patient_id=${pid}` : ""}`),
  reset: () => post<{ reset: boolean }>("/demo/reset"),

  // ---- OncoTwin 2.0 -------------------------------------------------------
  commandCenter: () => request<CommandCenter>("/command-center"),
  intelligence: (pid: string, asOfDay?: number) =>
    request<Intel>(`/patients/${pid}/intelligence${asOfDay ? `?as_of_day=${asOfDay}` : ""}`),
  whatif: (pid: string, body: { as_of_day?: number; scenarios?: string[]; custom?: ScenarioParams }) =>
    post<WhatIf>(`/patients/${pid}/whatif`, body),
  counterfactual: (pid: string, anchorDay?: number) =>
    request<Counterfactual>(`/patients/${pid}/counterfactual${anchorDay ? `?anchor_day=${anchorDay}` : ""}`),
  interventionCatalog: () => request<{ interventions: { kind: string; label: string }[]; note: string }>("/interventions/catalog"),
  recordIntervention: (pid: string, kind: string, note: string, alertId?: string | null) =>
    post<{ intervention: Json }>(`/patients/${pid}/interventions`, { kind, note, alert_id: alertId || undefined }),
  knowledge: (pid: string, q: { entry_id?: string; day?: number }) =>
    request<Json>(`/patients/${pid}/knowledge?${qs(q)}`),
  features: (pid: string, asOfDay?: number) =>
    request<Json>(`/patients/${pid}/features${asOfDay ? `?as_of_day=${asOfDay}` : ""}`),
  explain: (pid: string, asOfDay?: number) => post<Json>(`/patients/${pid}/explain`, asOfDay ? { as_of_day: asOfDay } : {}),
  clinicalContext: (pid: string, asOfDay?: number) =>
    request<Json>(`/patients/${pid}/clinical-context${asOfDay ? `?as_of_day=${asOfDay}` : ""}`),
  modelRegistry: () => request<Json>("/models/registry"),
  featureRegistry: () => request<Json>("/feature-store/registry"),
  predictions: () => request<Json>("/mlops/predictions?limit=100"),
  drift: (refresh = false) => request<Json>(`/mlops/drift${refresh ? "?refresh=true" : ""}`),
  events: (q: { patient_id?: string; category?: string; limit?: number } = {}) =>
    request<{ events: Json[]; stats: Json }>(`/events?${qs(q)}`),
  observability: () => request<Json>("/observability"),
  health: () => request<Json>("/health"),
  architecture: () => request<{ components: Json[] }>("/architecture"),
  researchResults: () => request<Json>("/research/results"),
  researchOptions: () => request<Json>("/research/options"),
  startExperiment: (body: Json) => post<{ job: Json }>("/research/experiments", body),
  experiment: (id: string) => request<Json>(`/research/experiments/${id}`),
  stressTest: () => post<Json>("/stress-test"),
  stressLatest: () => request<Json>("/stress-test/latest"),
};

function qs(q: Record<string, string | number | undefined | null>): string {
  return new URLSearchParams(Object.entries(q).filter(([, v]) => v != null).map(([k, v]) => [k, String(v)])).toString();
}
