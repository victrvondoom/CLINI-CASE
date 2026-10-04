/** FHIR resources built only from the fields a person supplied in the form. */
export function manualCaseBundle(patientName: string, diagnosis: string, stage: string) {
  const condition: Record<string, unknown> = {
    resourceType: "Condition",
    id: "manual-diagnosis",
    subject: { reference: "Patient/manual-patient" },
    code: { text: diagnosis.trim() },
  };
  const icd = diagnosis.match(/\b([A-Z]\d{2}(?:\.\d{1,4})?)\b/);
  if (icd) {
    condition.code = {
      text: diagnosis.trim(),
      coding: [{ code: icd[1] }],
    };
  }
  if (stage) condition.stage = [{ summary: { text: `Stage ${stage}` } }];
  return {
    resourceType: "Bundle",
    type: "collection",
    entry: [
      { resource: { resourceType: "Patient", id: "manual-patient", name: [{ text: patientName.trim() }] } },
      { resource: condition },
    ],
  };
}

export function stripDemoHints(text: string): string {
  return text.replace(/__VERDICT_HINT_[A-Z]+__/gi, "").trim();
}

export async function caseCreationError(response: Response): Promise<string> {
  const raw = await response.text();
  try {
    const detail = JSON.parse(raw).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) return detail.map((item) => item.msg ?? "Invalid case input").join("; ");
    if (detail?.message) return detail.message;
  } catch { /* An upstream may return plain text. */ }
  return `HTTP ${response.status}: ${raw.slice(0, 200) || response.statusText}`;
}
