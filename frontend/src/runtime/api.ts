import { authHeader, clearAuth } from "../lib/auth";

export type ProbeStatus = "up" | "down" | "embedded" | "not_probed" | "misconfigured";

export interface RuntimeService {
  id: "frontend" | "api" | "receiver" | "database" | "redis";
  name: string;
  role: string;
  image: string | null;
  endpoint: string | null;
  health_path: string | null;
  workload: string | null;
  engine?: string;
  status: ProbeStatus;
  detail: string;
  probe_ms: number | null;
  checked_at: string;
}

export interface RuntimeTopology {
  label: string;
  live: boolean;
  platform: {
    kind: "kubernetes" | "container" | "process";
    provider: string | null;
    namespace: string | null;
    pod: string | null;
    node: string | null;
    pod_ip: string | null;
    hostname: string;
    python: string;
    detected_from: string[];
  };
  services: RuntimeService[];
  edges: { from: string; to: string; protocol: string }[];
  routes: { prefix: string; routes: number; methods: string[] }[];
  route_count: number;
  generated_at: string;
  notice: string;
}

export async function fetchRuntime(): Promise<RuntimeTopology> {
  const res = await fetch("/api/v1/runtime", { headers: authHeader() });
  if (res.status === 401) {
    clearAuth();
    throw new Error("Session expired. Sign in again.");
  }
  if (!res.ok) throw new Error(`Runtime topology unavailable (HTTP ${res.status})`);
  return (await res.json()) as RuntimeTopology;
}
