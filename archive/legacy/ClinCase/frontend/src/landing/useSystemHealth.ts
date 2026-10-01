/**
 * Single real call to the backend's public liveness endpoint, shared by the
 * hero's credibility line, the live-status panel, and the metrics section —
 * no fabricated numbers anywhere on this page, only what the backend reports.
 *
 * /api/v1/healthz and /api/v1/capabilities are both unauthenticated, so the
 * landing page can call them before the visitor has an account.
 */
import { useCallback, useEffect, useState } from "react";

export const HEALTH_URL = "/api/v1/healthz";
export const CAPABILITIES_URL = "/api/v1/capabilities";

export interface SystemHealth {
  status: string;
  db: string;
}

export interface Capabilities {
  deployment?: {
    llm_provider?: string;
    aws_region?: string;
    bedrock_model_id?: string;
  };
  compliance?: {
    cms_0057f_clauses_tracked?: number;
  };
  thresholds?: {
    hitl_confidence_threshold?: number;
  };
}

export interface HealthState {
  health: SystemHealth | null;
  capabilities: Capabilities | null;
  latencyMs: number | null;
  loading: boolean;
  error: string | null;
  checkedAt: number | null;
}

async function probe(): Promise<{
  health: SystemHealth;
  capabilities: Capabilities | null;
  latencyMs: number;
}> {
  const started = performance.now();
  const res = await fetch(HEALTH_URL, { headers: { Accept: "application/json" } });
  const latencyMs = Math.round(performance.now() - started);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  const health = (await res.json()) as SystemHealth;

  // Capabilities is a nice-to-have: a failure here must not blank out the
  // health reading the rest of the page is built on.
  let capabilities: Capabilities | null = null;
  try {
    const capRes = await fetch(CAPABILITIES_URL, { headers: { Accept: "application/json" } });
    if (capRes.ok) capabilities = (await capRes.json()) as Capabilities;
  } catch {
    capabilities = null;
  }

  return { health, capabilities, latencyMs };
}

const INITIAL: HealthState = {
  health: null,
  capabilities: null,
  latencyMs: null,
  loading: true,
  error: null,
  checkedAt: null,
};

export function useSystemHealth(): HealthState & { refresh: () => void } {
  const [state, setState] = useState<HealthState>(INITIAL);

  const run = useCallback(() => {
    let cancelled = false;
    setState((s) => ({ ...s, loading: true, error: null }));
    probe()
      .then(({ health, capabilities, latencyMs }) => {
        if (cancelled) return;
        setState({
          health,
          capabilities,
          latencyMs,
          loading: false,
          error: null,
          checkedAt: Date.now(),
        });
      })
      .catch((err: Error) => {
        if (cancelled) return;
        setState({
          health: null,
          capabilities: null,
          latencyMs: null,
          loading: false,
          error: err.message,
          checkedAt: Date.now(),
        });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => run(), [run]);

  return { ...state, refresh: run };
}
