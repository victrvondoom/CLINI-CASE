/**
 * Payer cell — square logo placeholder + payer ID. Each payer gets a tinted
 * background based on a deterministic hash of its ID.
 */
import clsx from "clsx";

const PAYER_TINT: Record<string, string> = {
  aetna:  "bg-gray-50    text-gray-700    dark:bg-gray-500/15    dark:text-gray-300",
  uhc:    "bg-gray-50    text-gray-700    dark:bg-gray-500/15    dark:text-gray-300",
  bcbs:   "bg-gray-50    text-gray-700    dark:bg-gray-500/15    dark:text-gray-300",
  anthem: "bg-gray-50  text-gray-700  dark:bg-gray-500/15  dark:text-gray-300",
};

const PAYER_LABEL: Record<string, string> = {
  aetna:  "AETNA",
  uhc:    "UHC",
  bcbs:   "BCBS",
  anthem: "ANTHEM",
};

interface Props {
  payer_id: string;
  showLabel?: boolean;
  size?: "sm" | "md";
}

export function PayerCell({ payer_id, showLabel = true, size = "sm" }: Props) {
  const tint = PAYER_TINT[payer_id] ?? "bg-surface-panel text-ink-muted";
  const label = PAYER_LABEL[payer_id] ?? payer_id.toUpperCase();
  const initial = label.slice(0, 1);
  const dim = size === "sm" ? "w-5 h-5 text-[10px]" : "w-7 h-7 text-xs";

  return (
    <span className="inline-flex items-center gap-1.5">
      <span
        className={clsx(
          "rounded font-bold text-mono-tech flex items-center justify-center shrink-0",
          dim,
          tint,
        )}
      >
        {initial}
      </span>
      {showLabel && (
        <span className="text-[11px] text-mono-tech text-ink-muted">{label}</span>
      )}
    </span>
  );
}
