/** Shared fetchers for the agent manifest + live metrics (used by the Agents page and the Dashboard health panel). */
import { authHeader } from "./auth";
import type { AgentsManifest, MetricsReport } from "./agentsModel";

export async function getJson<T>(url: string, auth = true): Promise<T> {
  const res = await fetch(url, { headers: auth ? authHeader() : {} });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(typeof body?.detail === "string" ? body.detail : `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export const fetchManifest = () => getJson<AgentsManifest>("/api/v1/agents/manifest", false);
export const fetchMetrics = (hours = 24) => getJson<MetricsReport>(`/api/v1/agents/metrics?hours=${hours}`);
