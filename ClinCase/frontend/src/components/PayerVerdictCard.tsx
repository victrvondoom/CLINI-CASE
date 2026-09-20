/**
 * Single payer column in the Multi-payer Arbitration view.
 * Shows verdict + confidence + criteria summary + auth code/reason + cost/latency.
 */
import clsx from "clsx";
import { CheckCircle2, Clock, DollarSign, ShieldCheck, XCircle } from "lucide-react";

import type { PayerVerdict } from "../lib/compareSimulation";

const VERDICT_COLOR: Record<string, { ring: string; bg: string; pillBg: string; text: string; Icon: typeof CheckCircle2 }> = {
  APPROVE: {
    ring:   "border-accent-green/40",
    bg:     "bg-gradient-to-br from-accent-green/10 to-transparent",
    pillBg: "bg-accent-green/15 text-accent-green",
    text:   "text-accent-green",
    Icon:   CheckCircle2,
  },
  DENY: {
    ring:   "border-accent-red/40",
    bg:     "bg-gradient-to-br from-accent-red/10 to-transparent",
    pillBg: "bg-accent-red/15 text-accent-red",
    text:   "text-accent-red",
    Icon:   XCircle,
  },
  REFER: {
    ring:   "border-accent-amber/40",
    bg:     "bg-gradient-to-br from-accent-amber/10 to-transparent",
    pillBg: "bg-accent-amber/15 text-accent-amber",
    text:   "text-accent-amber",
    Icon:   ShieldCheck,
  },
};

const PAYER_TINT: Record<string, string> = {
  aetna:  "bg-gray-500/15    text-gray-700    dark:text-gray-300",
  uhc:    "bg-gray-500/15    text-gray-700    dark:text-gray-300",
  bcbs:   "bg-gray-500/15    text-gray-700    dark:text-gray-300",
  anthem: "bg-gray-500/15  text-gray-700  dark:text-gray-300",
};

interface Props {
  verdict: PayerVerdict;
  isRecommended: boolean;
  /** Animation entry index (0-3). */
  index: number;
}

function formatMs(ms: number): string {
  return ms < 60_000 ? `${(ms / 1000).toFixed(1)}s` : `${Math.floor(ms / 60_000)}m ${Math.round((ms % 60_000) / 1000)}s`;
}

export function PayerVerdictCard({ verdict, isRecommended, index }: Props) {
  const v = VERDICT_COLOR[verdict.verdict];
  const Icon = v.Icon;
  const dataModeColor =
    verdict.data_mode === "LIVE"
      ? "bg-accent-green text-ink-invert"
      : verdict.data_mode === "MOCK"
        ? "bg-surface-border text-ink-muted"
        : "bg-accent-cyan/15 text-accent-cyan";

  return (
    <div
      className={clsx(
        "border-2 rounded-2xl p-5 flex flex-col gap-3 animate-slide-in-up relative",
        v.ring,
        v.bg,
        isRecommended && "ring-2 ring-accent-brand ring-offset-2 ring-offset-surface-bg",
      )}
      style={{ animationDelay: `${index * 60}ms` }}
    >
      {isRecommended && (
        <span className="absolute -top-2 left-4 text-[10px] text-compact px-2 py-0.5 rounded bg-accent-brand text-ink-invert">
          Recommended
        </span>
      )}

      {/* Header */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <span
            className={clsx(
              "w-7 h-7 rounded font-bold text-mono-tech text-xs flex items-center justify-center shrink-0",
              PAYER_TINT[verdict.payer_id],
            )}
          >
            {verdict.payer_name.slice(0, 1)}
          </span>
          <div className="min-w-0">
            <div className="font-semibold text-sm text-ink-primary truncate">
              {verdict.payer_name}
            </div>
            <div className="text-[10px] text-mono-tech text-ink-muted">
              {verdict.payer_id}
            </div>
          </div>
        </div>
        <span
          className={clsx(
            "text-[9px] text-compact px-1.5 py-0.5 rounded",
            dataModeColor,
          )}
        >
          {verdict.data_mode}
        </span>
      </div>

      {/* Verdict */}
      <div className="flex items-center gap-2">
        <Icon size={20} className={v.text} strokeWidth={2.5} />
        <div>
          <div className={clsx("text-sm font-bold uppercase tracking-wider", v.text)}>
            {verdict.verdict}
          </div>
          <div className="text-[10px] text-mono-tech text-ink-muted">
            {Math.round(verdict.confidence * 100)}% confidence
          </div>
        </div>
      </div>

      {/* Confidence bar */}
      <div className="h-1 rounded-full bg-surface-border overflow-hidden">
        <div
          className={clsx(
            "h-full rounded-full transition-all duration-500",
            verdict.verdict === "APPROVE" && "bg-accent-green",
            verdict.verdict === "REFER"   && "bg-accent-amber",
            verdict.verdict === "DENY"    && "bg-accent-red",
          )}
          style={{ width: `${Math.round(verdict.confidence * 100)}%` }}
        />
      </div>

      {/* Reasoning summary */}
      <p className="text-xs text-ink-body leading-relaxed line-clamp-3">
        {verdict.reasoning_summary}
      </p>

      {/* Criteria met / missing */}
      {verdict.criteria_met.length > 0 && (
        <div>
          <div className="text-[9px] text-compact text-accent-green mb-1">
            ✓ Met ({verdict.criteria_met.length})
          </div>
          <ul className="text-xs text-ink-body space-y-0.5">
            {verdict.criteria_met.slice(0, 2).map((c, i) => (
              <li key={i} className="truncate">{c}</li>
            ))}
            {verdict.criteria_met.length > 2 && (
              <li className="text-ink-muted text-[10px]">
                +{verdict.criteria_met.length - 2} more
              </li>
            )}
          </ul>
        </div>
      )}
      {verdict.criteria_missing.length > 0 && (
        <div>
          <div className="text-[9px] text-compact text-accent-amber mb-1">
            ⚠ Issue ({verdict.criteria_missing.length})
          </div>
          <ul className="text-xs text-ink-body space-y-0.5">
            {verdict.criteria_missing.map((c, i) => (
              <li key={i}>{c}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Auth code / reason */}
      <div className={clsx("rounded-md px-2 py-1.5 text-[11px] text-mono-tech", v.pillBg)}>
        {verdict.auth_code_or_reason}
      </div>

      {/* Footer: latency + cost */}
      <div className="flex items-center justify-between text-[10px] text-mono-tech text-ink-muted border-t border-surface-border pt-2 mt-auto">
        <span className="flex items-center gap-1">
          <Clock size={10} />
          {formatMs(verdict.latency_ms)}
        </span>
        <span className="flex items-center gap-1">
          <DollarSign size={10} />
          {verdict.cost_usd.toFixed(4)}
        </span>
      </div>

      {/* CTA */}
      <button
        type="button"
        className={clsx(
          "w-full text-xs font-medium px-3 py-1.5 rounded-md transition-colors",
          isRecommended
            ? "bg-accent-brand text-ink-invert hover:opacity-90"
            : "border border-surface-border text-ink-body hover:bg-surface-raised-hi",
        )}
      >
        {verdict.verdict === "APPROVE" ? `Submit to ${verdict.payer_name} →` : "Details"}
      </button>
    </div>
  );
}
