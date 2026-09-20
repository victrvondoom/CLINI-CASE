/**
 * Pre-flight Documentation-Gap analyzer.
 *
 * Per requested treatment, defines the structured criteria a payer typically
 * requires for prior-auth approval. Each criterion is matched against the
 * physician_note text using simple keyword + regex heuristics. This is the
 * cheap pre-flight pass — the full Necessity Reasoner agent does the rigorous
 * analysis after Run.
 *
 * Status meanings:
 *   met     — evidence is plainly documented in the physician_note
 *   missing — required evidence is absent (action required)
 *   unknown — heuristic can't tell; defer to Necessity Reasoner after Run
 */
export type DocGapStatus = "met" | "missing" | "unknown";

export interface DocGapCriterion {
  id: string;
  label: string;
  rationale: string;     // why the payer requires this
  /** Pure-function predicate. Receives the lowercased physician note. */
  evaluate: (note: string) => DocGapStatus;
  /** If MISSING, suggested fix actions */
  suggestions?: string[];
}

interface TreatmentRules {
  matchKeywords: string[];   // matches against treatment.name (lowercased)
  criteria: DocGapCriterion[];
}

// =============================================================================
// Helpers
// =============================================================================

const re = (pattern: RegExp): ((note: string) => DocGapStatus) => (note) =>
  pattern.test(note) ? "met" : "missing";

const positiveOrNegativeMatch = (
  presentRegex: RegExp,
  negativeRegex?: RegExp,
): ((note: string) => DocGapStatus) =>
  (note) => {
    if (negativeRegex && negativeRegex.test(note)) return "missing";
    if (presentRegex.test(note)) return "met";
    return "unknown";
  };

// =============================================================================
// Per-treatment rule sets
// =============================================================================

const TRASTUZUMAB_RULES: TreatmentRules = {
  matchKeywords: ["trastuzumab", "herceptin", "t-dxd", "trastuzumab deruxtecan", "enhertu"],
  criteria: [
    {
      id: "her2-positive",
      label: "HER2 overexpression confirmed (IHC 3+ or ISH amplified)",
      rationale: "HER2-targeted therapy requires confirmed HER2 overexpression.",
      evaluate: positiveOrNegativeMatch(
        /her2[-\s]positive|her2\+|ihc\s*3\+|ish\s*amplified/i,
        /her2[-\s]negative|her2\s*-|ihc\s*0|ihc\s*1\+|ish\s*non-amplified/i,
      ),
      suggestions: ["Order HER2 IHC", "Order HER2 ISH (if IHC 2+)"],
    },
    {
      id: "lvef-baseline",
      label: "Baseline LVEF ≥ 50% by echocardiogram or MUGA within 90 days",
      rationale: "Trastuzumab is cardiotoxic; baseline cardiac function must be documented.",
      evaluate: re(/lvef\s*(\d{2})|ejection fraction|echocardiogram|muga/i),
      suggestions: ["Order ECHO", "Use prior LVEF (within 90d)"],
    },
    {
      id: "ecog-status",
      label: "ECOG performance status 0, 1, or 2",
      rationale: "Patients with ECOG 3-4 are excluded.",
      evaluate: re(/ecog\s*(0|1|2)|performance status (0|1|2)/i),
      suggestions: ["Document ECOG"],
    },
    {
      id: "no-active-ild",
      label: "No active interstitial lung disease",
      rationale: "ILD is an exclusion for HER2-targeted therapies.",
      evaluate: positiveOrNegativeMatch(
        /no.{0,30}interstitial|no.{0,30}ild|no history of.{0,30}lung disease/i,
        /active interstitial|active ild|symptomatic.{0,30}ild/i,
      ),
    },
    {
      id: "treatment-plan",
      label: "Treatment plan documented (combo regimen for early-stage)",
      rationale: "For Stage I-III, trastuzumab must be in adjuvant/neoadjuvant combination chemo.",
      evaluate: re(/tchp|adjuvant|neoadjuvant|combination chemotherapy|combo|pertuzumab/i),
      suggestions: ["Add chemotherapy regimen plan (e.g. TCHP)"],
    },
  ],
};

const OSIMERTINIB_RULES: TreatmentRules = {
  matchKeywords: ["osimertinib", "tagrisso"],
  criteria: [
    {
      id: "egfr-mutation",
      label: "Sensitizing EGFR mutation confirmed (exon 19 del / L858R / T790M)",
      rationale: "Osimertinib is an EGFR-TKI; targeted to EGFR-mutated NSCLC.",
      evaluate: re(/egfr|exon 19|l858r|t790m/i),
      suggestions: ["Order EGFR companion diagnostic"],
    },
    {
      id: "nsclc-diagnosis",
      label: "NSCLC pathologic diagnosis",
      rationale: "Osimertinib indication is non-small cell lung cancer.",
      evaluate: re(/nsclc|non-small cell|adenocarcinoma of lung/i),
      suggestions: ["Document NSCLC pathology"],
    },
    {
      id: "ecog-status",
      label: "ECOG performance status 0, 1, or 2",
      rationale: "Performance status assessed at baseline.",
      evaluate: re(/ecog\s*(0|1|2)|performance status (0|1|2)/i),
    },
    {
      id: "no-ild",
      label: "No active interstitial lung disease",
      rationale: "ILD is a known osimertinib AE; exclusion at baseline.",
      evaluate: positiveOrNegativeMatch(
        /no.{0,30}interstitial|no.{0,30}ild/i,
        /active.{0,30}ild|symptomatic.{0,30}ild/i,
      ),
    },
  ],
};

const PEMBROLIZUMAB_RULES: TreatmentRules = {
  matchKeywords: ["pembrolizumab", "keytruda"],
  criteria: [
    {
      id: "biomarker",
      label: "Biomarker documented (PD-L1 TPS, MSI-H, or TMB-H per indication)",
      rationale: "Pembrolizumab indication-specific biomarker required.",
      evaluate: re(/pd-l1|msi-h|dmmr|tmb|tumor mutational burden/i),
      suggestions: ["Order PD-L1 IHC", "Order MSI testing"],
    },
    {
      id: "no-autoimmune",
      label: "No active autoimmune disease requiring systemic immunosuppression",
      rationale: "Active autoimmune disease is an exclusion.",
      evaluate: positiveOrNegativeMatch(
        /no.{0,30}autoimmune|no history of.{0,30}autoimmune/i,
        /active autoimmune|on.{0,30}immunosuppress/i,
      ),
    },
    {
      id: "ecog-status",
      label: "ECOG performance status 0, 1, or 2",
      rationale: "Performance status assessed at baseline.",
      evaluate: re(/ecog\s*(0|1|2)|performance status (0|1|2)/i),
    },
  ],
};

const OLAPARIB_RULES: TreatmentRules = {
  matchKeywords: ["olaparib", "lynparza"],
  criteria: [
    {
      id: "brca-mutation",
      label: "BRCA1 or BRCA2 deleterious mutation (germline or somatic)",
      rationale: "PARP inhibitor; requires homologous-recombination deficiency.",
      evaluate: re(/brca[12]?|brca-mutated|hrd/i),
      suggestions: ["Order BRCA companion diagnostic"],
    },
    {
      id: "platinum-response",
      label: "Complete or partial response to first-line platinum chemo (ovarian)",
      rationale: "Maintenance therapy criterion; must follow platinum-based regimen.",
      evaluate: re(/platinum|carboplatin|cisplatin/i),
    },
    {
      id: "ecog-status",
      label: "ECOG performance status 0, 1, or 2",
      rationale: "Performance status assessed at baseline.",
      evaluate: re(/ecog\s*(0|1|2)|performance status (0|1|2)/i),
    },
  ],
};

const FALLBACK_RULES: TreatmentRules = {
  matchKeywords: [],
  criteria: [
    {
      id: "ecog-status",
      label: "ECOG performance status 0, 1, or 2",
      rationale: "Standard performance-status threshold for most oncology PA.",
      evaluate: re(/ecog\s*(0|1|2)|performance status (0|1|2)/i),
    },
    {
      id: "diagnosis-confirmed",
      label: "Pathologic diagnosis confirmed",
      rationale: "PA decisions require confirmed pathology.",
      evaluate: re(/diagnosis|pathology|biopsy/i),
    },
  ],
};

const ALL_RULES: TreatmentRules[] = [
  TRASTUZUMAB_RULES,
  OSIMERTINIB_RULES,
  PEMBROLIZUMAB_RULES,
  OLAPARIB_RULES,
];

// =============================================================================
// Public API
// =============================================================================

export interface DocGapAnalysis {
  treatment: string;
  total: number;
  metCount: number;
  missingCount: number;
  unknownCount: number;
  results: { criterion: DocGapCriterion; status: DocGapStatus }[];
  /** Boolean: ready to submit (no missing, may have unknowns). */
  readyToSubmit: boolean;
}

export function analyzeDocGap(
  treatmentName: string,
  physicianNote: string | null,
): DocGapAnalysis {
  const note = (physicianNote ?? "").toLowerCase();
  const lcTreatment = treatmentName.toLowerCase();

  const ruleSet =
    ALL_RULES.find((r) =>
      r.matchKeywords.some((kw) => lcTreatment.includes(kw)),
    ) ?? FALLBACK_RULES;

  const results = ruleSet.criteria.map((c) => ({
    criterion: c,
    status: c.evaluate(note),
  }));

  const metCount = results.filter((r) => r.status === "met").length;
  const missingCount = results.filter((r) => r.status === "missing").length;
  const unknownCount = results.filter((r) => r.status === "unknown").length;

  return {
    treatment: treatmentName,
    total: results.length,
    metCount,
    missingCount,
    unknownCount,
    results,
    readyToSubmit: missingCount === 0,
  };
}
