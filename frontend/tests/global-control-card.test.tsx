import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { aqua } from "../src/aquahealth/api";
import type { MapView } from "../src/aquahealth/types";
import GlobalControlCard from "../src/components/GlobalControlCard";

vi.mock("../src/aquahealth/api", async (orig) => {
  const real = await orig<typeof import("../src/aquahealth/api")>();
  return { ...real, aqua: { ...real.aqua, map: vi.fn() } };
});

vi.mock("../src/globe/AquaHealthMapLibre", () => ({
  default: ({ points, onCoordinateClick, onSelect }: { points: MapView["points"]; onCoordinateClick: (lon: number, lat: number) => void; onSelect: (point: MapView["points"][number]) => void }) => (
    <div data-testid="global-map">
      <span>{points.length} map markers</span>
      <button type="button" onClick={() => onCoordinateClick(10, 52)}>Map click Europe</button>
      {points[0] && <button type="button" onClick={() => onSelect(points[0])}>Select first map marker</button>}
    </div>
  ),
}));

vi.mock("../src/globe/ObservationGlobe", () => ({
  default: ({ onSurfaceSelect }: { onSurfaceSelect?: (latitude: number, longitude: number) => void }) => (
    <div data-testid="global-globe">Interactive globe<button type="button" onClick={() => onSurfaceSelect?.(52, 10)}>Globe tap Europe</button></div>
  ),
}));

const MAP: MapView = {
  points: [
    {
      observation_id: "europe-1", reference: "OBS-EU-1", waterbody_id: "lake-1", waterbody_name: "Lake Geneva",
      latitude: 46.2, longitude: 6.1, observed_at: "2026-10-01T00:00:00Z", status: "potential_stress",
      confidence: "medium", review_status: "pending_review", verification: "ai_assisted", source: "demonstration_data", is_demo: true, summary: null,
    },
    {
      observation_id: "na-1", reference: "OBS-NA-1", waterbody_id: "lake-2", waterbody_name: "Lake Superior",
      latitude: 47.7, longitude: -87.5, observed_at: "2026-10-01T00:00:00Z", status: "healthy_signal",
      confidence: "high", review_status: "completed", verification: "human_reviewed", source: "citizen_observation", is_demo: false, summary: null,
    },
  ],
  waterbodies: [],
  statuses: [],
};

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

describe("GlobalControlCard", () => {
  it("filters mapped observations and regional metrics from the inline selectors", async () => {
    vi.mocked(aqua.map).mockResolvedValue(MAP);
    render(<MemoryRouter><GlobalControlCard /></MemoryRouter>);

    await waitFor(() => expect(screen.getByText("2 mapped observations")).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: "Europe" }));

    expect(screen.getByText("1 mapped observation")).toBeTruthy();
    expect(screen.getByText("1 map markers")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Select first map marker" }));
    expect(screen.getByText("Lake Geneva")).toBeTruthy();
  });

  it("supports direct map context selection, record selection, and an embedded globe mode", async () => {
    vi.mocked(aqua.map).mockResolvedValue(MAP);
    render(<MemoryRouter><GlobalControlCard /></MemoryRouter>);
    await screen.findByText("2 mapped observations");

    fireEvent.click(screen.getByRole("button", { name: "Map click Europe" }));
    expect(screen.getByText("Europe", { selector: "span" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Select first map marker" }));
    expect(screen.getByText("Lake Geneva")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "3D Globe" }));
    expect(await screen.findByTestId("global-globe")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Globe tap Europe" }));
    expect(screen.getByRole("button", { name: "Europe" }).getAttribute("aria-pressed")).toBe("true");
  });
});
