import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CaseEconomicsStrip, runCostUsd } from "../src/components/CaseEconomicsStrip";
import { api } from "../src/lib/api";

vi.mock("../src/lib/api", () => ({ api: { getAudit: vi.fn(), getCaseValue: vi.fn() } }));
afterEach(() => { cleanup(); vi.resetAllMocks(); });

const pricing = { sonnet: { in: 3, out: 15 }, haiku: { in: 1, out: 5 } };
const run = (model_id: string | null, i: number, o: number, latency_ms = 1000) => ({ id: 1, agent_name: "a", model_id, input_tokens: i, output_tokens: o, latency_ms, started_at: "x", finished_at: "x", error_text: null });

describe("per-run costing by model family", () => {
  it("prices haiku and sonnet differently and treats unknown models as sonnet", () => {
    expect(runCostUsd({ model_id: "us.anthropic.claude-haiku-4-5", input_tokens: 1_000_000, output_tokens: 1_000_000 }, pricing)).toBe(6);
    expect(runCostUsd({ model_id: "claude-sonnet", input_tokens: 1_000_000, output_tokens: 1_000_000 }, pricing)).toBe(18);
    expect(runCostUsd({ model_id: null, input_tokens: null, output_tokens: null }, pricing)).toBe(0);
  });
});

describe("Case economics strip quotes the backend's baseline", () => {
  it("shows cost from actual runs and savings against the API's manual baseline", async () => {
    vi.mocked(api.getAudit).mockResolvedValue({ agent_runs: [run("claude-sonnet", 1_000_000, 100_000, 30_000), run("claude-haiku", 500_000, 50_000, 30_000)] } as never);
    vi.mocked(api.getCaseValue).mockResolvedValue({ manual_cost_usd: 1500, manual_minutes: 18, token_pricing_usd_per_m: pricing } as never);
    render(<CaseEconomicsStrip caseId="c1" />);
    await waitFor(() => expect(screen.getByText("$5.2500")).toBeTruthy()); // 4.5 (sonnet) + 0.75 (haiku)
    expect(screen.getByText("$1494.75 saved")).toBeTruthy();
    expect(screen.getByText(/17 min faster than the 18-min manual baseline/)).toBeTruthy();
    expect(screen.getByText(/\$1,500 \/ 18 min per manual PA/)).toBeTruthy();
    expect(screen.queryByText(/\$32\/hr|11 min/)).toBeNull(); // the old, contradictory baseline is gone
  });

  it("degrades to dashes rather than inventing a baseline when the ROI call fails", async () => {
    vi.mocked(api.getAudit).mockResolvedValue({ agent_runs: [run("claude-sonnet", 1000, 100)] } as never);
    vi.mocked(api.getCaseValue).mockRejectedValue(new Error("down"));
    render(<CaseEconomicsStrip caseId="c1" />);
    await waitFor(() => expect(screen.getByText("baseline unavailable")).toBeTruthy());
  });
});
