/**
 * Landing-page design tokens + copy.
 *
 * The landing page runs its own "aperture" palette (dark or light), separate
 * from the app's light/dark theme tokens — it is a marketing surface, not app
 * chrome, but it now follows the same theme choice (see lib/theme.ts) so a
 * visitor who flips to light doesn't land back on a dark page after signing
 * in. Colors live here (TS) as well as in landing.css (CSS vars) because the
 * inline SVG backdrop and the WebGL scene need them as literal values, not
 * CSS custom properties.
 */

export const apertureColorsDark = {
  void: "#050505",
  ink: "#101010",
  bone: "#ececec",
  cyan: "#e8e8e8",
  violet: "#8a8a8a",
  ember: "#6f6f6f",
} as const;

export const apertureColorsLight = {
  void: "#ffffff",
  ink: "#f4f4f4",
  bone: "#101010",
  cyan: "#1a1a1a",
  violet: "#5a5a5a",
  ember: "#787878",
} as const;

export type ApertureTheme = "dark" | "light";

export function getApertureColors(theme: ApertureTheme) {
  return theme === "light" ? apertureColorsLight : apertureColorsDark;
}

/** @deprecated Use `getApertureColors(theme)` — kept for any stray import. */
export const apertureColors = apertureColorsDark;

/** The six steps a prior-auth request passes through inside ClinCase. */
export const LIFECYCLE_STEPS = [
  {
    n: "01",
    title: "Referral lands",
    body: "A chart note, pathology report, or payer packet arrives — uploaded, faxed, or pushed from your EMR. No one retypes anything.",
  },
  {
    n: "02",
    title: "Text is screened, then indexed",
    body: "Recognized identifiers are redacted and recorded. Automated screening is not a guarantee of de-identification; review documents and deployment controls before using patient data.",
  },
  {
    n: "03",
    title: "The right policy is retrieved",
    body: "The agent retrieves the configured payer policy for that drug and indication — with the clause, the version, and the effective date.",
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
    title: "Prepared, reviewed, appealed",
    body: "Prepare the packet for review and draft an appeal from the same evidence. Live payer submission requires an external integration.",
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
  { label: "Privacy controls", status: "deployment review required" },
  { label: "CMS-0057-F",    status: "8 clauses tracked" },
  { label: "SOC 2 Type II",  status: "not independently attested" },
  { label: "Audit trail",    status: "every case event" },
] as const;
