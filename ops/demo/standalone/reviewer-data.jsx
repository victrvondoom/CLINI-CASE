/* global window */
(function () {
  const REFERS = [
    {
      id: "AUTH-2026-1841",
      initials: "A.K.",
      drug: "Trastuzumab + Pertuzumab",
      payer: "aetna",
      received: "27 min ago",
      reason: "LVEF baseline outside 60-day window (current policy v2025.4)",
      summary: "67F, HER2+ metastatic breast cancer, ECOG 1, no anthracycline history. LVEF 56% recorded 71 days prior. Concurrent docetaxel proposed.",
      missing: [
        { ok: false, label: "LVEF echo within 60 days" },
        { ok: true,  label: "HER2 IHC 3+ confirmation" },
        { ok: true,  label: "ECOG ≤ 2" },
        { ok: true,  label: "No NYHA III–IV heart failure" },
      ],
      hint: "Aetna 0123 §4.2 was just updated to a 90-day window — auto-rerun would APPROVE.",
    },
    {
      id: "AUTH-2026-1839",
      initials: "D.R.",
      drug: "Pembrolizumab",
      payer: "uhc",
      received: "1h 12m ago",
      reason: "PD-L1 result reported as TPS but no CPS supplied; UHC requires both for combination regimen.",
      summary: "58M, NSCLC adenocarcinoma stage IIIB, PD-L1 TPS 45%, no driver mutation. Carboplatin + pemetrexed + pembrolizumab proposed.",
      missing: [
        { ok: true,  label: "Stage IIIB or IV NSCLC" },
        { ok: true,  label: "EGFR / ALK / ROS1 negative" },
        { ok: false, label: "PD-L1 CPS reported" },
        { ok: true,  label: "ECOG ≤ 1" },
      ],
      hint: "Lab can recompute CPS from existing slide — typical 2-day TAT.",
    },
    {
      id: "AUTH-2026-1836",
      initials: "M.O.",
      drug: "Osimertinib",
      payer: "humana",
      received: "2h 04m ago",
      reason: "T790M status documented post-progression but EGFR exon 19/21 baseline missing.",
      summary: "71F, NSCLC adenocarcinoma, progressed on erlotinib. Repeat biopsy: T790M+. Plan: osimertinib 80mg daily.",
      missing: [
        { ok: false, label: "Baseline EGFR exon 19/21 mutation" },
        { ok: true,  label: "T790M positive (post-progression)" },
        { ok: true,  label: "Prior 1L EGFR TKI" },
      ],
      hint: "Original baseline NGS report likely in EHR — check ordering oncologist's note.",
    },
    {
      id: "AUTH-2026-1832",
      initials: "T.J.",
      drug: "Palbociclib",
      payer: "cigna",
      received: "3h 41m ago",
      reason: "ER/PR status confirmed but Ki-67 missing — Cigna 0512 requires Ki-67 documentation for HR+/HER2− metastatic.",
      summary: "62F, HR+/HER2− metastatic breast cancer, bone-only disease. Letrozole + palbociclib proposed.",
      missing: [
        { ok: true,  label: "ER ≥ 1% or PR ≥ 1%" },
        { ok: true,  label: "HER2 negative" },
        { ok: false, label: "Ki-67 documented" },
        { ok: true,  label: "First-line metastatic" },
      ],
    },
  ];
  window.CLINCASE_REVIEWER = { REFERS };
})();
