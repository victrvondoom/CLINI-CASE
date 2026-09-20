/**
 * Landing-page design tokens + copy.
 *
 * The landing page runs its own dark "aperture" palette, independent of the
 * app's light/dark theme tokens — it is a marketing surface, not app chrome.
 * Colors live here (TS) as well as in landing.css (CSS vars) because the
 * inline SVG backdrop needs them as literal values.
 */

export const apertureColors = {
  void: "#050505",
  ink: "#101010",
  bone: "#ececec",
  cyan: "#e8e8e8",
  violet: "#8a8a8a",
  ember: "#6f6f6f",
} as const;

/** The six steps a prior-auth request passes through inside ClinCase. */
export const LIFECYCLE_STEPS = [
  {
    n: "01",
    title: "Referral lands",
    body: "A chart note, pathology report, or payer packet arrives — uploaded, faxed, or pushed from your EMR. No one retypes anything.",
  },
  {
    n: "02",
    title: "PHI is redacted, then indexed",
    body: "Identifiers are stripped and receipted before a single token reaches a model. The redaction receipt is attached to the case for audit.",
  },
  {
    n: "03",
    title: "The right policy is retrieved",
    body: "The agent pulls the payer's current medical policy for that drug and that indication — with the clause, the version, and the effective date.",
  },
  {
    n: "04",
    title: "Evidence is matched to criteria",
    body: "Every policy criterion is checked against the chart. Met, unmet, or undocumented — each one cites the exact line it came from.",
  },
  {
    n: "05",
    title: "A verdict, with its reasoning",
    body: "APPROVE, DENY, or REFER. Low-confidence cases route to a human reviewer instead of guessing. Nothing auto-submits behind your back.",
  },
  {
    n: "06",
    title: "Submitted, tracked, appealed",
    body: "The packet goes out through the payer gateway. If it comes back denied, the appeal letter is already drafted from the same evidence.",
  },
] as const;

/** Cancer programs the oncology stack ships policy coverage for. */
export const DOMAINS = [
  { key: "breast",      label: "Breast" },
  { key: "lung",        label: "Lung (NSCLC)" },
  { key: "colorectal",  label: "Colorectal" },
  { key: "lymphoma",    label: "Lymphoma" },
  { key: "myeloma",     label: "Multiple myeloma" },
  { key: "melanoma",    label: "Melanoma" },
  { key: "prostate",    label: "Prostate" },
  { key: "ovarian",     label: "Ovarian" },
] as const;

/** Compliance posture — status strings are deliberately honest, not aspirational. */
export const COMPLIANCE_MARKS = [
  { label: "HIPAA",         status: "PHI redaction enforced" },
  { label: "CMS-0057-F",    status: "8 clauses tracked" },
  { label: "SOC 2 Type II",  status: "in progress" },
  { label: "Audit trail",    status: "every case event" },
] as const;
