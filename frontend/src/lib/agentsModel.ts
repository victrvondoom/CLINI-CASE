/**
 * Agents page view-model. Everything is derived from three live sources:
 *   GET /agents/manifest  — the auto-discovered agents, sub-agents, schemas, models and the real LangGraph topology
 *   GET /agents/metrics   — per-agent invocations / success / latency / tokens / cost from the org's agent_runs
 *   GET /mcp/manifest     — the MCP tools the server actually exposes
 * No numbers, names or ordering are hard-coded here.
 */

export interface ManifestSubAgent {
  name: string;
  qualified_name: string;
  role: string;
  description: string;
  is_llm_backed: boolean;
  primary_model: { size?: string; role?: string } | null;
}

export interface ManifestAgent {
  name: string;
  role: string;
  description: string;
  input_schema: string;
  output_schema: string;
  is_llm_backed: boolean;
  primary_model: { size?: string; role?: string } | null;
  pipeline_index: number | null;
  sub_agents: ManifestSubAgent[];
}

export interface PipelineGraph {
  nodes: string[];
  edges: { source: string; target: string; conditional: boolean }[];
  order: string[];
}

export interface AgentsManifest {
  n_agents: number;
  n_sub_agents: number;
  agents: ManifestAgent[];
  graph: PipelineGraph | null;
}

export interface AgentMetrics {
  invocations: number;
  success_pct: number | null;
  errors: number;
  running: number;
  p50_ms: number | null;
  p95_ms: number | null;
  mean_input_tokens: number | null;
  mean_output_tokens: number | null;
  cost_usd: number;
  model_id: string | null;
  last_run_at: string | null;
  state: "healthy" | "running" | "error";
}

export interface MetricsReport {
  window_hours: number;
  generated_at: string;
  agents: Record<string, AgentMetrics>;
  totals: { invocations: number; cost_usd: number };
}

export interface McpTool {
  name: string;
  description: string;
  inputSchema?: { properties?: Record<string, { type?: string }>; required?: string[] };
}

export type AgentState = AgentMetrics["state"] | "idle";

export interface AgentView {
  id: string;
  index: number;
  display: string;
  purpose: string;
  input_type: string;
  output_type: string;
  models: string[];
  /** true if the orchestrator or any of its sub-agents calls an LLM */
  llm_backed: boolean;
  sub_agents: { name: string; qualified_name: string; role: string; description: string; llm: boolean; metrics: AgentMetrics | null }[];
  metrics: AgentMetrics | null;
  state: AgentState;
}

export const titleCase = (id: string): string =>
  id.split("_").map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(" ");

const modelLabel = (m: { size?: string } | null): string | null => (m?.size ? `${m.size}-class LLM` : null);

/** Merge the manifest with live metrics; order follows the real pipeline, not alphabetical discovery order. */
export function buildAgents(manifest: AgentsManifest, metrics: MetricsReport | null): AgentView[] {
  const order = manifest.graph?.order ?? [];
  const pos = (a: ManifestAgent) => {
    const i = order.indexOf(a.name);
    return i >= 0 ? i : (a.pipeline_index ?? 1000) - 1 + 500;
  };
  return [...manifest.agents]
    .sort((a, b) => pos(a) - pos(b) || a.name.localeCompare(b.name))
    .map((a, i) => {
      const own = metrics?.agents[a.name] ?? null;
      const subs = a.sub_agents.map((s) => ({
        name: s.name,
        qualified_name: s.qualified_name,
        role: s.role,
        description: s.description,
        llm: s.is_llm_backed,
        metrics: metrics?.agents[s.qualified_name] ?? metrics?.agents[s.name] ?? null,
      }));
      const models = [
        ...new Set(
          [modelLabel(a.primary_model), ...a.sub_agents.map((s) => modelLabel(s.primary_model))].filter((m): m is string => !!m),
        ),
      ];
      const llm = a.is_llm_backed || a.sub_agents.some((s) => s.is_llm_backed);
      return {
        id: a.name,
        index: i + 1,
        display: titleCase(a.name),
        purpose: a.description,
        input_type: a.input_schema,
        output_type: a.output_schema,
        models,
        llm_backed: llm,
        sub_agents: subs,
        metrics: own,
        state: own ? own.state : ("idle" as const),
      };
    });
}

/** Edges that are conditional in the compiled graph, as readable text (e.g. "necessity_reasoner → review_gate"). */
export function conditionalBranches(graph: PipelineGraph | null): string[] {
  return (graph?.edges ?? []).filter((e) => e.conditional).map((e) => `${e.source} → ${e.target}`);
}

export function mcpArgs(t: McpTool): { name: string; type: string; required: boolean }[] {
  const props = t.inputSchema?.properties ?? {};
  const req = new Set(t.inputSchema?.required ?? []);
  return Object.entries(props).map(([name, p]) => ({ name, type: p.type ?? "any", required: req.has(name) }));
}
