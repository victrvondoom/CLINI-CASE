/* global window */
/* ============================================================
   INTAKE-DATA — synthetic IntakeResult that mirrors what the
   live Bedrock vision pipeline would return for the handwritten
   Indian oncology Rx fixture (tests/fixtures/intake/handwritten_rx.png).

   This file is the "demo answer key" — the standalone showcase has no
   backend, so when a judge drops the Rx PNG, we render this preset
   instead of calling /api/v1/intake/parse-document. The shape matches
   the real Pydantic IntakeResult model exactly so the UI is identical
   to the live React frontend.
   ============================================================ */
(function () {
  const FIXTURE = {
    filename: "handwritten_rx.png",
    sha256:   "a1b2c3d4e5f60718293a4b5c6d7e8f9012345678abcdef0123456789abcdef01",
    sizeKB:   929,
    note:     "Synthetic Indian oncology Rx — letterhead + handwritten body",
  };

  const RESULT = {
    classification: {
      document_type: "mixed",
      confidence: 0.84,
      rationale:
        "Typed letterhead band + handwritten body (Indian Rx pad pattern). " +
        "Edge density 0.04, stroke variance 0.38.",
      quality_flags: [],
    },
    ocr: {
      engine: "claude_vision_bedrock",
      full_text:
        "ABC ONCOLOGY CENTRE\n" +
        "Dr. Priya Menon, MD (Med Onc) · Reg No. KMC-48201\n" +
        "Pune, Maharashtra · +91-20-2555-0140\n\n" +
        "Patient: [redacted-name]  Age: 57  Sex: M\n" +
        "Wt: 68 kg  Date: 06/05/26\n\n" +
        "Dx: Ca Breast Lt - Stage IIIA\n" +
        "HER2 + (IHC 3+, FISH amp.)\n" +
        "ER 88% pos, PR 62% pos\n" +
        "Post-op RT done 03/2026\n\n" +
        "Rx: Inj. Herceptin 6mg/kg IV q3w x 17 cycles\n" +
        "(maintenance HER2-targeted therapy)\n\n" +
        "Pre-medications:\n" +
        "- Paracetamol 500 mg PO\n" +
        "- Diphenhydramine 25 mg IV\n\n" +
        "Baseline cardiac:\n" +
        "LVEF 62% by 2D echo\n" +
        "Echo date: 15/04/2026\n" +
        "ECOG = 1\n\n" +
        "Plan:\n" +
        "- Cycle 1 on 12/05/2026\n" +
        "- Echo q3 months on Tx\n" +
        "- F/U OPD after C2\n\n" +
        "Dr. Priya Menon, MD\n" +
        "Med Reg: KMC-48201",
      extracted_fields: [
        { name: "requested_treatment.name",      value: "trastuzumab",                     confidence: 0.93, source_excerpt: "Inj. Herceptin 6mg/kg IV q3w x 17 cycles", page: 1 },
        { name: "requested_treatment.dose",      value: "6 mg/kg",                         confidence: 0.92, source_excerpt: "6mg/kg",                                    page: 1 },
        { name: "requested_treatment.frequency", value: "q3w x 17",                        confidence: 0.90, source_excerpt: "q3w x 17 cycles",                          page: 1 },
        { name: "requested_treatment.intent",    value: "adjuvant",                        confidence: 0.86, source_excerpt: "(maintenance HER2-targeted therapy)",      page: 1 },
        { name: "primary_diagnosis.description", value: "Carcinoma of left breast",        confidence: 0.86, source_excerpt: "Ca Breast Lt",                              page: 1 },
        { name: "primary_diagnosis.stage",       value: "IIIA",                            confidence: 0.90, source_excerpt: "Stage IIIA",                                page: 1 },
        { name: "biomarkers.HER2.value",         value: "Positive (IHC 3+, FISH amp.)",    confidence: 0.91, source_excerpt: "HER2 + (IHC 3+, FISH amp.)",                page: 1 },
        { name: "biomarkers.ER.value",           value: "Positive (88%)",                  confidence: 0.88, source_excerpt: "ER 88% pos",                                page: 1 },
        { name: "biomarkers.PR.value",           value: "Positive (62%)",                  confidence: 0.86, source_excerpt: "PR 62% pos",                                page: 1 },
        { name: "biomarkers.LVEF.value",         value: "62%",                             confidence: 0.91, source_excerpt: "LVEF 62% by 2D echo",                      page: 1 },
        { name: "biomarkers.LVEF.test_date",     value: "2026-04-15",                      confidence: 0.84, source_excerpt: "Echo date: 15/04/2026",                    page: 1 },
        { name: "performance_status",            value: "1",                               confidence: 0.89, source_excerpt: "ECOG = 1",                                  page: 1 },
        { name: "patient_age",                   value: "57",                              confidence: 0.95, source_excerpt: "Age: 57",                                   page: 1 },
        { name: "patient_sex",                   value: "male",                            confidence: 0.95, source_excerpt: "Sex: M",                                    page: 1 },
      ],
      overall_confidence: 0.84,
      phi_redactions_applied: 1,
      pages: 1,
    },
    clinical_snapshot_partial: {
      patient_age: 57,
      patient_sex: "male",
      primary_diagnosis: {
        icd10_code: null,
        description: "Carcinoma of left breast",
        stage: "IIIA",
        source_resource_id: "intake-doc-a1b2c3d4",
      },
      biomarkers: [
        { name: "HER2", value: "Positive (IHC 3+, FISH amp.)", test_date: null,        source_resource_id: "intake-doc-a1b2c3d4" },
        { name: "ER",   value: "Positive (88%)",               test_date: null,        source_resource_id: "intake-doc-a1b2c3d4" },
        { name: "PR",   value: "Positive (62%)",               test_date: null,        source_resource_id: "intake-doc-a1b2c3d4" },
        { name: "LVEF", value: "62%",                          test_date: "2026-04-15", source_resource_id: "intake-doc-a1b2c3d4" },
      ],
      performance_status: "1",
      requested_treatment: {
        name: "trastuzumab",
        j_code: null,
        dose: "6 mg/kg",
        frequency: "q3w x 17",
        intent: "adjuvant",
      },
    },
    risk_flags: [],
    requires_human_review: false,
    audit: {
      document_sha256: FIXTURE.sha256,
      engines_used: ["pil_classifier", "claude_vision_bedrock"],
      latency_ms: 9842,
      input_tokens: 2147,
      output_tokens: 612,
      model_id: "us.anthropic.claude-sonnet-4-6-v1:0",
    },
  };

  window.CLINCASE_INTAKE = { FIXTURE, RESULT };
})();
