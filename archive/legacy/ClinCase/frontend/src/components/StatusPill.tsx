/**
 * Reusable status pill — small uppercase mono badge tinted by status type.
 */
import clsx from "clsx";

import type { CaseStatus } from "../lib/syntheticCases";

const STATUS_TINT: Record<CaseStatus, string> = {
  pending:    "bg-surface-border           text-ink-muted",
  running:    "bg-accent-brand/10          text-accent-brand",
  approved:   "bg-accent-green/10          text-accent-green",
  denied:     "bg-accent-red/10            text-accent-red",
  referred:   "bg-accent-amber/10          text-accent-amber",
  appealed:   "bg-accent-violet/10         text-accent-violet",
  overturned: "bg-accent-green/15          text-accent-green ring-1 ring-accent-green/30",
};

interface Props {
  status: CaseStatus;
  className?: string;
}

export function StatusPill({ status, className }: Props) {
  return (
    <span
      className={clsx(
        "inline-flex items-center text-[10px] text-mono-tech uppercase tracking-wide px-2 py-0.5 rounded",
        STATUS_TINT[status],
        className,
      )}
    >
      {status}
    </span>
  );
}
