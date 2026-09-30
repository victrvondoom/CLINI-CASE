import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import Metrics from "../src/landing/Metrics";
import * as health from "../src/landing/useSystemHealth";

vi.mock("../src/landing/CountUp", () => ({ default: ({ value }: { value: number | null }) => <span>{value == null ? "--" : String(value)}</span> }));
vi.mock("../src/landing/Reveal", () => ({ default: ({ children }: { children: React.ReactNode }) => <div>{children}</div> }));
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

const state = (over: Partial<health.HealthState>): health.HealthState => ({ health: { status: "ok", db: "x" }, capabilities: null, latencyMs: 12, loading: false, error: null, checkedAt: 1, ...over });

describe("landing 'live numbers' come from the deployment", () => {
  it("renders the counts the backend reports", () => {
    vi.spyOn(health, "useSystemHealth").mockReturnValue(state({ capabilities: { system: { agents: 7, sub_agents: 22, policies_indexed: 22, payers: 4 }, compliance: { cms_0057f_clauses_tracked: 8 } } }));
    render(<Metrics />);
    for (const [label, value] of [["agents in the pipeline", "7"], ["sub-agents", "22"], ["payer policies indexed", "22"], ["CMS-0057-F clauses tracked", "8"], ["this health check", "12ms"]]) {
      expect(screen.getByText(label).previousSibling?.textContent).toBe(value);
    }
    expect(screen.queryByText(/cancer programs covered|lifecycle stages/)).toBeNull();
  });

  it("shows '--' rather than a made-up number when capabilities are unavailable", () => {
    vi.spyOn(health, "useSystemHealth").mockReturnValue(state({ capabilities: null, latencyMs: null, health: null }));
    render(<Metrics />);
    expect(screen.getByText("sub-agents").previousSibling?.textContent).toBe("--");
    expect(screen.getByText("this health check").previousSibling?.textContent).toBe("--");
  });
});
