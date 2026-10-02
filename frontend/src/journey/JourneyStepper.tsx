/**
 * Ten-stage progress rail. Every step is a real link (/journey/:jobId/:stageId), so refresh,
 * back and forward work. Arrow/Home/End keys move focus between steps.
 */
import clsx from "clsx";
import { CheckCircle2, Circle, CircleDot, Lock, XCircle } from "lucide-react";
import type { KeyboardEvent } from "react";
import { Link } from "react-router-dom";

import type { Stage, StageId, StageStatus } from "./api";

export const STATUS_TEXT: Record<StageStatus, string> = {
  complete: "complete",
  ready: "ready for action",
  waiting: "waiting for an earlier stage",
  blocked: "blocked",
  failed: "failed",
};

export const STATUS_TONE: Record<StageStatus, string> = {
  complete: "text-accent-green",
  ready: "text-accent-brand",
  waiting: "text-ink-faint",
  blocked: "text-accent-amber",
  failed: "text-accent-red",
};

export function StatusIcon({ status, size = 16 }: { status: StageStatus; size?: number }) {
  const Icon = {
    complete: CheckCircle2,
    ready: CircleDot,
    waiting: Circle,
    blocked: Lock,
    failed: XCircle,
  }[status];
  return <Icon size={size} className={STATUS_TONE[status]} aria-hidden="true" />;
}

export function JourneyStepper({
  jobId,
  stages,
  activeStage,
  currentStage,
}: {
  jobId: string;
  stages: Stage[];
  activeStage: StageId;
  currentStage: StageId | null;
}) {
  function onKeyDown(event: KeyboardEvent<HTMLOListElement>) {
    const keys = ["ArrowRight", "ArrowLeft", "Home", "End"];
    if (!keys.includes(event.key)) return;
    const links = Array.from(event.currentTarget.querySelectorAll<HTMLAnchorElement>("a"));
    const index = links.indexOf(document.activeElement as HTMLAnchorElement);
    if (index < 0) return;
    event.preventDefault();
    const next =
      event.key === "Home"
        ? 0
        : event.key === "End"
          ? links.length - 1
          : (index + (event.key === "ArrowRight" ? 1 : -1) + links.length) % links.length;
    links[next].focus();
  }

  return (
    <nav aria-label="Journey stages" className="overflow-x-auto pb-1">
      <ol className="flex min-w-max items-stretch gap-1" onKeyDown={onKeyDown}>
        {stages.map((stage, i) => {
          const active = stage.id === activeStage;
          const isCurrent = stage.id === currentStage;
          return (
            <li key={stage.id} className="flex items-center">
              <Link
                to={`/journey/${encodeURIComponent(jobId)}/${stage.id}`}
                aria-current={active ? "step" : undefined}
                aria-label={`Stage ${stage.index} of ${stages.length}: ${stage.label}, ${STATUS_TEXT[stage.status]}${isCurrent ? ", next to complete" : ""}`}
                className={clsx(
                  "group flex min-w-[6.5rem] flex-col gap-1 rounded-lg border px-2.5 py-2 text-left transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-accent-brand",
                  active
                    ? "border-accent-brand bg-accent-brand/10"
                    : "border-surface-border bg-surface-raised hover:border-surface-border-hi",
                )}
              >
                <span className="flex items-center gap-1.5">
                  <span className="relative inline-flex">
                    <StatusIcon status={stage.status} size={15} />
                    {isCurrent && (
                      <span
                        className="absolute inset-0 rounded-full ring-2 ring-accent-brand/60 motion-safe:animate-pulse"
                        aria-hidden="true"
                      />
                    )}
                  </span>
                  <span className="text-[10px] text-mono-tech text-ink-faint">{String(stage.index).padStart(2, "0")}</span>
                </span>
                <span className={clsx("text-xs font-medium", active ? "text-accent-brand" : "text-ink-primary")}>
                  {stage.label}
                </span>
              </Link>
              {i < stages.length - 1 && (
                <span
                  aria-hidden="true"
                  className={clsx(
                    "mx-0.5 h-px w-3",
                    stage.status === "complete" ? "bg-accent-green/70" : "bg-surface-border",
                  )}
                />
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
