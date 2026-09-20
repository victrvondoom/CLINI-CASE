/* global window */
// Synthetic 24h runtime stats for the 5-agent DAG.
// Indexed by AGENT_SPECS[i].key.

(function () {
  const SYSTEM_PROMPTS = {
    clinical_extractor: [
      "You are the Clinical Extractor agent in the ClinCase DAG.",
      "INPUT  : a FHIR R4 Bundle (Patient, Conditions, Observations,",
      "         MedicationRequests, DiagnosticReports) plus the unstructured",
      "         physician note. PHI is pre-redacted by the gateway.",
      "OUTPUT : a strict ClinicalSnapshot JSON conforming to schema v2.4 —",
      "         demographics, dx, biomarkers, prior_therapies, labs, ECOG.",
      "RULES  : never fabricate values. If a field is not present in the",
      "         bundle, emit null. Echo the source pointer (Resource.id)",
      "         for every extracted field.  Refuse free-text reasoning.",
    ].join("\n"),
    policy_retriever: [
      "You are the Policy Retriever agent.",
      "INPUT  : ClinicalSnapshot + payer_id + drug_rxnorm.",
      "OUTPUT : top-K (K=5) PolicyExcerpt[], each with policy_id, version,",
      "         section pointer, verbatim text, and a relevance_score.",
      "RULES  : keyword filter against the indexed payer corpus first,",
      "         then LLM rerank. Always include the most recent policy",
      "         version. Return PolicyExcerpts only — no commentary.",
    ].join("\n"),
    necessity_reasoner: [
      "You are the Necessity Reasoner agent.",
      "INPUT  : ClinicalSnapshot + PolicyExcerpt[].",
      "OUTPUT : CriterionMatch[] — one row per policy bullet, with",
      "         status ∈ {MET, NOT_MET, AMBIGUOUS}, evidence_pointer,",
      "         and a one-sentence rationale.",
      "RULES  : evaluate criteria independently. Do not synthesize a",
      "         verdict — that is the Decision Composer's job. Cite the",
      "         specific snapshot field for every MET/NOT_MET claim.",
    ].join("\n"),
    decision_composer: [
      "You are the Decision Composer agent.",
      "INPUT  : ClinicalSnapshot + PolicyExcerpt[] + CriterionMatch[].",
      "OUTPUT : Decision {verdict ∈ {APPROVE, DENY, REFER}, confidence,",
      "         primary_reason, citation_chain, missing_evidence?}.",
      "RULES  : APPROVE only when every required criterion is MET.",
      "         REFER on AMBIGUOUS or missing evidence. DENY when a",
      "         hard exclusion is hit. Confidence is calibrated against",
      "         the agent's last 1000 decisions on this policy version.",
    ].join("\n"),
    appeals_drafter: [
      "You are the Appeals Drafter agent. You run only on DENY.",
      "INPUT  : ClinicalSnapshot + Decision + denial citation_chain.",
      "OUTPUT : an appeal letter (markdown) + structured arguments[]",
      "         each tagged to an NCCN guideline section or peer-",
      "         reviewed citation rebutting the denial reason.",
      "RULES  : never invent citations. NCCN Compendium and FDA label",
      "         only. Tone: professional, factual, plaintiff-friendly.",
    ].join("\n"),
  };

  // 24-hour rolling stats (synthesized but plausible for a 412-case/day system).
  const STATS = {
    clinical_extractor: {
      calls_24h: 412,
      median_ms: 2140,
      p95_ms: 3210,
      error_rate: 0.0024,
      cost_24h: 9.87,
      tokens_in: 1_984_240,
      tokens_out: 252_104,
    },
    policy_retriever: {
      calls_24h: 412,
      median_ms: 2680,
      p95_ms: 4180,
      error_rate: 0.0048,
      cost_24h: 12.41,
      tokens_in: 2_600_932,
      tokens_out: 201_068,
    },
    necessity_reasoner: {
      calls_24h: 412,
      median_ms: 3120,
      p95_ms: 5240,
      error_rate: 0.0073,
      cost_24h: 15.62,
      tokens_in: 3_049_624,
      tokens_out: 379_452,
    },
    decision_composer: {
      calls_24h: 412,
      median_ms: 1980,
      p95_ms: 2840,
      error_rate: 0.0012,
      cost_24h: 7.21,
      tokens_in: 2_102_848,
      tokens_out: 222_480,
    },
    appeals_drafter: {
      calls_24h: 38, // only runs on DENY
      median_ms: 4520,
      p95_ms: 7110,
      error_rate: 0.0,
      cost_24h: 4.84,
      tokens_in: 259_160,
      tokens_out: 68_856,
    },
  };

  // Latest 3 invocations per agent — timestamps relative to now.
  const now = Date.now();
  const minutes = (m) => new Date(now - m * 60_000).toISOString();

  const RECENT = {
    clinical_extractor: [
      { case_id: "AUTH-2026-1842", ts: minutes(1),  ms: 2104, verdict: "ok", note: "snapshot v2.4 emitted, 17 fields" },
      { case_id: "AUTH-2026-1841", ts: minutes(3),  ms: 2680, verdict: "ok", note: "ECOG inferred from note" },
      { case_id: "AUTH-2026-1840", ts: minutes(7),  ms: 1942, verdict: "ok", note: "snapshot v2.4 emitted, 14 fields" },
    ],
    policy_retriever: [
      { case_id: "AUTH-2026-1842", ts: minutes(1),  ms: 2480, verdict: "ok", note: "Aetna 0123 v2026.1, UHC ONC.00043" },
      { case_id: "AUTH-2026-1841", ts: minutes(3),  ms: 3120, verdict: "ok", note: "5 excerpts reranked" },
      { case_id: "AUTH-2026-1840", ts: minutes(7),  ms: 2510, verdict: "ok", note: "NCCN BINV-N v3.2026 cited" },
    ],
    necessity_reasoner: [
      { case_id: "AUTH-2026-1842", ts: minutes(1),  ms: 3040, verdict: "ok",        note: "8 of 8 criteria MET" },
      { case_id: "AUTH-2026-1841", ts: minutes(3),  ms: 3340, verdict: "ambiguous", note: "LVEF window edge case" },
      { case_id: "AUTH-2026-1840", ts: minutes(7),  ms: 2890, verdict: "ok",        note: "all criteria MET" },
    ],
    decision_composer: [
      { case_id: "AUTH-2026-1842", ts: minutes(1),  ms: 1880, verdict: "APPROVE", note: "confidence 0.94" },
      { case_id: "AUTH-2026-1841", ts: minutes(3),  ms: 2110, verdict: "REFER",   note: "missing baseline LVEF" },
      { case_id: "AUTH-2026-1840", ts: minutes(7),  ms: 1730, verdict: "APPROVE", note: "confidence 0.91" },
    ],
    appeals_drafter: [
      { case_id: "AUTH-2026-1837", ts: minutes(14), ms: 4520, verdict: "drafted", note: "NCCN BINV-N §4 rebuttal" },
      { case_id: "AUTH-2026-1829", ts: minutes(42), ms: 4180, verdict: "drafted", note: "FDA label cite, 3 args" },
      { case_id: "AUTH-2026-1812", ts: minutes(91), ms: 5210, verdict: "drafted", note: "MD anderson trial cite" },
    ],
  };

  // 12-step sparklines (calls per 2-hr bucket over last 24h)
  const SPARKS = {
    clinical_extractor: [22, 28, 31, 34, 38, 41, 44, 42, 38, 35, 31, 28],
    policy_retriever:   [22, 28, 31, 34, 38, 41, 44, 42, 38, 35, 31, 28],
    necessity_reasoner: [22, 28, 31, 34, 38, 41, 44, 42, 38, 35, 31, 28],
    decision_composer:  [22, 28, 31, 34, 38, 41, 44, 42, 38, 35, 31, 28],
    appeals_drafter:    [ 2,  3,  4,  3,  4,  5,  4,  3,  3,  4,  2,  1],
  };

  window.CLINCASE_AGENTS = {
    SYSTEM_PROMPTS,
    STATS,
    RECENT,
    SPARKS,
  };
})();
