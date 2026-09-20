// =============================================================
// Synthetic dataset for Dashboard / Cases / Compare
// All deterministic; no real PHI. Patient initials only.
// =============================================================

(function () {

  // ----- Payers (logos = tiny monogram + brand color) -----
  const PAYERS = [
    { id: "aetna",     name: "Aetna",                         tinyLogo: "Æ", color: "#7c3aed" },
    { id: "uhc",       name: "UnitedHealthcare",              tinyLogo: "U",  color: "#0ea5e9" },
    { id: "anthem",    name: "Anthem BCBS",                   tinyLogo: "A",  color: "#1e40af" },
    { id: "cigna",     name: "Cigna",                         tinyLogo: "C",  color: "#10b981" },
    { id: "humana",    name: "Humana",                        tinyLogo: "H",  color: "#16a34a" },
    { id: "bcbs_il",   name: "BCBS Illinois",                 tinyLogo: "BX", color: "#1d4ed8" },
    { id: "centene",   name: "Centene",                       tinyLogo: "Ce", color: "#0891b2" },
    { id: "kaiser",    name: "Kaiser Permanente",             tinyLogo: "K",  color: "#0d9488" },
  ];

  // ----- Treatment templates -----
  const TX = [
    { name: "Pembrolizumab",        j: "J9271", indication: "NSCLC, PD-L1+" },
    { name: "Trastuzumab",          j: "J9355", indication: "HER2+ breast" },
    { name: "Atezolizumab",         j: "J9022", indication: "TNBC" },
    { name: "Pembrolizumab",        j: "J9271", indication: "Melanoma, PD-L1 unknown" },
    { name: "Bevacizumab",          j: "J9035", indication: "mCRC" },
    { name: "Nivolumab",            j: "J9299", indication: "RCC" },
    { name: "Rituximab",            j: "J9312", indication: "DLBCL" },
    { name: "Pertuzumab",           j: "J9306", indication: "HER2+ breast" },
    { name: "Olaparib",             j: "J8999", indication: "Ovarian, BRCA+" },
    { name: "Trastuzumab deruxtecan", j: "J9358", indication: "HER2-low breast" },
    { name: "Daratumumab",          j: "J9145", indication: "Multiple myeloma" },
    { name: "Cetuximab",            j: "J9055", indication: "mCRC, KRAS-WT" },
  ];

  // ----- Cases (12 total) -----
  // status: "running" | "completed"
  // verdict: "APPROVE" | "DENY" | "REFER" | null (when running)
  const now = Date.now();
  const minutesAgo = (m) => new Date(now - m * 60_000).toISOString();

  const CASES = [
    { id: "AUTH-2026-001247", initials: "M.R.", treatment: "Pembrolizumab", j_code: "J9271", payer: "aetna",
      status: "completed", verdict: "APPROVE", confidence: 0.94, submitted_at: minutesAgo(7),    decided_at: minutesAgo(5),    cost: 0.34, agents_run: 5 },
    { id: "AUTH-2026-001246", initials: "S.K.", treatment: "Trastuzumab",   j_code: "J9355", payer: "uhc",
      status: "completed", verdict: "DENY",    confidence: 0.91, submitted_at: minutesAgo(14),   decided_at: minutesAgo(12),   cost: 0.42, agents_run: 5, appealed: true, overturned: true },
    { id: "AUTH-2026-001245", initials: "J.T.", treatment: "Atezolizumab",  j_code: "J9022", payer: "anthem",
      status: "completed", verdict: "REFER",   confidence: 0.62, submitted_at: minutesAgo(28),   decided_at: minutesAgo(26),   cost: 0.51, agents_run: 5 },
    { id: "AUTH-2026-001244", initials: "L.P.", treatment: "Pembrolizumab", j_code: "J9271", payer: "cigna",
      status: "running",   verdict: null,      confidence: null, submitted_at: minutesAgo(2),    decided_at: null,             cost: 0.18, agents_run: 3 },
    { id: "AUTH-2026-001243", initials: "D.W.", treatment: "Bevacizumab",   j_code: "J9035", payer: "humana",
      status: "completed", verdict: "APPROVE", confidence: 0.88, submitted_at: minutesAgo(43),   decided_at: minutesAgo(41),   cost: 0.36, agents_run: 5 },
    { id: "AUTH-2026-001242", initials: "A.B.", treatment: "Nivolumab",     j_code: "J9299", payer: "bcbs_il",
      status: "completed", verdict: "APPROVE", confidence: 0.92, submitted_at: minutesAgo(67),   decided_at: minutesAgo(65),   cost: 0.39, agents_run: 5 },
    { id: "AUTH-2026-001241", initials: "K.H.", treatment: "Rituximab",     j_code: "J9312", payer: "centene",
      status: "completed", verdict: "APPROVE", confidence: 0.96, submitted_at: minutesAgo(89),   decided_at: minutesAgo(87),   cost: 0.31, agents_run: 5 },
    { id: "AUTH-2026-001240", initials: "R.O.", treatment: "Pertuzumab",    j_code: "J9306", payer: "aetna",
      status: "completed", verdict: "DENY",    confidence: 0.83, submitted_at: minutesAgo(124),  decided_at: minutesAgo(122),  cost: 0.45, agents_run: 5, appealed: true, overturned: false },
    { id: "AUTH-2026-001239", initials: "T.E.", treatment: "Olaparib",      j_code: "J8999", payer: "uhc",
      status: "completed", verdict: "REFER",   confidence: 0.71, submitted_at: minutesAgo(168),  decided_at: minutesAgo(166),  cost: 0.48, agents_run: 5 },
    { id: "AUTH-2026-001238", initials: "Y.G.", treatment: "T-DXd",         j_code: "J9358", payer: "kaiser",
      status: "completed", verdict: "APPROVE", confidence: 0.90, submitted_at: minutesAgo(214),  decided_at: minutesAgo(212),  cost: 0.41, agents_run: 5 },
    { id: "AUTH-2026-001237", initials: "C.M.", treatment: "Daratumumab",   j_code: "J9145", payer: "anthem",
      status: "completed", verdict: "APPROVE", confidence: 0.89, submitted_at: minutesAgo(289),  decided_at: minutesAgo(287),  cost: 0.37, agents_run: 5 },
    { id: "AUTH-2026-001236", initials: "B.N.", treatment: "Cetuximab",     j_code: "J9055", payer: "humana",
      status: "completed", verdict: "DENY",    confidence: 0.86, submitted_at: minutesAgo(341),  decided_at: minutesAgo(339),  cost: 0.43, agents_run: 5, appealed: false },
  ];

  const ACTIVE_COUNT = CASES.filter((c) => c.status === "running").length || 1;
  const REFER_COUNT  = CASES.filter((c) => c.verdict === "REFER").length;

  // ----- KPIs -----
  const KPIS = {
    active_cases: 12,
    avg_decision_seconds: 3 * 60 + 47,         // 3m 47s
    approval_rate: 0.74,
    approval_band: [0.71, 0.77],
    cost_to_date: 18.42,
    sparkline_active: [4, 7, 6, 9, 8, 11, 10, 14, 12, 13, 15, 12],
  };

  // ----- Agent health -----
  const AGENT_HEALTH = [
    { key: "intake",   name: "Intake Validator", success: 1.000, p95_ms: 1200, running: false },
    { key: "evidence", name: "Evidence Extractor", success: 0.998, p95_ms: 4100, running: true },
    { key: "policy",   name: "Policy Lookup", success: 0.997, p95_ms: 3600, running: false },
    { key: "decision", name: "Decision Engine", success: 0.999, p95_ms: 5800, running: false },
    { key: "appeal",   name: "Appeal Drafter", success: 0.992, p95_ms: 7400, running: false },
  ];

  // ----- Policy updates -----
  const POLICY_UPDATES = [
    { policy_id: "AET-ONC-2026-031", payer: "aetna",  title: "Pembrolizumab — added MSI-H carve-out for CRC second-line",
      from: "v3.1", to: "v3.2", changed_at: minutesAgo(2 * 60 + 12),  impacted_cases: 3 },
    { policy_id: "UHC-ONC-2026-114", payer: "uhc",    title: "Trastuzumab — IHC 3+ now sufficient without FISH for biosimilar swap",
      from: "v2.4", to: "v2.5", changed_at: minutesAgo(8 * 60 + 41),  impacted_cases: 2 },
    { policy_id: "BCBS-ONC-2026-077", payer: "anthem", title: "Atezolizumab — TNBC tightening: PD-L1 SP142 ≥1% now mandatory",
      from: "v1.7", to: "v1.8", changed_at: minutesAgo(26 * 60),      impacted_cases: 1 },
    { policy_id: "HUM-ONC-2026-050", payer: "humana", title: "Bevacizumab — first-line mCRC step therapy lifted",
      from: "v4.0", to: "v4.1", changed_at: minutesAgo(2 * 24 * 60),  impacted_cases: 0 },
  ];

  // ----- Compliance pulse -----
  // CMS-0057-F mandate: assume 2027-01-01 deadline
  const deadline = new Date("2027-01-01T00:00:00Z").getTime();
  const cms_0057_days = Math.max(0, Math.floor((deadline - now) / (24 * 60 * 60 * 1000)));
  const COMPLIANCE_PULSE = {
    cms_0057_days,
    phi_redactions_24h: 1247,
    audit_completeness: 1.0,
  };

  // ----- timeAgo helper -----
  function timeAgo(iso) {
    if (!iso) return "—";
    const t = new Date(iso).getTime();
    const s = Math.max(1, Math.floor((Date.now() - t) / 1000));
    if (s < 60)         return `${s}s ago`;
    const m = Math.floor(s / 60);
    if (m < 60)         return `${m}m ago`;
    const h = Math.floor(m / 60);
    if (h < 24)         return `${h}h ago`;
    const d = Math.floor(h / 24);
    return `${d}d ago`;
  }

  window.CLINCASE_EXTRA = {
    PAYERS,
    CASES,
    KPIS,
    AGENT_HEALTH,
    POLICY_UPDATES,
    COMPLIANCE_PULSE,
    ACTIVE_COUNT,
    REFER_COUNT,
    timeAgo,
  };
})();
