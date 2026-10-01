/**
 * Synthetic case data for the /cases page. 12 realistic rows mixing the 3
 * demo fixtures with 9 historical cases across multiple payers / treatments.
 *
 * Phase 3+ may swap to a real backend list endpoint; for now this gives the
 * Cases page production-feel data immediately.
 */
import type { Verdict } from "./types";

export type CaseStatus =
  | "pending"
  | "running"
  | "approved"
  | "denied"
  | "referred"
  | "appealed"
  | "overturned";

export interface SyntheticCase {
  case_id: string;
  status: CaseStatus;
  patient_initials: string;
  treatment: string;
  j_code: string;
  payer_id: "aetna" | "uhc" | "bcbs" | "anthem";
  verdict: Verdict | null;
  confidence: number | null;  // 0..1
  submitted_at: string;        // ISO
  ago: string;                 // human-readable
  diagnosis: string;
  stage: string;
  is_synthetic?: boolean;
}

const now = Date.now();
const minute = 60_000;
const hour = 60 * minute;
const day = 24 * hour;

function ago(ms: number): string {
  if (ms < hour)        return `${Math.round(ms / minute)}m ago`;
  if (ms < day)         return `${Math.round(ms / hour)}h ago`;
  if (ms < 30 * day)    return `${Math.round(ms / day)}d ago`;
  return `${Math.round(ms / (30 * day))}mo ago`;
}

function iso(msAgo: number): string {
  return new Date(now - msAgo).toISOString();
}

export const SYNTHETIC_CASES: SyntheticCase[] = [
  // Top of list — recent demo fixtures (correspond to the 3 expected fixtures)
  {
    case_id: "case_8f4ad9c2", status: "approved", patient_initials: "S.D.",
    treatment: "trastuzumab", j_code: "J9355", payer_id: "aetna",
    verdict: "APPROVE", confidence: 0.92,
    submitted_at: iso(2 * minute), ago: ago(2 * minute),
    diagnosis: "Breast cancer (C50.911)", stage: "IIIA",
  },
  {
    case_id: "case_b8d84d77", status: "appealed", patient_initials: "M.D.",
    treatment: "trastuzumab", j_code: "J9355", payer_id: "aetna",
    verdict: "DENY", confidence: 0.50,
    submitted_at: iso(8 * minute), ago: ago(8 * minute),
    diagnosis: "Breast cancer (C50.912)", stage: "IIIB",
  },
  {
    case_id: "case_f7c44d9e", status: "referred", patient_initials: "J.D.",
    treatment: "trastuzumab", j_code: "J9355", payer_id: "aetna",
    verdict: "REFER", confidence: 0.50,
    submitted_at: iso(15 * minute), ago: ago(15 * minute),
    diagnosis: "Breast cancer (C50.911)", stage: "IIIA",
  },
  // Historical
  {
    case_id: "case_a8f23910", status: "approved", patient_initials: "R.K.",
    treatment: "osimertinib", j_code: "J9335", payer_id: "uhc",
    verdict: "APPROVE", confidence: 0.94,
    submitted_at: iso(27 * minute), ago: ago(27 * minute),
    diagnosis: "NSCLC (C34.91)", stage: "IIIB",
    is_synthetic: true,
  },
  {
    case_id: "case_3d44e1b9", status: "referred", patient_initials: "P.N.",
    treatment: "pembrolizumab", j_code: "J9271", payer_id: "bcbs",
    verdict: "REFER", confidence: 0.62,
    submitted_at: iso(1 * hour), ago: ago(1 * hour),
    diagnosis: "Colorectal (C18.9)", stage: "II",
    is_synthetic: true,
  },
  {
    case_id: "case_9c12fa70", status: "approved", patient_initials: "T.O.",
    treatment: "olaparib", j_code: "J9305", payer_id: "aetna",
    verdict: "APPROVE", confidence: 0.96,
    submitted_at: iso(3 * hour), ago: ago(3 * hour),
    diagnosis: "Ovarian (C56.9)", stage: "III",
    is_synthetic: true,
  },
  {
    case_id: "case_5e87bb31", status: "denied", patient_initials: "L.W.",
    treatment: "trastuzumab", j_code: "J9355", payer_id: "aetna",
    verdict: "DENY", confidence: 0.48,
    submitted_at: iso(5 * hour), ago: ago(5 * hour),
    diagnosis: "Breast cancer (C50.911)", stage: "IIIA",
    is_synthetic: true,
  },
  {
    case_id: "case_2b1f8a04", status: "approved", patient_initials: "K.M.",
    treatment: "dabrafenib + trametinib", j_code: "J9999", payer_id: "uhc",
    verdict: "APPROVE", confidence: 0.91,
    submitted_at: iso(8 * hour), ago: ago(8 * hour),
    diagnosis: "Melanoma (C43.9)", stage: "IV",
    is_synthetic: true,
  },
  {
    case_id: "case_7d3299f1", status: "overturned", patient_initials: "A.B.",
    treatment: "pembrolizumab", j_code: "J9271", payer_id: "bcbs",
    verdict: "APPROVE", confidence: 0.89,
    submitted_at: iso(13 * hour), ago: ago(13 * hour),
    diagnosis: "Melanoma (C43.5)", stage: "IV",
    is_synthetic: true,
  },
  {
    case_id: "case_e9128d3c", status: "approved", patient_initials: "F.E.",
    treatment: "T-DXd (trastuzumab deruxtecan)", j_code: "J9358", payer_id: "aetna",
    verdict: "APPROVE", confidence: 0.95,
    submitted_at: iso(1 * day), ago: ago(1 * day),
    diagnosis: "Breast cancer (C50.911)", stage: "IV",
    is_synthetic: true,
  },
  {
    case_id: "case_1a4b9c2e", status: "running", patient_initials: "H.S.",
    treatment: "olaparib", j_code: "J9305", payer_id: "aetna",
    verdict: null, confidence: null,
    submitted_at: iso(45 * minute), ago: ago(45 * minute),
    diagnosis: "Ovarian (C56.9)", stage: "II",
    is_synthetic: true,
  },
  {
    case_id: "case_6a7b8c9d", status: "appealed", patient_initials: "C.R.",
    treatment: "osimertinib", j_code: "J9335", payer_id: "anthem",
    verdict: "DENY", confidence: 0.55,
    submitted_at: iso(2 * day), ago: ago(2 * day),
    diagnosis: "NSCLC (C34.10)", stage: "IV",
    is_synthetic: true,
  },
  {
    case_id: "case_4f8c1a92", status: "approved", patient_initials: "B.T.",
    treatment: "ribociclib", j_code: "J9999", payer_id: "aetna",
    verdict: "APPROVE", confidence: 0.93,
    submitted_at: iso(3 * day), ago: ago(3 * day),
    diagnosis: "Breast cancer (C50.912)", stage: "IV",
    is_synthetic: true,
  },
  {
    case_id: "case_9b3e72fa", status: "approved", patient_initials: "V.D.",
    treatment: "enzalutamide", j_code: "J9180", payer_id: "uhc",
    verdict: "APPROVE", confidence: 0.97,
    submitted_at: iso(4 * day), ago: ago(4 * day),
    diagnosis: "Prostate cancer (C61)", stage: "IV",
    is_synthetic: true,
  },
  {
    case_id: "case_2c4d68fb", status: "approved", patient_initials: "Q.L.",
    treatment: "lorlatinib", j_code: "J9999", payer_id: "uhc",
    verdict: "APPROVE", confidence: 0.91,
    submitted_at: iso(6 * day), ago: ago(6 * day),
    diagnosis: "NSCLC (C34.91)", stage: "IIIB",
    is_synthetic: true,
  },
  {
    case_id: "case_8e5f1c43", status: "approved", patient_initials: "Y.J.",
    treatment: "brentuximab vedotin", j_code: "J9042", payer_id: "bcbs",
    verdict: "APPROVE", confidence: 0.94,
    submitted_at: iso(8 * day), ago: ago(8 * day),
    diagnosis: "Hodgkin lymphoma (C81.91)", stage: "II",
    is_synthetic: true,
  },
  {
    case_id: "case_3a9d24ce", status: "referred", patient_initials: "N.G.",
    treatment: "nivolumab", j_code: "J9299", payer_id: "bcbs",
    verdict: "REFER", confidence: 0.68,
    submitted_at: iso(11 * day), ago: ago(11 * day),
    diagnosis: "Renal cell carcinoma (C64.9)", stage: "IV",
    is_synthetic: true,
  },
  {
    case_id: "case_5b8e7fda", status: "approved", patient_initials: "Z.O.",
    treatment: "bevacizumab", j_code: "J9035", payer_id: "anthem",
    verdict: "APPROVE", confidence: 0.88,
    submitted_at: iso(15 * day), ago: ago(15 * day),
    diagnosis: "Glioblastoma (C71.9)", stage: "IV",
    is_synthetic: true,
  },
];

export const PAYERS: { id: SyntheticCase["payer_id"]; label: string }[] = [
  { id: "aetna",  label: "Aetna" },
  { id: "uhc",    label: "UnitedHealthcare" },
  { id: "bcbs",   label: "BlueCross BlueShield" },
  { id: "anthem", label: "Anthem" },
];

export const STATUSES: CaseStatus[] = [
  "pending", "running", "approved", "denied", "referred", "appealed", "overturned",
];
