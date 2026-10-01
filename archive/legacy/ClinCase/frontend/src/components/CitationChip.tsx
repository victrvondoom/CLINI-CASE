import clsx from "clsx";
import { Award, BookOpen, FileText, ScrollText, Stethoscope } from "lucide-react";
import type { LucideIcon } from "lucide-react";

import type { Citation, CitationKind } from "../lib/types";

interface CitationChipProps {
  citation: Citation;
  /** When provided, the chip is clickable and triggers this handler. */
  onClick?: () => void;
}

// Kind-aware visual mapping. Each citation kind gets its own icon, color
// scheme, and label so a reviewer can distinguish at a glance:
//
//   clinical    blue    Stethoscope    "clinical:"   FHIR resource
//   policy      violet  FileText       "policy:"     payer CPB / coverage doc
//   compendium  green   BookOpen       "compendium:" NCCN / AHFS / Lexi-Drugs
//   fda_label   amber   ScrollText     "fda label:"  FDA HCP / Indications
//   guideline   cyan    Award          "guideline:"  NCCN / ASCO / ESMO
const KIND_META: Record<CitationKind, { icon: LucideIcon; label: string; chipClass: string }> = {
  clinical: {
    icon: Stethoscope,
    label: "clinical:",
    chipClass:
      "bg-gray-50 border-gray-200 text-gray-800 dark:bg-gray-500/10 dark:border-gray-500/30 dark:text-gray-300",
  },
  policy: {
    icon: FileText,
    label: "policy:",
    chipClass:
      "bg-gray-50 border-gray-200 text-gray-800 dark:bg-gray-500/10 dark:border-gray-500/30 dark:text-gray-300",
  },
  compendium: {
    icon: BookOpen,
    label: "compendium:",
    chipClass:
      "bg-gray-50 border-gray-200 text-gray-800 dark:bg-gray-500/10 dark:border-gray-500/30 dark:text-gray-300",
  },
  fda_label: {
    icon: ScrollText,
    label: "fda label:",
    chipClass:
      "bg-gray-50 border-gray-200 text-gray-800 dark:bg-gray-500/10 dark:border-gray-500/30 dark:text-gray-300",
  },
  guideline: {
    icon: Award,
    label: "guideline:",
    chipClass:
      "bg-gray-50 border-gray-200 text-gray-800 dark:bg-gray-500/10 dark:border-gray-500/30 dark:text-gray-300",
  },
};

export function CitationChip({ citation, onClick }: CitationChipProps) {
  const meta = KIND_META[citation.kind] ?? KIND_META.policy;
  const Icon = meta.icon;

  const className = clsx(
    "inline-flex items-center gap-1.5 text-xs text-mono-tech px-2 py-1 rounded border transition-all",
    meta.chipClass,
    onClick && "cursor-pointer hover:shadow-sm hover:scale-[1.02] active:scale-95",
  );

  const inner = (
    <>
      <Icon size={12} />
      <span className="opacity-70">{meta.label}</span>
      <span className="font-semibold truncate max-w-[28ch]">
        {citation.pointer}
      </span>
    </>
  );

  if (onClick) {
    return (
      <button type="button" onClick={onClick} className={className} title={citation.text}>
        {inner}
      </button>
    );
  }

  return (
    <span className={className} title={citation.text}>
      {inner}
    </span>
  );
}
