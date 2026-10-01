/**
 * Policy data for /policies and /policies/:id/diff. Mirrors the 21 entries in
 * backend/app/data/policies.json so the demo catalog reflects what the
 * Policy Retriever agent can actually retrieve. Diff data is fully synthetic —
 * represents a hypothetical v3.1 → v3.2 update on Aetna 0048.
 *
 * Cross-payer coverage:
 *  - trastuzumab: aetna, uhc, bcbs, anthem (4/4)
 *  - pembrolizumab: aetna, uhc, bcbs, anthem (4/4)
 *  - osimertinib: aetna, uhc, bcbs (3/4)
 * This makes Multi-payer Arbitration on the Compare page backend-real for
 * the top oncology drugs.
 */
import type { PayerId } from "./compareSimulation";

export interface Policy {
  payer_id: PayerId;
  policy_id: string;
  title: string;
  treatment_keywords: string[];
  source_url: string;
  version: string;
  last_updated_iso: string;
  word_count: number;
  section_count: number;
  /** Plausible per-payer logo character */
  initial: string;
  status: "current" | "updated_recently";
}

const D = (days: number): string =>
  new Date(Date.now() - days * 24 * 60 * 60 * 1000).toISOString();

export const POLICIES: Policy[] = [
  // ============ AETNA (6) ============
  {
    payer_id: "aetna",
    policy_id: "0048",
    title: "Trastuzumab (Herceptin) for HER2-Positive Breast Cancer",
    treatment_keywords: ["trastuzumab", "herceptin"],
    source_url: "https://www.aetna.com/cpb/medical/data/0048.html",
    version: "v3.2",
    last_updated_iso: D(14),
    word_count: 1247,
    section_count: 3,
    initial: "A",
    status: "updated_recently",
  },
  {
    payer_id: "aetna",
    policy_id: "0468",
    title: "Fam-Trastuzumab Deruxtecan (Enhertu, T-DXd)",
    treatment_keywords: ["t-dxd", "trastuzumab deruxtecan", "enhertu"],
    source_url: "https://www.aetna.com/cpb/medical/data/0468.html",
    version: "v2.0",
    last_updated_iso: D(90),
    word_count: 812,
    section_count: 2,
    initial: "A",
    status: "current",
  },
  {
    payer_id: "aetna",
    policy_id: "0421",
    title: "Olaparib (Lynparza) for BRCA-Mutated Cancers",
    treatment_keywords: ["olaparib", "lynparza"],
    source_url: "https://www.aetna.com/cpb/medical/data/0421.html",
    version: "v1.7",
    last_updated_iso: D(120),
    word_count: 758,
    section_count: 2,
    initial: "A",
    status: "current",
  },
  {
    payer_id: "aetna",
    policy_id: "0721",
    title: "Ribociclib (Kisqali) for HR+/HER2- Advanced Breast Cancer",
    treatment_keywords: ["ribociclib", "kisqali", "cdk4/6"],
    source_url: "https://www.aetna.com/cpb/medical/data/0721.html",
    version: "v2.1",
    last_updated_iso: D(22),
    word_count: 942,
    section_count: 2,
    initial: "A",
    status: "updated_recently",
  },
  {
    payer_id: "aetna",
    policy_id: "0556",
    title: "Pembrolizumab (Keytruda) for Solid Tumors",
    treatment_keywords: ["pembrolizumab", "keytruda"],
    source_url: "https://www.aetna.com/cpb/medical/data/0556.html",
    version: "v3.4",
    last_updated_iso: D(31),
    word_count: 1188,
    section_count: 2,
    initial: "A",
    status: "current",
  },
  {
    payer_id: "aetna",
    policy_id: "0613",
    title: "Osimertinib (Tagrisso) for EGFR-Mutated NSCLC",
    treatment_keywords: ["osimertinib", "tagrisso"],
    source_url: "https://www.aetna.com/cpb/medical/data/0613.html",
    version: "v2.0",
    last_updated_iso: D(48),
    word_count: 814,
    section_count: 1,
    initial: "A",
    status: "current",
  },

  // ============ UHC (5) ============
  {
    payer_id: "uhc",
    policy_id: "OnCG-2025-D045",
    title: "Osimertinib (Tagrisso) for EGFR-Mutated NSCLC",
    treatment_keywords: ["osimertinib", "tagrisso"],
    source_url: "https://www.uhcprovider.com/policies/oncology/osimertinib",
    version: "v1.4",
    last_updated_iso: D(45),
    word_count: 894,
    section_count: 2,
    initial: "U",
    status: "current",
  },
  {
    payer_id: "uhc",
    policy_id: "OnCG-2025-D012",
    title: "Trastuzumab (Herceptin) for HER2-Positive Breast and Gastric Cancer",
    treatment_keywords: ["trastuzumab", "herceptin"],
    source_url: "https://www.uhcprovider.com/policies/oncology/trastuzumab",
    version: "v2.6",
    last_updated_iso: D(28),
    word_count: 1402,
    section_count: 3,
    initial: "U",
    status: "current",
  },
  {
    payer_id: "uhc",
    policy_id: "OnCG-2025-D098",
    title: "Pembrolizumab (Keytruda) for Multi-Tumor Immunotherapy",
    treatment_keywords: ["pembrolizumab", "keytruda"],
    source_url: "https://www.uhcprovider.com/policies/oncology/pembrolizumab",
    version: "v3.1",
    last_updated_iso: D(18),
    word_count: 1614,
    section_count: 2,
    initial: "U",
    status: "updated_recently",
  },
  {
    payer_id: "uhc",
    policy_id: "OnCG-2025-D108",
    title: "Enzalutamide (Xtandi) for Castration-Resistant Prostate Cancer",
    treatment_keywords: ["enzalutamide", "xtandi"],
    source_url: "https://www.uhcprovider.com/policies/oncology/enzalutamide",
    version: "v1.3",
    last_updated_iso: D(75),
    word_count: 814,
    section_count: 2,
    initial: "U",
    status: "current",
  },
  {
    payer_id: "uhc",
    policy_id: "OnCG-2025-D211",
    title: "Lorlatinib (Lorbrena) for ALK-Positive NSCLC",
    treatment_keywords: ["lorlatinib", "lorbrena", "alk"],
    source_url: "https://www.uhcprovider.com/policies/oncology/lorlatinib",
    version: "v1.1",
    last_updated_iso: D(40),
    word_count: 776,
    section_count: 2,
    initial: "U",
    status: "current",
  },

  // ============ BCBS (5) ============
  {
    payer_id: "bcbs",
    policy_id: "PA-2025-014",
    title: "Pembrolizumab (Keytruda) for Solid Tumors",
    treatment_keywords: ["pembrolizumab", "keytruda"],
    source_url: "https://www.bcbs.com/provider/policy/pa-2025-014",
    version: "v2.2",
    last_updated_iso: D(60),
    word_count: 1583,
    section_count: 2,
    initial: "B",
    status: "current",
  },
  {
    payer_id: "bcbs",
    policy_id: "PA-2025-022",
    title: "Trastuzumab (Herceptin) for HER2-Positive Malignancies",
    treatment_keywords: ["trastuzumab", "herceptin"],
    source_url: "https://www.bcbs.com/provider/policy/pa-2025-022",
    version: "v2.8",
    last_updated_iso: D(36),
    word_count: 1318,
    section_count: 2,
    initial: "B",
    status: "current",
  },
  {
    payer_id: "bcbs",
    policy_id: "PA-2025-027",
    title: "Osimertinib (Tagrisso) for EGFR-Mutated NSCLC",
    treatment_keywords: ["osimertinib", "tagrisso"],
    source_url: "https://www.bcbs.com/provider/policy/pa-2025-027",
    version: "v1.5",
    last_updated_iso: D(52),
    word_count: 982,
    section_count: 2,
    initial: "B",
    status: "current",
  },
  {
    payer_id: "bcbs",
    policy_id: "PA-2025-029",
    title: "Brentuximab Vedotin (Adcetris) for Classical Hodgkin Lymphoma",
    treatment_keywords: ["brentuximab", "adcetris", "cd30"],
    source_url: "https://www.bcbs.com/provider/policy/pa-2025-029",
    version: "v2.4",
    last_updated_iso: D(95),
    word_count: 1102,
    section_count: 3,
    initial: "B",
    status: "current",
  },
  {
    payer_id: "bcbs",
    policy_id: "PA-2025-035",
    title: "Nivolumab (Opdivo) for Solid Tumors and Hematologic Malignancies",
    treatment_keywords: ["nivolumab", "opdivo"],
    source_url: "https://www.bcbs.com/provider/policy/pa-2025-035",
    version: "v3.0",
    last_updated_iso: D(5),
    word_count: 1726,
    section_count: 3,
    initial: "B",
    status: "updated_recently",
  },

  // ============ ANTHEM (5) ============
  {
    payer_id: "anthem",
    policy_id: "MED-2026-014",
    title: "Bevacizumab (Avastin) for Multi-Tumor Indications",
    treatment_keywords: ["bevacizumab", "avastin", "vegf"],
    source_url: "https://www.anthem.com/medicalpolicies/MED-2026-014.html",
    version: "v4.0",
    last_updated_iso: D(180),
    word_count: 1547,
    section_count: 4,
    initial: "N",
    status: "current",
  },
  {
    payer_id: "anthem",
    policy_id: "MED-2026-019",
    title: "Imatinib (Gleevec) for CML and GIST",
    treatment_keywords: ["imatinib", "gleevec", "tki"],
    source_url: "https://www.anthem.com/medicalpolicies/MED-2026-019.html",
    version: "v5.2",
    last_updated_iso: D(220),
    word_count: 789,
    section_count: 2,
    initial: "N",
    status: "current",
  },
  {
    payer_id: "anthem",
    policy_id: "MED-2026-031",
    title: "Trastuzumab (Herceptin) for HER2-Positive Cancers",
    treatment_keywords: ["trastuzumab", "herceptin"],
    source_url: "https://www.anthem.com/medicalpolicies/MED-2026-031.html",
    version: "v3.5",
    last_updated_iso: D(11),
    word_count: 1281,
    section_count: 2,
    initial: "N",
    status: "updated_recently",
  },
  {
    payer_id: "anthem",
    policy_id: "MED-2026-038",
    title: "Pembrolizumab (Keytruda) for Solid Tumor Immunotherapy",
    treatment_keywords: ["pembrolizumab", "keytruda"],
    source_url: "https://www.anthem.com/medicalpolicies/MED-2026-038.html",
    version: "v2.9",
    last_updated_iso: D(24),
    word_count: 1492,
    section_count: 3,
    initial: "N",
    status: "updated_recently",
  },
  {
    payer_id: "anthem",
    policy_id: "MED-2026-044",
    title: "Olaparib (Lynparza) for HRR-Mutated Cancers",
    treatment_keywords: ["olaparib", "lynparza"],
    source_url: "https://www.anthem.com/medicalpolicies/MED-2026-044.html",
    version: "v1.6",
    last_updated_iso: D(67),
    word_count: 851,
    section_count: 2,
    initial: "N",
    status: "current",
  },
];

// =============================================================================
// Synthetic policy diff (Aetna 0048 v3.1 → v3.2) for /policies/0048/diff
// =============================================================================

export interface DiffSegment {
  type: "unchanged" | "removed" | "added";
  text: string;
}

export interface PolicyDiff {
  policy_id: string;
  payer_id: PayerId;
  title: string;
  from_version: string;
  to_version: string;
  changed_at_iso: string;
  segments_v_old: DiffSegment[];
  segments_v_new: DiffSegment[];
  summary_changes: string[];
  affected_in_flight_cases: {
    case_id: string;
    patient: string;
    treatment: string;
    old_verdict: "APPROVE" | "REFER" | "DENY";
    new_verdict: "APPROVE" | "REFER" | "DENY";
    reason: string;
  }[];
}

export const POLICY_DIFFS: Record<string, PolicyDiff> = {
  "0048": {
    policy_id: "0048",
    payer_id: "aetna",
    title: "Trastuzumab (Herceptin) for HER2-Positive Breast Cancer",
    from_version: "v3.1",
    to_version: "v3.2",
    changed_at_iso: new Date(Date.now() - 14 * 24 * 60 * 60 * 1000).toISOString(),
    segments_v_old: [
      { type: "unchanged", text: "Aetna considers trastuzumab medically necessary when ALL of the following are met:\n\n(1) Pathologic confirmation of HER2 overexpression (IHC 3+ or ISH amplified).\n(2) For early-stage (Stage I-III), given in adjuvant or neoadjuvant setting with chemotherapy.\n(3) Adequate baseline cardiac function defined as " },
      { type: "removed",   text: "LVEF >= 50% by echocardiogram or MUGA scan within 90 days of treatment initiation." },
      { type: "unchanged", text: "\n(4) ECOG performance status 0, 1, or 2." },
    ],
    segments_v_new: [
      { type: "unchanged", text: "Aetna considers trastuzumab medically necessary when ALL of the following are met:\n\n(1) Pathologic confirmation of HER2 overexpression (IHC 3+ or ISH amplified).\n(2) For early-stage (Stage I-III), given in adjuvant or neoadjuvant setting with chemotherapy.\n(3) Adequate baseline cardiac function defined as " },
      { type: "added",     text: "LVEF >= 50% by echocardiogram or MUGA scan within 60 days of treatment initiation. If patient has prior anthracycline exposure, LVEF assessment required within 30 days." },
      { type: "unchanged", text: "\n(4) ECOG performance status 0, 1, or 2." },
    ],
    summary_changes: [
      "LVEF assessment window tightened from 90 days → 60 days",
      "New stricter requirement (30 days) for patients with prior anthracycline exposure",
      "ECOG 0-2 unchanged",
      "HER2 IHC/ISH criteria unchanged",
    ],
    affected_in_flight_cases: [
      {
        case_id: "case_a8f23910",
        patient: "S.D.",
        treatment: "trastuzumab",
        old_verdict: "APPROVE",
        new_verdict: "REFER",
        reason: "LVEF dated 75d ago; outside new 60-day window",
      },
      {
        case_id: "case_8f4ad9c2",
        patient: "S.D.",
        treatment: "trastuzumab",
        old_verdict: "APPROVE",
        new_verdict: "APPROVE",
        reason: "LVEF dated 16d ago; within new window",
      },
      {
        case_id: "case_b8d84d77",
        patient: "M.D.",
        treatment: "trastuzumab",
        old_verdict: "DENY",
        new_verdict: "DENY",
        reason: "Biomarker mismatch unchanged",
      },
      {
        case_id: "case_e9128d3c",
        patient: "F.E.",
        treatment: "T-DXd",
        old_verdict: "APPROVE",
        new_verdict: "REFER",
        reason: "Prior anthracycline; new 30-day LVEF requirement triggered",
      },
      {
        case_id: "case_1a4b9c2e",
        patient: "H.S.",
        treatment: "olaparib",
        old_verdict: "APPROVE",
        new_verdict: "APPROVE",
        reason: "Different policy; not affected by this diff",
      },
    ],
  },
};
