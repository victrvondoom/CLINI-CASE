import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { api, type OrgValueRollup } from "../src/lib/api";
import Dashboard from "../src/routes/Dashboard";

vi.mock("../src/lib/api", () => ({ api: { listFixtures: vi.fn(), getOrgValue: vi.fn(), listCases: vi.fn(), createFromFixture: vi.fn() } }));
vi.mock("../src/components/AgentHealthPanel", () => ({ AgentHealthPanel: () => <div /> }));
vi.mock("../src/components/RecentCasesRibbon", () => ({ RecentCasesRibbon: () => <div /> }));
vi.mock("../src/components/LivePipelineConsole", () => ({ LivePipelineConsole: () => <div /> }));
afterEach(() => { cleanup(); vi.resetAllMocks(); vi.unstubAllGlobals(); });

const rollup = (over: Partial<OrgValueRollup> = {}): OrgValueRollup => ({
  organization_id: "o", asof_iso: "x", cases_total: 14, cases_decided: 9, verdict_breakdown: {}, direct_savings_mtd_usd: 12345, direct_savings_annual_projection_usd: 246000,
  avg_decision_seconds: 42.5, avg_speedup_factor: 25.4, citations: [], daily_cases_7d: [0, 1, 2, 0, 3, 4, 4], avg_decision_change_pct: -31.5,
  assumptions: { manual_pa_cost_usd: 1200, manual_pa_minutes: 20 }, ...over });
const sub = { name: "s", qualified_name: "x.s", role: "r", description: "d", is_llm_backed: false, primary_model: null };
const ag = (name: string, i: number) => ({ name, role: "r", description: "d", input_schema: "I", output_schema: "O", is_llm_backed: false, primary_model: null, pipeline_index: i, sub_agents: [sub] });
beforeEach(() => {
  vi.mocked(api.listFixtures).mockResolvedValue([]);
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    if (url.includes("/agents/manifest")) return new Response(JSON.stringify({ n_agents: 2, n_sub_agents: 5, agents: [ag("policy_retriever", 2), ag("clinical_extractor", 1)], graph: { nodes: [], edges: [], order: ["clinical_extractor", "policy_retriever"] } }));
    if (url.includes("/capabilities")) return new Response(JSON.stringify({ deployment: { llm_provider: "bedrock", bedrock_model_id: "model-x" } }));
    return new Response("{}", { status: 404 });
  }));
});
const mount = () => render(<MemoryRouter><Dashboard /></MemoryRouter>);

describe("Dashboard KPI tiles are computed, not typed in", () => {
  it("uses the org's own values, trend and baselines from the API", async () => {
    vi.mocked(api.getOrgValue).mockResolvedValue(rollup());
    mount();
    await waitFor(() => expect(screen.getByText("14")).toBeTruthy());
    expect(screen.getByText("CASES · MTD")).toBeTruthy();
    expect(screen.getByText("9 decided MTD")).toBeTruthy();
    expect(screen.getByText("42.5s")).toBeTruthy();
    expect(screen.getByText(/25\.4× faster than the 20-min manual baseline/)).toBeTruthy(); // baseline from the API, not "18"
    expect(screen.getByText(/vs \$1,200 \/ case manual baseline/)).toBeTruthy();
    expect(screen.getByText(/31\.5/)).toBeTruthy(); // real month-over-month change, not a fixed −98
    expect(screen.queryByText(/98/)).toBeNull();
  });

  it("shows no trend or sparkline when there is nothing real to plot", async () => {
    vi.mocked(api.getOrgValue).mockResolvedValue(rollup({ daily_cases_7d: [0, 0, 0, 0, 0, 0, 0], avg_decision_change_pct: null, cases_total: 0, cases_decided: 0, avg_decision_seconds: null, avg_speedup_factor: null }));
    mount();
    await waitFor(() => expect(screen.getByText("0 decided MTD")).toBeTruthy());
    expect(screen.queryByText(/%/)).toBeNull();
  });
});

describe("Dashboard DAG summary is read from the manifest", () => {
  it("shows the live agent / sub-agent counts, pipeline order and provider", async () => {
    vi.mocked(api.getOrgValue).mockResolvedValue(rollup());
    mount();
    await waitFor(() => expect(screen.getByTestId("dag-summary").textContent).toBe("2-AGENT LANGGRAPH DAG · 5 SUB-AGENTS"));
    expect(screen.getByTestId("dag-flow").textContent).toBe("Clinical Extractor → Policy Retriever");
    expect(screen.getByTestId("dag-provider").textContent).toMatch(/bedrock · model-x/);
    expect(screen.queryByText(/Claude Sonnet 4\.6/)).toBeNull();
  });
});
