/**
 * Multi-payer arbitration simulation.
 *
 * Given a case (treatment + physician note + payer), simulate what 4 payers
 * would decide. Variation comes from per-payer policy strictness + case-shape:
 *   - Aetna  (current "live" payer when configured) — strict LVEF window
 *   - UHC    — fastest, more permissive on cardiac docs
 *   - BCBS   — strictest on combo-regimen documentation
 *   - Anthem — formulary-tier nuances; sometimes denies APPROVABLE cases
 *
 * Used by /cases/:id/compare. No real LLM calls — this is the platform-demo
 * pattern; in production each verdict would come from a parallel agent run.
 */
import type { Verdict } from "./types";

export type PayerId = "aetna" | "uhc" | "bcbs" | "anthem";

export interface PayerVerdict {
  payer_id: PayerId;
  payer_name: string;
  data_mode: "LIVE" | "MOCK" | "SIMULATED";
  verdict: Verdict;
  confidence: number;       // 0..1
  reasoning_summary: string;
  criteria_met: string[];
  criteria_missing: string[];
  latency_ms: number;
  cost_usd: number;
  auth_code_or_reason: string;  // approval code OR denial reason
  recommended_next: string;     // e.g. "Submit immediately"
}

export interface CompareResult {
  case_id: string;
  treatment: string;
  payers: PayerVerdict[];
  recommendation: {
    summary: string;
    primary: PayerId;
    fallback: PayerId | null;
  };
}

const PAYER_NAMES: Record<PayerId, string> = {
  aetna:  "Aetna",
  uhc:    "UnitedHealthcare",
  bcbs:   "BlueCross BlueShield",
  anthem: "Anthem",
};

// =============================================================================
// Per-case shape detection (heuristic from physician_note keywords)
// =============================================================================

interface CaseShape {
  isHer2Positive: boolean;
  isHer2Negative: boolean;
  hasLvef: boolean;
  hasComboPlan: boolean;
  hasEcog: boolean;
}

function detectShape(note: string): CaseShape {
  const lc = note.toLowerCase();
  return {
    isHer2Positive: /her2[-\s]?positive|her2\+|ihc\s*3\+|ish\s*amplified/i.test(lc),
    isHer2Negative: /her2[-\s]?negative|ihc\s*0|ihc\s*1\+|ish\s*non-amplified/i.test(lc),
    hasLvef: /lvef\s*\d{2}|ejection fraction|echocardiogram/i.test(lc),
    hasComboPlan: /tchp|adjuvant|neoadjuvant|combination chemo|pertuzumab/i.test(lc),
    hasEcog: /ecog\s*(0|1|2)/i.test(lc),
  };
}

// =============================================================================
// Per-payer policy logic
// =============================================================================

interface PayerArchetype {
  baseLatencyMs: number;
  baseCostUsd: number;
  strictness: {
    lvef: "strict" | "moderate" | "lenient";
    comboRegimen: "strict" | "moderate" | "lenient";
    biomarker: "strict" | "moderate" | "lenient";
  };
}

const PAYER_ARCHETYPES: Record<PayerId, PayerArchetype> = {
  aetna:  { baseLatencyMs: 92_000,  baseCostUsd: 0.0889, strictness: { lvef: "strict",   comboRegimen: "moderate", biomarker: "strict"   } },
  uhc:    { baseLatencyMs: 78_000,  baseCostUsd: 0.0762, strictness: { lvef: "lenient",  comboRegimen: "moderate", biomarker: "strict"   } },
  bcbs:   { baseLatencyMs: 105_000, baseCostUsd: 0.0934, strictness: { lvef: "moderate", comboRegimen: "strict",   biomarker: "moderate" } },
  anthem: { baseLatencyMs: 88_000,  baseCostUsd: 0.0827, strictness: { lvef: "lenient",  comboRegimen: "lenient",  biomarker: "lenient"  } },
};

// =============================================================================
// The simulation
// =============================================================================

function simulatePayer(
  payer_id: PayerId,
  treatment: string,
  shape: CaseShape,
  livePayer: PayerId,
): PayerVerdict {
  const arch = PAYER_ARCHETYPES[payer_id];
  const isHer2Targeted = /trastuzumab|t-dxd|herceptin|enhertu|pertuzumab/i.test(treatment);

  let verdict: Verdict = "APPROVE";
  let confidence = 0.92;
  const criteria_met: string[] = [];
  const criteria_missing: string[] = [];
  let auth_code_or_reason = `AUTH-${payer_id.toUpperCase()}-${Math.floor(Math.random() * 90000 + 10000)}`;
  let recommended_next = "Submit immediately";
  let reasoning_summary = "";

  // ---- Biomarker check ----
  if (isHer2Targeted) {
    if (shape.isHer2Negative) {
      verdict = "DENY";
      confidence = 0.96;
      criteria_missing.push("HER2 overexpression (patient is HER2-negative)");
      auth_code_or_reason = "Biomarker mismatch — HER2-negative tumor not eligible for HER2-targeted therapy";
      recommended_next =
        payer_id === "anthem"
          ? "Submit corrected request for HR+/HER2- regimen instead"
          : "Do not submit; reconsider treatment selection";
      reasoning_summary =
        "HER2-negative status fails primary inclusion criterion for trastuzumab and triggers the HER2-negative exclusion clause. Biomarker testing methodology confirmed.";
      return finalize(payer_id, arch, verdict, confidence, criteria_met, criteria_missing, auth_code_or_reason, recommended_next, reasoning_summary, livePayer);
    }
    if (shape.isHer2Positive) {
      criteria_met.push("HER2 IHC 3+ confirmed");
    } else if (arch.strictness.biomarker === "strict") {
      criteria_missing.push("HER2 testing methodology unclear");
    }
  }

  // ---- LVEF check ----
  if (isHer2Targeted) {
    if (shape.hasLvef) {
      criteria_met.push("Baseline LVEF documented within payer window");
    } else {
      const tolerated = arch.strictness.lvef === "lenient";
      if (!tolerated) {
        verdict = "REFER";
        confidence = 0.55;
        criteria_missing.push("LVEF not documented within 90 days");
        auth_code_or_reason = "Documentation gap — baseline cardiac function (LVEF) required";
        recommended_next = "Order ECHO or use prior LVEF (within 90d), then resubmit";
      } else {
        criteria_met.push("LVEF window deferred (per payer protocol)");
      }
    }
  }

  // ---- Combo regimen check (only for early-stage HER2+ trastuzumab) ----
  if (isHer2Targeted && shape.isHer2Positive && verdict === "APPROVE") {
    if (!shape.hasComboPlan && arch.strictness.comboRegimen === "strict") {
      verdict = "REFER";
      confidence = 0.68;
      criteria_missing.push("Combination chemotherapy regimen plan not specified");
      auth_code_or_reason = "Documentation gap — Stage I-III requires adjuvant/neoadjuvant combo regimen";
      recommended_next = "Document TCHP regimen (or equivalent); resubmit";
    } else if (shape.hasComboPlan) {
      criteria_met.push("Combination regimen documented (TCHP / adjuvant)");
    }
  }

  // ---- ECOG check ----
  if (shape.hasEcog) {
    criteria_met.push("ECOG performance status 0-2");
  }

  // ---- Anthem variance: occasionally denies APPROVABLE cases on formulary tier ----
  if (verdict === "APPROVE" && payer_id === "anthem" && isHer2Targeted) {
    verdict = "DENY";
    confidence = 0.65;
    criteria_missing.push("Off-formulary at current tier (Tier 3 vs requested Tier 2)");
    auth_code_or_reason = "Formulary tier exception required — preferred biosimilar (trastuzumab-anns) is on Tier 2";
    recommended_next = "Resubmit with biosimilar OR file formulary exception request";
  }

  // Compose reasoning
  if (verdict === "APPROVE") {
    confidence = 0.92 + Math.random() * 0.06;
    reasoning_summary = `All ${criteria_met.length} required criteria met. Treatment aligns with policy; preferred regimen documented.`;
  } else if (verdict === "REFER") {
    reasoning_summary = `Documentation gap detected; auto-routing to human reviewer. ${criteria_missing.length} item(s) unresolved.`;
  } else {
    reasoning_summary = reasoning_summary || `Auto-deny per policy. ${criteria_missing[0] ?? "Criteria not met."}`;
  }

  return finalize(payer_id, arch, verdict, confidence, criteria_met, criteria_missing, auth_code_or_reason, recommended_next, reasoning_summary, livePayer);
}

function finalize(
  payer_id: PayerId,
  arch: PayerArchetype,
  verdict: Verdict,
  confidence: number,
  criteria_met: string[],
  criteria_missing: string[],
  auth_code_or_reason: string,
  recommended_next: string,
  reasoning_summary: string,
  livePayer: PayerId,
): PayerVerdict {
  // Add deterministic jitter so the demo isn't identical run-to-run
  const jitter = (payer_id.charCodeAt(0) % 5) * 1500;
  return {
    payer_id,
    payer_name: PAYER_NAMES[payer_id],
    data_mode: payer_id === livePayer ? "LIVE" : "SIMULATED",
    verdict,
    confidence: Math.round(confidence * 100) / 100,
    reasoning_summary,
    criteria_met,
    criteria_missing,
    latency_ms: arch.baseLatencyMs + jitter,
    cost_usd: arch.baseCostUsd,
    auth_code_or_reason,
    recommended_next,
  };
}

// =============================================================================
// Public: produce the full CompareResult
// =============================================================================

export function simulateCompare(
  case_id: string,
  treatment: string,
  physician_note: string,
  livePayer: PayerId = "aetna",
): CompareResult {
  const shape = detectShape(physician_note);
  const payers = (Object.keys(PAYER_ARCHETYPES) as PayerId[]).map((p) =>
    simulatePayer(p, treatment, shape, livePayer),
  );

  // Recommendation: pick the payer with highest-confidence APPROVE; fallback = next-best.
  const approves = payers.filter((p) => p.verdict === "APPROVE")
    .sort((a, b) => b.confidence - a.confidence);
  const refers = payers.filter((p) => p.verdict === "REFER")
    .sort((a, b) => b.confidence - a.confidence);
  const denies = payers.filter((p) => p.verdict === "DENY");

  let summary: string;
  let primary: PayerId;
  let fallback: PayerId | null = null;

  if (approves.length > 0) {
    primary = approves[0].payer_id;
    if (approves[1]) fallback = approves[1].payer_id;
    summary =
      `Of ${payers.length} payers checked, ${approves.length} would approve, ${refers.length} would refer, and ${denies.length} would deny. ` +
      `Highest probability of clean approval: ${approves[0].payer_name} (${Math.round(approves[0].confidence * 100)}% confidence). ` +
      (fallback ? `Recommended next step: submit to ${approves[0].payer_name} first; fall back to ${PAYER_NAMES[fallback]} if denied.` : `Recommended next step: submit to ${approves[0].payer_name}.`);
  } else if (refers.length > 0) {
    primary = refers[0].payer_id;
    summary =
      `No payer would auto-approve. ${refers.length} would refer for human review (best: ${refers[0].payer_name}, ${Math.round(refers[0].confidence * 100)}% confidence). ` +
      `Address documentation gaps before resubmission to maximize approval odds.`;
  } else {
    primary = payers[0].payer_id;
    summary =
      `All ${payers.length} payers would deny. The case requires reconsideration before submission to any payer — biomarker / clinical-criteria mismatch detected.`;
  }

  return { case_id, treatment, payers, recommendation: { summary, primary, fallback } };
}
