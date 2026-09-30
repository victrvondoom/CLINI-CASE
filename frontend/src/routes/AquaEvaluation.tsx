/** Track 3 safety evaluation, calculated live by the production assessment rules. */
import { AlertTriangle, CheckCircle2, FlaskConical, ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";

import { aqua } from "../aquahealth/api";
import { ErrorNote, LoadingNote, PageHeader, StatusBadge } from "../aquahealth/panels";
import type { Track3Evaluation } from "../aquahealth/types";

const pct = (value: number) => `${Math.round(value * 100)}%`;

export default function AquaEvaluation() {
  const [report, setReport] = useState<Track3Evaluation | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    aqua
      .evaluation()
      .then(setReport)
      .catch((e) =>
        setError(e instanceof Error ? e.message : "Failed to run the Track 3 benchmark"),
      );
  }, []);

  return (
    <div className="p-6 lg:p-8 max-w-[1400px]">
      <PageHeader
        eyebrow="AQUAHEALTH · TRACK 3"
        title="Responsible assessment evaluation"
        description="A transparent, reproducible boundary-case benchmark for abstention, concern detection and input validation. Results are calculated from the production assessment functions—not typed into this page."
      />

      {error && <ErrorNote message={error} />}
      {!report && !error && <LoadingNote label="Running safety benchmark…" />}

      {report && (
        <div className="space-y-5">
          <section className="rounded-2xl border border-accent-cyan/30 bg-accent-cyan/5 p-5">
            <div className="flex items-start gap-3">
              <ShieldCheck className="text-accent-cyan shrink-0" size={20} aria-hidden />
              <div>
                <h2 className="text-sm text-ink-primary">What this benchmark establishes</h2>
                <p className="mt-1.5 text-[12px] text-ink-muted max-w-4xl">
                  It verifies that declared software safety behaviours remain true: missing data
                  causes abstention, concerning patterns reach review, and contradictory values are
                  surfaced. It does not establish ecological, diagnostic or public-health validity.
                </p>
              </div>
            </div>
          </section>

          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
            <Metric label="Status expectations" value={pct(report.metrics.exact_status_accuracy)} />
            <Metric label="Concern detection" value={pct(report.metrics.concern_detection_recall)} />
            <Metric
              label="Insufficient-data abstention"
              value={pct(report.metrics.insufficient_data_abstention_rate)}
            />
            <Metric label="Validation checks" value={pct(report.metrics.validation_check_accuracy)} />
            <Metric
              label="False healthy on sparse data"
              value={String(report.metrics.false_healthy_on_insufficient_count)}
              good={report.metrics.false_healthy_on_insufficient_count === 0}
            />
          </div>

          <section className="rounded-2xl border border-surface-border bg-surface-raised overflow-hidden">
            <div className="p-5 border-b border-surface-border">
              <div className="flex items-center gap-2">
                <FlaskConical size={15} className="text-accent-cyan" aria-hidden />
                <h2 className="text-sm text-ink-primary">
                  {report.case_count} synthetic boundary cases
                </h2>
              </div>
              <p className="text-[11px] text-ink-muted mt-1">
                Benchmark {report.benchmark} v{report.version} · {report.generated_from}
              </p>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-[12px]">
                <thead className="bg-surface-panel text-ink-muted">
                  <tr>
                    <th className="text-left font-medium px-4 py-2.5">Case</th>
                    <th className="text-left font-medium px-3 py-2.5">Expected</th>
                    <th className="text-left font-medium px-3 py-2.5">Produced</th>
                    <th className="text-left font-medium px-3 py-2.5">Validation</th>
                    <th className="text-left font-medium px-3 py-2.5">Result</th>
                  </tr>
                </thead>
                <tbody>
                  {report.cases.map((row) => (
                    <tr key={row.case_id} className="border-t border-surface-border/70">
                      <td className="px-4 py-3 min-w-64">
                        <div className="text-ink-primary">{row.title}</div>
                        <div className="text-[10px] text-ink-faint mt-0.5">
                          {row.category.replace(/-/g, " ")} · {row.case_id}
                        </div>
                      </td>
                      <td className="px-3 py-3">
                        <StatusBadge status={row.expected_status} size="sm" />
                      </td>
                      <td className="px-3 py-3">
                        <StatusBadge status={row.predicted_status} size="sm" />
                      </td>
                      <td className="px-3 py-3 text-ink-muted min-w-44">
                        {row.validation_issue_detected
                          ? "Issue surfaced for review"
                          : "No issue expected"}
                      </td>
                      <td className="px-3 py-3">
                        {row.passed ? (
                          <span className="inline-flex items-center gap-1 text-accent-green">
                            <CheckCircle2 size={13} aria-hidden /> Pass
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-accent-red">
                            <AlertTriangle size={13} aria-hidden /> Review
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="rounded-2xl border border-accent-amber/30 bg-accent-amber/5 p-5">
            <h2 className="text-sm text-ink-primary">Limitations</h2>
            <ul className="mt-2 space-y-1.5 text-[11px] text-ink-muted">
              {report.limitations.map((item) => (
                <li key={item}>• {item}</li>
              ))}
            </ul>
          </section>
        </div>
      )}
    </div>
  );
}

function Metric({
  label,
  value,
  good = true,
}: {
  label: string;
  value: string;
  good?: boolean;
}) {
  return (
    <div className="rounded-2xl border border-surface-border bg-surface-raised p-4">
      <div className="text-[10px] text-ink-muted min-h-8">{label}</div>
      <div
        className={
          good ? "text-2xl text-accent-green mt-1" : "text-2xl text-accent-red mt-1"
        }
      >
        {value}
      </div>
    </div>
  );
}
