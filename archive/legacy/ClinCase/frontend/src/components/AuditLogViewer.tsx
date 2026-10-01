import { ChevronDown, ChevronUp, FileText } from "lucide-react";
import { useEffect, useState } from "react";

import { api } from "../lib/api";
import type { AgentRun } from "../lib/types";

interface Props {
  caseId: string;
  /** Increment to trigger a re-fetch (e.g. after a run completes). */
  refreshKey?: number;
}

const AGENT_DISPLAY: Record<string, string> = {
  clinical_extractor: "Clinical Extractor",
  policy_retriever: "Policy Retriever",
  necessity_reasoner: "Necessity Reasoner",
  decision_composer: "Decision Composer",
  appeals_drafter: "Appeals Drafter",
};

export function AuditLogViewer({ caseId, refreshKey = 0 }: Props) {
  const [runs, setRuns] = useState<AgentRun[] | null>(null);
  const [open, setOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    api
      .getAudit(caseId)
      .then((d) => setRuns(d.agent_runs))
      .catch((e) => setError(String(e)));
  }, [caseId, open, refreshKey]);

  const totalIn = runs?.reduce((s, r) => s + (r.input_tokens ?? 0), 0) ?? 0;
  const totalOut = runs?.reduce((s, r) => s + (r.output_tokens ?? 0), 0) ?? 0;
  // Sonnet 4.6 pricing: $3 / Mtok in, $15 / Mtok out
  const cost = (totalIn * 3) / 1_000_000 + (totalOut * 15) / 1_000_000;
  const totalLatency = runs?.reduce((s, r) => s + (r.latency_ms ?? 0), 0) ?? 0;

  return (
    <div className="bg-white border border-neutral-200 rounded-xl overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="w-full px-5 py-3 flex items-center justify-between hover:bg-neutral-50 transition-colors"
      >
        <div className="flex items-center gap-2">
          <FileText size={16} className="text-brand-600" />
          <span className="font-semibold text-neutral-900">Audit Trail</span>
          <span className="text-xs text-neutral-500 text-mono-tech">
            (every input, every output, every token — reproducible)
          </span>
        </div>
        {open ? (
          <ChevronUp size={16} className="text-neutral-400" />
        ) : (
          <ChevronDown size={16} className="text-neutral-400" />
        )}
      </button>

      {open && (
        <div className="border-t border-neutral-200">
          {error && (
            <div className="m-4 p-3 rounded bg-gray-50 text-gray-700 text-sm">
              {error}
            </div>
          )}

          {!runs && !error && (
            <div className="p-6 text-center text-neutral-400 text-sm">
              Loading audit trail...
            </div>
          )}

          {runs && runs.length === 0 && (
            <div className="p-6 text-center text-neutral-400 text-sm">
              No agent runs yet for this case. Click "Run ClinCase" first.
            </div>
          )}

          {runs && runs.length > 0 && (
            <>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-neutral-50 text-xs text-neutral-500 uppercase tracking-wider">
                    <tr>
                      <th className="text-left px-4 py-2 text-mono-tech">#</th>
                      <th className="text-left px-4 py-2">Agent</th>
                      <th className="text-right px-4 py-2">Latency</th>
                      <th className="text-right px-4 py-2">Tokens (in / out)</th>
                      <th className="text-left px-4 py-2">Model</th>
                      <th className="text-left px-4 py-2">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-neutral-100">
                    {runs.map((r) => {
                      const ok = !r.error_text;
                      return (
                        <tr key={r.id} className="hover:bg-neutral-50">
                          <td className="px-4 py-2 text-mono-tech text-xs text-neutral-500">
                            {r.id}
                          </td>
                          <td className="px-4 py-2 font-medium text-neutral-900">
                            {AGENT_DISPLAY[r.agent_name] ?? r.agent_name}
                          </td>
                          <td className="px-4 py-2 text-right text-mono-tech">
                            {r.latency_ms != null
                              ? r.latency_ms < 1000
                                ? `${r.latency_ms}ms`
                                : `${(r.latency_ms / 1000).toFixed(1)}s`
                              : "—"}
                          </td>
                          <td className="px-4 py-2 text-right text-mono-tech text-xs">
                            {(r.input_tokens ?? 0).toLocaleString()} /{" "}
                            {(r.output_tokens ?? 0).toLocaleString()}
                          </td>
                          <td className="px-4 py-2 text-mono-tech text-xs text-neutral-500">
                            {r.model_id?.split("/").pop() ?? "—"}
                          </td>
                          <td className="px-4 py-2">
                            {ok ? (
                              <span className="text-xs px-2 py-0.5 rounded bg-gray-100 text-gray-700">
                                OK
                              </span>
                            ) : (
                              <span
                                className="text-xs px-2 py-0.5 rounded bg-gray-100 text-gray-700"
                                title={r.error_text ?? ""}
                              >
                                ERROR
                              </span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              <div className="px-5 py-3 bg-neutral-50 border-t border-neutral-200 flex items-center justify-between text-xs text-neutral-600">
                <div className="flex items-center gap-4">
                  <span>
                    Total wall-clock:{" "}
                    <span className="text-mono-tech font-semibold text-neutral-900">
                      {(totalLatency / 1000).toFixed(1)}s
                    </span>
                  </span>
                  <span>
                    Total tokens:{" "}
                    <span className="text-mono-tech font-semibold text-neutral-900">
                      {totalIn.toLocaleString()} in / {totalOut.toLocaleString()} out
                    </span>
                  </span>
                </div>
                <span>
                  Estimated cost (Sonnet 4.6):{" "}
                  <span className="text-mono-tech font-bold text-gray-700">
                    ${cost.toFixed(4)}
                  </span>
                </span>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
