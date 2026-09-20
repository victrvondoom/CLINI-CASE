/**
 * Per-case CMS-0057-F § IV.B SLA badge.
 *
 * Shows days remaining against the 7-day standard turnaround (or 72-hour
 * expedited) prescribed in 89 FR 8758 § IV.B.1 / IV.B.2. Tone shifts from
 * green → amber → red as the deadline approaches.
 *
 * Cases that already have a final verdict (approved/denied/overturned) show
 * a "met" pill instead of a countdown — the SLA was satisfied at decision
 * time and the badge stays as a permanent compliance receipt.
 */
import clsx from "clsx";
import { CheckCircle2, Clock } from "lucide-react";

import { caseSLADays, slaLabel, slaTone } from "../lib/regulatory";

interface SLABadgeProps {
  /** ISO datetime when the case was created. */
  createdAt: string;
  /** ISO datetime when the case reached a final verdict (if it has). */
  decidedAt?: string | null;
  /** Mark expedited cases — uses 72h instead of 7-day budget. */
  expedited?: boolean;
  /** Compact mode for tight table cells. */
  compact?: boolean;
}

const TONE_STYLES: Record<"green" | "amber" | "red", string> = {
  green: "bg-accent-green/10 text-accent-green border-accent-green/30",
  amber: "bg-accent-amber/10 text-accent-amber border-accent-amber/30",
  red:   "bg-accent-red/10 text-accent-red border-accent-red/30",
};

export function SLABadge({
  createdAt,
  decidedAt,
  expedited = false,
  compact = false,
}: SLABadgeProps): JSX.Element {
  // Already-decided case: show met-SLA pill anchored to decision time
  if (decidedAt) {
    const days = caseSLADays(createdAt, expedited);
    const met = days >= 0 || // decided before deadline
      (new Date(decidedAt).getTime() - new Date(createdAt).getTime()) /
        (1000 * 60 * 60 * 24) <=
        (expedited ? 3 : 7);
    return (
      <span
        title={`CMS-0057-F § IV.B${expedited ? ".2 (72-hour expedited)" : ".1 (7-day standard)"} — ${
          met ? "met at decision time" : "missed"
        }`}
        className={clsx(
          "inline-flex items-center gap-1 text-mono-tech rounded border whitespace-nowrap",
          compact ? "text-[9px] px-1 py-0.5" : "text-[10px] px-1.5 py-0.5",
          met ? TONE_STYLES.green : TONE_STYLES.red,
        )}
      >
        <CheckCircle2 size={compact ? 9 : 10} />
        SLA {met ? "met" : "missed"}
      </span>
    );
  }

  // Open case: live countdown
  const days = caseSLADays(createdAt, expedited);
  const tone = slaTone(days);
  return (
    <span
      title={`CMS-0057-F § IV.B${expedited ? ".2 (72-hour expedited)" : ".1 (7-day standard)"} — ${slaLabel(days)}`}
      className={clsx(
        "inline-flex items-center gap-1 text-mono-tech rounded border whitespace-nowrap nums-tabular",
        compact ? "text-[9px] px-1 py-0.5" : "text-[10px] px-1.5 py-0.5",
        TONE_STYLES[tone],
      )}
    >
      <Clock size={compact ? 9 : 10} />
      {days >= 0 ? `T-${days}d` : `${Math.abs(days)}d over`}
    </span>
  );
}
