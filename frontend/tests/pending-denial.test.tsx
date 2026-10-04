import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";

import { api, normalizeRunResult } from "../src/lib/api";
import CaseDetail from "../src/routes/CaseDetail";

vi.mock("../src/lib/api", async (original) => ({ ...(await original<typeof import("../src/lib/api")>()), api: { getCase: vi.fn(), retryCaseLetters: vi.fn() } }));
vi.mock("../src/components/AuditLogViewer", () => ({ AuditLogViewer: () => null }));
vi.mock("../src/components/BusinessValuePanel", () => ({ BusinessValuePanel: () => null }));
vi.mock("../src/components/CaseTwinPanel", () => ({ CaseTwinPanel: () => null }));
vi.mock("../src/components/CaseEconomicsStrip", () => ({ CaseEconomicsStrip: () => null }));
vi.mock("../src/components/ComplianceScorecardCard", () => ({ ComplianceScorecardCard: () => null }));
vi.mock("../src/components/EvidencePackButton", () => ({ EvidencePackButton: () => null }));
vi.mock("../src/components/PHIRedactionReceipt", () => ({ PHIRedactionReceipt: () => null }));
vi.mock("../src/onehealth/ContextPanel", () => ({ ExposureContext: () => null }));
vi.mock("../src/components/TrizettoSubmitPanel", () => ({ TrizettoSubmitPanel: () => <div>Submit final determination</div> }));

const pending = () => normalizeRunResult({
  case_id: "pending-case", clinical_snapshot: null, policy_excerpts: [], necessity_assessment: null, decision: null,
  provisional_decision: { verdict: "DENY", confidence: 0.98, rationale: "Draft adverse assessment", citations: [], risk_flags: [] },
  paused_for_review: true, human_review_required: true, documents_draft: true, pause_kind: "ai_denial", pause_reason: "Every AI DENY needs clinician sign-off.",
  appeal_draft: { patient_initials: "A.P.", payer_id: "aetna", requested_treatment: "trastuzumab", denial_date: "2026-10-04", appeal_body: "Proposed appeal evidence.", structured_arguments: [], attachments_referenced: [], requested_action: "Reconsider proposed denial" },
  patient_communication: { headline: "Proposed patient letter", body: "Letter awaiting clinical review.", next_steps: [], tone: "neutral", reading_level_grade: 6, contains_phi: false },
});
afterEach(() => { cleanup(); vi.clearAllMocks(); vi.unstubAllGlobals(); localStorage.clear(); });

it("keeps the provisional AI DENY separate from an authoritative decision", () => {
  const result = pending();
  expect(result.decision).toBeNull();
  expect(result.provisional_decision?.verdict).toBe("DENY");
  expect(result.documents_draft).toBe(true);
  expect(result.human_review_required).toBe(true);
});

it("reloads pending evidence and draft letters without enabling patient email or final submission", async () => {
  vi.mocked(api.getCase).mockResolvedValue({ case_id: "pending-case", payer_id: "aetna", patient_initials: "A.P.", status: "awaiting_review", physician_note: null, requested_treatment: { name: "trastuzumab", j_code: null }, created_at: null, pending_review: pending() });
  render(<MemoryRouter initialEntries={["/cases/pending-case"]}><Routes><Route path="/cases/:caseId" element={<CaseDetail />} /></Routes></MemoryRouter>);
  expect(await screen.findByText(/Awaiting clinician review — no final decision/)).toBeTruthy();
  expect(screen.getByText("AI proposed DENY")).toBeTruthy();
  expect(screen.getByText("Proposed appeal evidence.")).toBeTruthy();
  expect(screen.getByText("Draft Patient Communication")).toBeTruthy();
  expect(screen.getByText(/This proposed appeal has not been approved or submitted/)).toBeTruthy();
  expect((screen.getByRole("button", { name: "Email" }) as HTMLButtonElement).disabled).toBe(true);
  expect(screen.queryByText("Submit final determination")).toBeNull();
  expect((screen.getByRole("button", { name: /Run ClinCase/ }) as HTMLButtonElement).disabled).toBe(true);
});

it("marks downloaded pending appeal contents as a draft", async () => {
  const { AppealLetterEditor } = await import("../src/components/AppealLetterEditor");
  const fetcher = vi.fn(async () => new Response("draft PDF", { status: 200 }));
  vi.stubGlobal("fetch", fetcher);
  vi.stubGlobal("URL", { createObjectURL: vi.fn(() => "blob:draft-pdf"), revokeObjectURL: vi.fn() });
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  render(<AppealLetterEditor appeal={pending().appeal_draft!} caseId="pending-case" pendingReview />);
  fireEvent.click(screen.getByRole("button", { name: "Download PDF" }));
  await screen.findByRole("button", { name: "Download PDF" });
  expect(JSON.parse((fetcher.mock.calls[0][1] as RequestInit).body as string).appeal_body).toMatch(/^DRAFT — HUMAN REVIEW REQUIRED/);
});

it("reloads a human approval and its current patient letter without stale denial drafts", async () => {
  const approved = normalizeRunResult({
    ...pending(), decision: { verdict: "APPROVE", confidence: 1, rationale: "Clinician approved", citations: [], risk_flags: [] },
    provisional_decision: null, paused_for_review: false, human_review_required: false,
    documents_draft: false, appeal_draft: null,
    patient_communication: { ...pending().patient_communication, headline: "Reviewed approval letter" },
  });
  vi.mocked(api.getCase).mockResolvedValue({ case_id: "pending-case", payer_id: "aetna", patient_initials: "A.P.", status: "approved", physician_note: null, requested_treatment: { name: "trastuzumab", j_code: null }, created_at: null, pending_review: null, latest_result: approved });
  render(<MemoryRouter initialEntries={["/cases/pending-case"]}><Routes><Route path="/cases/:caseId" element={<CaseDetail />} /></Routes></MemoryRouter>);
  expect(await screen.findByText("Reviewed approval letter")).toBeTruthy();
  expect(screen.queryByText("AI proposed DENY")).toBeNull();
  expect(screen.queryByText("Proposed appeal evidence.")).toBeNull();
  expect((screen.getByRole("button", { name: "Email" }) as HTMLButtonElement).disabled).toBe(false);
});

it("lets a reviewer retry interrupted letters without submitting another clinical verdict", async () => {
  localStorage.setItem("clincase-user", JSON.stringify({ role: "reviewer" }));
  const info = { case_id: "pending-case", payer_id: "aetna", patient_initials: "A.P.", status: "denied", physician_note: null, requested_treatment: { name: "trastuzumab", j_code: null }, created_at: null };
  vi.mocked(api.getCase).mockResolvedValueOnce({ ...info, continuation: { status: "failed", can_retry: true } }).mockResolvedValueOnce({ ...info, continuation: null });
  vi.mocked(api.retryCaseLetters).mockResolvedValue({ status: "done" });
  render(<MemoryRouter initialEntries={["/cases/pending-case"]}><Routes><Route path="/cases/:caseId" element={<CaseDetail />} /></Routes></MemoryRouter>);
  fireEvent.click(await screen.findByRole("button", { name: "Retry letter generation" }));
  await vi.waitFor(() => expect(api.retryCaseLetters).toHaveBeenCalledWith("pending-case"));
  await vi.waitFor(() => expect(screen.queryByRole("button", { name: "Retry letter generation" })).toBeNull());
});
