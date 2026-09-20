// ClinCase demo fixtures — three realistic prior-auth scenarios for oncology.
// Data shapes mirror the FHIR R4 + NCCN-cited types in the brief.

const FIXTURES = [
  {
    name: "her2_positive_approve",
    title: "HER2+ Stage IIIA — trastuzumab",
    description:
      "Adjuvant trastuzumab + paclitaxel for HER2-positive invasive ductal carcinoma. LVEF documented at 62%. All inclusion criteria met under Aetna policy 0123.",
    expected_verdict: "APPROVE",
    payer: "aetna",
    payer_id: "AETNA-COMMERCIAL-2026",
    treatment: "Trastuzumab",
    j_code: "J9355",
    hcpcs_code: "J9355",
    initials: "M.K.",
    case_id: "case_8f4ad9c2",
    requested_treatment_full: "Trastuzumab 6 mg/kg IV q3w × 17 cycles",
  },
  {
    name: "her2_positive_refer",
    title: "HER2+ Stage IIIA — missing LVEF",
    description:
      "Same patient, same regimen — but no baseline LVEF on file. Necessity Reasoner flags AMBIGUOUS on cardiac workup criterion. Verdict REFER for human review.",
    expected_verdict: "REFER",
    payer: "aetna",
    payer_id: "AETNA-COMMERCIAL-2026",
    treatment: "Trastuzumab",
    j_code: "J9355",
    hcpcs_code: "J9355",
    initials: "M.K.",
    case_id: "case_3b21e0fa",
    requested_treatment_full: "Trastuzumab 6 mg/kg IV q3w × 17 cycles",
  },
  {
    name: "her2_negative_deny",
    title: "HER2-negative — biomarker mismatch",
    description:
      "Trastuzumab requested for IHC 0 / FISH non-amplified tumor. Exclusion criterion failed. Verdict DENY; appeal letter auto-drafted with NCCN BINV-N citations.",
    expected_verdict: "DENY",
    payer: "uhc",
    payer_id: "UHC-COMMERCIAL-2026",
    treatment: "Trastuzumab",
    j_code: "J9355",
    hcpcs_code: "J9355",
    initials: "R.S.",
    case_id: "case_d710c4be",
    requested_treatment_full: "Trastuzumab 6 mg/kg IV q3w × 17 cycles",
  },
];

const CLINICAL_SNAPSHOTS = {
  her2_positive_approve: {
    patient_age: 54,
    patient_sex: "female",
    primary_diagnosis: {
      icd10_code: "C50.911",
      description: "Malignant neoplasm of right breast, female",
      stage: "IIIA",
      source_resource_id: "Condition/cond-7821",
    },
    biomarkers: [
      { name: "HER2 IHC", value: "3+", source_resource_id: "Observation/obs-901" },
      { name: "HER2 FISH", value: "amplified (ratio 4.8)", source_resource_id: "Observation/obs-902" },
      { name: "ER", value: "positive (95%)", source_resource_id: "Observation/obs-903" },
      { name: "PR", value: "positive (60%)", source_resource_id: "Observation/obs-904" },
      { name: "Ki-67", value: "32%", source_resource_id: "Observation/obs-905" },
      { name: "LVEF", value: "62%", source_resource_id: "Observation/obs-906" },
    ],
    performance_status: "ECOG 1",
    requested_treatment: {
      name: "Trastuzumab",
      j_code: "J9355",
      hcpcs_code: "J9355",
      regimen: "6 mg/kg IV q3w × 17 cycles",
    },
    free_text_summary:
      "54-year-old female with right-breast invasive ductal carcinoma, T2N2M0 (Stage IIIA). Tumor is HER2-positive (IHC 3+, FISH-amplified ratio 4.8) and strongly hormone-receptor positive. Baseline LVEF 62% (MUGA, 2026-04-02). ECOG 1. Cardiology cleared for HER2-directed therapy on 2026-04-09. Provider requests adjuvant trastuzumab per NCCN BINV-N pathway following AC × 4 induction.",
  },
  her2_positive_refer: {
    patient_age: 54,
    patient_sex: "female",
    primary_diagnosis: {
      icd10_code: "C50.911",
      description: "Malignant neoplasm of right breast, female",
      stage: "IIIA",
      source_resource_id: "Condition/cond-7821",
    },
    biomarkers: [
      { name: "HER2 IHC", value: "3+", source_resource_id: "Observation/obs-901" },
      { name: "HER2 FISH", value: "amplified (ratio 4.8)", source_resource_id: "Observation/obs-902" },
      { name: "ER", value: "positive (95%)", source_resource_id: "Observation/obs-903" },
      { name: "PR", value: "positive (60%)", source_resource_id: "Observation/obs-904" },
      { name: "Ki-67", value: "32%", source_resource_id: "Observation/obs-905" },
    ],
    performance_status: "ECOG 1",
    requested_treatment: {
      name: "Trastuzumab",
      j_code: "J9355",
      hcpcs_code: "J9355",
      regimen: "6 mg/kg IV q3w × 17 cycles",
    },
    free_text_summary:
      "54-year-old female with right-breast invasive ductal carcinoma, T2N2M0 (Stage IIIA). Tumor is HER2-positive (IHC 3+, FISH-amplified). No baseline LVEF or MUGA on file in the FHIR bundle. ECOG 1. Provider requests adjuvant trastuzumab per NCCN BINV-N pathway. Cardiac workup is required by Aetna policy 0123 §4.2 prior to HER2-directed therapy.",
  },
  her2_negative_deny: {
    patient_age: 61,
    patient_sex: "female",
    primary_diagnosis: {
      icd10_code: "C50.912",
      description: "Malignant neoplasm of left breast, female",
      stage: "IIB",
      source_resource_id: "Condition/cond-4412",
    },
    biomarkers: [
      { name: "HER2 IHC", value: "0", source_resource_id: "Observation/obs-2201" },
      { name: "HER2 FISH", value: "non-amplified (ratio 1.1)", source_resource_id: "Observation/obs-2202" },
      { name: "ER", value: "positive (88%)", source_resource_id: "Observation/obs-2203" },
      { name: "PR", value: "positive (45%)", source_resource_id: "Observation/obs-2204" },
      { name: "LVEF", value: "65%", source_resource_id: "Observation/obs-2205" },
    ],
    performance_status: "ECOG 0",
    requested_treatment: {
      name: "Trastuzumab",
      j_code: "J9355",
      hcpcs_code: "J9355",
      regimen: "6 mg/kg IV q3w × 17 cycles",
    },
    free_text_summary:
      "61-year-old female with left-breast invasive ductal carcinoma, T2N1M0 (Stage IIB). Pathology demonstrates HER2 IHC 0 with FISH ratio 1.1 (non-amplified) — definitively HER2-negative per ASCO/CAP 2018 guidelines. Strongly hormone-receptor positive. Provider requests trastuzumab; this is inconsistent with NCCN BINV-N which restricts HER2-directed therapy to HER2-positive disease.",
  },
};

const POLICY_EXCERPTS = {
  her2_positive_approve: [
    {
      payer_id: "AETNA-COMMERCIAL-2026",
      policy_id: "0123",
      section: "§4.1",
      title: "Trastuzumab — Indications (HER2-positive breast cancer)",
      text: "Trastuzumab is medically necessary for adjuvant treatment of HER2-overexpressing (IHC 3+ or FISH-amplified, HER2/CEP17 ratio ≥ 2.0) node-positive or high-risk node-negative invasive breast cancer.",
    },
    {
      payer_id: "AETNA-COMMERCIAL-2026",
      policy_id: "0123",
      section: "§4.2",
      title: "Cardiac workup requirement",
      text: "Baseline LVEF (echocardiogram or MUGA) must be documented within 90 days of initiation; LVEF must be ≥ 50% or ≥ institutional lower limit of normal.",
    },
    {
      payer_id: "NCCN",
      policy_id: "BINV-N",
      section: "v3.2026",
      title: "NCCN — Preoperative/Adjuvant Therapy for HER2-Positive Disease",
      text: "For HER2-positive Stage II–III disease, AC followed by paclitaxel + trastuzumab (Category 1) is preferred when anthracyclines are appropriate.",
    },
  ],
  her2_positive_refer: [
    {
      payer_id: "AETNA-COMMERCIAL-2026",
      policy_id: "0123",
      section: "§4.2",
      title: "Cardiac workup requirement",
      text: "Baseline LVEF (echocardiogram or MUGA) must be documented within 90 days of initiation; LVEF must be ≥ 50% or ≥ institutional lower limit of normal.",
    },
    {
      payer_id: "AETNA-COMMERCIAL-2026",
      policy_id: "0123",
      section: "§4.1",
      title: "Trastuzumab — Indications (HER2-positive breast cancer)",
      text: "Trastuzumab is medically necessary for adjuvant treatment of HER2-overexpressing (IHC 3+ or FISH-amplified, HER2/CEP17 ratio ≥ 2.0) node-positive or high-risk node-negative invasive breast cancer.",
    },
  ],
  her2_negative_deny: [
    {
      payer_id: "UHC-COMMERCIAL-2026",
      policy_id: "ONC.00043",
      section: "§3.1",
      title: "Trastuzumab — Coverage Criteria",
      text: "Coverage requires documented HER2-positivity by IHC 3+ OR FISH HER2/CEP17 ratio ≥ 2.0. HER2-negative disease (IHC 0/1+ with non-amplified FISH) is an exclusion.",
    },
    {
      payer_id: "NCCN",
      policy_id: "BINV-N",
      section: "v3.2026",
      title: "NCCN — HER2-Directed Therapy",
      text: "HER2-directed therapy (trastuzumab, pertuzumab, T-DM1) is indicated only in HER2-positive disease as defined by ASCO/CAP 2018 testing guidelines.",
    },
  ],
};

const NECESSITY = {
  her2_positive_approve: [
    { criterion: "HER2-positive disease (IHC 3+ or FISH-amplified)", type: "inclusion", status: "MET", evidence: "IHC 3+, FISH ratio 4.8 — Observation/obs-901, obs-902" },
    { criterion: "Stage II–III invasive breast cancer", type: "inclusion", status: "MET", evidence: "Stage IIIA, T2N2M0 — Condition/cond-7821" },
    { criterion: "Baseline LVEF ≥ 50% within 90 days", type: "inclusion", status: "MET", evidence: "LVEF 62% on 2026-04-02 — Observation/obs-906" },
    { criterion: "ECOG performance status 0–2", type: "inclusion", status: "MET", evidence: "ECOG 1 — Observation/obs-907" },
    { criterion: "Active uncontrolled cardiac disease", type: "exclusion", status: "MET", evidence: "Cardiology clearance 2026-04-09 — DocumentReference/doc-3201" },
  ],
  her2_positive_refer: [
    { criterion: "HER2-positive disease", type: "inclusion", status: "MET", evidence: "IHC 3+, FISH ratio 4.8" },
    { criterion: "Stage II–III invasive breast cancer", type: "inclusion", status: "MET", evidence: "Stage IIIA" },
    { criterion: "Baseline LVEF ≥ 50% within 90 days", type: "inclusion", status: "AMBIGUOUS", evidence: "No LVEF/MUGA Observation found in bundle — missing_evidence" },
    { criterion: "ECOG performance status 0–2", type: "inclusion", status: "MET", evidence: "ECOG 1" },
  ],
  her2_negative_deny: [
    { criterion: "HER2-positive disease (IHC 3+ or FISH ≥ 2.0)", type: "inclusion", status: "NOT_MET", evidence: "IHC 0, FISH ratio 1.1 (non-amplified) — Observation/obs-2201, obs-2202" },
    { criterion: "Stage II–III invasive breast cancer", type: "inclusion", status: "MET", evidence: "Stage IIB, T2N1M0" },
    { criterion: "Baseline LVEF ≥ 50% within 90 days", type: "inclusion", status: "MET", evidence: "LVEF 65%" },
    { criterion: "HER2-negative disease (excluded)", type: "exclusion", status: "NOT_MET", evidence: "Patient is HER2-negative — exclusion failed" },
  ],
};

const DECISIONS = {
  her2_positive_approve: {
    verdict: "APPROVE",
    confidence: 0.92,
    rationale:
      "All five inclusion criteria for trastuzumab under Aetna policy 0123 are met. HER2-positivity is confirmed by both IHC (3+) and FISH (ratio 4.8). Baseline LVEF of 62% satisfies the cardiac workup requirement. ECOG 1 and cardiology clearance support tolerability. NCCN BINV-N v3.2026 lists AC → paclitaxel + trastuzumab as Category 1 for this presentation.",
    citations: [
      { kind: "clinical", text: "HER2 IHC 3+", pointer: "Observation/obs-901" },
      { kind: "clinical", text: "HER2 FISH amplified (4.8)", pointer: "Observation/obs-902" },
      { kind: "clinical", text: "LVEF 62% MUGA 2026-04-02", pointer: "Observation/obs-906" },
      { kind: "clinical", text: "Stage IIIA T2N2M0", pointer: "Condition/cond-7821" },
      { kind: "policy", text: "Aetna 0123 §4.1 indications", pointer: "policy/aetna-0123#4.1" },
      { kind: "policy", text: "Aetna 0123 §4.2 cardiac workup", pointer: "policy/aetna-0123#4.2" },
      { kind: "policy", text: "NCCN BINV-N v3.2026", pointer: "nccn/BINV-N" },
    ],
    risk_flags: [],
  },
  her2_positive_refer: {
    verdict: "REFER",
    confidence: 0.71,
    rationale:
      "Four of five inclusion criteria are met. Cardiac workup criterion is AMBIGUOUS — the FHIR bundle contains no LVEF or MUGA Observation within the 90-day window. ClinCase declines to auto-approve in the absence of cardiac evidence; this case is escalated to a human reviewer per Aetna policy 0123 §4.2.",
    citations: [
      { kind: "clinical", text: "HER2 IHC 3+", pointer: "Observation/obs-901" },
      { kind: "clinical", text: "Stage IIIA", pointer: "Condition/cond-7821" },
      { kind: "clinical", text: "missing LVEF / MUGA", pointer: "missing_evidence:LVEF" },
      { kind: "policy", text: "Aetna 0123 §4.2 cardiac workup", pointer: "policy/aetna-0123#4.2" },
    ],
    risk_flags: ["missing-cardiac-workup", "evidence-incomplete"],
  },
  her2_negative_deny: {
    verdict: "DENY",
    confidence: 0.97,
    rationale:
      "The patient's tumor is definitively HER2-negative: IHC 0 with non-amplified FISH (ratio 1.1) per ASCO/CAP 2018 testing guidelines. UHC ONC.00043 §3.1 explicitly excludes HER2-negative disease from trastuzumab coverage. NCCN BINV-N v3.2026 restricts HER2-directed therapy to HER2-positive disease. ClinCase denies the request and drafts an appeal preserving the provider's right to contest.",
    citations: [
      { kind: "clinical", text: "HER2 IHC 0", pointer: "Observation/obs-2201" },
      { kind: "clinical", text: "HER2 FISH non-amplified (1.1)", pointer: "Observation/obs-2202" },
      { kind: "policy", text: "UHC ONC.00043 §3.1 exclusion", pointer: "policy/uhc-onc00043#3.1" },
      { kind: "policy", text: "NCCN BINV-N v3.2026", pointer: "nccn/BINV-N" },
      { kind: "policy", text: "ASCO/CAP 2018 HER2 testing", pointer: "asco-cap-2018" },
    ],
    risk_flags: ["biomarker-mismatch", "exclusion-criterion-failed"],
  },
};

const APPEAL_DRAFT = {
  patient_initials: "R.S.",
  payer_id: "UHC-COMMERCIAL-2026",
  requested_treatment: "Trastuzumab (J9355)",
  denial_date: "2026-04-30",
  appeal_body: `Dear UnitedHealthcare Medical Director,

I am writing to formally appeal the denial of prior authorisation for trastuzumab (HCPCS J9355) for my patient R.S., dated 2026-04-30 under policy ONC.00043.

The denial cites HER2-negativity as an exclusion criterion. After thorough review of the case, I respectfully agree with the denial in this specific instance and request that the record reflect a reconciled determination rather than a contested one. The patient's tumor is documented as HER2 IHC 0 with FISH ratio 1.1, which is non-amplified per ASCO/CAP 2018 guidelines. NCCN BINV-N v3.2026 restricts HER2-directed therapy to HER2-positive disease, and trastuzumab in HER2-negative disease has not demonstrated benefit in randomised trials (NSABP B-47, JCO 2020).

We are concurrently submitting a corrected request for an appropriate regimen aligned with the patient's hormone-receptor-positive, HER2-negative profile (NCCN BINV-L), specifically an aromatase inhibitor with consideration of a CDK4/6 inhibitor per nodal status and Oncotype DX recurrence score (pending; expected 2026-05-04).

This letter preserves the patient's right to a peer-to-peer review should new biomarker data emerge. We attach the pathology report, FISH report, and the relevant NCCN excerpts. We request acknowledgement within 14 days per CMS-0057-F timelines.

Sincerely,
Dr. A. Mehta, MD — Medical Oncology
NPI 1346789021 · Tata Memorial Centre, Mumbai`,
  structured_arguments: [
    {
      contested_criterion: "HER2-positivity (UHC ONC.00043 §3.1)",
      payer_position: "Trastuzumab is excluded for HER2-negative disease (IHC 0/1+ with non-amplified FISH).",
      counter_position: "Provider acknowledges HER2-negativity. Appeal is submitted to reconcile the record and preserve appeal rights for any future biomarker re-testing per ASCO/CAP 2018.",
      cited_evidence: ["IHC 0 (Observation/obs-2201)", "FISH ratio 1.1 (Observation/obs-2202)"],
      cited_guideline: "ASCO/CAP 2018 HER2 testing in invasive breast cancer",
    },
    {
      contested_criterion: "Treatment alignment (NCCN BINV-N v3.2026)",
      payer_position: "HER2-directed therapy not indicated.",
      counter_position: "A corrected request aligned with NCCN BINV-L (HR+/HER2– pathway) is being submitted in parallel. We request expedited review of the corrected authorisation to avoid treatment delay.",
      cited_evidence: ["ER 88% positive (Observation/obs-2203)", "PR 45% positive (Observation/obs-2204)"],
      cited_guideline: "NCCN BINV-L v3.2026 — HR-positive/HER2-negative disease",
    },
  ],
  attachments_referenced: [
    "Pathology report 2026-04-12",
    "FISH report 2026-04-15",
    "NCCN BINV-N v3.2026 excerpt",
    "ASCO/CAP 2018 testing guideline",
  ],
  requested_action:
    "Acknowledge denial as reconciled (not contested) and pre-authorise expedited review of corrected NCCN BINV-L request within 14 days per CMS-0057-F.",
};

const AGENT_SPECS = [
  {
    key: "clinical_extractor",
    name: "Clinical Extractor",
    description: "Parses FHIR R4 bundle + physician note into a typed ClinicalSnapshot.",
    model: "anthropic/claude-sonnet-4-6",
  },
  {
    key: "policy_retriever",
    name: "Policy Retriever",
    description: "Keyword filter + LLM rerank over payer medical policy corpus.",
    model: "anthropic/claude-sonnet-4-6",
  },
  {
    key: "necessity_reasoner",
    name: "Necessity Reasoner",
    description: "Line-by-line criterion matching with MET / NOT_MET / AMBIGUOUS.",
    model: "anthropic/claude-sonnet-4-6",
  },
  {
    key: "decision_composer",
    name: "Decision Composer",
    description: "Synthesises verdict, confidence, and citation chain.",
    model: "anthropic/claude-sonnet-4-6",
  },
  {
    key: "appeals_drafter",
    name: "Appeals Drafter",
    description: "On DENY: drafts NCCN-cited appeal letter and structured arguments.",
    model: "anthropic/claude-sonnet-4-6",
  },
];

// Realistic-looking token + latency profiles per agent per fixture
function buildAgentRuns(fixtureName) {
  const baseFor = {
    her2_positive_approve: [
      { in: 4820, out: 612, ms: 2140 },
      { in: 6311, out: 488, ms: 2680 },
      { in: 7402, out: 921, ms: 3120 },
      { in: 5104, out: 540, ms: 1980 },
    ],
    her2_positive_refer: [
      { in: 4612, out: 598, ms: 2010 },
      { in: 6188, out: 471, ms: 2540 },
      { in: 7301, out: 1042, ms: 3340 },
      { in: 5022, out: 612, ms: 2110 },
    ],
    her2_negative_deny: [
      { in: 4790, out: 588, ms: 2080 },
      { in: 6402, out: 502, ms: 2710 },
      { in: 7228, out: 884, ms: 3050 },
      { in: 5310, out: 511, ms: 2030 },
      { in: 6820, out: 1812, ms: 4520 }, // appeals drafter
    ],
  };
  return baseFor[fixtureName] || baseFor.her2_positive_approve;
}

window.CLINCASE_DATA = {
  FIXTURES,
  CLINICAL_SNAPSHOTS,
  POLICY_EXCERPTS,
  NECESSITY,
  DECISIONS,
  APPEAL_DRAFT,
  AGENT_SPECS,
  buildAgentRuns,
};
