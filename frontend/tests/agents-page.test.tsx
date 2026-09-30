import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { buildAgents, conditionalBranches, mcpArgs, titleCase, type AgentsManifest, type MetricsReport } from "../src/lib/agentsModel";
import Agents from "../src/routes/Agents";

const sub = (name: string, parent: string, llm = false) => ({ name, qualified_name: `${parent}.${name}`, role: `${name}_role`, description: "d", is_llm_backed: llm, primary_model: llm ? { size: "haiku" } : null });
const agent = (name: string, idx: number, subs = [sub("s1", name)]) => ({ name, role: "r", description: `${name} purpose`, input_schema: `${name}In`, output_schema: `${name}Out`, is_llm_backed: false, primary_model: null, pipeline_index: idx, sub_agents: subs });

// alphabetical (discovery) order on purpose: the page must reorder by the real graph
const MANIFEST: AgentsManifest = {
  n_agents: 3, n_sub_agents: 4,
  agents: [agent("appeals_drafter", 3), agent("clinical_extractor", 1, [sub("bio", "clinical_extractor", true), sub("val", "clinical_extractor")]), agent("policy_retriever", 2)],
  graph: {
    nodes: ["clinical_extractor", "policy_retriever", "appeals_drafter", "review_gate"],
    order: ["clinical_extractor", "policy_retriever", "appeals_drafter"],
    edges: [{ source: "clinical_extractor", target: "policy_retriever", conditional: false }, { source: "policy_retriever", target: "appeals_drafter", conditional: true }, { source: "policy_retriever", target: "review_gate", conditional: true }],
  },
};
const METRICS: MetricsReport = {
  window_hours: 24, generated_at: "x", totals: { invocations: 17, cost_usd: 0.42 },
  agents: {
    clinical_extractor: { invocations: 12, success_pct: 91.7, errors: 1, running: 0, p50_ms: 1500, p95_ms: 4200, mean_input_tokens: 2000, mean_output_tokens: 400, cost_usd: 0.3, model_id: "claude-sonnet-4-6", last_run_at: "2026-01-01T00:00:00Z", state: "healthy" },
    "clinical_extractor.bio": { invocations: 12, success_pct: 100, errors: 0, running: 0, p50_ms: 400, p95_ms: 900, mean_input_tokens: 10, mean_output_tokens: 5, cost_usd: 0.01, model_id: "haiku", last_run_at: null, state: "healthy" },
    policy_retriever: { invocations: 5, success_pct: 40, errors: 3, running: 0, p50_ms: 800, p95_ms: 900, mean_input_tokens: 1, mean_output_tokens: 1, cost_usd: 0.12, model_id: null, last_run_at: null, state: "error" },
  },
};
const MCP = { tools: [{ name: "policy_lookup", description: "look up", inputSchema: { properties: { payer_id: { type: "string" } }, required: ["payer_id"] } }], endpoint: "/mcp", spec_version: "2024-11-05" };

function mockFetch(over: { metrics?: () => Response | Promise<Response> } = {}) {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    const j = (b: unknown, status = 200) => new Response(JSON.stringify(b), { status, headers: { "Content-Type": "application/json" } });
    if (url.includes("/agents/manifest")) return j(MANIFEST);
    if (url.includes("/agents/metrics")) return over.metrics ? over.metrics() : j(METRICS);
    if (url.includes("/mcp/manifest")) return j(MCP);
    return j({ runs: [] });
  }));
}
beforeEach(() => mockFetch());
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe("agents view-model", () => {
  it("orders agents by the real pipeline, not discovery order, and merges metrics by name", () => {
    const v = buildAgents(MANIFEST, METRICS);
    expect(v.map((a) => a.id)).toEqual(["clinical_extractor", "policy_retriever", "appeals_drafter"]);
    expect(v.map((a) => a.index)).toEqual([1, 2, 3]);
    expect(v[0].metrics?.invocations).toBe(12);
    expect(v[0].sub_agents.find((s) => s.name === "bio")?.metrics?.invocations).toBe(12); // qualified-name lookup
    expect(v[0].models).toEqual(["haiku-class LLM"]);
    expect(v[2].state).toBe("idle"); // no runs → idle, never a made-up "healthy"
  });
  it("derives conditional branches and MCP args from data", () => {
    expect(conditionalBranches(MANIFEST.graph)).toEqual(["policy_retriever → appeals_drafter", "policy_retriever → review_gate"]);
    expect(mcpArgs(MCP.tools[0])).toEqual([{ name: "payer_id", type: "string", required: true }]);
    expect(titleCase("clinical_extractor")).toBe("Clinical Extractor");
  });
});

describe("Agents page reads live data", () => {
  it("shows real totals, per-agent stats, idle agents and live MCP tools", async () => {
    render(<Agents />);
    await waitFor(() => expect(screen.getByTestId("agents-summary").textContent).toMatch(/3.*parent agents.*4.*sub-agents.*17.*invocations.*\$0\.42/));
    expect(screen.getByText("Clinical Extractor")).toBeTruthy();
    expect(screen.getByText("91.7%")).toBeTruthy();
    expect(screen.getByText("1.5s")).toBeTruthy();
    expect(screen.getAllByText("NO RUNS IN WINDOW").length).toBe(1); // appeals_drafter
    expect(screen.getByTestId("dag-branches").textContent).toMatch(/policy_retriever → review_gate/);
    expect(await screen.findByText("policy_lookup")).toBeTruthy();
    expect(screen.queryByText(/1,247/)).toBeNull(); // the old invented invocation count is gone
  });

  it("switching the window refetches metrics with that window", async () => {
    render(<Agents />);
    await screen.findByText("Clinical Extractor");
    fireEvent.click(screen.getByRole("button", { name: "7 d" }));
    await waitFor(() => expect((fetch as unknown as ReturnType<typeof vi.fn>).mock.calls.some((c) => String(c[0]).includes("hours=168"))).toBe(true));
  });

  it("still shows definitions when live metrics fail, with '—' instead of invented numbers", async () => {
    mockFetch({ metrics: () => new Response(JSON.stringify({ detail: "Agent metrics need the case database" }), { status: 503 }) });
    render(<Agents />);
    expect((await screen.findByTestId("agents-metrics-error")).textContent).toMatch(/case database/);
    expect(screen.getByText("Clinical Extractor")).toBeTruthy();
    expect(screen.getByTestId("agents-summary").textContent).toMatch(/—.*invocations/);
  });

  it("tells the user when there are simply no runs", async () => {
    mockFetch({ metrics: () => new Response(JSON.stringify({ window_hours: 24, generated_at: "x", agents: {}, totals: { invocations: 0, cost_usd: 0 } })) });
    render(<Agents />);
    expect((await screen.findByTestId("agents-no-runs")).textContent).toMatch(/No agent runs recorded/);
  });
});

describe("no fabricated status", () => {
  it("does not claim a contract test passed before one was run", async () => {
    render(<Agents />);
    await screen.findByText("Clinical Extractor");
    expect(screen.queryByText(/last passed/)).toBeNull();
    expect(screen.getAllByTestId("contract-not-run").length).toBe(3);
  });
});
