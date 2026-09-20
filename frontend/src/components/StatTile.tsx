/**
 * Dashboard KPI tile. Eyebrow + big value + optional trend / extra widget.
 * Variants:
 *   default: plain text value
 *   sparkline: shows a sparkline beside / under
 *   trend: shows ↑ or ↓ delta vs prior period
 *   gauge: bar gauge for 0-100 percentages
 *
 * Hover treatment: lifts -2px, brand-coloured shadow, accent gradient
 * top-border becomes visible. Designed to communicate "click me / read me"
 * without needing a CTA on every tile.
 */
import clsx from "clsx";
import { TrendingDown, TrendingUp } from "lucide-react";
import type { ReactNode } from "react";

import { Sparkline } from "./Sparkline";

interface Props {
  eyebrow: string;
  value: string;
  hint?: string;
  /** Sparkline values (small array, 5-12 numbers) */
  spark?: number[];
  /** Trend in % vs prior period; positive = up (good or bad depending on context) */
  trend?: { value: number; goodDirection: "up" | "down" };
  /** For gauge variant: numeric percent 0-100 */
  gauge?: number;
  /** Confidence interval label like "band 71%-77% · 95% CI" */
  confidenceLabel?: string;
  /** Color override for value (e.g. "text-accent-cyan") */
  valueClassName?: string;
  /** Extra slot, e.g. cost breakdown */
  extra?: ReactNode;
}

export function StatTile({
  eyebrow,
  value,
  hint,
  spark,
  trend,
  gauge,
  confidenceLabel,
  valueClassName,
  extra,
}: Props) {
  return (
    <div className="card-premium bg-surface-raised border border-surface-border rounded-2xl p-5 flex flex-col gap-2 hover:border-accent-brand/40">
      <div className="text-compact text-[10px] text-ink-muted">
        {eyebrow}
      </div>

      <div className="flex items-end gap-3">
        <div className={clsx("text-data-numeric text-3xl text-ink-primary nums-tabular", valueClassName)}>
          {value}
        </div>
        {trend && (
          <TrendBadge value={trend.value} goodDirection={trend.goodDirection} />
        )}
      </div>

      {spark && (
        <div className="text-accent-brand">
          <Sparkline values={spark} width={140} height={32} />
        </div>
      )}

      {gauge !== undefined && (
        <div className="mt-1 h-1.5 w-full bg-surface-border rounded-full overflow-hidden">
          <div
            className="h-full bg-accent-brand rounded-full transition-all"
            style={{ width: `${Math.max(0, Math.min(100, gauge))}%` }}
          />
        </div>
      )}

      {hint && (
        <div className="text-ui-secondary text-[11px] text-ink-muted">{hint}</div>
      )}

      {confidenceLabel && (
        <div className="text-mono-tech text-[11px] text-ink-muted">{confidenceLabel}</div>
      )}

      {extra && <div className="mt-1">{extra}</div>}
    </div>
  );
}

function TrendBadge({ value, goodDirection }: { value: number; goodDirection: "up" | "down" }) {
  const isUp = value > 0;
  const isGood = goodDirection === "up" ? isUp : !isUp;
  const Icon = isUp ? TrendingUp : TrendingDown;
  return (
    <div
      className={clsx(
        "flex items-center gap-1 text-xs text-mono-tech mb-1",
        isGood ? "text-accent-green" : "text-accent-red",
      )}
    >
      <Icon size={12} strokeWidth={2.5} />
      <span>
        {isUp ? "+" : ""}
        {value}%
      </span>
    </div>
  );
}
