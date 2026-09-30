import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../src/lib/api";
import type { ReviewQueueReport } from "../src/lib/types";
import Reviewer from "../src/routes/Reviewer";

vi.mock("../src/lib/api", () => ({ api: { getReviewQueue: vi.fn(), submitReview: vi.fn(), listCases: vi.fn(), resumeCase: vi.fn() } }));
afterEach(() => { cleanup(); vi.resetAllMocks(); });

const item = (id: string, over = {}) => ({ case_id: id, patient: "S.D.", treatment: "trastuzumab", payer: "aetna", status: "referred", priority: "high" as const,
  reason: "Baseline LVEF outside window.", missing_evidence: "ECHO within 60 days", unresolved_criteria: 2, confidence: 0.5, age_minutes: 30, referred_at: "x", ...over });
const report = (items = [item("c1"), item("c2", { patient: "P.N.", treatment: "pembrolizumab", priority: "low", confidence: null, missing_evidence: null, age_minutes: 90 })]): ReviewQueueReport => ({
  generated_at: "x", total: items.length, priority_rule: "r", counts: { high: items.filter((i) => i.priority === "high").length, medium: 0, low: items.filter((i) => i.priority === "low").length }, items });
const mount = () => render(<MemoryRouter><Reviewer /></MemoryRouter>);

beforeEach(() => {
  vi.mocked(api.listCases).mockResolvedValue({ cases: [], total: 0 });
  vi.mocked(api.getReviewQueue).mockResolvedValue(report());
});

describe("Reviewer queue is the organisation's real queue", () => {
  it("renders exactly the cases the API returns, with derived counts and average wait", async () => {
    mount();
    expect((await screen.findByTestId("queue-total")).textContent).toBe("2");
    expect(screen.getByTestId("queue-item-c1")).toBeTruthy();
    expect(screen.getByTestId("queue-item-c2").textContent).toMatch(/pembrolizumab/);
    expect(screen.getByTestId("avg-wait").textContent).toBe("avg wait: 1h 0m"); // (30 + 90) / 2 = 60 min
    expect(screen.queryByText(/S\.D\..*trastuzumab.*case_8f4ad9c2/)).toBeNull();
    expect(screen.queryByText(/38m/)).toBeNull(); // the old invented average wait
  });

  it("handles missing model output honestly", async () => {
    mount();
    fireEvent.click(await screen.findByTestId("queue-item-c2"));
    expect(screen.getByText("None recorded by the Necessity Reasoner.")).toBeTruthy();
    expect(screen.getByText(/confidence —/)).toBeTruthy();
  });

  it("shows an empty state and an error state instead of fake rows", async () => {
    vi.mocked(api.getReviewQueue).mockResolvedValue(report([]));
    mount();
    expect((await screen.findByTestId("queue-empty")).textContent).toMatch(/No REFER cases are waiting/);
    cleanup();
    vi.mocked(api.getReviewQueue).mockRejectedValue(new Error("The reviewer queue needs the case database"));
    mount();
    expect((await screen.findByTestId("queue-error")).textContent).toMatch(/case database/);
    expect(screen.queryByTestId("queue-item-c1")).toBeNull();
  });

  it("records a review only when the backend confirms it, and refreshes the queue", async () => {
    vi.mocked(api.submitReview).mockResolvedValue({ case_id: "c1", action: "override_to_approve", new_status: "approved" } as never);
    mount();
    fireEvent.click(await screen.findByTestId("queue-item-c1"));
    fireEvent.click(screen.getByRole("button", { name: /Override → APPROVE/ }));
    await waitFor(() => expect(api.submitReview).toHaveBeenCalledWith("c1", { action: "override_to_approve", note: undefined }));
    await waitFor(() => expect(api.getReviewQueue).toHaveBeenCalledTimes(2)); // reloaded from the server
    expect(await screen.findByText(/Recent actions \(1\)/)).toBeTruthy();
  });

  it("NEVER pretends a review succeeded when the API call fails", async () => {
    vi.mocked(api.submitReview).mockRejectedValue(new Error("HTTP 500"));
    mount();
    fireEvent.click(await screen.findByTestId("queue-item-c1"));
    fireEvent.click(screen.getByRole("button", { name: /Override → DENY/ }));
    expect(await screen.findByText(/HTTP 500/)).toBeTruthy();
    expect(screen.queryByText(/Recent actions/)).toBeNull(); // nothing recorded
    expect(screen.getByTestId("queue-item-c1")).toBeTruthy(); // case stays in the queue
  });
});
