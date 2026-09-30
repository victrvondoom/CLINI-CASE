import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { aqua } from "../src/aquahealth/api";
import type { Track3Evaluation } from "../src/aquahealth/types";
import AquaEvaluation from "../src/routes/AquaEvaluation";

vi.mock("../src/aquahealth/api", async (orig) => {
  const real = await orig<typeof import("../src/aquahealth/api")>();
  return { ...real, aqua: { ...real.aqua, evaluation: vi.fn() } };
});

const REPORT: Track3Evaluation = {
  benchmark: "aquahealth.track3.boundary-cases",
  version: "1.0.0",
  generated_from: "production assessment functions",
  synthetic: true,
  case_count: 1,
  metrics: {
    exact_status_accuracy: 1,
    concern_detection_recall: 1,
    insufficient_data_abstention_rate: 1,
    validation_check_accuracy: 1,
    false_healthy_on_insufficient_count: 0,
  },
  counts: {},
  limitations: ["Synthetic boundary cases test software behaviour, not ecological validity."],
  cases: [
    {
      case_id: "sparse-empty",
      title: "Empty qualitative observation abstains",
      category: "abstention",
      expected_status: "insufficient_data",
      predicted_status: "insufficient_data",
      confidence: "low",
      status_reason: "Not enough information.",
      expected_validation_issue: true,
      validation_issue_detected: true,
      validation_finding: "Data-quality issues found.",
      passed: true,
    },
  ],
};

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

describe("AquaHealth Track 3 evaluation", () => {
  it("renders live metrics, case outcomes and the ecological-validity limitation", async () => {
    vi.mocked(aqua.evaluation).mockResolvedValue(REPORT);

    render(
      <MemoryRouter>
        <AquaEvaluation />
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByText("Responsible assessment evaluation")).toBeTruthy());
    expect(screen.getByText("False healthy on sparse data")).toBeTruthy();
    expect(screen.getByText("Empty qualitative observation abstains")).toBeTruthy();
    expect(screen.getByText("Issue surfaced for review")).toBeTruthy();
    expect(screen.getByText(/not ecological validity/i)).toBeTruthy();
  });

  it("surfaces API failures instead of displaying stale metrics", async () => {
    vi.mocked(aqua.evaluation).mockRejectedValue(new Error("benchmark unavailable"));

    render(
      <MemoryRouter>
        <AquaEvaluation />
      </MemoryRouter>,
    );

    expect(await screen.findByText("benchmark unavailable")).toBeTruthy();
    expect(screen.queryByText("Status expectations")).toBeNull();
  });
});
