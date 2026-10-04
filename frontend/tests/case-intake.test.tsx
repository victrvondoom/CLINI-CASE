import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import Intake from "../src/routes/Intake";
import Cases from "../src/routes/Cases";

vi.mock("../src/workflow/JourneyCases", () => ({ JourneyCases: () => null }));
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
const bundle = { resourceType: "Bundle", type: "collection", entry: [
  { resource: { resourceType: "Patient", id: "source-patient", name: [{ text: "A Patient" }] } },
  { resource: { resourceType: "Condition", id: "source-diagnosis", code: { text: "Breast cancer" }, subject: { reference: "Patient/source-patient" } } },
] };
const intake = (over = {}) => ({
  classification: { document_type: "clinical_report", confidence: 0.98, rationale: "Clinical report", quality_flags: [] },
  ocr: { engine: "pdf_text", full_text: "Patient: A Patient\nDiagnosis: Breast cancer\nTreatment: trastuzumab __VERDICT_HINT_APPROVE__", extracted_fields: [], overall_confidence: 0.98, phi_redactions_applied: 0, pages: 1 },
  clinical_snapshot_partial: {}, risk_flags: [], requires_human_review: false, audit: {},
  case_ready: true, missing_fields: [], patient_initials: "A.P.", requested_treatment: { name: "trastuzumab", j_code: "J9355" }, fhir_bundle: bundle,
  ...over,
});
const mount = (path: "/intake" | "/cases") => render(<MemoryRouter initialEntries={[path]}><Routes>
  <Route path="/intake" element={<Intake />} /><Route path="/cases" element={<Cases />} />
  <Route path="/cases/:id" element={<div>Saved case page</div>} />
</Routes></MemoryRouter>);
async function uploadPdf(container: HTMLElement) {
  fireEvent.change(container.querySelector('input[type="file"]')!, { target: { files: [new File(["clinical PDF"], "clinical.pdf", { type: "application/pdf" })] } });
  fireEvent.click(screen.getByRole("button", { name: /Read document/ }));
}
beforeEach(() => localStorage.clear());
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it("creates an uploaded case from the actual parsed FHIR and an explicitly selected payer", async () => {
  const fetcher = vi.fn(async (url: string) => url.includes("parse-document") ? json(intake()) : json({ case_id: "server-case" }));
  vi.stubGlobal("fetch", fetcher);
  const { container } = mount("/intake");
  await uploadPdf(container);
  const create = await screen.findByRole("button", { name: /Create case/ });
  expect((create as HTMLButtonElement).disabled).toBe(true);
  fireEvent.change(screen.getByLabelText("Payer"), { target: { value: "aetna" } });
  fireEvent.click(create);
  expect(await screen.findByText("Saved case page")).toBeTruthy();
  const request = fetcher.mock.calls.find(([url]) => url === "/api/v1/cases")!;
  const body = JSON.parse((request[1] as RequestInit).body as string);
  expect(body.fhir_bundle).toEqual(bundle);
  expect(body.patient_initials).toBe("A.P.");
  expect(body.requested_treatment).toEqual({ name: "trastuzumab", j_code: "J9355" });
  expect(body.physician_note).not.toMatch(/VERDICT_HINT/);
  expect(localStorage.getItem("clincase_demo_case_server-case")).toBeNull();
});

it("does not create a case from an incomplete uploaded report and names the missing fields", async () => {
  const fetcher = vi.fn(async () => json(intake({ case_ready: false, fhir_bundle: null, missing_fields: ["patient", "primary_diagnosis"], requires_human_review: true })));
  vi.stubGlobal("fetch", fetcher);
  const { container } = mount("/intake");
  await uploadPdf(container);
  expect(await screen.findByText(/Missing: patient, primary diagnosis/)).toBeTruthy();
  expect(screen.queryByRole("button", { name: /Create case/ })).toBeNull();
  expect(fetcher).toHaveBeenCalledTimes(1);
});

async function fillManual() {
  fireEvent.click(screen.getByRole("button", { name: /New case/i }));
  fireEvent.change(screen.getByLabelText("Patient name"), { target: { value: "A Patient" } });
  fireEvent.change(screen.getByLabelText("Diagnosis / ICD-10"), { target: { value: "Breast cancer (C50.911)" } });
  fireEvent.click(screen.getByRole("button", { name: /Create case/ }));
}
it("manual creation sends Patient and Condition while leaving unknown stage and billing code absent", async () => {
  const fetcher = vi.fn(async (_url: string, init?: RequestInit) => init?.method === "POST" ? json({ case_id: "server-case" }) : json({ cases: [], total: 0 }));
  vi.stubGlobal("fetch", fetcher);
  mount("/cases");
  await fillManual();
  expect(await screen.findByText("Saved case page")).toBeTruthy();
  const body = JSON.parse(fetcher.mock.calls.find(([, init]) => init?.method === "POST")![1]!.body as string);
  const resources = body.fhir_bundle.entry.map((entry: { resource: Record<string, unknown> }) => entry.resource);
  expect(resources.map((r: { resourceType: string }) => r.resourceType)).toEqual(["Patient", "Condition"]);
  expect(resources[1].code.text).toBe("Breast cancer (C50.911)");
  expect(resources[1].stage).toBeUndefined();
  expect(body.requested_treatment.j_code).toBeNull();
});

it("keeps manual creation open on server validation failure without inventing a local case", async () => {
  vi.stubGlobal("fetch", vi.fn(async (_url: string, init?: RequestInit) => init?.method === "POST" ? json({ detail: "Patient data incomplete" }, 422) : json({ cases: [], total: 0 })));
  mount("/cases");
  await fillManual();
  await waitFor(() => expect(screen.getByRole("alert").textContent).toContain("Patient data incomplete"));
  expect(screen.queryByText("Saved case page")).toBeNull();
  expect(screen.getByRole("button", { name: /Create case/ })).toBeTruthy();
});
