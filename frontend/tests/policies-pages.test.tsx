import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { api } from "../src/lib/api";
import type { PolicyCatalog, PolicyDetail } from "../src/lib/types";
import PolicyDiff from "../src/routes/PolicyDiff";
import Policies from "../src/routes/Policies";

vi.mock("../src/lib/api", () => ({ api: { getPolicyCatalog: vi.fn(), getPolicyDetail: vi.fn() } }));
afterEach(() => { cleanup(); vi.resetAllMocks(); vi.unstubAllGlobals(); });

const catalog = (over: Partial<PolicyCatalog> = {}): PolicyCatalog => ({
  n: 2, payers: ["aetna", "uhc"], n_with_recent_change: 1, snapshot: { taken_at: "2026-05-06T14:32:00Z", version: "demo" },
  policies: [
    { payer_id: "aetna", policy_id: "0421", title: "Olaparib (Lynparza)", treatment_keywords: ["olaparib"], source_url: "https://x", section_count: 2, word_count: 321, recent_change_at: "2026-04-29T09:15:00Z", has_recent_change: true },
    { payer_id: "uhc", policy_id: "D045", title: "Osimertinib", treatment_keywords: ["osimertinib"], source_url: null, section_count: 1, word_count: 99, recent_change_at: null, has_recent_change: false },
  ], ...over });

function mountPolicies() {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ n: 0, backend: "local", bucket: null, policies: [] }))));
  return render(<MemoryRouter><Policies /></MemoryRouter>);
}

describe("Policy library reads the real catalog", () => {
  it("shows computed counts, per-policy stats and the payers that exist in the data", async () => {
    vi.mocked(api.getPolicyCatalog).mockResolvedValue(catalog());
    mountPolicies();
    await waitFor(() => expect(screen.getByTestId("policy-count").textContent).toBe("2"));
    expect(screen.getByTestId("payer-count").textContent).toBe("2");
    expect(screen.getByText("Olaparib (Lynparza)")).toBeTruthy();
    expect(screen.getByText(/2 sections · 321 words/)).toBeTruthy();
    expect(screen.getByText(/1 policy updated recently/)).toBeTruthy();
    expect(screen.getByText(/change recorded/)).toBeTruthy();
    expect(screen.getByText("no recorded change")).toBeTruthy(); // no invented "updated 14 days ago"
  });

  it("filters the fetched policies and derives the payer dropdown from data", async () => {
    vi.mocked(api.getPolicyCatalog).mockResolvedValue(catalog());
    mountPolicies();
    await screen.findByText("Olaparib (Lynparza)");
    fireEvent.change(screen.getByPlaceholderText(/Search by treatment/), { target: { value: "osimertinib" } });
    expect(screen.queryByText("Olaparib (Lynparza)")).toBeNull();
    expect(screen.getByText("Osimertinib")).toBeTruthy();
    expect(screen.queryByRole("option", { name: "Anthem" })).toBeNull(); // no payer in the data → no option
  });

  it("shows an error with retry when the catalog cannot load", async () => {
    vi.mocked(api.getPolicyCatalog).mockRejectedValue(new Error("HTTP 500"));
    mountPolicies();
    expect((await screen.findByTestId("catalog-error")).textContent).toMatch(/HTTP 500/);
  });
});

const detail = (over: Partial<PolicyDetail> = {}): PolicyDetail => ({
  ...catalog().policies[0], sections: [{ heading: "Initial Criteria", page_number: 2, word_count: 120, text: "BRCA-mutated…" }],
  diffs: [{ payer: "Aetna", treatment: "olaparib", policy_id: "AETNA-CPB-0084", version_old: "v2024.08", version_new: "v2026.04", changed_at: "2026-04-29T09:15:00Z",
    summary: "Added HRD-positive indication.", diff: [{ action: "added", section: "Indications", text: "HRD-positive ovarian cancer." }, { action: "removed", section: "Step therapy", text: "Prior platinum required." }] }],
  related: [{ payer_id: "uhc", policy_id: "D045", title: "Osimertinib" }],
  snapshot: { taken_at: "2026-05-06T14:32:00Z", version: "demo-2026.05", note: "Demo snapshot of recorded changes." },
  open_cases: [{ case_id: "abc", patient: "R.K.", treatment: "olaparib", status: "awaiting_review", created_at: "2026-09-01T00:00:00Z" }],
  open_cases_available: true, ...over });

const mountDetail = () => render(<MemoryRouter initialEntries={["/policies/0421/diff"]}><Routes><Route path="/policies/:policyId/diff" element={<PolicyDiff />} /></Routes></MemoryRouter>);

describe("Policy detail is built from the API, not fixtures", () => {
  it("renders recorded changes, the org's open cases and the sections", async () => {
    vi.mocked(api.getPolicyDetail).mockResolvedValue(detail());
    mountDetail();
    expect((await screen.findByTestId("diff-card")).textContent).toMatch(/v2024\.08.*v2026\.04.*Added HRD-positive indication/s);
    expect(screen.getByText("HRD-positive ovarian cancer.")).toBeTruthy();
    expect(screen.getByTestId("open-case").textContent).toMatch(/R\.K\..*olaparib.*awaiting review/i);
    expect(screen.getByText(/Demo snapshot of recorded changes/)).toBeTruthy();
    expect(api.getPolicyDetail).toHaveBeenCalledWith("0421");
    fireEvent.click(screen.getByRole("button", { name: /Initial Criteria/ }));
    expect(screen.getByText("BRCA-mutated…")).toBeTruthy();
  });

  it("says so plainly when no change is recorded and no open case is affected", async () => {
    vi.mocked(api.getPolicyDetail).mockResolvedValue(detail({ diffs: [], open_cases: [] }));
    mountDetail();
    expect((await screen.findByTestId("no-diffs")).textContent).toMatch(/No change is recorded/);
    expect(screen.getByTestId("no-open-cases")).toBeTruthy();
    expect(screen.queryByTestId("diff-card")).toBeNull();
  });

  it("is honest when the case database is unavailable", async () => {
    vi.mocked(api.getPolicyDetail).mockResolvedValue(detail({ open_cases: [], open_cases_available: false }));
    mountDetail();
    expect(await screen.findByText(/case database is unavailable/)).toBeTruthy();
  });

  it("shows a 404 / error state with a way back", async () => {
    vi.mocked(api.getPolicyDetail).mockRejectedValue(new Error("Policy '0421' is not in the corpus"));
    mountDetail();
    expect((await screen.findByTestId("policy-error")).textContent).toMatch(/not in the corpus/);
  });
});
