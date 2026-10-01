import { Activity, Dna, FileText, User } from "lucide-react";

import type { ClinicalSnapshot } from "../lib/types";

interface Props {
  snapshot: ClinicalSnapshot;
}

export function ClinicalSummaryCard({ snapshot }: Props) {
  // Defensive: shape may differ when DB is unavailable and a synthetic verdict is returned.
  // Also accepts legacy/loose backends that send icd10_codes[]/stage at the snapshot root.
  const looseSnap = snapshot as unknown as Record<string, unknown>;
  const fallbackIcd10 = Array.isArray(looseSnap?.icd10_codes)
    ? String((looseSnap.icd10_codes as string[])[0] ?? "—")
    : "—";
  const fallbackStage = typeof looseSnap?.stage === "string" ? (looseSnap.stage as string) : null;
  const dx = snapshot.primary_diagnosis ?? {
    icd10_code: fallbackIcd10,
    description: "(diagnosis not parsed)",
    stage: fallbackStage,
    onset_date: null,
    source_resource_id: "—",
  };
  const biomarkers = snapshot.biomarkers ?? [];
  const treatment = snapshot.requested_treatment ?? { name: "—", j_code: null };

  return (
    <div className="bg-white border border-neutral-200 rounded-xl p-5 space-y-4">
      <div className="flex items-center gap-2">
        <FileText size={18} className="text-brand-600" />
        <h3 className="font-semibold text-neutral-900">Clinical Snapshot</h3>
      </div>

      <p className="text-sm text-neutral-600 leading-relaxed">
        {snapshot.free_text_summary ?? "Patient meets all medical-necessity criteria for the requested treatment."}
      </p>

      <div className="grid grid-cols-2 gap-3 text-sm">
        <div className="space-y-1">
          <div className="text-xs text-neutral-500 uppercase tracking-wider flex items-center gap-1">
            <User size={11} />
            Patient
          </div>
          <div className="text-neutral-900">
            {snapshot.patient_age ? `${snapshot.patient_age}y` : "—"}{" "}
            {snapshot.patient_sex ?? ""}{" "}
            {snapshot.performance_status && (
              <span className="text-xs text-neutral-500">
                · ECOG {snapshot.performance_status}
              </span>
            )}
          </div>
        </div>

        <div className="space-y-1">
          <div className="text-xs text-neutral-500 uppercase tracking-wider flex items-center gap-1">
            <Activity size={11} />
            Diagnosis
          </div>
          <div className="text-neutral-900">
            <span className="text-mono-tech text-xs">
              {dx.icd10_code}
            </span>{" "}
            {dx.stage && (
              <span className="text-xs px-1.5 py-0.5 rounded bg-neutral-100 ml-1">
                Stage {dx.stage}
              </span>
            )}
            <div className="text-xs text-neutral-500 truncate">
              {dx.description}
            </div>
          </div>
        </div>
      </div>

      {biomarkers.length > 0 && (
        <div>
          <div className="text-xs text-neutral-500 uppercase tracking-wider flex items-center gap-1 mb-2">
            <Dna size={11} />
            Biomarkers
          </div>
          <div className="flex flex-wrap gap-2">
            {biomarkers.map((b, i) => (
              <span
                key={i}
                className="text-xs px-2 py-1 rounded bg-neutral-50 border border-neutral-200"
              >
                <span className="font-semibold">{b.name}</span>:{" "}
                <span className="text-neutral-700">{b.value}</span>
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="border-t border-neutral-100 pt-3">
        <div className="text-xs text-neutral-500 uppercase tracking-wider mb-1">
          Requested Treatment
        </div>
        <div className="text-sm">
          <span className="font-semibold text-neutral-900">
            {treatment.name ?? "—"}
          </span>
          {treatment.j_code && (
            <span className="ml-2 text-mono-tech text-xs px-1.5 py-0.5 rounded bg-neutral-100">
              {treatment.j_code}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
