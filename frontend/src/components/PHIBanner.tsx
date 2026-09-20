/**
 * PHI Redaction Banner — simulates AWS Bedrock Guardrails firing on a case
 * with sensitive PHI in the physician note. Slide-in from top with a red-tinted
 * backdrop pulse, auto-dismisses after 8s.
 *
 * This is the demo-day cinematic moment for healthcare compliance — when the
 * Bedrock Guardrails are wired in production (May 6), this exact UX is what
 * fires automatically every time PHI is detected.
 */
import clsx from "clsx";
import { Eye, EyeOff, ShieldCheck, X } from "lucide-react";
import { useEffect, useState } from "react";

interface RedactedEntity {
  type: "SSN" | "DOB" | "MRN" | "PHONE" | "ADDRESS" | "EMAIL";
  value_redacted: string;
  position: string;  // e.g. "physician_note:char_142"
}

interface Props {
  open: boolean;
  onClose: () => void;
  /** Entities reported as redacted. Default = SSN + DOB demo set. */
  entities?: RedactedEntity[];
  /** Auto-dismiss after this many ms. 0 = never. */
  autoDismissMs?: number;
}

const DEFAULT_ENTITIES: RedactedEntity[] = [
  { type: "SSN", value_redacted: "***-**-1234", position: "physician_note:char_142" },
  { type: "DOB", value_redacted: "**/**/19**",  position: "physician_note:char_38" },
];

const ENTITY_COLOR: Record<RedactedEntity["type"], string> = {
  SSN:     "bg-accent-red/15 text-accent-red border-accent-red/30",
  DOB:     "bg-accent-amber/15 text-accent-amber border-accent-amber/30",
  MRN:     "bg-accent-violet/15 text-accent-violet border-accent-violet/30",
  PHONE:   "bg-accent-cyan/15 text-accent-cyan border-accent-cyan/30",
  ADDRESS: "bg-accent-blue/15 text-accent-blue border-accent-blue/30",
  EMAIL:   "bg-accent-brand/15 text-accent-brand border-accent-brand/30",
};

export function PHIBanner({
  open,
  onClose,
  entities = DEFAULT_ENTITIES,
  autoDismissMs = 8_000,
}: Props) {
  const [showRedacted, setShowRedacted] = useState(true);

  useEffect(() => {
    if (!open || autoDismissMs <= 0) return;
    const t = setTimeout(onClose, autoDismissMs);
    return () => clearTimeout(t);
  }, [open, autoDismissMs, onClose]);

  if (!open) return null;

  return (
    <>
      {/* Subtle red-tinted backdrop pulse */}
      <div
        aria-hidden
        className="fixed inset-0 z-40 pointer-events-none"
        style={{
          background: "radial-gradient(circle at top, rgba(18, 18, 18, 0.12), transparent 60%)",
          animation: "phi-backdrop 0.4s ease-out both",
        }}
      />

      {/* Slide-in banner from top */}
      <div
        className="fixed top-3 left-1/2 -translate-x-1/2 z-50 max-w-2xl w-[calc(100%-2rem)]"
        role="alert"
        style={{ animation: "phi-slide 0.25s cubic-bezier(0.16, 1, 0.3, 1) both" }}
      >
        <div className="bg-surface-raised border-2 border-accent-red rounded-2xl shadow-2xl overflow-hidden">
          {/* Header */}
          <div className="flex items-center gap-3 px-4 py-3 bg-accent-red/5 border-b border-accent-red/30">
            <div className="w-9 h-9 rounded-lg bg-accent-red text-ink-invert flex items-center justify-center shrink-0">
              <ShieldCheck size={18} strokeWidth={2.5} />
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-[10px] text-compact text-accent-red font-bold">
                Bedrock Guardrail Fired
              </div>
              <div className="font-semibold text-ink-primary text-sm">
                {entities.length} PHI entit{entities.length === 1 ? "y" : "ies"} redacted before LLM call
              </div>
            </div>
            <button
              type="button"
              onClick={() => setShowRedacted(!showRedacted)}
              className="p-1.5 rounded hover:bg-surface-raised-hi text-ink-muted"
              title={showRedacted ? "Hide redactions" : "Show redactions"}
            >
              {showRedacted ? <Eye size={14} /> : <EyeOff size={14} />}
            </button>
            <button
              type="button"
              onClick={onClose}
              className="p-1.5 rounded hover:bg-surface-raised-hi text-ink-muted"
              aria-label="Dismiss"
            >
              <X size={14} />
            </button>
          </div>

          {/* Entities */}
          <div className="px-4 py-3 space-y-2">
            {entities.map((e, i) => (
              <div key={i} className="flex items-center gap-3 text-xs">
                <span className={clsx(
                  "text-[10px] text-compact px-1.5 py-0.5 rounded border w-14 text-center",
                  ENTITY_COLOR[e.type],
                )}>
                  {e.type}
                </span>
                <code className="text-mono-tech text-ink-body flex-1">
                  {showRedacted ? e.value_redacted : "[REDACTED]"}
                </code>
                <span className="text-[10px] text-mono-tech text-ink-faint truncate">
                  {e.position}
                </span>
              </div>
            ))}
          </div>

          {/* Footer */}
          <div className="px-4 py-2 border-t border-surface-border bg-surface-panel/40 flex items-center justify-between text-[11px] text-ink-muted text-mono-tech">
            <span>via AWS Bedrock Guardrails · clincase-phi-guard</span>
            <span>auto-dismiss in {Math.ceil(autoDismissMs / 1000)}s</span>
          </div>
        </div>
      </div>

      <style>{`
        @keyframes phi-slide {
          0%   { opacity: 0; transform: translate(-50%, -16px); }
          100% { opacity: 1; transform: translate(-50%, 0); }
        }
        @keyframes phi-backdrop {
          0%   { opacity: 0; }
          50%  { opacity: 1; }
          100% { opacity: 0.4; }
        }
      `}</style>
    </>
  );
}
