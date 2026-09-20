/* global window */
(function () {
  // CMS-0057-F § IV — eight clauses ClinCase maps against.
  const CLAUSES = [
    {
      id: "iv.a",
      title: "Patient Access API",
      blurb: "FHIR R4 endpoint for member-facing prior-auth status, decision rationale, and citation.",
      status: "in_force",
      evidence: "endpoint /v1/patient/auth-status — last test 2026-04-28",
    },
    {
      id: "iv.b",
      title: "Provider Access API",
      blurb: "Read-only FHIR access for in-network providers to query member auth history.",
      status: "in_force",
      evidence: "OAuth2 scopes patient/*.read, last attestation 2026-04-15",
    },
    {
      id: "iv.c",
      title: "Payer-to-Payer Data Exchange",
      blurb: "USCDI v3 + claims data on member transition between payers.",
      status: "in_force",
      evidence: "$member-match operation passes 12/12 NCQA test cases",
    },
    {
      id: "iv.d",
      title: "Prior Auth API ($submit)",
      blurb: "FHIR Da Vinci PAS endpoint accepting Bundle, returning ClaimResponse with decision.",
      status: "in_force",
      evidence: "p95 response time 4.2s · 412 requests/24h",
    },
    {
      id: "iv.e",
      title: "Decision Reason — structured",
      blurb: "Every denial / referral returns CodeableConcept-tagged reasons + policy citation pointer.",
      status: "in_force",
      evidence: "100% of 24h decisions include citation_chain[]",
    },
    {
      id: "iv.f",
      title: "Decision Timeliness",
      blurb: "Standard requests ≤ 7 days, expedited ≤ 72 hours. ClinCase auto-tags expedited cases.",
      status: "in_force",
      evidence: "median time-to-decision 4m 18s · zero late decisions in 90d",
    },
    {
      id: "iv.g",
      title: "Public Reporting Metrics",
      blurb: "Annual CMS report: approved / denied / appealed / overturned counts by indication.",
      status: "in_force",
      evidence: "report builder ready · last generated 2026-04-30",
    },
    {
      id: "iv.h",
      title: "Audit Trail Retention",
      blurb: "7-year append-only ledger of every agent invocation, prompt hash, and decision.",
      status: "in_force",
      evidence: "S3 Object Lock (compliance mode) · 412 / 412 entries last 24h",
    },
  ];

  // 7-day PHI redaction events per day.
  const PHI_REDACTIONS_7D = [1184, 1247, 1198, 1322, 1278, 1156, 1247];

  const SCORECARD = {
    in_force: 8,
    total: 8,
    last_audit: "2026-04-30",
    next_audit: "2026-07-30",
    audit_completeness: 1.0,
    phi_redactions_7d_total: PHI_REDACTIONS_7D.reduce((a, b) => a + b, 0),
    phi_redactions_24h: 1247,
    days_to_deadline: Math.max(
      0,
      Math.floor((new Date("2027-01-01T00:00:00Z").getTime() - Date.now()) / (24 * 60 * 60 * 1000))
    ),
  };

  window.CLINCASE_COMPLIANCE = {
    CLAUSES,
    PHI_REDACTIONS_7D,
    SCORECARD,
  };
})();
