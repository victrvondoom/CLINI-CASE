import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../src/lib/api";
import type { CaseComparison, PayerColumn, PolicyCatalog } from "../src/lib/types";
import Compare from "../src/routes/Compare";
import Sandbox from "../src/routes/Sandbox";

vi.mock("../src/lib/api", () => ({ api: { getCaseComparison: vi.fn(), createComparisonCase: vi.fn(), getPolicyCatalog: vi.fn() } }));
afterEach(() => { cleanup(); vi.resetAllMocks(); localStorage.clear(); });

const pol = (id: string) => ({ policy_id: id, title: "t", source_url: null, section_count: 3, has_recent_change: false });
const col = (payer_id: string, over: Partial<PayerColumn> = {}): PayerColumn => ({ payer_id, name: payer_id.toUpperCase(), is_this_case: false, policy: pol(`P-${payer_id}`), case: null, decision: null, state: "not_started", can_create: true, ...over });
const comparison = (payers: PayerColumn[], rec = { primary: null as string | null, fallback: null as string | null, summary: "Only one payer has a recorded decision." }): CaseComparison => ({
  case_id: "case_1", treatment: "Trastuzumab", j_code: "J9355", patient: "S.D.", payer_id: "aetna", payers, recommendation: rec, method: "Recorded decisions only." });
const mount = () => render(<MemoryRouter initialEntries={["/cases/case_1/compare"]}><Routes>
  <Route path="/cases/:caseId/compare" element={<Compare />} /><Route path="/cases/:caseId" element={<div data-testid="case-page" />} /></Routes></MemoryRouter>);

describe("Compare shows recorded outcomes, never simulated ones", () => {
  it("renders real decisions and policies, and no invented latency / cost / auth codes", async () => {
    vi.mocked(api.getCaseComparison).mockResolvedValue(comparison([
      col("aetna", { is_this_case: true, state: "decided", can_create: false, decision: { verdict: "DENY", confidence: 0.82, rationale: "LVEF too low.", decided_at: "x" } }),
      col("uhc"), col("bcbs", { policy: null, state: "no_policy", can_create: false }), col("anthem"),
    ]));
    mount();
    expect((await screen.findByTestId("verdict-aetna")).textContent).toMatch(/DENY.*82% confidence.*LVEF too low/s);
    expect(screen.getByTestId("policy-aetna").textContent).toMatch(/P-aetna.*3 sections/);
    expect(screen.getByTestId("payer-col-bcbs").textContent).toMatch(/No matching policy in the corpus/);
    expect(screen.getByTestId("recommendation").textContent).toMatch(/Only one payer/);
    expect(screen.queryByText(/LIVE|SIMULATED|MOCK|\$0\.0/)).toBeNull();
    expect(screen.queryByTestId("create-bcbs")).toBeNull(); // cannot create where there is no policy
  });

  it("marks the recommended payer only when the backend derived one from ≥2 recorded decisions", async () => {
    vi.mocked(api.getCaseComparison).mockResolvedValue(comparison([
      col("aetna", { is_this_case: true, state: "decided", can_create: false, decision: { verdict: "DENY", confidence: 0.8, rationale: null, decided_at: "x" } }),
      col("uhc", { state: "decided", can_create: false, decision: { verdict: "APPROVE", confidence: 0.9, rationale: null, decided_at: "x" } }),
    ], { primary: "uhc", fallback: "aetna", summary: "Ranked from recorded decisions only." }));
    mount();
    await screen.findByTestId("payer-col-uhc");
    expect(screen.getByTestId("payer-col-uhc").textContent).toMatch(/Recommended/);
    expect(screen.getByTestId("payer-col-aetna").textContent).not.toMatch(/Recommended/);
  });

  it("creates a comparison case for a payer and opens it", async () => {
    vi.mocked(api.getCaseComparison).mockResolvedValue(comparison([col("aetna", { is_this_case: true, state: "decided", can_create: false, decision: { verdict: "APPROVE", confidence: 0.9, rationale: null, decided_at: "x" } }), col("uhc")]));
    vi.mocked(api.createComparisonCase).mockResolvedValue({ case_id: "case_new", created: true, payer_id: "uhc" });
    mount();
    fireEvent.click(await screen.findByTestId("create-uhc"));
    await waitFor(() => expect(api.createComparisonCase).toHaveBeenCalledWith("case_1", "uhc"));
    expect(await screen.findByTestId("case-page")).toBeTruthy(); // navigated to the new case
  });

  it("shows create failures and load failures instead of pretending", async () => {
    vi.mocked(api.getCaseComparison).mockResolvedValue(comparison([col("aetna", { is_this_case: true, state: "decided", can_create: false, decision: null }), col("uhc")]));
    vi.mocked(api.createComparisonCase).mockRejectedValue(new Error("UHC has no policy on file for x."));
    mount();
    fireEvent.click(await screen.findByTestId("create-uhc"));
    expect((await screen.findByTestId("compare-error")).textContent).toMatch(/no policy on file/);
    cleanup();
    vi.mocked(api.getCaseComparison).mockRejectedValue(new Error("Case case_1 not found"));
    mount();
    expect((await screen.findByTestId("compare-error")).textContent).toMatch(/not found/);
  });
});

const catalog: PolicyCatalog = { n: 2, payers: ["aetna", "uhc"], n_with_recent_change: 0, snapshot: { taken_at: "x", version: "v" }, policies: [
  { payer_id: "aetna", policy_id: "0421", title: "Olaparib", treatment_keywords: ["olaparib", "lynparza"], source_url: null, section_count: 2, word_count: 10, recent_change_at: null, has_recent_change: false },
  { payer_id: "uhc", policy_id: "D045", title: "Osimertinib", treatment_keywords: ["osimertinib"], source_url: null, section_count: 1, word_count: 5, recent_change_at: null, has_recent_change: false }] };

describe("Sandbox options come from the live policy catalog", () => {
  beforeEach(() => vi.mocked(api.getPolicyCatalog).mockResolvedValue(catalog));

  it("offers exactly the catalog's treatments and payers", async () => {
    render(<MemoryRouter><Sandbox /></MemoryRouter>);
    await waitFor(() => expect(screen.queryByRole("option", { name: "Anthem" })).toBeNull());
    expect(screen.getByRole("option", { name: "olaparib" })).toBeTruthy();
    expect(screen.getByRole("option", { name: "osimertinib" })).toBeTruthy();
    expect(screen.queryByRole("option", { name: "bevacizumab" })).toBeNull(); // not in the catalog → not offered
  });

  it("labels results as a heuristic simulation and shows the real policy on file per payer", async () => {
    render(<MemoryRouter><Sandbox /></MemoryRouter>);
    await waitFor(() => expect(screen.queryByRole("option", { name: "Anthem" })).toBeNull());
    fireEvent.change(screen.getAllByRole("combobox")[0], { target: { value: "olaparib" } });
    fireEvent.click(screen.getByRole("button", { name: /Run scenario|Run/ }));
    expect(await screen.findByText(/SIMULATED · heuristic/)).toBeTruthy();
    expect((await screen.findByTestId("sandbox-policy-aetna")).textContent).toMatch(/real policy on file: 0421/);
    expect(screen.getByTestId("sandbox-policy-uhc").textContent).toMatch(/no policy on file/);
  });
});
