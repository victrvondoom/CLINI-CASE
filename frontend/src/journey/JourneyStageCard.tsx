import clsx from "clsx";
import { ChevronRight, Loader2 } from "lucide-react";
import { Link } from "react-router-dom";

import type { ActionId, Stage } from "./api";
import { BUTTON, PRIMARY_BUTTON } from "./cards";
import { STATUS_TEXT, STATUS_TONE, StatusIcon } from "./JourneyStepper";

const ACTIONABLE = new Set(["ready", "failed", "blocked"]);

export function JourneyStageCard({
  stage,
  total,
  isCurrent,
  busyAction,
  onAction,
  onOpenDetails,
}: {
  stage: Stage;
  total: number;
  isCurrent: boolean;
  busyAction: ActionId | null;
  onAction: (action: ActionId) => void;
  onOpenDetails: () => void;
}) {
  const action = stage.next_action && ACTIONABLE.has(stage.status) ? stage.next_action : null;
  return (
    <article
      aria-labelledby={`stage-${stage.id}-title`}
      className={clsx(
        "rounded-2xl border bg-surface-raised p-5 motion-safe:animate-fade-in",
        isCurrent ? "border-accent-brand/60" : "border-surface-border",
      )}
    >
      <div className="flex flex-wrap items-start gap-3">
        <StatusIcon status={stage.status} size={22} />
        <div className="min-w-0 flex-1">
          <p className="text-[11px] uppercase tracking-wider text-ink-faint">
            Stage {stage.index} of {total} · {stage.owner}
          </p>
          <h2 id={`stage-${stage.id}-title`} className="mt-0.5 text-xl font-semibold text-ink-primary">
            {stage.label}
          </h2>
        </div>
        <span
          className={clsx("rounded-full border border-current px-2 py-0.5 text-[11px] font-medium", STATUS_TONE[stage.status])}
        >
          {STATUS_TEXT[stage.status]}
        </span>
      </div>

      <p className="mt-3 text-sm text-ink-body" aria-live="polite">
        {stage.summary}
      </p>

      {!!stage.facts.length && (
        <dl className="mt-4 grid gap-x-6 gap-y-2 sm:grid-cols-2">
          {stage.facts.map((fact) => (
            <div key={fact.label} className="min-w-0">
              <dt className="text-[11px] text-ink-faint">{fact.label}</dt>
              <dd className="break-words text-sm text-ink-primary">{String(fact.value)}</dd>
            </div>
          ))}
        </dl>
      )}

      <div className="mt-5 flex flex-wrap items-center gap-2">
        {action && (
          <button
            type="button"
            className={PRIMARY_BUTTON}
            disabled={busyAction !== null}
            onClick={() => onAction(action.id)}
          >
            {busyAction === action.id && <Loader2 size={14} className="motion-safe:animate-spin" aria-hidden="true" />}
            {action.label}
          </button>
        )}
        {stage.secondary_actions.map((secondary) => (
          <button
            key={secondary.id}
            type="button"
            className={BUTTON}
            disabled={busyAction !== null}
            onClick={() => onAction(secondary.id)}
          >
            {busyAction === secondary.id && (
              <Loader2 size={13} className="motion-safe:animate-spin" aria-hidden="true" />
            )}
            {secondary.label}
          </button>
        ))}
        <button type="button" className={BUTTON} onClick={onOpenDetails}>
          View details{stage.evidence.length ? ` · ${stage.evidence.length} proof` : ""}
          <ChevronRight size={13} aria-hidden="true" />
        </button>
        {stage.links.map((link) => (
          <Link key={link.href} to={link.href} className={BUTTON}>
            {link.label}
          </Link>
        ))}
      </div>
    </article>
  );
}
