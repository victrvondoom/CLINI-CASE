/**
 * Citation drill-down modal — opens when a CitationChip is clicked. Shows
 * the source the citation points to: FHIR resource (clinical) or policy
 * excerpt (policy).
 *
 * For demo, source content is synthesized from the citation pointer when no
 * deeper data is available; in production this would fetch the actual FHIR
 * resource or policy chunk from Bedrock KB.
 */
import clsx from "clsx";
import { Award, BookOpen, ExternalLink, FileText, ScrollText, Stethoscope, X } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useEffect } from "react";

import type { Citation, CitationKind } from "../lib/types";

interface Props {
  citation: Citation | null;
  onClose: () => void;
}

// Synthetic source content keyed by pointer pattern
const SOURCE_CONTENT: Record<string, { title: string; content: string; meta?: string }> = {
  // Clinical FHIR resource pointers
  "obs-her2": {
    title: "FHIR Observation · obs-her2",
    content: JSON.stringify(
      {
        resourceType: "Observation",
        id: "obs-her2",
        status: "final",
        category: [{ coding: [{ system: "http://terminology.hl7.org/CodeSystem/observation-category", code: "laboratory" }] }],
        code: {
          coding: [{ system: "http://loinc.org", code: "85319-2", display: "HER2 [Presence] in Breast cancer specimen by Immunohistochemistry" }],
          text: "HER2 IHC",
        },
        effectiveDateTime: "2026-02-22",
        valueCodeableConcept: {
          coding: [{ system: "http://loinc.org", code: "LA6577-6" }],
          text: "Positive (3+)",
        },
      },
      null,
      2,
    ),
    meta: "Effective: 2026-02-22 · LOINC 85319-2",
  },
  "obs-her2neg-her2": {
    title: "FHIR Observation · obs-her2neg-her2",
    content: JSON.stringify(
      {
        resourceType: "Observation",
        id: "obs-her2neg-her2",
        status: "final",
        code: { coding: [{ system: "http://loinc.org", code: "85319-2" }], text: "HER2 IHC" },
        effectiveDateTime: "2026-01-26",
        valueCodeableConcept: {
          coding: [{ system: "http://loinc.org", code: "LA6576-8" }],
          text: "Negative (IHC 1+, ISH non-amplified)",
        },
      },
      null,
      2,
    ),
    meta: "Effective: 2026-01-26 · LOINC 85319-2",
  },
  "condition-primary": {
    title: "FHIR Condition · condition-primary",
    content: JSON.stringify(
      {
        resourceType: "Condition",
        id: "condition-primary",
        clinicalStatus: { coding: [{ code: "active" }] },
        verificationStatus: { coding: [{ code: "confirmed" }] },
        code: {
          coding: [{ system: "http://hl7.org/fhir/sid/icd-10-cm", code: "C50.911", display: "Malignant neoplasm of unspecified site of right female breast" }],
          text: "Stage IIIA invasive ductal carcinoma of right breast",
        },
        stage: [{ summary: { text: "IIIA" } }],
        onsetDateTime: "2026-02-12",
      },
      null,
      2,
    ),
    meta: "Onset: 2026-02-12 · ICD-10-CM C50.911",
  },
  "obs-approve-her2": {
    title: "FHIR Observation · obs-approve-her2",
    content: JSON.stringify(
      {
        resourceType: "Observation",
        id: "obs-approve-her2",
        status: "final",
        code: { coding: [{ system: "http://loinc.org", code: "85319-2" }], text: "HER2 IHC" },
        effectiveDateTime: "2026-02-22",
        valueCodeableConcept: { text: "Positive (3+)" },
      },
      null,
      2,
    ),
    meta: "Effective: 2026-02-22",
  },
  "condition-approve-primary": {
    title: "FHIR Condition · condition-approve-primary",
    content: JSON.stringify(
      {
        resourceType: "Condition",
        id: "condition-approve-primary",
        code: { coding: [{ code: "C50.911" }], text: "Stage IIIA invasive ductal carcinoma of right breast" },
        stage: [{ summary: { text: "IIIA" } }],
        onsetDateTime: "2026-02-12",
      },
      null,
      2,
    ),
    meta: "ICD-10 C50.911 · Stage IIIA",
  },
};

const POLICY_CONTENT: Record<string, { title: string; section: string; text: string; payer: string; policy_id: string }> = {
  "policy:0048#Initial Authorization Criteria": {
    title: "Trastuzumab (Herceptin) for HER2-Positive Breast Cancer",
    section: "Initial Authorization Criteria",
    payer: "Aetna",
    policy_id: "0048",
    text:
      "Aetna considers trastuzumab medically necessary for the treatment of patients with HER2-positive breast cancer when ALL of the following criteria are met:\n\n" +
      "(1) Pathologic confirmation of breast cancer with HER2 overexpression, defined as immunohistochemistry (IHC) score of 3+, OR in-situ hybridization (ISH) demonstrating HER2 gene amplification.\n\n" +
      "(2) For early-stage (Stage I-III) disease, treatment is given in the adjuvant or neoadjuvant setting in combination with chemotherapy.\n\n" +
      "(3) For metastatic (Stage IV) disease, trastuzumab may be given as a single agent or in combination with chemotherapy or endocrine therapy.\n\n" +
      "(4) Adequate baseline cardiac function defined as left ventricular ejection fraction (LVEF) >= 50% by echocardiogram or MUGA scan, performed within 90 days of treatment initiation.\n\n" +
      "(5) ECOG performance status of 0, 1, or 2.",
  },
  "policy:0048#Exclusions": {
    title: "Trastuzumab (Herceptin) for HER2-Positive Breast Cancer",
    section: "Exclusions",
    payer: "Aetna",
    policy_id: "0048",
    text:
      "Trastuzumab is NOT considered medically necessary in the following circumstances:\n\n" +
      "• HER2-negative tumors (IHC 0 or 1+, OR ISH non-amplified).\n" +
      "• Patients with baseline LVEF below 50%.\n" +
      "• Symptomatic heart failure (NYHA class II-IV) at baseline.\n" +
      "• Concurrent anthracycline chemotherapy administration in the metastatic setting.\n" +
      "• Uncontrolled hypertension.",
  },
};

// Round-14 visual mapping for all 5 citation kinds.
// Each kind has its own icon, label, and color tokens, so the modal
// faithfully renders the source authority — not a one-size-fits-all "policy".
const KIND_DISPLAY: Record<CitationKind, {
  icon: LucideIcon;
  label: string;          // header eyebrow text
  sourceLabel: string;    // "Source · ..." text
  textColor: string;      // text token for the eyebrow
  bgColor: string;        // background token for the icon badge
  bgFaint: string;        // background token for the source pre / panel
  borderFaint: string;    // border token for the source pre / panel
  headerBg: string;       // header tint
  headerBorder: string;   // header bottom border
}> = {
  clinical: {
    icon: Stethoscope,
    label: "CLINICAL EVIDENCE",
    sourceLabel: "Source · FHIR JSON",
    textColor: "text-accent-blue",
    bgColor: "bg-accent-blue",
    bgFaint: "bg-surface-bg",
    borderFaint: "border-surface-border",
    headerBg: "bg-accent-blue/5",
    headerBorder: "border-accent-blue/30",
  },
  policy: {
    icon: FileText,
    label: "POLICY EXCERPT",
    sourceLabel: "Source · Policy text",
    textColor: "text-accent-violet",
    bgColor: "bg-accent-violet",
    bgFaint: "bg-accent-violet/5",
    borderFaint: "border-accent-violet/20",
    headerBg: "bg-accent-violet/5",
    headerBorder: "border-accent-violet/30",
  },
  compendium: {
    icon: BookOpen,
    label: "DRUG COMPENDIUM",
    sourceLabel: "Source · Compendium entry",
    textColor: "text-accent-green",
    bgColor: "bg-accent-green",
    bgFaint: "bg-accent-green/5",
    borderFaint: "border-accent-green/20",
    headerBg: "bg-accent-green/5",
    headerBorder: "border-accent-green/30",
  },
  fda_label: {
    icon: ScrollText,
    label: "FDA LABEL",
    sourceLabel: "Source · FDA HCP",
    textColor: "text-accent-amber",
    bgColor: "bg-accent-amber",
    bgFaint: "bg-accent-amber/5",
    borderFaint: "border-accent-amber/20",
    headerBg: "bg-accent-amber/5",
    headerBorder: "border-accent-amber/30",
  },
  guideline: {
    icon: Award,
    label: "CLINICAL GUIDELINE",
    sourceLabel: "Source · Guideline section",
    textColor: "text-accent-cyan",
    bgColor: "bg-accent-cyan",
    bgFaint: "bg-accent-cyan/5",
    borderFaint: "border-accent-cyan/20",
    headerBg: "bg-accent-cyan/5",
    headerBorder: "border-accent-cyan/30",
  },
};

function lookupSource(citation: Citation): {
  title: string;
  content: string;
  meta?: string;
  isFhir: boolean;
} {
  if (citation.kind === "clinical") {
    const found = SOURCE_CONTENT[citation.pointer];
    if (found) return { ...found, isFhir: true };
    return {
      title: `FHIR Resource · ${citation.pointer}`,
      content: JSON.stringify({ id: citation.pointer, text: citation.text }, null, 2),
      meta: "(synthesized for demo · production fetches from real FHIR store)",
      isFhir: true,
    };
  }
  if (citation.kind === "policy") {
    const found = POLICY_CONTENT[citation.pointer];
    if (found) {
      return {
        title: found.title,
        content: found.text,
        meta: `${found.payer} · Policy ${found.policy_id} · ${found.section}`,
        isFhir: false,
      };
    }
    return {
      title: citation.pointer,
      content: citation.text,
      meta: "(synthesized for demo · production fetches from Bedrock Knowledge Base)",
      isFhir: false,
    };
  }
  // Round-14 kinds: compendium / fda_label / guideline.
  // Production fetches from a per-kind upstream:
  //   compendium → NCCN/AHFS/Lexi-Drugs API
  //   fda_label  → DailyMed / DrugBank
  //   guideline  → NCCN-Guidelines / ASCO / ESMO
  // Demo: synthesize from the citation pointer + text so the modal is
  // self-explanatory even without the upstream fetch.
  const kindToProvider: Record<CitationKind, string> = {
    clinical: "FHIR store",
    policy: "Bedrock Knowledge Base",
    compendium: "NCCN / AHFS / Lexi-Drugs API",
    fda_label: "DailyMed / FDA HCP",
    guideline: "NCCN-Guidelines / ASCO / ESMO",
  };
  return {
    title: citation.pointer,
    content: citation.text,
    meta: `(synthesized for demo · production fetches from ${kindToProvider[citation.kind]})`,
    isFhir: false,
  };
}

export function CitationModal({ citation, onClose }: Props) {
  // ESC closes
  useEffect(() => {
    if (!citation) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [citation, onClose]);

  if (!citation) return null;

  const source = lookupSource(citation);
  const display = KIND_DISPLAY[citation.kind] ?? KIND_DISPLAY.policy;
  const Icon = display.icon;
  const viewFullLabel: Record<CitationKind, string> = {
    clinical: "FHIR bundle",
    policy: "policy",
    compendium: "compendium entry",
    fda_label: "FDA label",
    guideline: "guideline section",
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-[10vh] px-4"
      onClick={onClose}
    >
      <div className="absolute inset-0 bg-ink-primary/40 backdrop-blur-sm animate-slide-in-up" />

      <div
        className="relative w-full max-w-2xl bg-surface-raised border border-surface-border rounded-2xl shadow-2xl overflow-hidden animate-slide-in-up"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className={clsx(
          "flex items-center gap-3 px-5 py-3 border-b",
          display.headerBg,
          display.headerBorder,
        )}>
          <div className={clsx(
            "w-9 h-9 rounded-lg text-ink-invert flex items-center justify-center shrink-0",
            display.bgColor,
          )}>
            <Icon size={16} strokeWidth={2.5} />
          </div>
          <div className="flex-1 min-w-0">
            <div className={clsx(
              "text-[10px] text-compact font-bold",
              display.textColor,
            )}>
              {display.label}
            </div>
            <div className="font-semibold text-ink-primary text-sm truncate">
              {source.title}
            </div>
            {source.meta && (
              <div className="text-[11px] text-ink-muted text-mono-tech mt-0.5">
                {source.meta}
              </div>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded hover:bg-surface-raised-hi text-ink-muted"
            aria-label="Close"
          >
            <X size={16} />
          </button>
        </div>

        {/* Cited claim */}
        <div className="px-5 py-3 border-b border-surface-border bg-surface-panel/40">
          <div className="text-compact text-[10px] text-ink-muted mb-1">
            Cited claim
          </div>
          <p className="text-editorial-italic text-sm text-ink-body">"{citation.text}"</p>
        </div>

        {/* Source content */}
        <div className="px-5 py-4 max-h-[50vh] overflow-y-auto">
          <div className="text-[10px] text-compact text-ink-muted mb-2">
            {display.sourceLabel}
          </div>
          <pre className={clsx(
            "text-xs leading-relaxed whitespace-pre-wrap rounded-lg p-3 border text-ink-body",
            source.isFhir
              ? "text-mono-tech bg-surface-bg border-surface-border"
              : clsx("font-sans", display.bgFaint, display.borderFaint),
          )}>
            {source.content}
          </pre>
        </div>

        {/* Footer */}
        <div className="px-5 py-2.5 border-t border-surface-border bg-surface-panel/40 flex items-center justify-between text-[11px] text-ink-muted">
          <span className="text-mono-tech">pointer: {citation.pointer}</span>
          <button
            type="button"
            className="text-accent-brand hover:underline flex items-center gap-1"
          >
            View full {viewFullLabel[citation.kind]} <ExternalLink size={10} />
          </button>
        </div>
      </div>
    </div>
  );
}
