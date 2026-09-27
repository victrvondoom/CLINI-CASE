/**
 * PA Decision Sandbox — simulation engine.
 *
 * Purely additive: builds a synthetic clinical scenario from structured form
 * inputs, then reuses the existing Multi-payer Arbitration engine
 * (simulateCompare, in ./compareSimulation) exactly as Compare.tsx does for
 * real cases — no fork of that decision logic, no new payer/policy rules.
 *
 * Unlike Compare.tsx, the Sandbox needs no real case: it synthesizes a
 * physician-note string from the scenario's structured fields (the same
 * fields Compare's detectShape() regex-parses from real notes), so the
 * existing payer-simulation logic runs unmodified from a hypothetical input.
 *
 * 100% client-side. No backend calls, no persistence beyond localStorage —
 * running a sandbox scenario can never create, modify, or appear in real
 * case data, counts, or audit trails.
 */
import { simulateCompare, type CompareResult, type PayerId } from "./compareSimulation";

// =============================================================================
// Scenario input — the "what can the user configure" surface.
// Every field maps to a real clinical/documentation concept the production
// ClinCase pipeline actually evaluates (see backend/app/agents/necessity_reasoner
// and lib/compareSimulation.ts's detectShape()) — nothing invented for size.
// =============================================================================

export type Her2Status = "positive" | "negative" | "equivocal" | "unknown";

export interface ScenarioParams {
  /** Display name for this scenario, shown in history / comparison. */
  label: string;
  treatment: string;
  j_code: string;
  /** The payer the case would actually be submitted to (drives the "LIVE" column). */
  livePayer: PayerId;
  diagnosis: string;
  stage: string;
  her2Status: Her2Status;
  /** Baseline LVEF documented within the payer's cardiac-function window? */
  lvefDocumented: boolean;
  /** Combination regimen (e.g. TCHP, adjuvant/neoadjuvant plan) documented? */
  comboRegimenDocumented: boolean;
  /** ECOG performance status documented? */
  ecogDocumented: boolean;
}

export const HER2_STATUS_LABELS: Record<Her2Status, string> = {
  positive: "IHC 3+ / FISH-amplified (positive)",
  negative: "IHC 0 / IHC 1+ / FISH non-amplified (negative)",
  equivocal: "IHC 2+ (equivocal)",
  unknown: "Not yet tested",
};

export function defaultScenarioParams(): ScenarioParams {
  return {
    label: "Untitled scenario",
    treatment: "trastuzumab",
    j_code: "J9355",
    livePayer: "aetna",
    diagnosis: "Breast cancer",
    stage: "IIIA",
    her2Status: "positive",
    lvefDocumented: true,
    comboRegimenDocumented: true,
    ecogDocumented: true,
  };
}

// =============================================================================
// Scenario → synthetic physician note
//
// simulateCompare()'s detectShape() regex-parses a free-text note for these
// exact phrase patterns. Building the note this way means the sandbox drives
// the *same* detection + decision code Compare.tsx uses for real cases —
// zero duplicated payer/policy logic, so sandbox and production can never
// silently drift apart.
// =============================================================================

function buildSyntheticNote(p: ScenarioParams): string {
  const lines: string[] = [
    `${p.diagnosis}, Stage ${p.stage}.`,
    `Requested treatment: ${p.treatment} (${p.j_code}).`,
  ];

  if (p.her2Status === "positive") lines.push("HER2 IHC 3+ (HER2-positive), FISH amplified.");
  else if (p.her2Status === "negative") lines.push("HER2 IHC 0, HER2-negative.");
  else if (p.her2Status === "equivocal") lines.push("HER2 IHC 2+, equivocal; confirmatory FISH pending.");
  else lines.push("HER2 status not yet tested.");

  lines.push(
    p.lvefDocumented
      ? "Baseline LVEF 58% (echocardiogram within 60 days)."
      : "LVEF assessment not yet documented.",
  );
  lines.push(
    p.comboRegimenDocumented
      ? "Adjuvant combination chemotherapy regimen (TCHP) documented."
      : "Combination regimen plan not yet specified.",
  );
  if (p.ecogDocumented) lines.push("ECOG performance status 1.");

  return lines.join(" ");
}

// =============================================================================
// Public API
// =============================================================================

export interface ScenarioRunResult {
  params: ScenarioParams;
  synthetic_note: string;
  result: CompareResult;
  ranAt: string; // ISO
}

/** Run one scenario through the existing multi-payer arbitration engine. */
export function runScenario(params: ScenarioParams): ScenarioRunResult {
  const note = buildSyntheticNote(params);
  const result = simulateCompare(
    `sandbox_${Math.random().toString(36).slice(2, 10)}`,
    params.treatment,
    note,
    params.livePayer,
  );
  return { params, synthetic_note: note, result, ranAt: new Date().toISOString() };
}

/** Outcome counts across the 4 payers, for at-a-glance comparison badges. */
export function tallyVerdicts(r: CompareResult): { approve: number; refer: number; deny: number } {
  return {
    approve: r.payers.filter((p) => p.verdict === "APPROVE").length,
    refer: r.payers.filter((p) => p.verdict === "REFER").length,
    deny: r.payers.filter((p) => p.verdict === "DENY").length,
  };
}

/** Mean confidence across the 4 payers — a single comparable "scenario strength" number. */
export function meanConfidence(r: CompareResult): number {
  return r.payers.reduce((s, p) => s + p.confidence, 0) / r.payers.length;
}
