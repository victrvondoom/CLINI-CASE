"""CMS-0057-F + state AI law compliance instrumentation.

This subpackage answers ONE question for ONE auditor in ONE call: "is this
case compliant with the regulations that are LIVE today?"

The relevant rules:

  • CMS-0057-F (CMS Interoperability + Prior Authorization Final Rule)
      - § IV.A   Prior Auth API exposed (Da Vinci PAS); LIVE Jan 1 2027 (FHIR PARDA)
      - § IV.B.1 Decision TAT: 72 hr expedited / 7 days standard; LIVE Jan 1 2026
      - § IV.B.2 Specific denial reasons regardless of channel; LIVE Jan 1 2026
      - § IV.C   Public PA metrics reporting; first report due Mar 31 2026 (PASSED)
      - § IV.D   Audit trail / 7-year retention; LIVE
      - § IV.E   Patient access / member-facing PA status; LIVE Jan 1 2027

  • CA SB 1120 (Physicians Make Decisions Act, eff. Jan 1, 2025)
      - AI cannot make final medical-necessity denials
      - Qualified health-care professional MUST review + sign

  • Da Vinci PAS / CRD / DTR  — adoption tracker (CMS proposed v2.2.1 / 2.2.0)
      - Sunset of pre-v2.2.1 versions: Jan 1, 2028

  • CO AI Act (eff. Feb 1, 2026)
      - High-risk AI in healthcare/insurance: risk management programs

This module's API:

  clauses_satisfied_for_case(case_id) -> list[clause_id]
  case_scorecard(case_id) -> dict
  org_scorecard(organization_id) -> dict
"""
from app.compliance.cms_0057f import (
    case_scorecard,
    clauses_satisfied_for_case,
    org_scorecard,
)

__all__ = ["case_scorecard", "clauses_satisfied_for_case", "org_scorecard"]
