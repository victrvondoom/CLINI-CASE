/* global window */
(function () {
  const ROWS = [
    { id: "AUTH-2026-1843", initials: "M.K.", drug: "Trastuzumab",   payer: "aetna",  status: "done",    progress: 1.00, verdict: "APPROVE" },
    { id: "AUTH-2026-1844", initials: "R.P.", drug: "Pembrolizumab", payer: "cigna",  status: "done",    progress: 1.00, verdict: "APPROVE" },
    { id: "AUTH-2026-1845", initials: "L.S.", drug: "Trastuzumab",   payer: "uhc",    status: "running", progress: 0.74, agent: "necessity_reasoner" },
    { id: "AUTH-2026-1846", initials: "T.W.", drug: "Osimertinib",   payer: "humana", status: "running", progress: 0.52, agent: "policy_retriever" },
    { id: "AUTH-2026-1847", initials: "J.D.", drug: "Pembrolizumab", payer: "aetna",  status: "running", progress: 0.31, agent: "clinical_extractor" },
    { id: "AUTH-2026-1848", initials: "K.L.", drug: "Trastuzumab",   payer: "uhc",    status: "running", progress: 0.18, agent: "clinical_extractor" },
    { id: "AUTH-2026-1849", initials: "B.M.", drug: "Palbociclib",   payer: "cigna",  status: "queued",  progress: 0 },
    { id: "AUTH-2026-1850", initials: "E.G.", drug: "Trastuzumab",   payer: "aetna",  status: "queued",  progress: 0 },
    { id: "AUTH-2026-1851", initials: "S.H.", drug: "Osimertinib",   payer: "uhc",    status: "queued",  progress: 0 },
    { id: "AUTH-2026-1852", initials: "C.R.", drug: "Pembrolizumab", payer: "humana", status: "queued",  progress: 0 },
    { id: "AUTH-2026-1853", initials: "N.B.", drug: "Trastuzumab",   payer: "aetna",  status: "queued",  progress: 0 },
    { id: "AUTH-2026-1854", initials: "P.O.", drug: "Pembrolizumab", payer: "cigna",  status: "queued",  progress: 0 },
  ];
  window.CLINCASE_BULK = { ROWS };
})();
