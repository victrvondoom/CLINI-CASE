/**
 * Denial Forecast card — output of the 6th agent (Denial Forecaster).
 *
 * Shows the predicted *payer's* denial probability for this submission,
 * the top-3 likely denial rationales, and (when probability >= 0.35) the
 * recommended appeal angle. Calibrated against KFF-2024 (80.7% baseline
 * for appealed Medicare-Advantage overturns).
 */
import { AlertCircle, ChevronDown, ChevronUp, Target, TrendingUp } from "lucide-react";
import { useState } from "react";

import type { DenialForecast } from "../lib/types";

interface Props {
  forecast: DenialForecast;
}

const ANGLE_DISPLAY: Record<string, string> = {
  biomarker_evidence: "Biomarker evidence",
  guideline_alignment: "NCCN guideline alignment",
  prior_therapy_failure: "Prior therapy failure",
  step_therapy_completed: "Step therapy completed",
  medical_necessity_letter: "Medical-necessity letter",
  documentation_gap_resolved: "Documentation gap resolved",
};

function probTone(p: number): "green" | "amber" | "red" {
  if (p < 0.2) return "green";
  if (p < 0.5) return "amber";
  return "red";
}

const TONE_BG: Record<"green" | "amber" | "red", string> = {
  green: "bg-accent-green/10 text-accent-green border-accent-green/30",
  amber: "bg-accent-amber/10 text-accent-amber border-accent-amber/30",
  red:   "bg-accent-red/10 text-accent-red border-accent-red/30",
};

export function DenialForecastCard({ forecast }: Props) {
  const [expanded, setExpanded] = useState(true);
  const tone = probTone(forecast.denial_probability);
  const pct = Math.round(forecast.denial_probability * 100);

  return (
    <div className="bg-surface-raised border border-surface-border rounded-2xl overflow-hidden">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center justify-between px-5 py-3 border-b border-surface-border hover:bg-surface-raised-hi transition-colors"
      >
        <div className="flex items-center gap-2">
          <Target size={16} className="text-accent-amber" />
          <h3 className="text-sm font-semibold text-ink-primary">Denial Forecaster</h3>
          <span className="text-[10px] text-compact text-ink-muted">
            agent 5 / 7 · KFF-2024 calibrated
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className={`text-mono-tech text-sm px-2 py-0.5 rounded border ${TONE_BG[tone]}`}>
            {pct}% denial risk
          </span>
          {expanded ? <ChevronUp size={14} className="text-ink-muted" /> : <ChevronDown size={14} className="text-ink-muted" />}
        </div>
      </button>

      {expanded && (
        <>
          <div className="px-5 py-3 text-sm text-ink-body leading-relaxed bg-surface-panel/30 border-b border-surface-border">
            {forecast.summary}
          </div>

          {forecast.top_reasons.length > 0 && (
            <div className="px-5 py-3 border-b border-surface-border">
              <div className="text-[10px] text-compact text-ink-muted mb-2">
                Top likely payer reasons
              </div>
              <ol className="space-y-2">
                {forecast.top_reasons.map((r) => (
                  <li key={r.rank} className="flex items-start gap-3 text-sm">
                    <span className="text-[10px] text-mono-tech text-ink-faint w-5 shrink-0 mt-1">
                      #{r.rank}
                    </span>
                    <div className="flex-1">
                      <div className="text-ink-body">{r.text}</div>
                      {r.policy_section_pointer && (
                        <div className="text-[10px] text-mono-tech text-accent-cyan mt-0.5">
                          {r.policy_section_pointer}
                        </div>
                      )}
                    </div>
                    <span className="text-[10px] text-mono-tech text-ink-muted shrink-0 mt-1">
                      {Math.round(r.likelihood * 100)}%
                    </span>
                  </li>
                ))}
              </ol>
            </div>
          )}

          {forecast.appeal_strategy && (
            <div className="px-5 py-3 bg-accent-brand/5 border-b border-surface-border">
              <div className="flex items-center gap-1.5 text-[10px] text-compact text-accent-brand mb-2">
                <TrendingUp size={11} />
                Recommended appeal angle
              </div>
              <div className="text-sm text-ink-primary font-medium">
                {ANGLE_DISPLAY[forecast.appeal_strategy.primary_angle] ?? forecast.appeal_strategy.primary_angle}
              </div>
              <p className="text-[12px] text-ink-muted mt-1 leading-relaxed">
                {forecast.appeal_strategy.rationale}
              </p>
              <div className="text-[11px] text-mono-tech text-accent-green mt-2 flex items-center gap-1">
                <AlertCircle size={11} />
                Expected overturn probability:{" "}
                <span className="font-semibold">
                  {Math.round(forecast.appeal_strategy.expected_overturn_probability * 100)}%
                </span>
                <span className="text-ink-faint ml-1">(KFF baseline 80.7%)</span>
              </div>
            </div>
          )}

          <div className="px-5 py-2 bg-surface-panel/40 text-[10px] text-mono-tech text-ink-muted">
            Forecaster confidence: {Math.round(forecast.confidence * 100)}% · sub-agents: probability_estimator · reason_predictor · appeal_path_recommender
          </div>
        </>
      )}
    </div>
  );
}
