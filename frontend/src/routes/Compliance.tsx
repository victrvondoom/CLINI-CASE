/**
 * /compliance — Org-level live CMS-0057-F + state-AI-law compliance scorecard.
 *
 * Replaces the previous hardcoded mockup. Every number on this page comes
 * from a LIVE backend call to /api/v1/compliance/org. The clauses block
 * iterates the same 8-clause registry the per-case scorecard uses, with
 * deadline countdowns computed against today's date.
 *
 * What a compliance officer / CFO can do here:
 *   • Read TAT compliance %, SB-1120 (HITL signoff) %, audit completeness %
 *   • See which clauses are in force today vs upcoming with day countdowns
 *   • Print the page to PDF as a quarterly compliance report
 */
import {
  CheckCircle2,
  Download,
  FileSpreadsheet,
  Mail,
  Printer,
  ScrollText,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { useEffect, useState } from "react";

import { api, type OrgComplianceScorecard } from "../lib/api";

export default function Compliance() {
  const [data, setData] = useState<OrgComplianceScorecard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .getOrgCompliance()
      .then((r) => {
        if (!cancelled) {
          setData(r);
          setError(null);
        }
      })
      .catch((e) => {
        if (!cancelled) setError(String(e));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="px-6 py-6">
      <div className="bg-surface-raised border border-surface-border rounded-2xl overflow-hidden">
        {/* Header */}
        <div className="border-b border-surface-border bg-accent-brand-soft/40 px-8 py-6 flex items-center justify-between">
          <div>
            <div className="text-[10px] text-compact text-accent-brand mb-1">
              ClinCase · Compliance Report (LIVE)
            </div>
            <h1 className="text-2xl font-semibold text-ink-primary leading-tight">
              CMS-0057-F + State AI Law Scorecard
            </h1>
            <p className="text-sm text-ink-muted mt-1">
              Org{" "}
              <span className="font-medium text-ink-body">
                {data?.organization_id ?? "…"}
              </span>{" "}
              · {data ? new Date(data.asof_iso).toLocaleString() : "…"}
            </p>
          </div>
          <div className="flex items-center gap-2 print:hidden">
            <button
              type="button"
              onClick={() => window.print()}
              className="text-xs font-medium px-3 py-1.5 rounded-md border border-surface-border text-ink-body hover:bg-surface-raised-hi transition-colors flex items-center gap-1.5"
            >
              <Printer size={11} />
              Print
            </button>
            <button
              type="button"
              onClick={() => {
                const subject = encodeURIComponent("ClinCase Compliance Report");
                const body = encodeURIComponent(
                  "Live compliance scorecard at:\n" +
                    window.location.origin +
                    "/compliance\n\nPrint > Save as PDF for the full document.",
                );
                window.location.href = `mailto:cfo@aerofyta.health?subject=${subject}&body=${body}`;
              }}
              className="text-xs font-medium px-3 py-1.5 rounded-md border border-surface-border text-ink-body hover:bg-surface-raised-hi transition-colors flex items-center gap-1.5"
            >
              <Mail size={11} />
              Email CFO
            </button>
            <button
              type="button"
              onClick={() => window.print()}
              className="text-xs font-medium px-3 py-1.5 rounded-md bg-accent-brand text-ink-invert hover:opacity-90 transition-opacity flex items-center gap-1.5"
              title="Opens print dialog · choose 'Save as PDF'"
            >
              <Download size={11} />
              Download PDF
            </button>
          </div>
        </div>

        <div className="px-8 py-6 space-y-8">
          {loading && (
            <div className="text-sm text-ink-muted">Computing live scorecard…</div>
          )}
          {error && (
            <div className="text-sm text-accent-red bg-accent-red/10 border border-accent-red/30 rounded p-3">
              Could not load compliance scorecard: {error}
            </div>
          )}

          {data && (
            <>
              {/* Headline metrics */}
              <section>
                <h2 className="text-sm font-semibold text-ink-primary mb-3 flex items-center gap-2">
                  <Sparkles size={14} className="text-accent-brand" />
                  Headline metrics (live from RDS)
                </h2>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  <Metric
                    label="TAT compliance"
                    value={`${data.headline_metrics.tat_compliance_pct.toFixed(1)}%`}
                    benchmark={`max ${data.headline_metrics.max_tat_seconds.toFixed(1)}s vs 7-day SLA`}
                    accent={data.headline_metrics.tat_compliance_pct >= 95 ? "green" : "amber"}
                  />
                  <Metric
                    label="SB-1120 HITL signoff"
                    value={`${data.headline_metrics.sb1120_compliance_pct.toFixed(1)}%`}
                    benchmark={`${data.totals.denies_with_review} of ${data.totals.denies} denies reviewed`}
                    accent={data.headline_metrics.sb1120_compliance_pct >= 99 ? "green" : "amber"}
                  />
                  <Metric
                    label="Audit completeness"
                    value={`${data.headline_metrics.audit_completeness_pct.toFixed(1)}%`}
                    benchmark={`${data.totals.audit_complete_cases} of ${data.totals.cases_total} cases retained`}
                    accent={data.headline_metrics.audit_completeness_pct >= 95 ? "green" : "amber"}
                  />
                </div>
              </section>

              {/* Clauses */}
              <section>
                <h2 className="text-sm font-semibold text-ink-primary mb-1 flex items-center gap-2">
                  <ScrollText size={14} className="text-accent-amber" />
                  CMS-0057-F + state-AI-law clause readiness
                </h2>
                <div className="text-[11px] text-ink-muted mb-3 text-mono-tech">
                  CMS Interoperability and Prior Authorization Final Rule · 89 FR 8758 · Feb 8 2024
                </div>
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-2">
                  {data.clauses.map((c) => (
                    <div
                      key={c.clause_id}
                      className="border border-surface-border rounded-lg p-3 bg-surface-panel/40"
                    >
                      <div className="flex items-start justify-between gap-2 mb-1">
                        <div className="flex items-baseline gap-2 min-w-0">
                          <span className="text-[11px] text-mono-tech text-accent-amber whitespace-nowrap">
                            {c.clause_id}
                          </span>
                          <span className="text-sm text-ink-primary font-medium truncate">
                            {c.title}
                          </span>
                        </div>
                        <span
                          className={`text-[10px] text-mono-tech px-1.5 py-0.5 rounded shrink-0 ${
                            c.in_force_today
                              ? "bg-accent-green/15 text-accent-green"
                              : "bg-accent-amber/15 text-accent-amber"
                          }`}
                        >
                          {c.in_force_today ? "IN FORCE" : `T-${c.days_until_effective}d`}
                        </span>
                      </div>
                      <p className="text-[11px] text-ink-muted leading-snug">
                        {c.summary}
                      </p>
                    </div>
                  ))}
                </div>
              </section>

              {/* Volumes */}
              <section className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <Tile
                  label="Cases processed"
                  value={data.totals.cases_total.toLocaleString()}
                  hint={`${data.totals.cases_decided.toLocaleString()} decided`}
                />
                <Tile
                  label="Mean decision TAT"
                  value={`${(data.headline_metrics.mean_tat_seconds || 0).toFixed(1)}s`}
                  hint={`max ${data.headline_metrics.max_tat_seconds.toFixed(1)}s`}
                />
                <Tile
                  label="HITL-reviewed denies"
                  value={`${data.totals.denies_with_review} / ${data.totals.denies}`}
                  hint="CA SB 1120 § final-denial signoff"
                />
              </section>

              {/* Deadlines */}
              <section>
                <h2 className="text-sm font-semibold text-ink-primary mb-3 flex items-center gap-2">
                  <ShieldCheck size={14} className="text-accent-green" />
                  Regulatory deadlines
                </h2>
                <div className="bg-surface-panel/40 border border-surface-border rounded-xl overflow-hidden">
                  <table className="w-full text-sm">
                    <tbody className="divide-y divide-surface-border">
                      {Object.entries(data.deadlines).map(([k, v]) => (
                        <tr key={k}>
                          <td className="px-4 py-2.5 text-ink-body">
                            {k.replaceAll("_", " ")}
                          </td>
                          <td className="px-4 py-2.5 text-mono-tech text-ink-primary nums-tabular w-32">
                            {v.iso}
                          </td>
                          <td className="px-4 py-2.5 text-[11px] text-ink-muted w-32">
                            {v.passed
                              ? "passed"
                              : v.days_until > 0
                              ? `T-${v.days_until} days`
                              : "today"}
                          </td>
                          <td className="px-4 py-2.5 w-12">
                            {v.passed ? (
                              <CheckCircle2 size={14} className="text-accent-green" />
                            ) : null}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>

              {/* Audit readiness */}
              <section>
                <h2 className="text-sm font-semibold text-ink-primary mb-3 flex items-center gap-2">
                  <FileSpreadsheet size={14} className="text-accent-brand" />
                  Audit readiness
                </h2>
                <div className="bg-surface-panel/40 border border-surface-border rounded-xl p-4 text-sm text-ink-body leading-relaxed">
                  Every prior-authorization decision in this org is fully reproducible.
                  For each case, the{" "}
                  <code className="text-xs text-mono-tech px-1 py-0.5 rounded bg-surface-raised">
                    agent_runs
                  </code>{" "}
                  table contains complete inputs, outputs, model identifiers, token counts,
                  and citations.{" "}
                  <strong className="text-ink-primary">
                    Per-case Evidence Pack
                  </strong>{" "}
                  available at <code className="text-mono-tech text-xs">/api/v1/cases/&#123;case_id&#125;/evidence-pack</code> —
                  single JSON bundle with bundle-level SHA-256 tamper-evident hash.
                </div>
              </section>

              {/* Sign-off */}
              <section className="pt-4 border-t border-surface-border text-[11px] text-ink-faint text-mono-tech">
                Generated {new Date(data.asof_iso).toISOString()} · clincase-v0.1.0 ·{" "}
                {data.totals.cases_total.toLocaleString()} cases under audit ·
                {" "}cryptographic audit log SHA-256 enabled.
              </section>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

const ACCENT_TINT: Record<"green" | "amber", { bg: string; text: string }> = {
  green: { bg: "bg-accent-green/5 border-accent-green/30", text: "text-accent-green" },
  amber: { bg: "bg-accent-amber/5 border-accent-amber/30", text: "text-accent-amber" },
};

function Metric({
  label,
  value,
  benchmark,
  accent,
}: {
  label: string;
  value: string;
  benchmark: string;
  accent: "green" | "amber";
}) {
  return (
    <div className={`border-2 rounded-xl p-4 ${ACCENT_TINT[accent].bg}`}>
      <div className={`text-3xl font-bold nums-tabular ${ACCENT_TINT[accent].text} leading-none`}>
        {value}
      </div>
      <div className="text-[11px] text-compact text-ink-muted mt-2">
        {label}
      </div>
      <div className="text-[11px] text-ink-faint mt-0.5">{benchmark}</div>
    </div>
  );
}

function Tile({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <div className="bg-surface-panel/40 border border-surface-border rounded-xl p-4">
      <div className="text-[10px] text-compact text-ink-muted mb-1">
        {label}
      </div>
      <div className="text-2xl font-bold text-ink-primary nums-tabular">{value}</div>
      <div className="text-[11px] text-ink-faint">{hint}</div>
    </div>
  );
}
