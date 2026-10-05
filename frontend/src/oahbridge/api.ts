// OAH-Bridge API client — backend/app/oahbridge (router mounted at /api/v1/oah-bridge).
// Weather goes through our backend, never straight to Open-Meteo, so the browser sends no
// third-party request and the server can cache and label freshness.
import { authHeader, clearAuth } from "../lib/auth";
import type {
  CdsDiscovery,
  CdsResponse,
  ConformancePack,
  DemoRunResponse,
  FhirBundle,
  FhirResource,
  MonitorSnapshot,
  ScenarioSummary,
  TerminologyManifest,
  WeatherResponse,
} from "./types";

export const OAH_BRIDGE_BASE = "/api/v1/oah-bridge";

export class OahBridgeError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "OahBridgeError";
  }
}

async function request<T>(path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  const res = await fetch(`${OAH_BRIDGE_BASE}${path}`, {
    method: body === undefined ? "GET" : "POST",
    headers: {
      ...(body === undefined ? {} : { "Content-Type": "application/json" }),
      ...authHeader(),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal,
  });
  if (res.status === 401) {
    clearAuth();
    throw new OahBridgeError(401, "Session expired. Sign in again.");
  }
  if (!res.ok) {
    let detail = "";
    try {
      const data = await res.json();
      detail = typeof data?.detail === "string" ? data.detail : JSON.stringify(data?.detail ?? data);
    } catch {
      // non-JSON error body
    }
    throw new OahBridgeError(res.status, detail || `Request failed (${res.status})`);
  }
  return (await res.json()) as T;
}

/** Coarsen to 2 decimals (~1 km) before a coordinate leaves the browser. */
function coarse(value: number): number {
  return Math.round(value * 100) / 100;
}

function hookInstance(): string {
  try {
    if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") return crypto.randomUUID();
  } catch {
    // fall through
  }
  return `hook-${Date.now().toString(36)}`;
}

export const oahBridge = {
  scenarios: () => request<ScenarioSummary[]>("/scenarios"),

  run: (scenarioId: string) =>
    request<DemoRunResponse>(`/demo/run?scenario=${encodeURIComponent(scenarioId)}`),

  cdsDiscovery: () => request<CdsDiscovery>("/cds-services"),

  /**
   * CDS Hooks 1.0 patient-view call. `coordinates` is [longitude, latitude]. Without it the
   * server uses the scenario's synthetic demo patient and says so in `location_source`.
   */
  evaluateExposure: (scenarioId: string, coordinates?: [number, number]) =>
    request<CdsResponse>("/cds-services/oah-exposure-advisory", {
      hook: "patient-view",
      hookInstance: hookInstance(),
      scenario: scenarioId,
      context: {
        patientId: "synthetic-demo-patient",
        ...(coordinates ? { coordinates } : {}),
      },
    }),

  conformance: () => request<ConformancePack>("/conformance"),

  terminology: () => request<TerminologyManifest>("/terminology"),

  capabilityStatement: () => request<FhirResource>("/fhir/metadata"),

  fhirSearch: (
    resourceType: string,
    scenarioId: string,
    params: { hazard?: string; location?: string } = {},
  ) => {
    const query = new URLSearchParams({ scenario: scenarioId });
    if (params.hazard) query.set("oah-hazard", params.hazard);
    if (params.location) query.set("oah-location", params.location);
    return request<FhirBundle>(`/fhir/${encodeURIComponent(resourceType)}?${query.toString()}`);
  },

  /** POST so the (already coarsened) point stays out of URLs and access logs. */
  weather: (latitude: number, longitude: number, signal?: AbortSignal) =>
    request<WeatherResponse>(
      "/weather",
      { latitude: coarse(latitude), longitude: coarse(longitude) },
      signal,
    ),

  monitor: () => request<MonitorSnapshot>("/monitor"),
};
