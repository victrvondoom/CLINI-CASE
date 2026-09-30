import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AgentHealthPanel } from "../src/components/AgentHealthPanel";
import { ComplianceScorecardCard } from "../src/components/ComplianceScorecardCard";
import { TopBar } from "../src/components/TopBar";
import { api } from "../src/lib/api";
import { buildNotifications, EMPTY_SNAPSHOT, resetSnapshotCache, type FeedSnapshot } from "../src/lib/liveFeed";

vi.mock("../src/components/AuthContext", () => ({ useAuth: () => ({ user: { id: "u", email: "a@b.c", full_name: "Ann Lee", role: "admin", organization_id: "o", organization_name: "Org" }, logout: vi.fn() }) }));
vi.mock("../src/components/ProfilePanel", () => ({ ProfilePanel: () => null }));
vi.mock("../src/lib/api", async (orig) => ({ ...(await orig<typeof import("../src/lib/api")>()), api: { getCaseCompliance: vi.fn() } }));

const j = (b: unknown, status = 200) => new Response(JSON.stringify(b), { status });
const stub = (routes: Record<string, unknown | (() => Response)>) =>
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    const k = Object.keys(routes).find((x) => url.includes(x));
    if (!k) return j({ detail: "no" }, 404);
    const v = routes[k];
    return typeof v === "function" ? (v as () => Response)() : j(v);
  }));

beforeEach(() => { resetSnapshotCache(); localStorage.clear(); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.resetAllMocks(); });

const sub = (n: string) => ({ name: n, qualified_name: `x.${n}`, role: "r", description: "d", is_llm_backed: false, primary_model: null });
const manifest = { n_agents: 2, n_sub_agents: 2, agents: [
  { name: "policy_retriever", role: "r", description: "d", input_schema: "I", output_schema: "O", is_llm_backed: false, primary_model: null, pipeline_index: 2, sub_agents: [sub("a")] },
  { name: "clinical_extractor", role: "r", description: "d", input_schema: "I", output_schema: "O", is_llm_backed: false, primary_model: null, pipeline_index: 1, sub_agents: [sub("b")] }],
  graph: { nodes: [], edges: [], order: ["clinical_extractor", "policy_retriever"] } };
const m = (over = {}) => ({ invocations: 10, success_pct: 90, errors: 1, running: 0, p50_ms: 800, p95_ms: 2400, mean_input_tokens: 1, mean_output_tokens: 1, cost_usd: 0.1, model_id: null, last_run_at: null, state: "healthy", ...over });

describe("Dashboard agent health is real", () => {
  it("lists agents in pipeline order with real success/p95 and idle agents as dashes", async () => {
    stub({ "/agents/manifest": manifest, "/agents/metrics": { window_hours: 24, generated_at: "x", totals: { invocations: 10, cost_usd: 0.1 }, agents: { clinical_extractor: m() } } });
    render(<AgentHealthPanel />);
    await waitFor(() => expect(screen.getByTestId("agent-health-clinical_extractor").textContent).toMatch(/Clinical Extractor90\.0%2\.4s/));
    const rows = screen.getAllByTestId(/^agent-health-/).filter((e) => e.getAttribute("data-testid") !== "agent-health");
    expect(rows.map((r) => r.getAttribute("data-testid"))).toEqual(["agent-health-clinical_extractor", "agent-health-policy_retriever"]);
    expect(screen.getByTestId("agent-health-policy_retriever").textContent).toMatch(/Policy Retriever—\s*—|Policy Retriever——/);
    expect(screen.queryByText(/99\.4%|31\.2s|52\.4s/)).toBeNull(); // the old invented numbers
    expect(screen.getByText(/10 runs/)).toBeTruthy();
  });

  it("flags unavailable metrics but still shows the agents", async () => {
    stub({ "/agents/manifest": manifest, "/agents/metrics": () => j({ detail: "Agent metrics need the case database" }, 503) });
    render(<AgentHealthPanel />);
    expect((await screen.findByTestId("agent-health-metrics-error")).textContent).toMatch(/case database/);
    expect(screen.getByTestId("agent-health-clinical_extractor")).toBeTruthy();
  });
});

describe("Compliance scorecard never fabricates a passing result", () => {
  it("shows the error instead of a canned all-satisfied scorecard when the API fails", async () => {
    vi.mocked(api.getCaseCompliance).mockRejectedValue(new Error("HTTP 503"));
    render(<ComplianceScorecardCard caseId="c1" />);
    expect(await screen.findByText(/Could not compute scorecard: HTTP 503/)).toBeTruthy();
    expect(screen.queryByText(/AUDIT-READY|76\.5s|Decision in/)).toBeNull();
  });
});

const snap = (o: Partial<FeedSnapshot>): FeedSnapshot => ({ ...EMPTY_SNAPSHOT, ...o });

describe("notification rules", () => {
  it("emits nothing for a healthy idle system, and actionable items otherwise", () => {
    expect(buildNotifications(snap({ health: { status: "ok", db: "connected" }, cases: { total: 5, awaiting: 0 }, onco: { open_alerts: 0, patients: 8, ledger_valid: true }, agents: { invocations: 3, errors: 0, hours: 24 } }))).toEqual([]);
    const n = buildNotifications(snap({ cases: { total: 5, awaiting: 2 }, onco: { open_alerts: 3, patients: 8, ledger_valid: false }, cardio: { integrity: false, version: "1", cad_auc: null }, agents: { invocations: 3, errors: 1, hours: 24 } }));
    expect(n.map((x) => x.key)).toEqual(["awaiting", "onco-alerts", "onco-ledger", "cardio-integrity", "agent-errors"]);
    expect(n[0]).toMatchObject({ title: "2 cases awaiting human review", to: "/reviewer" });
  });
});

describe("TopBar notifications bell", () => {
  const backend = (awaiting: number) => stub({
    "/healthz": { status: "ok", db: "connected" }, "status=awaiting_review": { total: awaiting }, "/cases?limit=1": { total: 9 } });
  const mount = () => render(<MemoryRouter><TopBar onOpenSearch={vi.fn()} /></MemoryRouter>);

  it("shows real, linkable notifications with an unread count, and remembers 'mark all read'", async () => {
    backend(3);
    mount();
    const bell = screen.getByRole("button", { name: "Notifications" });
    await waitFor(() => expect(bell.textContent).toBe("1"));
    fireEvent.click(bell);
    const item = await screen.findByTestId("notif-awaiting");
    expect(item.textContent).toMatch(/3 cases awaiting human review/);
    expect(item.querySelector("a")?.getAttribute("href")).toBe("/reviewer");
    expect(screen.queryByText(/Demo: approval event|sample/)).toBeNull();
    fireEvent.click(screen.getByText("Mark all read"));
    await waitFor(() => expect(screen.getByRole("button", { name: "Notifications" }).textContent).toBe(""));
    expect(JSON.parse(localStorage.getItem("clincase-notifs-read")!)).toEqual(["awaiting:3"]);
  });

  it("says all clear when there is nothing to act on", async () => {
    backend(0);
    mount();
    fireEvent.click(screen.getByRole("button", { name: "Notifications" }));
    expect((await screen.findByTestId("notif-empty")).textContent).toMatch(/Nothing needs your attention/);
    expect(screen.getByTestId("notif-count").textContent).toBe("all clear");
  });
});
