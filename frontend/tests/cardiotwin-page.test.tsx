import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { cardio } from "../src/cardiotwin/api";
import CardioTwin from "../src/routes/CardioTwin";
import type { CounterfactualResult, FeatureCatalog, Prediction, Scenario, TargetId, TargetPrediction, VesselId } from "../src/cardiotwin/types";

vi.mock("../src/cardiotwin/api", async (orig) => {
  const real = await orig<typeof import("../src/cardiotwin/api")>();
  return { ...real, cardio: { features: vi.fn(), scenarios: vi.fn(), predict: vi.fn(), counterfactual: vi.fn(), sensitivity: vi.fn() } };
});

// jsdom has no WebGL: replace the R3F viewer with a stub that exposes the same props contract.
vi.mock("../src/cardiotwin/HeartViewer", () => ({
  default: (p: { viz: Record<VesselId, { probability: number; halo: number }> | null; selected: VesselId | null; onSelect: (v: VesselId | null) => void }) => (
    <div data-testid="heart-stub" data-selected={p.selected ?? ""} data-lad={p.viz ? p.viz.LAD.probability : ""} data-rca={p.viz ? p.viz.RCA.probability : ""}>
      {(["LAD", "LCX", "RCA"] as const).map((id) => (
        <button key={id} data-testid={`3d-${id}`} onClick={() => p.onSelect(id)}>{id}</button>
      ))}
    </div>
  ),
}));

const CATALOG: FeatureCatalog = {
  groups: [{ id: "lab", label: "Laboratory" }],
  features: [
    { name: "LDL", label: "LDL cholesterol", group: "lab", kind: "numeric", unit: "mg/dL", min: 10, max: 500, ref_low: null, ref_high: 100, options: [], core: true, note: "" },
    { name: "Age", label: "Age", group: "lab", kind: "numeric", unit: "years", min: 18, max: 100, ref_low: null, ref_high: null, options: [], core: true, note: "" },
  ],
};

const target = (t: TargetId, p: number, over: Partial<TargetPrediction> = {}): TargetPrediction => ({
  target: t, name: t, probability: p, model_probability: p, calibrated: true, calibration_method: "platt", interval_80: [Math.max(0, p - 0.1), Math.min(1, p + 0.1)],
  ensemble_sd: 0.05, operating_point: 0.6, above_operating_point: p > 0.6, band: p < 0.33 ? "low" : p < 0.66 ? "intermediate" : "elevated", confidence: "high",
  held_out_auc: 0.8, held_out_auc_ci95: [0.7, 0.9], ...over,
});

function prediction(probs: { CAD: number; LAD: number; LCX: number; RCA: number }, over: Partial<Prediction> = {}): Prediction {
  const vessels = { LAD: target("LAD", probs.LAD), LCX: target("LCX", probs.LCX), RCA: target("RCA", probs.RCA) };
  const expl = (t: TargetId) => ({
    baseline_logit: 0.5,
    sum_check_logit: 1.5,
    features: [
      { feature: "EF-TTE", label: `${t} driver EF`, group: "echo", value: 30, unit: "%", imputed: false, contribution: 0.7, direction: "raises" as const, share: 0.6 },
      { feature: "Age", label: "Age", group: "demographics", value: 52, unit: "years", imputed: false, contribution: -0.3, direction: "lowers" as const, share: 0.3 },
    ],
  });
  return {
    cad: target("CAD", probs.CAD),
    vessels,
    explanations: { CAD: expl("CAD"), LAD: expl("LAD"), LCX: expl("LCX"), RCA: expl("RCA") },
    representativeness: { status: "representative", distance_squared: 30, percentile_of_training: 40, borderline_above: 140, outside_above: 276, out_of_range_features: [] },
    feature_completeness: { provided: 54, total: 54, fraction: 1, imputed: [] },
    warnings: [],
    visualization: {
      encoding: {},
      vessels: {
        LAD: { id: "LAD", probability: probs.LAD, band: vessels.LAD.band, confidence: "high", halo: 0.2 },
        LCX: { id: "LCX", probability: probs.LCX, band: vessels.LCX.band, confidence: "high", halo: 0.2 },
        RCA: { id: "RCA", probability: probs.RCA, band: vessels.RCA.band, confidence: "high", halo: 0.2 },
      },
      cad_probability: probs.CAD,
    },
    provenance: {
      model_id: "cardiotwin-lr-multivessel", version: "1.0.0", artifact_sha256: "a".repeat(64), integrity_verified: true, dataset_sha256: "b".repeat(64),
      trained_on: "Extension of Z-Alizadeh Sani Dataset", prediction_timestamp: "2026-09-30T00:00:00+00:00", input_sha256: "c".repeat(64), scenario_id: null,
      leakage_audit: "pass", calibration: { CAD: "platt", LAD: "platt", LCX: "platt", RCA: "platt" },
    },
    safety_notice: "Decision support only",
    claims: { is: "x", is_not: "y" },
    ...over,
  };
}

const SCENARIOS: Scenario[] = [
  { id: "C", title: "Mixed-vessel pattern", description: "mixed", patient: { LDL: 160, Age: 60 }, source: "dataset_sample", dataset_row: 239, reference_labels: { Cath: "CAD", LAD: "Stenotic", LCX: "Normal", RCA: "Normal" } },
  { id: "D", title: "Unrepresentative profile", description: "ood", patient: { LDL: 900, Age: 21 }, source: "synthetic" },
  { id: "E", title: "Sensitivity simulation", description: "cf", patient: { LDL: 160, Age: 60 }, source: "dataset_sample", dataset_row: 147, perturbation: { LDL: 100 } },
];

const MIXED = prediction({ CAD: 0.99, LAD: 0.88, LCX: 0.41, RCA: 0.21 });

beforeEach(() => {
  vi.mocked(cardio.features).mockResolvedValue(CATALOG);
  vi.mocked(cardio.scenarios).mockResolvedValue({ note: "n", scenarios: SCENARIOS });
  vi.mocked(cardio.predict).mockResolvedValue(MIXED);
  vi.mocked(cardio.sensitivity).mockResolvedValue({ feature: "LDL", label: "LDL", unit: "mg/dL", current_value: 160, curve: [{ value: 100, LAD: 0.6 }, { value: 200, LAD: 0.9 }], note: "" });
});
afterEach(() => { cleanup(); vi.resetAllMocks(); });

const mount = () => render(<MemoryRouter><CardioTwin /></MemoryRouter>);

describe("CardioTwin dashboard", () => {
  it("always shows the clinical safety disclaimer, on the page and on the 3D view", async () => {
    mount();
    expect((await screen.findAllByTestId("cardiotwin-disclaimer"))[0].textContent).toMatch(/not a substitute for coronary angiography/);
    expect((await screen.findByTestId("viewer-disclaimer")).textContent).toMatch(/not a lesion location/);
  });

  it("renders predicted CAD and per-vessel estimated probabilities and drives the 3D state", async () => {
    mount();
    await waitFor(() => expect(screen.getByTestId("cad-probability").textContent).toBe("99%"));
    expect(screen.getByTestId("vessel-prob-LAD").textContent).toBe("88%");
    expect(screen.getByTestId("vessel-prob-LCX").textContent).toBe("41%");
    expect(screen.getByTestId("vessel-prob-RCA").textContent).toBe("21%");
    const heart = screen.getByTestId("heart-stub");
    expect(heart.getAttribute("data-lad")).toBe("0.88");
    expect(heart.getAttribute("data-rca")).toBe("0.21");
    expect(screen.getByText(/Predicted CAD probability/)).toBeTruthy();
    expect(cardio.predict).toHaveBeenCalledWith({ LDL: 160, Age: 60 }, "C");
  });

  it("selects the highest-probability vessel first, then keeps 3D view, cards and evidence in sync", async () => {
    mount();
    await waitFor(() => screen.getByTestId("cad-probability"));
    expect(screen.getByTestId("heart-stub").getAttribute("data-selected")).toBe("LAD");
    expect(screen.getByTestId("evidence-panel").textContent).toMatch(/Why LAD is highlighted/);

    fireEvent.click(screen.getByTestId("3d-RCA")); // click in the 3D scene
    expect(screen.getByTestId("heart-stub").getAttribute("data-selected")).toBe("RCA");
    expect(screen.getByTestId("evidence-panel").textContent).toMatch(/Why RCA is highlighted/);
    expect(screen.getByTestId("vessel-card-RCA").getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByTestId("vessel-card-LAD").getAttribute("aria-pressed")).toBe("false");

    fireEvent.click(screen.getByTestId("vessel-card-LCX")); // click a dashboard card
    expect(screen.getByTestId("heart-stub").getAttribute("data-selected")).toBe("LCX");
    expect(screen.getByTestId("select-LCX").getAttribute("aria-pressed")).toBe("true");

    fireEvent.click(screen.getByTestId("cad-card")); // overall CAD is not a vessel → nothing selected in 3D
    expect(screen.getByTestId("heart-stub").getAttribute("data-selected")).toBe("");
    expect(screen.getByTestId("evidence-panel").textContent).toMatch(/CAD estimate/);
  });

  it("after loading a scenario, selects the vessel with the highest estimated probability", async () => {
    const rcaHigh = prediction({ CAD: 0.9, LAD: 0.3, LCX: 0.2, RCA: 0.85 });
    vi.mocked(cardio.predict).mockImplementation(async (f) => (f.LDL === 900 ? rcaHigh : MIXED));
    mount();
    await waitFor(() => screen.getByTestId("cad-probability"));
    fireEvent.click(screen.getByTestId("scenario-D"));
    await waitFor(() => expect(screen.getByTestId("heart-stub").getAttribute("data-selected")).toBe("RCA"));
    expect(screen.getByTestId("evidence-panel").textContent).toMatch(/Why RCA is highlighted/);
  });

  it("explains a vessel with model evidence, not with a claim about a physical lesion", async () => {
    mount();
    const panel = await screen.findByTestId("evidence-panel");
    await waitFor(() => expect(panel.textContent).toMatch(/LAD driver EF/));
    expect(within(panel).getAllByTestId("contribution-row").length).toBeGreaterThan(0);
    expect(panel.textContent).toMatch(/▲ raises/);
    expect(panel.textContent).toMatch(/does not localise a physical lesion/);
  });

  it("surfaces an out-of-distribution warning instead of silent confidence", async () => {
    const ood = prediction({ CAD: 0.98, LAD: 0.9, LCX: 0.8, RCA: 0.9 }, {
      representativeness: { status: "outside", distance_squared: 900, percentile_of_training: 100, borderline_above: 140, outside_above: 276, out_of_range_features: [{ feature: "Age", value: 21, training_min: 30, training_max: 86 }] },
      warnings: [{ code: "OUT_OF_DISTRIBUTION", severity: "high", message: "Prediction generated, but this profile lies outside the well-represented region of the training cohort." }],
    });
    vi.mocked(cardio.predict).mockImplementation(async (f) => (f.LDL === 900 ? ood : MIXED));
    mount();
    fireEvent.click(await screen.findByTestId("scenario-D"));
    expect((await screen.findByTestId("warning-OUT_OF_DISTRIBUTION")).textContent).toMatch(/Prediction generated, but/);
    expect(screen.getByTestId("trust-panel").textContent).toMatch(/outside/);
  });

  it("shows a validation error from the backend instead of stale numbers", async () => {
    mount();
    await waitFor(() => screen.getByTestId("cad-probability"));
    vi.mocked(cardio.predict).mockRejectedValue(new Error("Age: 999 outside the valid range [18, 100]"));
    fireEvent.click(screen.getByTestId("scenario-D"));
    expect((await screen.findByTestId("cardiotwin-error")).textContent).toMatch(/outside the valid range/);
  });

  it("model trust panel exposes provenance, integrity and calibration", async () => {
    mount();
    const trust = await screen.findByTestId("trust-panel");
    expect(trust.textContent).toMatch(/SHA-256 verified/);
    expect(trust.textContent).toMatch(/cardiotwin-lr-multivessel v1.0.0/);
    expect(trust.textContent).toMatch(/passed/);
    expect(trust.textContent).toMatch(/54\/54 provided/);
  });
});

describe("sensitivity simulation (counterfactual)", () => {
  const cf = (): CounterfactualResult => {
    const perturbed = prediction({ CAD: 0.9, LAD: 0.55, LCX: 0.4, RCA: 0.2 });
    return {
      changes: [{ feature: "LDL", label: "LDL cholesterol", before: 160, after: 100, unit: "mg/dL", was_imputed: false }],
      targets: {
        CAD: { before: 0.99, after: 0.9, delta: -0.09, within_model_uncertainty: false, baseline_ensemble_sd: 0.05 },
        LAD: { before: 0.88, after: 0.55, delta: -0.33, within_model_uncertainty: false, baseline_ensemble_sd: 0.05 },
        LCX: { before: 0.41, after: 0.4, delta: -0.01, within_model_uncertainty: true, baseline_ensemble_sd: 0.05 },
        RCA: { before: 0.21, after: 0.2, delta: -0.01, within_model_uncertainty: true, baseline_ensemble_sd: 0.05 },
      },
      baseline: MIXED,
      perturbed,
      label: "Model sensitivity simulation — not a treatment recommendation and not a causal claim.",
    };
  };

  it("re-runs the model, shows before/after/delta, and the 3D state follows the perturbed prediction", async () => {
    vi.mocked(cardio.counterfactual).mockResolvedValue(cf());
    mount();
    await waitFor(() => screen.getByTestId("cad-probability"));
    fireEvent.click(screen.getByTestId("sensitivity-toggle"));
    fireEvent.change(await screen.findByTestId("sensitivity-number"), { target: { value: "100" } });

    await waitFor(() => expect(cardio.counterfactual).toHaveBeenCalledWith({ LDL: 160, Age: 60 }, { LDL: 100 }));
    const lad = await screen.findByTestId("delta-LAD");
    expect(lad.textContent).toMatch(/88%/);
    expect(lad.textContent).toMatch(/55%/);
    expect(lad.textContent).toMatch(/-33\.0 pp/);
    expect(screen.getByTestId("delta-LCX").textContent).toMatch(/within model noise/);
    expect(screen.getByTestId("sensitivity-panel").textContent).toMatch(/not a treatment recommendation/i);

    await waitFor(() => expect(screen.getByTestId("heart-stub").getAttribute("data-lad")).toBe("0.55")); // perturbed
    expect(screen.getByTestId("viewer-mode").textContent).toMatch(/perturbed/);
    fireEvent.click(screen.getByTestId("view-baseline"));
    expect(screen.getByTestId("heart-stub").getAttribute("data-lad")).toBe("0.88"); // back to baseline
    expect(screen.getByTestId("vessel-prob-LAD").textContent).toBe("88%");
  });

  it("scenario E opens the simulator pre-loaded with its perturbation", async () => {
    vi.mocked(cardio.counterfactual).mockResolvedValue(cf());
    mount();
    fireEvent.click(await screen.findByTestId("scenario-E"));
    await waitFor(() => expect(cardio.counterfactual).toHaveBeenCalledWith({ LDL: 160, Age: 60 }, { LDL: 100 }));
    expect((screen.getByTestId("sensitivity-toggle") as HTMLInputElement).checked).toBe(true);
  });
});
