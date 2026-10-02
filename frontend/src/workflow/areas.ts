export const areas = [
  {
    path: "/intake-tools",
    label: "Intake",
    summary: "Choose how to bring evidence into the journey.",
    links: [
      ["New case / scan", "/intake"],
      ["Bulk import", "/cases/bulk-import"],
      ["Import environmental evidence", "/journey"],
    ],
  },
  {
    path: "/evidence",
    label: "Evidence",
    summary: "Explore source observations and their traceable evidence.",
    links: [
      ["Environmental overview", "/aquahealth"],
      ["New observation", "/aquahealth/observations/new"],
      ["Observations", "/aquahealth/observations"],
      ["Map", "/aquahealth/map"],
      ["Trends", "/aquahealth/trends"],
      ["One Health", "/aquahealth/one-health"],
      ["Community", "/aquahealth/community"],
      ["Evidence workbench / passport", "/onehealth"],
    ],
  },
  {
    path: "/interop",
    label: "Interoperability",
    summary: "Map, standardize, validate, exchange and verify evidence.",
    links: [
      ["Connected standards journey", "/journey"],
      ["Gateway", "/interop"],
    ],
  },
  {
    path: "/review",
    label: "Review & Safety",
    summary: "Choose the review appropriate to this evidence.",
    links: [
      ["Environmental review queue", "/aquahealth/review"],
      ["Safety evaluation", "/aquahealth/evaluation"],
      ["Clinical reviewer queue", "/reviewer"],
      ["Mapping review", "/journey"],
    ],
  },
  {
    path: "/clinical-context",
    label: "Clinical Context",
    summary:
      "Choose relevant context. Oncology and digital twins are optional; environmental evidence does not imply a cancer or cardiovascular diagnosis.",
    links: [
      ["General case context", "/cases"],
      ["Oncology", "/onco"],
      ["Agents", "/agents"],
      ["Policies", "/policies"],
      ["Sandbox", "/sandbox"],
      ["OncoTwin", "/twin"],
      ["Guided twin demo", "/twin/demo"],
      ["Twin overview", "/twin/overview"],
      ["CardioTwin", "/cardiotwin"],
      ["CardioTwin evaluation", "/cardiotwin/evaluation"],
    ],
  },
  {
    path: "/follow-up",
    label: "Follow-up",
    summary:
      "Return to the evidence workbench to review follow-up tasks and retest evidence. Clinical twins are optional.",
    links: [
      ["Follow-up / retest workbench", "/onehealth"],
      ["Continue without a clinical twin", "/journey"],
      ["Cases", "/cases"],
    ],
  },
  {
    path: "/research",
    label: "Research",
    summary: "Choose a supporting research or evaluation capability.",
    links: [
      ["Research lab", "/twin/lab"],
      ["Observability", "/twin/ops"],
      ["Cohorts / insights", "/cohorts"],
      ["Evaluation harness", "/eval"],
      ["ROI", "/roi"],
      ["Compliance", "/compliance"],
      ["Industrialization", "/industrialize"],
    ],
  },
] as const;
export function areaFor(path: string) {
  const exact = areas.find((a) => a.path === path);
  if (exact) return exact;
  return areas
    .flatMap((area) => area.links.map(([, href]) => ({ area, href })))
    .filter(({ href }) => path === href || path.startsWith(href + "/"))
    .sort((a, b) => b.href.length - a.href.length)[0]?.area;
}
