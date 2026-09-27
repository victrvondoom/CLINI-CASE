/**
 * Shared AquaHealth UI primitives.
 *
 * These components carry the module's honesty requirements into the interface:
 * a status is always labelled as a prototype signal, every record shows where
 * its data came from and how much human scrutiny it has had, and every AI
 * finding is rendered with its evidence, confidence, data quality and
 * recommended next step — never as a bare verdict.
 *
 * Styling uses ClinCase's existing design tokens (surface-*, ink-*, accent-*)
 * so AquaHealth reads as part of the same application.
 */
import clsx from "clsx";
import {
  AlertTriangle,
  Bot,
  CheckCircle2,
  CircleHelp,
  Database,
  Droplets,
  FlaskConical,
  Info,
  ShieldCheck,
  Sparkles,
  User,
} from "lucide-react";
import type { ReactNode } from "react";

import type {
  AgentFinding,
  Confidence,
  DataQuality,
  DataSource,
  EcosystemStatus,
  Evidence,
  Presence,
  VerificationState,
} from "./types";

// =============================================================================
// Status
// =============================================================================

export const STATUS_LABEL: Record<EcosystemStatus, string> = {
  healthy_signal: "Healthy Signal",
  watch: "Watch",
  potential_stress: "Potential Stress",
  critical_signal: "Critical Signal",
  insufficient_data: "Insufficient Data",
};

/** Colour ramp. `insufficient_data` is neutral, never green — absence of data
 *  must not read as good news. */
export const STATUS_CLASS: Record<EcosystemStatus, string> = {
  healthy_signal: "bg-accent-green/10 text-accent-green border-accent-green/30",
  watch: "bg-accent-blue/10 text-accent-blue border-accent-blue/30",
  potential_stress: "bg-accent-amber/10 text-accent-amber border-accent-amber/30",
  critical_signal: "bg-accent-red/10 text-accent-red border-accent-red/30",
  insufficient_data: "bg-surface-raised text-ink-muted border-surface-border",
};

export function StatusBadge({
  status,
  size = "md",
}: {
  status: EcosystemStatus;
  size?: "sm" | "md";
}) {
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1.5 rounded-md border font-medium",
        STATUS_CLASS[status],
        size === "sm" ? "px-1.5 py-0.5 text-[10px]" : "px-2.5 py-1 text-xs",
      )}
      title="Prototype Ecosystem Observation Status — not a validated environmental index"
    >
      <Droplets size={size === "sm" ? 10 : 12} aria-hidden="true" />
      {STATUS_LABEL[status]}
    </span>
  );
}

/** The status with its mandatory framing. Use at the top of any detail view. */
export function PrototypeStatusHeader({
  status,
  reason,
  confidence,
  dataQuality,
  humanVerification,
}: {
  status: EcosystemStatus;
  reason: string;
  confidence: Confidence;
  dataQuality: DataQuality;
  humanVerification: "required" | "reviewed";
}) {
  return (
    <div className="rounded-2xl border border-surface-border bg-surface-raised p-5 space-y-3">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="text-compact text-[10px] text-ink-muted">
            Prototype Ecosystem Observation Status
          </div>
          <div className="mt-1.5">
            <StatusBadge status={status} />
          </div>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <ConfidenceChip confidence={confidence} />
          <DataQualityChip quality={dataQuality} />
          <VerificationChip verification={humanVerification} />
        </div>
      </div>

      <p className="text-ui-secondary text-sm text-ink-body">{reason}</p>

      <p className="text-[11px] text-ink-faint border-t border-surface-border pt-2.5">
        This is a prototype triage signal derived from citizen observations. It is
        not a scientifically validated universal environmental index.
      </p>
    </div>
  );
}

// =============================================================================
// Confidence / data quality / verification
// =============================================================================

const CONFIDENCE_CLASS: Record<Confidence, string> = {
  low: "bg-surface-raised text-ink-muted border-surface-border",
  medium: "bg-accent-blue/10 text-accent-blue border-accent-blue/30",
  high: "bg-accent-violet/10 text-accent-violet border-accent-violet/30",
};

export function ConfidenceChip({ confidence }: { confidence: Confidence }) {
  return (
    <Chip className={CONFIDENCE_CLASS[confidence]} icon={<Sparkles size={11} />}>
      Confidence: {confidence}
    </Chip>
  );
}

const QUALITY_CLASS: Record<DataQuality, string> = {
  good: "bg-accent-green/10 text-accent-green border-accent-green/30",
  limited: "bg-accent-amber/10 text-accent-amber border-accent-amber/30",
  insufficient: "bg-accent-red/10 text-accent-red border-accent-red/30",
};

export function DataQualityChip({ quality }: { quality: DataQuality }) {
  return (
    <Chip className={QUALITY_CLASS[quality]} icon={<FlaskConical size={11} />}>
      Data quality: {quality}
    </Chip>
  );
}

export function VerificationChip({
  verification,
}: {
  verification: "required" | "reviewed";
}) {
  const reviewed = verification === "reviewed";
  return (
    <Chip
      className={
        reviewed
          ? "bg-accent-green/10 text-accent-green border-accent-green/30"
          : "bg-accent-amber/10 text-accent-amber border-accent-amber/30"
      }
      icon={reviewed ? <CheckCircle2 size={11} /> : <AlertTriangle size={11} />}
    >
      Human verification: {reviewed ? "reviewed" : "required"}
    </Chip>
  );
}

// =============================================================================
// Provenance — required on every record
// =============================================================================

const SOURCE_LABEL: Record<DataSource, string> = {
  citizen_observation: "Citizen observation",
  sensor: "Sensor",
  imported_dataset: "Imported dataset",
  demonstration_data: "Demonstration data",
};

const SOURCE_ICON: Record<DataSource, ReactNode> = {
  citizen_observation: <User size={11} />,
  sensor: <FlaskConical size={11} />,
  imported_dataset: <Database size={11} />,
  demonstration_data: <Info size={11} />,
};

export function SourceChip({ source }: { source: DataSource }) {
  return (
    <Chip
      className="bg-surface-raised text-ink-muted border-surface-border"
      icon={SOURCE_ICON[source]}
    >
      {SOURCE_LABEL[source]}
    </Chip>
  );
}

const VERIFICATION_LABEL: Record<VerificationState, string> = {
  unverified: "Unverified",
  ai_assisted: "AI-assisted",
  human_reviewed: "Human reviewed",
  verified: "Verified",
};

const VERIFICATION_CLASS: Record<VerificationState, string> = {
  unverified: "bg-surface-raised text-ink-muted border-surface-border",
  ai_assisted: "bg-accent-blue/10 text-accent-blue border-accent-blue/30",
  human_reviewed: "bg-accent-violet/10 text-accent-violet border-accent-violet/30",
  verified: "bg-accent-green/10 text-accent-green border-accent-green/30",
};

const VERIFICATION_ICON: Record<VerificationState, ReactNode> = {
  unverified: <CircleHelp size={11} />,
  ai_assisted: <Bot size={11} />,
  human_reviewed: <User size={11} />,
  verified: <ShieldCheck size={11} />,
};

export function VerificationStateChip({
  verification,
}: {
  verification: VerificationState;
}) {
  return (
    <Chip
      className={VERIFICATION_CLASS[verification]}
      icon={VERIFICATION_ICON[verification]}
    >
      {VERIFICATION_LABEL[verification]}
    </Chip>
  );
}

/** DEMO DATA badge. Rendered anywhere synthetic data appears. */
export function DemoBadge({ className }: { className?: string }) {
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1 rounded border border-accent-amber/40 " +
          "bg-accent-amber/10 px-1.5 py-0.5 text-[10px] text-mono-tech text-accent-amber",
        className,
      )}
      title="Synthetic demonstration data — not a real environmental measurement"
    >
      DEMO DATA
    </span>
  );
}

// =============================================================================
// Explainability
// =============================================================================

const AGENT_LABEL: Record<string, string> = {
  environmental_validation: "Environmental Validation",
  water_quality: "Water Quality",
  biodiversity: "Biodiversity",
  environmental_context: "Environmental Context",
  trend: "Trend",
  one_health: "One Health",
  explanation: "Explanation",
};

export function agentLabel(agent: string): string {
  return AGENT_LABEL[agent] ?? agent.replace(/_/g, " ");
}

/**
 * One AI finding, rendered in full: finding, evidence, confidence, data
 * quality, uncertainty and recommended next step.
 *
 * Evidence rows name the exact observation field that produced them, which is
 * what makes the assessment auditable rather than merely plausible.
 */
export function FindingCard({ finding }: { finding: AgentFinding }) {
  return (
    <div className="rounded-xl border border-surface-border bg-surface-raised p-4 space-y-3">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div className="text-compact text-[10px] text-ink-muted">
          {agentLabel(finding.agent)} agent
        </div>
        <div className="flex items-center gap-1.5 flex-wrap">
          <ConfidenceChip confidence={finding.confidence} />
          <DataQualityChip quality={finding.data_quality} />
        </div>
      </div>

      <div>
        <div className="text-compact text-[10px] text-ink-faint">Finding</div>
        <p className="text-sm text-ink-primary mt-0.5">{finding.finding}</p>
      </div>

      {finding.evidence.length > 0 && (
        <div>
          <div className="text-compact text-[10px] text-ink-faint">Evidence</div>
          <ul className="mt-1 space-y-1">
            {finding.evidence.map((e, i) => (
              <EvidenceRow key={`${e.field}-${i}`} evidence={e} />
            ))}
          </ul>
        </div>
      )}

      {finding.uncertainty && (
        <div>
          <div className="text-compact text-[10px] text-ink-faint">Uncertainty</div>
          <p className="text-[12px] text-ink-muted mt-0.5">{finding.uncertainty}</p>
        </div>
      )}

      {finding.recommended_next_step && (
        <div className="border-t border-surface-border pt-2.5">
          <div className="text-compact text-[10px] text-ink-faint">
            Recommended next step
          </div>
          <p className="text-[12px] text-ink-body mt-0.5">
            {finding.recommended_next_step}
          </p>
        </div>
      )}
    </div>
  );
}

function EvidenceRow({ evidence }: { evidence: Evidence }) {
  return (
    <li className="flex items-start gap-2 text-[12px]">
      <span className="text-accent-cyan mt-[3px]" aria-hidden="true">
        •
      </span>
      <span className="text-ink-body">
        <span className="text-ink-primary">{evidence.label}</span>
        <span className="text-ink-faint"> — </span>
        <span className="text-mono-tech text-[11px] text-accent-cyan">
          {evidence.value.replace(/_/g, " ")}
        </span>
        <span className="text-ink-muted"> · {evidence.interpretation}</span>
      </span>
    </li>
  );
}

// =============================================================================
// Presence
// =============================================================================

export const PRESENCE_LABEL: Record<Presence, string> = {
  observed: "Observed",
  not_observed: "Not observed",
  unknown: "Unknown",
  not_available: "Not available",
};

const PRESENCE_CLASS: Record<Presence, string> = {
  observed: "bg-accent-cyan/10 text-accent-cyan border-accent-cyan/30",
  not_observed: "bg-surface-raised text-ink-body border-surface-border",
  unknown: "bg-surface-bg text-ink-faint border-surface-border",
  not_available: "bg-surface-bg text-ink-faint border-surface-border",
};

export function PresencePill({ presence }: { presence: Presence }) {
  return (
    <span
      className={clsx(
        "inline-flex rounded border px-1.5 py-0.5 text-[10px]",
        PRESENCE_CLASS[presence],
      )}
    >
      {PRESENCE_LABEL[presence]}
    </span>
  );
}

// =============================================================================
// Generic bits
// =============================================================================

export function Chip({
  children,
  className,
  icon,
}: {
  children: ReactNode;
  className?: string;
  icon?: ReactNode;
}) {
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-[10px]",
        className,
      )}
    >
      {icon}
      {children}
    </span>
  );
}

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow: string;
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="flex items-start justify-between gap-4 flex-wrap mb-6">
      <div className="min-w-0">
        <div className="text-compact text-[10px] text-accent-cyan">{eyebrow}</div>
        <h1 className="text-display text-2xl text-ink-primary mt-1">{title}</h1>
        {description && (
          <p className="text-ui-secondary text-sm text-ink-muted mt-1.5 max-w-3xl">
            {description}
          </p>
        )}
      </div>
      {actions && <div className="flex items-center gap-2 shrink-0">{actions}</div>}
    </div>
  );
}

export function EmptyState({
  title,
  detail,
  action,
}: {
  title: string;
  detail: string;
  action?: ReactNode;
}) {
  return (
    <div className="rounded-2xl border border-dashed border-surface-border bg-surface-raised/50 p-10 text-center">
      <Droplets size={28} className="mx-auto text-ink-faint" aria-hidden="true" />
      <div className="text-ink-primary text-sm mt-3">{title}</div>
      <p className="text-ink-muted text-[12px] mt-1.5 max-w-md mx-auto">{detail}</p>
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function ErrorNote({ message }: { message: string }) {
  return (
    <div className="rounded-xl border border-accent-red/30 bg-accent-red/5 p-4 text-sm text-accent-red">
      {message}
    </div>
  );
}

export function LoadingNote({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="rounded-xl border border-surface-border bg-surface-raised p-6 text-center text-sm text-ink-muted animate-pulse-soft">
      {label}
    </div>
  );
}

/** Module-wide disclaimer strip. */
export function PrototypeNotice({ children }: { children?: ReactNode }) {
  return (
    <div className="rounded-xl border border-accent-blue/25 bg-accent-blue/5 p-3 flex items-start gap-2">
      <Info size={13} className="text-accent-blue mt-0.5 shrink-0" aria-hidden="true" />
      <p className="text-[11px] text-ink-muted">
        {children ?? (
          <>
            AquaHealth is a prototype freshwater-ecosystem module. AI assessments
            are advisory, always require human verification, and never constitute
            a public-health determination.
          </>
        )}
      </p>
    </div>
  );
}

export function formatDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export function formatDateTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
