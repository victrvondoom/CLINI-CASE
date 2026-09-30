import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CaseTwinPanel } from "../src/components/CaseTwinPanel";
import { api } from "../src/lib/api";

vi.mock("../src/lib/api", () => ({ api: { getCaseTwin: vi.fn() } }));
afterEach(() => { cleanup(); vi.resetAllMocks(); });

const twin = (over: object = {}) => ({
  case_intelligence_id: "CI-ABCDEFGHIJKL", case_id: "c1",
  trace: { stages: [
    { stage: "policy_retriever", actor: "agent", offset_ms: 0, duration_ms: 2100, status: "ok" },
    { stage: "human_review", actor: "human", offset_ms: 5000, duration_ms: null, status: "waiting" },
  ], totals: { agent_ms: 2100, human_wait_ms: null, input_tokens: 1000, output_tokens: 200, estimated_cost_usd: 0.006 } },
  evidence: [{ evidence_id: "EV-1", kind: "clinical", pointer: "obs-her2", resolved: true, fhir_resource_type: "Observation", policy_version: null, first_seen_agent: "clinical_extractor" }],
  infrastructure_events: [{ event: "queued" }, { event: "claimed" }, { event: "done" }],
  integrity: { dangling_citations: [], citations_total: 1, all_clinical_citations_resolve: true },
  twin_sha256: "f".repeat(64),
  ...over,
});

describe("Case digital twin panel", () => {
  it("shows the case id, real stage timings, a waiting reviewer and resolved lineage", async () => {
    vi.mocked(api.getCaseTwin).mockResolvedValue(twin() as never);
    render(<CaseTwinPanel caseId="c1" />);
    await waitFor(() => expect(screen.getByTestId("ciid").textContent).toBe("CI-ABCDEFGHIJKL"));
    expect(screen.getByText("2.1 s")).toBeTruthy();
    expect(screen.getByText("waiting for reviewer")).toBeTruthy();
    expect(screen.getByText(/Every clinical citation resolves/)).toBeTruthy();
    expect(screen.getByText(/queued → claimed → done/)).toBeTruthy();
  });

  it("flags a citation that points at a FHIR resource that was never submitted", async () => {
    vi.mocked(api.getCaseTwin).mockResolvedValue(twin({
      evidence: [{ evidence_id: "EV-9", kind: "clinical", pointer: "obs-ghost", resolved: false }],
      integrity: { dangling_citations: ["EV-9"], citations_total: 1, all_clinical_citations_resolve: false },
    }) as never);
    render(<CaseTwinPanel caseId="c1" />);
    await waitFor(() => expect(screen.getByRole("alert").textContent).toMatch(/1 clinical citation\(s\) point to a FHIR resource/));
    expect(screen.getByText(/unresolved/)).toBeTruthy();
  });

  it("reports an error instead of inventing a twin", async () => {
    vi.mocked(api.getCaseTwin).mockRejectedValue(new Error("503"));
    render(<CaseTwinPanel caseId="c1" />);
    await waitFor(() => expect(screen.getByRole("alert").textContent).toMatch(/Could not load the case twin: 503/));
  });
});
