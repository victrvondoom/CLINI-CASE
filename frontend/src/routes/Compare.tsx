/**
 * /cases/:id/compare — Multi-payer comparison from RECORDED data.
 *
 * Each column shows the payer's real policy for this treatment, the real recorded decision for this case (or for a
 * sibling case with the same clinical bundle submitted to that payer), and the next real action. Nothing is
 * simulated: with one evaluated payer there is no recommendation, and the page says how to get one.
 */
import { ArrowLeft, Loader2, Scale, Sparkles } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { PayerComparisonCard } from "../components/PayerComparisonCard";
import { api } from "../lib/api";
import { useLive } from "../lib/useLive";

export default function Compare() {
  const { caseId = "" } = useParams<{ caseId: string }>();
  const navigate = useNavigate();
  const { data, error, loading, reload } = useLive(() => api.getCaseComparison(caseId), [caseId], 20_000);
  const [creating, setCreating] = useState<string | null>(null);
  const [createError, setCreateError] = useState<string | null>(null);

  async function create(payerId: string) {
    setCreating(payerId);
    setCreateError(null);
    try {
      const r = await api.createComparisonCase(caseId, payerId);
      reload();
      if (r.created) navigate(`/cases/${r.case_id}`);
    } catch (e) {
      setCreateError(e instanceof Error ? e.message : String(e));
    } finally {
      setCreating(null);
    }
  }

  return (
    <div className="mx-auto max-w-7xl px-6 py-6" data-testid="compare-page">
      <div className="flex items-center justify-between mb-5">
        <Link to={`/cases/${caseId}`} className="text-sm text-ink-muted hover:text-ink-primary flex items-center gap-1">
          <ArrowLeft size={14} /> Back to case
        </Link>
        <div className="text-xs text-mono-tech text-ink-muted">
          case <span className="bg-surface-panel px-1.5 py-0.5 rounded text-ink-body">{caseId}</span>
        </div>
      </div>

      <div className="mb-6">
        <div className="flex items-center gap-2 text-[10px] text-compact text-accent-brand mb-2">
          <Scale size={12} /> MULTI-PAYER COMPARISON
        </div>
        <h1 className="text-2xl font-semibold text-ink-primary leading-tight">How does each payer's policy and decision compare?</h1>
        {data && (
          <p className="text-sm text-ink-muted mt-2 max-w-2xl leading-relaxed" data-testid="compare-subject">
            <span className="font-medium text-ink-body">{data.treatment}</span>
            {data.j_code && <span className="ml-1 text-mono-tech text-xs px-1.5 py-0.5 rounded bg-surface-panel text-ink-body">{data.j_code}</span>}
            {" · Patient "}
            <span className="text-mono-tech">{data.patient}</span>
          </p>
        )}
      </div>

      {(error || createError) && (
        <div role="alert" data-testid="compare-error" className="mb-5 p-3 rounded-lg bg-accent-red/10 border border-accent-red/30 text-accent-red text-sm">
          {createError ?? error}{" "}
          {error && <button type="button" onClick={reload} className="underline">Retry</button>}
        </div>
      )}
      {!data && loading && (
        <div className="p-12 text-center text-sm text-ink-muted" role="status">
          <Loader2 size={28} className="animate-spin mx-auto mb-3 text-accent-brand" /> Loading comparison…
        </div>
      )}

      {data && (
        <>
          <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
            {data.payers.map((p) => (
              <PayerComparisonCard
                key={p.payer_id}
                col={p}
                recommended={p.payer_id === data.recommendation.primary}
                creating={creating === p.payer_id}
                onCreate={() => void create(p.payer_id)}
              />
            ))}
          </section>

          <section className="bg-surface-raised border border-accent-brand/20 rounded-2xl overflow-hidden">
            <div className="px-5 py-3 border-b border-surface-border flex items-center gap-2">
              <Sparkles size={16} className="text-accent-brand" />
              <h3 className="font-semibold text-sm text-ink-primary">Recommendation</h3>
            </div>
            <p data-testid="recommendation" className="px-5 py-4 text-sm text-ink-body leading-relaxed">{data.recommendation.summary}</p>
            <div className="px-5 py-2.5 border-t border-surface-border bg-surface-panel/40 text-[11px] text-ink-muted">{data.method}</div>
          </section>
        </>
      )}
    </div>
  );
}
