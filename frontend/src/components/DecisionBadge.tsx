import clsx from "clsx";
import { AlertCircle, CheckCircle2, XCircle } from "lucide-react";

import type { Decision, Verdict } from "../lib/types";

interface DecisionBadgeProps {
  decision: Decision;
  appealInProgress?: boolean;
}

const verdictConfig: Record<
  Verdict,
  {
    bg: string;
    border: string;
    text: string;
    icon: typeof CheckCircle2;
    label: string;
    headline: string;
  }
> = {
  APPROVE: {
    bg: "bg-gray-50",
    border: "border-gray-300",
    text: "text-gray-900",
    icon: CheckCircle2,
    label: "APPROVE",
    headline: "ClinCase recommends APPROVE",
  },
  DENY: {
    bg: "bg-gray-50",
    border: "border-gray-300",
    text: "text-gray-900",
    icon: XCircle,
    label: "DENY",
    headline: "ClinCase recommends DENY",
  },
  REFER: {
    bg: "bg-gray-50",
    border: "border-gray-300",
    text: "text-gray-900",
    icon: AlertCircle,
    label: "REFER TO REVIEWER",
    headline: "ClinCase flags for human review",
  },
};

export function DecisionBadge({ decision, appealInProgress }: DecisionBadgeProps) {
  const c = verdictConfig[decision.verdict];
  const Icon = c.icon;

  return (
    <div
      className={clsx(
        "border-2 rounded-2xl p-5",
        c.bg,
        c.border,
        c.text,
      )}
    >
      <div className="flex items-start gap-4">
        <Icon size={36} strokeWidth={2} className="flex-shrink-0 mt-1" />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            <span className="text-xs uppercase tracking-widest font-bold opacity-80">
              {c.label}
            </span>
            <span className="text-xs text-mono-tech opacity-70">
              confidence {(decision.confidence * 100).toFixed(0)}%
            </span>
            {appealInProgress && decision.verdict === "DENY" && (
              <span className="text-xs text-mono-tech px-2 py-0.5 rounded bg-white/60">
                Appeal drafting...
              </span>
            )}
          </div>
          <div className="text-xl font-bold mb-2">{c.headline}</div>
          <p className="text-sm leading-relaxed opacity-90">{decision.rationale}</p>

          {decision.risk_flags.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-2">
              {decision.risk_flags.map((flag) => (
                <span
                  key={flag}
                  className="text-[11px] text-compact px-2 py-1 rounded bg-white/70"
                >
                  ⚠ {flag}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
