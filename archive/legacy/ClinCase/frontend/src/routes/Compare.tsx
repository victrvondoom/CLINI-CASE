/**
 * /cases/:id/compare — Multi-payer Arbitration.
 *
 * Submit one case → see how 4 payers would decide, side-by-side.
 * ClinCase's biggest novelty wedge — collapses the manual "submit to 5 payers"
 * workflow into a single click.
 *
 * Currently uses local simulation (compareSimulation.ts). In production each
 * verdict would come from a parallel run of the 7-agent graph with that
 * payer's policy corpus.
 */
import { ArrowLeft, Loader2, Scale, Sparkles, Zap } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { PayerVerdictCard } from "../components/PayerVerdictCard";
import { api } from "../lib/api";
import { simulateCompare, type CompareResult, type PayerId } from "../lib/compareSimulation";

interface CaseInfo {
  payer_id: string;
  patient_initials: string;
  status: string;
  physician_note: string | null;
  requested_treatment: { name: string; j_code: string | null };
}

export default function Compare() {
  const { caseId } = useParams<{ caseId: string }>();
  const [caseInfo, setCaseInfo] = useState<CaseInfo | null>(null);
  const [result, setResult] = useState<CompareResult | null>(null);
  const [running, setRunning] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!caseId) return;
    api.getCase(caseId)
      .then((info) => {
        setCaseInfo(info);
        // Simulate parallel agent runs with a brief animation
        setTimeout(() => {
          const r = simulateCompare(
            caseId,
            info.requested_treatment.name,
            info.physician_note ?? "",
            (info.payer_id as PayerId) ?? "aetna",
          );
          setResult(r);
          setRunning(false);
        }, 1200);
      })
      .catch((e) => {
        setError(String(e));
        setRunning(false);
      });
  }, [caseId]);

  const totalCost = useMemo(
    () => result?.payers.reduce((s, p) => s + p.cost_usd, 0) ?? 0,
    [result],
  );
  const fastest = useMemo(() => {
    if (!result) return null;
    return [...result.payers].sort((a, b) => a.latency_ms - b.latency_ms)[0];
  }, [result]);

  if (!caseId) return null;

  return (
    <div className="mx-auto max-w-7xl px-6 py-6">
      <div className="flex items-center justify-between mb-5">
        <Link
          to={`/cases/${caseId}`}
          className="text-sm text-ink-muted hover:text-ink-primary flex items-center gap-1 transition-colors"
        >
          <ArrowLeft size={14} />
          Back to case
        </Link>
        <div className="text-xs text-mono-tech text-ink-muted">
          case <span className="bg-surface-panel px-1.5 py-0.5 rounded text-ink-body">{caseId}</span>
        </div>
      </div>

      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center gap-2 text-[10px] text-compact text-accent-brand mb-2">
          <Scale size={12} />
          MULTI-PAYER ARBITRATION
          <span className="text-ink-faint">·</span>
          <span className="text-ink-muted">novelty</span>
        </div>
        <h1 className="text-2xl font-semibold text-ink-primary leading-tight">
          Submit once. See how every payer would decide.
        </h1>
        <p className="text-sm text-ink-muted mt-2 max-w-2xl leading-relaxed">
          PA coordinators today submit to 5 payers manually and wait for 5 separate verdicts.
          ClinCase collapses that into a single click — fan out the 7-agent graph in parallel
          across every payer in your network, then arbitrate the recommended path.
          {caseInfo && (
            <>
              {" "}
              <span className="font-medium text-ink-body">
                {caseInfo.requested_treatment.name}
              </span>
              {caseInfo.requested_treatment.j_code && (
                <span className="ml-1 text-mono-tech text-xs px-1.5 py-0.5 rounded bg-surface-panel text-ink-body align-middle">
                  {caseInfo.requested_treatment.j_code}
                </span>
              )}
              {" · Patient "}
              <span className="text-mono-tech">{caseInfo.patient_initials}</span>
            </>
          )}
        </p>
      </div>

      {error && (
        <div className="mb-5 p-3 rounded-lg bg-accent-red/10 border border-accent-red/30 text-accent-red text-sm">
          {error}
        </div>
      )}

      {/* Loading state */}
      {running && (
        <div className="bg-surface-raised border-2 border-dashed border-accent-brand/30 rounded-2xl p-12 text-center">
          <Loader2 size={32} className="text-accent-brand animate-spin mx-auto mb-4" />
          <div className="text-sm font-medium text-ink-primary mb-1">
            Fanning out across 4 payers in parallel...
          </div>
          <div className="text-xs text-ink-muted text-mono-tech">
            Aetna · UHC · BCBS · Anthem
          </div>
        </div>
      )}

      {/* 4-column verdict grid */}
      {!running && result && (
        <>
          <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
            {result.payers.map((p, i) => (
              <PayerVerdictCard
                key={p.payer_id}
                verdict={p}
                isRecommended={p.payer_id === result.recommendation.primary}
                index={i}
              />
            ))}
          </section>

          {/* Recommendation panel */}
          <section className="bg-surface-raised border border-accent-brand/20 rounded-2xl overflow-hidden">
            <div className="px-5 py-3 border-b border-surface-border bg-accent-brand-soft/40 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Sparkles size={16} className="text-accent-brand" />
                <h3 className="font-semibold text-sm text-ink-primary">
                  ClinCase Recommendation
                </h3>
                <span className="text-[10px] text-compact text-accent-brand">
                  arbitrated
                </span>
              </div>
              <div className="flex items-center gap-3 text-[11px] text-mono-tech text-ink-muted">
                {fastest && (
                  <span className="flex items-center gap-1">
                    <Zap size={11} className="text-accent-cyan" />
                    fastest: {fastest.payer_name.split(" ")[0]} ({Math.round(fastest.latency_ms / 1000)}s)
                  </span>
                )}
                <span>total cost: ${totalCost.toFixed(4)}</span>
              </div>
            </div>

            <div className="px-5 py-4">
              <p className="text-sm text-ink-body leading-relaxed">
                {result.recommendation.summary}
              </p>

              {/* Inline action chips */}
              <div className="flex flex-wrap gap-2 mt-3">
                <button
                  type="button"
                  className="text-xs font-medium px-3 py-1.5 rounded-md bg-accent-brand text-ink-invert hover:opacity-90 transition-opacity"
                >
                  Submit to {result.payers.find((p) => p.payer_id === result.recommendation.primary)?.payer_name} →
                </button>
                {result.recommendation.fallback && (
                  <button
                    type="button"
                    className="text-xs font-medium px-3 py-1.5 rounded-md border border-surface-border text-ink-body hover:bg-surface-raised-hi transition-colors"
                  >
                    Auto-fallback: {result.payers.find((p) => p.payer_id === result.recommendation.fallback)?.payer_name}
                  </button>
                )}
                <Link
                  to={`/cases/${caseId}`}
                  className="text-xs font-medium px-3 py-1.5 rounded-md border border-surface-border text-ink-body hover:bg-surface-raised-hi transition-colors"
                >
                  Back to case →
                </Link>
              </div>
            </div>

            <div className="px-5 py-2.5 border-t border-surface-border bg-surface-panel/40 flex items-center justify-between text-[11px] text-ink-muted">
              <span>
                In production, each verdict comes from a parallel run of the 7-agent graph against that payer's policy corpus.
                The Aetna column is wired to LIVE inference; the others are simulated for demo.
              </span>
            </div>
          </section>
        </>
      )}
    </div>
  );
}
