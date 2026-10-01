import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useAuth } from "../src/components/AuthContext";
import { interop, type Job } from "../src/interop/api";
import Interop from "../src/routes/Interop";
vi.mock("../src/components/AuthContext", () => ({ useAuth: vi.fn() }));
vi.mock("../src/interop/api", () => ({ interop: vi.fn() }));
const JOB: Job = {
  id: "ig-test",
  version: 1,
  source: {
    source_system: "SYN Lab A",
    original_record_id: "SYN-1",
    payload: { arsenic: 18.2 },
  },
  fields: { arsenic: 18.2 },
  mappings: [],
  mapping_version: 0,
  ai_status: "not_requested",
  bundle: null,
  validation: null,
  assessment: null,
  metrics: { fields_detected: 1 },
  events: [],
  transfers: [],
  schema: {
    fields: [{ name: "arsenic", detected_type: "float" }],
    missing_required_fields: ["analyte"],
    ambiguities: ["arsenic"],
  },
};
function page() {
  render(
    <MemoryRouter>
      <Interop />
    </MemoryRouter>,
  );
}
beforeEach(() => {
  vi.mocked(useAuth).mockReturnValue({
    user: { role: "reviewer" },
  } as ReturnType<typeof useAuth>);
  vi.mocked(interop).mockImplementation(async (path) =>
    path === "/meta"
      ? {
          targets: { value: "Observation.valueQuantity.value" },
          receiver_mode: "Independent ASGI receiver",
        }
      : structuredClone(JOB),
  );
});
afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

describe("Track 7 interoperability workbench", () => {
  it("protects source evidence from non-reviewer roles", () => {
    vi.mocked(useAuth).mockReturnValue({
      user: { role: "coordinator" },
    } as ReturnType<typeof useAuth>);
    page();
    expect(screen.getByText(/requires a reviewer/)).toBeTruthy();
    expect(interop).not.toHaveBeenCalled();
  });
  it("loads synthetic source and never auto-approves ambiguous speciation", async () => {
    page();
    fireEvent.click(
      screen.getByRole("button", {
        name: "Start Track 7 Interoperability Demo",
      }),
    );
    await screen.findByRole("button", {
      name: "Analyze schema and propose mappings",
    });
    const analyzed = {
      ...JOB,
      version: 2,
      ai_status: "deterministic_offline; no model called",
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
          reason: "Confirm assay speciation",
          reviewer: null,
        },
      ],
    };
    vi.mocked(interop).mockResolvedValueOnce(analyzed);
    fireEvent.click(
      screen.getByRole("button", {
        name: "Analyze schema and propose mappings",
      }),
    );
    const accept = await screen.findByRole("button", {
      name: "Accept mapping",
    });
    expect(accept.hasAttribute("disabled")).toBe(true);
    expect(
      screen
        .getByRole("button", { name: "Generate reviewed FHIR/OAH bundle" })
        .hasAttribute("disabled"),
    ).toBe(true);
    fireEvent.change(screen.getByLabelText("Confirm arsenic speciation"), {
      target: { value: "total_arsenic" },
    });
    expect(accept.hasAttribute("disabled")).toBe(false);
    vi.mocked(interop).mockResolvedValueOnce({
      ...analyzed,
      version: 3,
      mappings: [
        {
          ...analyzed.mappings[0],
          concept: "total_arsenic",
          decision: "accepted",
          reviewer: "r",
        },
      ],
    });
    fireEvent.click(accept);
    await waitFor(() =>
      expect(interop).toHaveBeenCalledWith("/mappings/ig-test/approve", {
        job_id: "ig-test",
        expected_version: 2,
        source_field: "arsenic",
        target: "value",
        concept: "total_arsenic",
      }),
    );
  });
  it("shows actual rejection and invalidates the verdict when the editor changes", async () => {
    const generated = {
      ...JOB,
      version: 2,
      bundle: {
        resourceType: "Bundle",
        entry: [
          {
            resource: {
              resourceType: "Observation",
              valueQuantity: { code: "ug/L", unit: "ug/L" },
            },
          },
        ],
      },
      validation: {
        valid: true,
        sha256: "hash",
        standards: {
          target: "FHIR R4",
          oah_package: "draft",
          oah_commit: "pinned",
          source: "source",
          validation_scope: "partial",
          full_hl7_profile_validation: false,
          notice: "Not certified",
        },
        checks: [{ name: "contract", passed: true }],
        operation_outcome: {
          issue: [{ severity: "information", diagnostics: "Contract passed" }],
        },
      },
    };
    page();
    await screen.findByText(/Independent ASGI receiver/);
    vi.mocked(interop).mockResolvedValueOnce(generated);
    fireEvent.click(
      screen.getByRole("button", {
        name: "Start Track 7 Interoperability Demo",
      }),
    );
    await screen.findByText("VALIDATION PASSED");
    fireEvent.change(screen.getByLabelText("Editable FHIR bundle"), {
      target: { value: "{}" },
    });
    expect(screen.queryByText("VALIDATION PASSED")).toBeNull();
    expect(
      screen
        .getByRole("button", { name: /Transfer to independent/ })
        .hasAttribute("disabled"),
    ).toBe(true);
    fireEvent.click(
      screen.getByRole("button", { name: "Restore generated bundle" }),
    );
    vi.mocked(interop).mockResolvedValueOnce({
      ...generated,
      version: 3,
      validation: {
        ...generated.validation,
        valid: false,
        sha256: "broken",
        checks: [{ name: "contract", passed: false }],
        operation_outcome: {
          issue: [{ severity: "error", diagnostics: "Unsupported unit ppm" }],
        },
      },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Run validation failure" }),
    );
    expect(
      await screen.findByText("VALIDATION FAILED — TRANSFER BLOCKED"),
    ).toBeTruthy();
    expect(screen.getByText("Unsupported unit ppm")).toBeTruthy();
    const sent = vi.mocked(interop).mock.calls.find(([p]) => p === "/validate");
    expect(JSON.stringify(sent?.[1])).toContain("ppm");
  });
  it("surfaces backend failure without an invented success", async () => {
    page();
    await screen.findByText(/Independent ASGI receiver/);
    vi.mocked(interop).mockRejectedValueOnce(new Error("Receiver unavailable"));
    fireEvent.click(
      screen.getByRole("button", {
        name: "Start Track 7 Interoperability Demo",
      }),
    );
    expect((await screen.findByRole("alert")).textContent).toContain(
      "Receiver unavailable",
    );
    expect(screen.queryByText("DELIVERED")).toBeNull();
  });
});
