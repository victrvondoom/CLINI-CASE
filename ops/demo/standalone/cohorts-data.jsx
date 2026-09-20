/* global window */
(function () {
  // Approval rate by payer × drug (12 combos).
  // Counts: { approve, deny, refer }
  const PAYERS = ["aetna", "uhc", "cigna", "humana"];
  const DRUGS  = ["Trastuzumab", "Pembrolizumab", "Osimertinib"];

  const MATRIX = {
    aetna: {
      Trastuzumab:   { approve: 84, deny:  6, refer: 12 },
      Pembrolizumab: { approve: 71, deny: 11, refer:  9 },
      Osimertinib:   { approve: 52, deny:  4, refer:  8 },
    },
    uhc: {
      Trastuzumab:   { approve: 78, deny:  9, refer: 14 },
      Pembrolizumab: { approve: 64, deny: 14, refer: 11 },
      Osimertinib:   { approve: 48, deny:  6, refer:  7 },
    },
    cigna: {
      Trastuzumab:   { approve: 69, deny:  8, refer: 10 },
      Pembrolizumab: { approve: 59, deny:  9, refer: 13 },
      Osimertinib:   { approve: 41, deny:  5, refer:  6 },
    },
    humana: {
      Trastuzumab:   { approve: 62, deny:  7, refer:  9 },
      Pembrolizumab: { approve: 51, deny: 10, refer: 10 },
      Osimertinib:   { approve: 38, deny:  6, refer:  8 },
    },
  };

  const KPIS = {
    total_cases: Object.values(MATRIX).reduce(
      (a, byDrug) => a + Object.values(byDrug).reduce((b, c) => b + c.approve + c.deny + c.refer, 0),
      0
    ),
    overall_approval: 0, // computed below
    median_decision_seconds: 264,
    appeals_overturned: 0.78,
  };
  let totA = 0, totT = 0;
  Object.values(MATRIX).forEach((byDrug) =>
    Object.values(byDrug).forEach((c) => { totA += c.approve; totT += c.approve + c.deny + c.refer; })
  );
  KPIS.overall_approval = totA / totT;

  window.CLINCASE_COHORTS = { PAYERS, DRUGS, MATRIX, KPIS };
})();
