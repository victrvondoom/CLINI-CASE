import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { api } from "../src/lib/api";
import type { CohortReport } from "../src/lib/types";
import Cohorts from "../src/routes/Cohorts";

vi.mock("../src/lib/api", () => ({ api: { getCohorts: vi.fn() } }));
afterEach(() => { cleanup(); vi.resetAllMocks(); });

const report = (over: Partial<CohortReport> = {}): CohortReport => ({
  window_days: 90, generated_at: "2026-09-30T00:00:00+00:00", total_cases: 12, decided_cases: 9, pending_cases: 3,
  verdicts: { APPROVE: 6, DENY: 2, REFER: 1 },
  approval_by_payer: [{ payer: "aetna", decided: 5, approve: 4, deny: 1, refer: 0, rate: 80 }, { payer: "uhc", decided: 4, approve: 2, deny: 1, refer: 1, rate: 50 }],
  time_to_decision: { buckets: [{ bucket: "< 1m", count: 2 }, { bucket: "1-3m", count: 5 }], timed_cases: 7, median_seconds: 95, p90_seconds: 200 },
  verdict_by_treatment: [{ treatment: "trastuzumab", approve: 4, deny: 1, refer: 0 }],
  status_counts: { approved: 6 },
  insights: [{ id: "payer-approval-gap", accent: "blue", metric: "30 pp", metric_label: "approval-rate gap between payers", title: "aetna approves 80% vs uhc 50%", detail: "d", link: { label: "View cases", to: "/cases" } }],
  min_group_size: 3, ...over,
});
const mount = () => render(<MemoryRouter><Cohorts /></MemoryRouter>);

describe("Cohorts page is driven by the API, not fixtures", () => {
  it("renders the real counts, insights and per-payer numbers it is given", async () => {
    vi.mocked(api.getCohorts).mockResolvedValue(report());
    mount();
    expect((await screen.findByTestId("cohorts-summary")).textContent).toMatch(/12.*cases.*last 90 days.*9.*decided.*3.*pending/);
    expect(screen.getByTestId("insight-payer-approval-gap").textContent).toMatch(/aetna approves 80% vs uhc 50%/);
    expect(screen.getByText("aetna")).toBeTruthy();
    expect(screen.getByText("80%")).toBeTruthy();
    expect(screen.queryByText(/124/)).toBeNull(); // the old hard-coded case count is gone
  });

  it("changes when the data changes (switching the window refetches)", async () => {
    vi.mocked(api.getCohorts).mockImplementation(async (d) => (d === 30 ? report({ window_days: 30, total_cases: 4, decided_cases: 4, pending_cases: 0 }) : report()));
    mount();
    await screen.findByTestId("cohorts-summary");
    fireEvent.click(screen.getByRole("button", { name: "30 days" }));
    await waitFor(() => expect(screen.getByTestId("cohorts-summary").textContent).toMatch(/4.*cases.*last 30 days/));
    expect(api.getCohorts).toHaveBeenCalledWith(30);
  });

  it("shows an honest empty state when the organisation has no cases", async () => {
    vi.mocked(api.getCohorts).mockResolvedValue(report({ total_cases: 0, decided_cases: 0, pending_cases: 0, approval_by_payer: [], verdict_by_treatment: [], insights: [], time_to_decision: { buckets: [], timed_cases: 0, median_seconds: null, p90_seconds: null } }));
    mount();
    expect((await screen.findByTestId("cohorts-empty")).textContent).toMatch(/No cases in the last 90 days/);
    expect(screen.queryByTestId("insight-payer-approval-gap")).toBeNull();
  });

  it("explains missing insights instead of inventing them", async () => {
    vi.mocked(api.getCohorts).mockResolvedValue(report({ insights: [] }));
    mount();
    expect((await screen.findByTestId("cohorts-no-insights")).textContent).toMatch(/at least 3 decided/);
  });

  it("surfaces backend failures with a retry, and recovers", async () => {
    vi.mocked(api.getCohorts).mockRejectedValueOnce(new Error("Cohort analytics need the case database")).mockResolvedValue(report());
    mount();
    expect((await screen.findByTestId("cohorts-error")).textContent).toMatch(/case database/);
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    await screen.findByTestId("cohorts-summary");
    await waitFor(() => expect(screen.queryByTestId("cohorts-error")).toBeNull());
  });
});
