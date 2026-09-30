import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { onehealth, type ExposureRecord } from "./api";

/** Shared evidence, never an extra feature in the existing disease classifiers. */
export function ExposureContext({
  patientId,
  caseId,
  exposureId,
  independentCardio = false,
}: {
  patientId?: string;
  caseId?: string;
  exposureId?: string;
  independentCardio?: boolean;
}) {
  const [records, setRecords] = useState<ExposureRecord[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  useEffect(() => {
    let active = true;
    setRecords([]);
    setError("");
    if (!patientId && !caseId && !exposureId) return;
    setLoading(true);
    const load = exposureId
      ? onehealth.get(exposureId).then((r) => [r])
      : onehealth
          .list({
            ...(patientId ? { patient_id: patientId } : {}),
            ...(caseId ? { case_id: caseId } : {}),
          })
          .then((r) => r.records);
    load
      .then((r) => {
        if (active) setRecords(r.filter((row) => !row.consent_withdrawn));
      })
      .catch((e) => {
        if (active)
          setError(
            e instanceof Error ? e.message : "Exposure context unavailable",
          );
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [patientId, caseId, exposureId]);
  return (
    <section
      className="rounded-xl border border-accent-cyan/30 bg-accent-cyan/5 p-4 my-4"
      aria-label="One Health exposure context"
    >
      <div className="flex flex-wrap justify-between gap-2">
        <h2 className="text-sm font-semibold text-ink-primary">
          One Health · Environmental evidence
        </h2>
        <Link className="text-xs text-accent-cyan underline" to="/onehealth">
          Track 7 workbench →
        </Link>
      </div>
      <p className="text-xs text-ink-muted mt-2">
        Exposure context is separate from diagnosis, treatment authorization and
        clinical model scores.
      </p>
      {independentCardio && (
        <p className="text-xs text-accent-amber mt-2">
          The CAD inputs below are an independent scenario. No patient matching
          or exposure-based score adjustment has been performed.
        </p>
      )}
      {loading && (
        <p role="status" className="text-xs mt-2">
          Loading exposure evidence…
        </p>
      )}
      {error && (
        <p role="status" className="text-xs text-ink-muted mt-2">
          Exposure evidence requires reviewer access or is unavailable. {error}
        </p>
      )}
      {!loading && !error && !records.length && (
        <p className="text-xs text-ink-muted mt-2">
          No consented exposure evidence loaded. No environmental inference is
          made.
        </p>
      )}
      {records.map((r) => (
        <Link
          key={r.id}
          className="block text-xs mt-3 rounded-lg border border-surface-border p-3 hover:border-accent-cyan"
          to={`/onehealth?record=${encodeURIComponent(r.id)}`}
        >
          <strong>
            {r.synthetic ? "SYNTHETIC · " : ""}
            {r.waterbody_name}
          </strong>{" "}
          · {r.assessment.state.replaceAll("_", " ")}
          <div className="mt-1 text-ink-muted">
            Sample {r.sample.sample_id} · {r.sample.collected_at.slice(0, 10)} ·{" "}
            {r.sample.qualifier === "lt" ? "< " : ""}
            {r.assessment.concentration_ug_l} µg/L arsenic · review{" "}
            {r.review.replaceAll("_", " ")}
          </div>
        </Link>
      ))}
    </section>
  );
}
