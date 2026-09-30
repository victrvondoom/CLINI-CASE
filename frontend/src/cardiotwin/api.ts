// CardioTwin API client — same auth + 401 behaviour as lib/api.ts and the OncoTwin / AquaHealth clients.
import { authHeader, clearAuth } from "../lib/auth";
import type {
  CounterfactualResult,
  EvaluationReport,
  FeatureCatalog,
  Overview,
  PatientValues,
  Prediction,
  Scenario,
} from "./types";

const BASE = "/api/v1/cardiotwin";

export class CardioTwinError extends Error {
  constructor(
    public status: number,
    message: string,
    public problems: string[] = [],
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
    throw new CardioTwinError(401, "Session expired");
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    const d = body?.detail;
    const problems: string[] = Array.isArray(d?.problems) ? d.problems : [];
    const message =
      typeof d === "string" ? d : problems.length ? problems.join("; ") : JSON.stringify(d ?? body);
    throw new CardioTwinError(res.status, message || `Request failed (${res.status})`, problems);
  }
  return res.json() as Promise<T>;
}

const post = <T,>(path: string, body: unknown) =>
  request<T>(path, { method: "POST", body: JSON.stringify(body) });

/** Drop empty / null entries so the backend imputes them and reports completeness honestly. */
export function cleanValues(v: PatientValues): PatientValues {
  const out: PatientValues = {};
  for (const [k, val] of Object.entries(v)) {
    if (val === null || val === undefined || val === "") continue;
    out[k] = val;
  }
  return out;
}

export const cardio = {
  overview: () => request<Overview>("/overview"),
  features: () => request<FeatureCatalog>("/features"),
  scenarios: () => request<{ note: string; scenarios: Scenario[] }>("/scenarios"),
  predict: (features: PatientValues, scenarioId?: string | null) =>
    post<Prediction>("/predict", { features: cleanValues(features), scenario_id: scenarioId ?? null }),
  counterfactual: (features: PatientValues, perturbations: Record<string, number | string>) =>
    post<CounterfactualResult>("/counterfactual", { features: cleanValues(features), perturbations }),
  sensitivity: (features: PatientValues, feature: string, points = 15) =>
    post<{
      feature: string;
      label: string;
      unit: string;
      current_value: number | string;
      curve: ({ value: number | string } & Record<string, number | string>)[];
      note: string;
    }>("/sensitivity", { features: cleanValues(features), feature, points }),
  model: () => request<Record<string, unknown>>("/model"),
  evaluation: () => request<EvaluationReport>("/evaluation"),
};
