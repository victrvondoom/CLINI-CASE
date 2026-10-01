/**
 * Trust badge row — 5 enterprise/regulatory badges with subtle accent dots.
 * Adapted from Claude Design Wave 1 output (USCDI v3 added unprompted; we keep it).
 */
const BADGES = [
  { label: "HIPAA",         dot: "bg-accent-green" },
  { label: "PHI redaction", dot: "bg-accent-green" },
  { label: "FHIR R4",       dot: "bg-accent-cyan" },
  { label: "USCDI v3",      dot: "bg-accent-cyan" },
  { label: "Bedrock-ready", dot: "bg-accent-brand" },
];

export function TrustBadgeRow() {
  return (
    <div className="flex flex-wrap items-center gap-2">
      {BADGES.map((b) => (
        <span
          key={b.label}
          className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-surface-raised border border-surface-border text-[11px] text-mono-tech text-ink-body"
        >
          <span className={`w-1.5 h-1.5 rounded-full ${b.dot} animate-pulse-soft`} />
          {b.label}
        </span>
      ))}
    </div>
  );
}
