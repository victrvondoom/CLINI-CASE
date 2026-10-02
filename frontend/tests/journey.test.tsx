import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  journeyActions,
  journeyApi,
  STAGE_ORDER,
  type JourneyView,
  type Stage,
  type StageId,
  type StageStatus,
} from "../src/journey/api";
import Journey from "../src/routes/Journey";

vi.mock("../src/journey/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../src/journey/api")>();
  return {
    ...actual,
    journeyApi: { list: vi.fn(), get: vi.fn() },
    journeyActions: {
      startDemo: vi.fn(),
      importSource: vi.fn(),
      map: vi.fn(),
      decide: vi.fn(),
      generate: vi.fn(),
      validate: vi.fn(),
      transfer: vi.fn(),
      returnTrip: vi.fn(),
      bind: vi.fn(),
      passport: vi.fn(),
    },
  };
});

const LABELS: Record<StageId, string> = {
  ingest: "Ingest",
  understand: "Understand",
  map: "Map",
  review: "Review",
  standardize: "Standardize",
  validate: "Validate",
  exchange: "Exchange",
  verify: "Verify",
  clinical_context: "Clinical context",
  follow_up: "Follow-up",
};
const NEXT: Partial<Record<StageId, NonNullable<Stage["next_action"]>>> = {
  review: { id: "review", label: "Review mappings" },
  standardize: { id: "generate", label: "Generate OAH/FHIR bundle" },
  exchange: { id: "transfer", label: "Send to System B" },
};

function view(current: StageId): JourneyView {
  const at = STAGE_ORDER.indexOf(current);
  const stages: Stage[] = STAGE_ORDER.map((id, i) => {
    const status: StageStatus = i < at ? "complete" : i === at ? "ready" : "waiting";
    return {
      id,
      index: i + 1,
      label: LABELS[id],
      owner: `${LABELS[id]} owner`,
      status,
      summary: `${LABELS[id]} summary`,
      facts: [{ label: "Fact", value: `${LABELS[id]} value` }],
      evidence:
        status === "complete"
          ? [{ event_type: `${id}_event`, timestamp: "2026-10-01T18:00:00+00:00", actor: "reviewer-1", status: "ok", correlation_id: "ig-1" }]
          : [],
      next_action: status === "ready" ? (NEXT[id] ?? null) : null,
      links: [],
      detail:
        id === "review"
          ? {
              targets: { value: "Observation.valueQuantity.value", unit: "Observation.valueQuantity.code" },
              mappings: [
                {
                  source_field: "arsenic",
                  target: "value",
                  fhir_target: "Observation.valueQuantity.value",
                  confidence: 0.65,
                  origin: "deterministic",
                  decision: "pending",
                  concept: null,
                  terminology_status: "unresolved",
                  reason: "",
                  reviewer: null,
                },
              ],
            }
          : {},
    };
  });
  return {
    job_id: "ig-1",
    job_version: 4,
    exposure_id: null,
    exposure_version: null,
    source: { system: "Synthetic Lab A", record_id: "SYN-1", format: "json", synthetic: true },
    consent_status: null,
    trust_states: ["RAW", "IMPORTED"],
    current_stage: current,
    progress: { complete: at, total: 10 },
    last_activity: "2026-10-01T18:00:00+00:00",
    stages,
  };
}

function Where() {
  return <div data-testid="where">{useLocation().pathname}</div>;
}

function page(path: string) {
  render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/journey" element={<Journey />} />
        <Route path="/journey/:jobId" element={<Journey />} />
        <Route path="/journey/:jobId/:stageId" element={<Journey />} />
        <Route path="*" element={<div>elsewhere</div>} />
      </Routes>
      <Where />
    </MemoryRouter>,
  );
}

const where = () => screen.getByTestId("where").textContent;

beforeEach(() => {
  vi.mocked(journeyApi.get).mockResolvedValue(view("review"));
  vi.mocked(journeyApi.list).mockResolvedValue({
    journeys: [
      {
        job_id: "ig-1",
        source: { system: "Synthetic Lab A", record_id: "SYN-1", format: "json", synthetic: true },
        exposure_id: null,
        current_stage: "review",
        current_status: "ready",
        current_summary: "13 mapping decision(s) await a reviewer",
        progress: { complete: 3, total: 10 },
        last_activity: null,
      },
    ],
    persistence: "volatile_synthetic_demo_only",
    stages: STAGE_ORDER.map((id) => ({ id, label: LABELS[id], owner: `${LABELS[id]} owner` })),
  });
});
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("unified evidence journey", () => {
  it("redirects a bare journey URL to the stage that needs work next", async () => {
    page("/journey/ig-1");
    await waitFor(() => expect(where()).toBe("/journey/ig-1/review"));
    const steps = within(screen.getByRole("navigation", { name: "Journey stages" })).getAllByRole("link");
    expect(steps).toHaveLength(10);
    expect(steps[3].getAttribute("aria-current")).toBe("step");
    expect(screen.getByRole("heading", { level: 2, name: "Review" })).toBeTruthy();
  });

  it("moves between stages with real URLs and shows proof in an accessible drawer", async () => {
    page("/journey/ig-1/review");
    fireEvent.click(await screen.findByRole("link", { name: /Stage 2 of 10: Understand, complete/ }));
    await waitFor(() => expect(where()).toBe("/journey/ig-1/understand"));
    const opener = screen.getByRole("button", { name: /View details · 1 proof/ });
    opener.focus();
    fireEvent.click(opener);
    const dialog = screen.getByRole("dialog", { name: "2. Understand" });
    expect(within(dialog).getByText("understand_event")).toBeTruthy();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(document.activeElement).toBe(opener);
  });

  it("runs the next action through the existing gateway and follows the server's new stage", async () => {
    vi.mocked(journeyApi.get)
      .mockResolvedValueOnce(view("standardize"))
      .mockResolvedValueOnce(view("exchange"));
    vi.mocked(journeyActions.generate).mockResolvedValue({} as never);
    page("/journey/ig-1/standardize");
    fireEvent.click(await screen.findByRole("button", { name: "Generate OAH/FHIR bundle" }));
    await waitFor(() => expect(where()).toBe("/journey/ig-1/exchange"));
    expect(journeyActions.generate).toHaveBeenCalledWith(expect.objectContaining({ job_id: "ig-1", job_version: 4 }));
  });

  it("shows the server's refusal and reloads state after a conflict", async () => {
    vi.mocked(journeyApi.get).mockResolvedValue(view("exchange"));
    vi.mocked(journeyActions.transfer).mockRejectedValue(new Error("Job changed; reload before retrying"));
    page("/journey/ig-1/exchange");
    fireEvent.click(await screen.findByRole("button", { name: "Send to System B" }));
    expect((await screen.findByRole("alert")).textContent).toContain("Job changed; reload before retrying");
    expect(vi.mocked(journeyApi.get).mock.calls.length).toBeGreaterThanOrEqual(2);
  });

  it("keeps the human review gate: generic arsenic needs an explicit concept", async () => {
    vi.mocked(journeyActions.decide).mockResolvedValue({} as never);
    page("/journey/ig-1/review");
    fireEvent.click(await screen.findByRole("button", { name: "Review mappings" }));
    const dialog = screen.getByRole("dialog");
    const approve = within(dialog).getByRole("button", { name: "Approve" });
    expect((approve as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(within(dialog).getByLabelText("Arsenic concept for arsenic"), {
      target: { value: "total_arsenic" },
    });
    expect((approve as HTMLButtonElement).disabled).toBe(false);
    fireEvent.click(approve);
    await waitFor(() =>
      expect(journeyActions.decide).toHaveBeenCalledWith(
        expect.objectContaining({ job_id: "ig-1" }),
        expect.objectContaining({ source_field: "arsenic" }),
        "approve",
        "value",
        "total_arsenic",
      ),
    );
  });

  it("starts a golden-path journey and lists recent journeys from the server", async () => {
    vi.mocked(journeyActions.startDemo).mockResolvedValue({ id: "ig-new" } as never);
    page("/journey");
    const recent = await screen.findByRole("link", { name: /Synthetic Lab A/ });
    expect(recent.getAttribute("href")).toBe("/journey/ig-1");
    expect(screen.getByText("13 mapping decision(s) await a reviewer")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /Start evidence journey/ }));
    await waitFor(() => expect(where()).toBe("/journey/ig-new"));
    expect(journeyActions.startDemo).toHaveBeenCalledWith("dissolved");
  });

  it("explains role and not-found errors instead of rendering an empty journey", async () => {
    vi.mocked(journeyApi.get).mockRejectedValue(new Error("The evidence journey needs a reviewer or admin role."));
    page("/journey/ig-1");
    expect((await screen.findByRole("alert")).textContent).toContain("reviewer or admin role");
    expect(screen.getByRole("link", { name: "Back to evidence journeys" }).getAttribute("href")).toBe("/journey");
  });
});
