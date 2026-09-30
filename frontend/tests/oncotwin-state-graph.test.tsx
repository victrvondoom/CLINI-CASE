import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { StateGraph } from "../src/oncotwin/intel";
import type { Graph } from "../src/oncotwin/types2";

const graph: Graph = {
  nodes: [
    { id: "lab", group: "lab", label: "Neutrophil count", status: "1.7 x10^3/µL", severity: "attention", basis: "fact", evidence: [{ type: "Laboratory", ids: ["lab-123"] }], detail: { day: 14, unit: "x10^3/µL" } },
    { id: "risk", group: "risk", label: "OT-ACUTE-7 risk (7 d)", status: "NORMAL · 11%", severity: "normal", basis: "model", evidence: [{ type: "model_contribution", features: ["ANC"] }], detail: { risk: 0.11, model: "v1" } },
  ],
  edges: [{ source: "lab", target: "risk", kind: "model", label: "+0.24 log-odds", weight: 0.24 }],
  edge_kinds: { clinical: "recorded fact", temporal: "timestamp order", data: "provenance", model: "model association, not causation" },
  groups: ["lab", "risk"], counts: { clinical: 0, temporal: 0, data: 0, model: 1 },
  note: "Model-derived associations do not imply causation.",
};

afterEach(cleanup);

describe("Patient State Graph", () => {
  it("opens on a useful estimate explanation with its provenance", () => {
    render(<StateGraph graph={graph} />);
    expect(screen.getAllByText("OT-ACUTE-7 risk (7 d)").length).toBeGreaterThan(1);
    expect(screen.getByText(/does not establish causation/i)).toBeTruthy();
    expect(screen.getAllByText("NORMAL · 11%").length).toBeGreaterThan(1);
    expect(screen.getByText("Evidence & provenance")).toBeTruthy();
  });

  it("lets users follow a relationship directly to its linked input", () => {
    render(<StateGraph graph={graph} />);
    fireEvent.click(screen.getByRole("button", { name: /From Neutrophil count/i }));
    expect(screen.getByText("lab-123")).toBeTruthy();
    expect(screen.getByText("x10^3/µL")).toBeTruthy();
  });

  it("provides zoom and a resettable layout control", () => {
    render(<StateGraph graph={graph} />);
    fireEvent.click(screen.getByRole("button", { name: "Zoom in" }));
    expect(screen.getByText("110%")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Reset graph layout" }));
    expect(screen.getByText("100%")).toBeTruthy();
  });
});
