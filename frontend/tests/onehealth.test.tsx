import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { aqua } from "../src/aquahealth/api";
import { useAuth } from "../src/components/AuthContext";
import { onehealth, type ExposureRecord, type Meta, type Validation } from "../src/onehealth/api";
import { LabForm } from "../src/onehealth/Forms";
import { ExposureContext } from "../src/onehealth/ContextPanel";
import OneHealth from "../src/routes/OneHealth";

vi.mock("../src/components/AuthContext", () => ({ useAuth: vi.fn() }));
vi.mock("../src/onehealth/api", () => ({ onehealth: { meta: vi.fn(), list: vi.fn(), patients: vi.fn(), get: vi.fn(), demo: vi.fn(), action: vi.fn(), export: vi.fn(), validate: vi.fn(), import: vi.fn() } }));
vi.mock("../src/aquahealth/api", () => ({ aqua: { listObservations: vi.fn(), getObservation: vi.fn() } }));

const META: Meta = { product: "ClinCase One Health", primary_track: "Track 7", supporting_track: "Track 3", persistence: "volatile_synthetic_demo_only", notice: "Exposure context is not a disease probability.", standards: { target: "FHIR R4", oah_package: "hl7.eu.fhir.oah#0.1.0-ci-build", oah_commit: "b907cf0", source: "https://github.com/hl7-eu/oah", validation_scope: "Selected draft constraints", full_hl7_profile_validation: false, notice: "Not certified" } };
const RECORD: ExposureRecord = {
  id: "oh-test", version: 1, observation_id: "obs-test", waterbody_name: "Demo Brook", synthetic: true, created_at: "2026-09-28T12:00:00Z",
  sample: { sample_id: "S1", location_name: "Demo outlet", kind: "drinking_water", laboratory: "Demo lab", collector: "Demo sampler", report_reference: "R1", method: "Synthetic ICP-MS", collected_at: "2026-09-27T12:00:00Z", reported_at: "2026-09-28T12:00:00Z", analyte: "total_arsenic", value: 25, unit: "ug/L", qualifier: "eq" },
  history: null, lab_verified: false, consent_withdrawn: false, review: "pending", followup_status: "requested", case_id: null, audit: [],
  assessment: { state: "evidence_incomplete", eligible_for_review: false, concentration_ug_l: 25, comparison: "not_applicable", gates: [{ id: "consent", label: "Recorded consent remains active", passed: false }], reference: { value: 10, unit: "ug/L", name: "WHO provisional guideline", url: "https://www.who.int/news-room/fact-sheets/detail/arsenic" }, meaning: "Not a water-safety certificate", notice: "Not a diagnosis", clinical_context: { oncology: "Exposure context only", cardiovascular: "Clinical CAD model unchanged", speciation: "Total arsenic is not inorganic dose" } },
  ablation: [{ removed: "Recorded consent remains active", eligible_for_review: false, state: "evidence_incomplete" }], source_bundle_sha256: null, persistence: "volatile_synthetic_demo_only",
};
const VALIDATION: Validation = { valid: true, sha256: "abc", standards: META.standards, operation_outcome: { issue: [{ severity: "information", diagnostics: "Selected contract passed" }] }, roundtrip: { sample_preserved: true, history_preserved: true, trust_policy: "Reconfirm consent" } };

beforeEach(() => {
  vi.mocked(useAuth).mockReturnValue({ user: { id: "r", role: "reviewer" } } as ReturnType<typeof useAuth>);
  vi.mocked(onehealth.meta).mockResolvedValue(META);
  vi.mocked(onehealth.list).mockResolvedValue({ records: [RECORD], persistence: META.persistence });
  vi.mocked(onehealth.patients).mockResolvedValue({ patients: [] });
  vi.mocked(aqua.listObservations).mockResolvedValue({ observations: [], total: 0, limit: 500, offset: 0 });
  vi.mocked(aqua.getObservation).mockResolvedValue({
    id: RECORD.observation_id,
    reference: "OBS-TEST",
    waterbody_name: RECORD.waterbody_name,
    review_status: "pending_review",
    verification: "unverified",
  } as Awaited<ReturnType<typeof aqua.getObservation>>);
});
afterEach(() => { cleanup(); vi.resetAllMocks(); });
function page() { return render(<MemoryRouter><OneHealth /></MemoryRouter>); }

describe("Track 7 workbench", () => {
  it("disables real environmental records in volatile demo mode", () => {
    render(<LabForm observations={[{ id: "obs-real", reference: "OBS-REAL", waterbody_name: "River", is_demo: false }]} persistence="volatile_synthetic_demo_only" busy={false} onSubmit={vi.fn()} />);
    expect(screen.getByRole("option", { name: /OBS-REAL/ }).hasAttribute("disabled")).toBe(true);
    expect(screen.getByRole("button", { name: "Save unverified laboratory evidence" }).hasAttribute("disabled")).toBe(true);
    expect(screen.getByRole("status").textContent).toMatch(/Only synthetic observations/);
  });
  it("shows primary Track 7 and preserves the clinical safety boundary", async () => {
    page();
    expect(await screen.findByText("Evidence connection")).toBeTruthy();
    expect(screen.getByText(/PRIMARY TRACK 7/)).toBeTruthy();
    expect(screen.getByText(/volatile synthetic data only/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Record clinical review" }).hasAttribute("disabled")).toBe(true);
    expect(screen.getByText("Clinical CAD model unchanged")).toBeTruthy();
    expect(await screen.findByText(/OBS-TEST · Demo Brook · pending review · unverified/)).toBeTruthy();
    expect(screen.getByText("06 · AQUAHEALTH")).toBeTruthy();
  });
  it("requires a reviewer note before verifying a lab report", async () => {
    vi.mocked(onehealth.action).mockResolvedValue({ ...RECORD, version: 2, lab_verified: true });
    page();
    const verify = await screen.findByRole("button", { name: "Verify laboratory report" });
    expect(verify.hasAttribute("disabled")).toBe(true);
    fireEvent.change(screen.getByLabelText(/Reviewer note/), { target: { value: "Checked sample and report reference" } });
    fireEvent.click(verify);
    await waitFor(() => expect(onehealth.action).toHaveBeenCalledWith(RECORD, "verify", { note: "Checked sample and report reference" }));
  });
  it("runs the evidence challenge without a mutation", async () => {
    page();
    fireEvent.click(await screen.findByRole("button", { name: "Evidence challenge" }));
    expect(screen.getByText("Withheld")).toBeTruthy();
    expect(onehealth.action).not.toHaveBeenCalled();
  });
  it("renders round-trip results and invalidates validation when JSON changes", async () => {
    vi.mocked(onehealth.export).mockResolvedValue({ bundle: { resourceType: "Bundle" }, validation: VALIDATION });
    page(); fireEvent.click(await screen.findByRole("button", { name: "FHIR exchange" }));
    fireEvent.click(screen.getByRole("button", { name: "Export & check round-trip" }));
    expect(await screen.findByText("Selected contract checks passed")).toBeTruthy();
    expect(screen.getByText(/Full HL7 profile validation: not performed/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Stage as new unverified evidence" }).hasAttribute("disabled")).toBe(false);
    fireEvent.change(screen.getByLabelText("FHIR collection bundle JSON"), { target: { value: "{}" } });
    expect(screen.getByRole("button", { name: "Stage as new unverified evidence" }).hasAttribute("disabled")).toBe(true);
  });
  it("does not load sensitive records for a citizen role", () => {
    vi.mocked(useAuth).mockReturnValue({ user: { role: "coordinator" } } as ReturnType<typeof useAuth>);
    page(); expect(screen.getByText(/restricted to reviewers/)).toBeTruthy();
    expect(onehealth.list).not.toHaveBeenCalled();
  });
  it("surfaces API failure and does not invent records", async () => {
    vi.mocked(onehealth.list).mockRejectedValue(new Error("Evidence service unavailable"));
    page(); expect(await screen.findByRole("alert")).toBeTruthy();
    expect(screen.queryByText("Demo Brook")).toBeNull();
  });
});

describe("Cross-module exposure context", () => {
  it("does not auto-bind CAD inputs to an exposure patient", () => {
    render(<MemoryRouter><ExposureContext independentCardio /></MemoryRouter>);
    expect(screen.getByText(/independent scenario/)).toBeTruthy();
    expect(onehealth.list).not.toHaveBeenCalled();
  });
  it("renders patient-linked evidence in the twin", async () => {
    render(<MemoryRouter><ExposureContext patientId="ot-005" /></MemoryRouter>);
    expect(await screen.findByText(/SYNTHETIC · Demo Brook/)).toBeTruthy();
    expect(onehealth.list).toHaveBeenCalledWith({ patient_id: "ot-005" });
  });
  it("hides withdrawn evidence even on a direct context link", async () => {
    vi.mocked(onehealth.get).mockResolvedValue({ ...RECORD, consent_withdrawn: true });
    render(<MemoryRouter><ExposureContext exposureId="oh-test" /></MemoryRouter>);
    await waitFor(() => expect(screen.queryByText(/Loading exposure/)).toBeNull());
    expect(screen.queryByText(/SYNTHETIC · Demo Brook/)).toBeNull();
  });
});
