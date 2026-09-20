/**
 * Live Agent Pipeline console.
 *
 * Sits in the dashboard hero and renders one run of the 7-agent
 * prior-authorisation DAG as it executes, driven by the backend's existing
 * per-agent SSE trace stream (see lib/usePipelineRun.ts).
 *
 * This is the only surface in the product where the agent architecture is
 * actually visible: which agent is working, how long each one took, which
 * model answered, and which sub-agents fired underneath it. Everywhere else
 * shows the verdict after the fact.
 *
 * Styling uses the app's design tokens only (ink / surface / accent), so it
 * follows light and dark mode without a second code path.
 */
import { useMemo } from "react";
import { Link } from "react-router-dom";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  Check,
  Loader2,
  Minus,
  RotateCcw,
  XCircle,
} from "lucide-react";

import type { DemoFixture } from "../lib/types";
import type {
  PipelineAgentState,
  PipelineStatus,
  UsePipelineRun,
} from "../lib/usePipelineRun";

interface Props {
  run: UsePipelineRun;
  fixtures: DemoFixture[] | null;
}

function formatMs(ms: number | null): string {
  if (ms === null) return "";
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

/** Strip the provider/region prefix so long Bedrock model ids stay readable. */
function shortModel(modelId: string | null): string | null {
  if (!modelId) return null;
  const parts = modelId.split(".");
  const tail = parts[parts.length - 1] ?? modelId;
  return tail.replace(/-v\d+:\d+$/, "");
}

/**
 * Terminal wording is deliberately plain. On a cancer-authorisation screen the
 * difference between "finished" and "finished correctly" has to survive a
 * two-second glance, so each state says what happened rather than relying on
 * the reader to decode a colour.
 */
const STATUS_LABEL: Record<PipelineStatus, string> = {
  idle: "idle",
  starting: "starting",
  running: "running",
  complete: "complete",
  degraded: "completed with errors",
  incomplete: "ended early",
  paused: "awaiting review",
  failed: "failed",
};

const STATUS_TONE: Record<PipelineStatus, { dot: string; text: string }> = {
  idle: { dot: "bg-ink-faint", text: "text-ink-muted" },
  starting: { dot: "bg-accent-cyan", text: "text-ink-muted" },
  running: { dot: "bg-accent-cyan", text: "text-ink-body" },
  complete: { dot: "bg-accent-green", text: "text-ink-body" },
  degraded: { dot: "bg-accent-amber", text: "text-accent-amber" },
  incomplete: { dot: "bg-accent-amber", text: "text-accent-amber" },
  paused: { dot: "bg-accent-cyan", text: "text-ink-body" },
  failed: { dot: "bg-accent-red", text: "text-accent-red" },
};

function StatusChip({ status, reconnecting }: { status: PipelineStatus; reconnecting: boolean }) {
  const label = reconnecting ? "reconnecting" : STATUS_LABEL[status];
  const live = status === "running" || status === "starting" || reconnecting;
  const tone = STATUS_TONE[status];

  return (
    <span
      role="status"
      aria-live="polite"
      className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md border border-surface-border bg-surface-raised-hi shrink-0"
    >
      <span
        aria-hidden="true"
        className={`w-1.5 h-1.5 rounded-full ${tone.dot} ${live ? "motion-safe:animate-pulse" : ""}`}
      />
      <span className={`text-compact text-[9.5px] ${tone.text}`}>{label}</span>
    </span>
  );
}

/** Human wording for each phase, used for the accessible label and tooltip. */
const PHASE_LABEL: Record<PipelineAgentState["phase"], string> = {
  pending: "waiting",
  running: "running",
  done: "done",
  error: "failed",
  not_required: "not required for this verdict",
  aborted: "did not run — pipeline ended early",
};

function PhaseIcon({ phase }: { phase: PipelineAgentState["phase"] }) {
  const label = PHASE_LABEL[phase];

  if (phase === "running") {
    return (
      <Loader2
        size={12}
        role="img"
        aria-label={label}
        className="text-accent-brand-glow motion-safe:animate-spin"
      />
    );
  }
  if (phase === "done") {
    return <Check size={12} role="img" aria-label={label} className="text-accent-green" />;
  }
  if (phase === "error") {
    return <AlertTriangle size={12} role="img" aria-label={label} className="text-accent-red" />;
  }
  if (phase === "aborted") {
    // Distinct from "not required": this agent should have run and did not.
    return <XCircle size={12} role="img" aria-label={label} className="text-accent-amber" />;
  }
  if (phase === "not_required") {
    return <Minus size={12} role="img" aria-label={label} className="text-ink-faint" />;
  }
  return (
    <span
      role="img"
      aria-label={label}
      className="block w-[6px] h-[6px] rounded-full bg-ink-faint/50"
    />
  );
}

function AgentRow({ agent, index }: { agent: PipelineAgentState; index: number }) {
  const dimmed =
    agent.phase === "pending" ||
    agent.phase === "not_required" ||
    agent.phase === "aborted";
  const doneSubs = agent.subAgents.filter((s) => s.phase === "done").length;
  const model = shortModel(agent.modelId);

  return (
    <li className="flex items-start gap-2.5 py-[5px]">
      <span className="text-mono-tech text-[10px] text-ink-faint w-4 shrink-0 pt-[3px] nums-tabular">
        {String(index + 1).padStart(2, "0")}
      </span>
      <span className="shrink-0 pt-[4px] w-3 flex justify-center">
        <PhaseIcon phase={agent.phase} />
      </span>

      <span className="min-w-0 flex-1">
        <span className="flex items-baseline gap-2">
          <span
            className={`text-[12.5px] truncate ${
              agent.phase === "running"
                ? "text-ink-primary"
                : dimmed
                  ? "text-ink-faint"
                  : "text-ink-body"
            }`}
          >
            {agent.display}
          </span>
          <span className="ml-auto shrink-0 text-mono-tech text-[10px] text-ink-muted nums-tabular">
            {agent.phase === "not_required" || agent.phase === "aborted"
              ? "—"
              : formatMs(agent.latencyMs)}
          </span>
        </span>

        {/* Sub-agent progress: the specialists underneath each of the 7 agents. */}
        {agent.subAgents.length > 0 && (
          <span className="flex items-center gap-1 mt-1">
            {agent.subAgents.map((s) => (
              <span
                key={s.name}
                title={s.error ? `${s.name}: ${s.error}` : s.name}
                className={`h-[3px] w-3.5 rounded-full ${
                  s.phase === "error"
                    ? "bg-accent-red"
                    : s.phase === "done"
                      ? "bg-accent-green/70"
                      : s.phase === "running"
                        ? "bg-accent-brand-glow motion-safe:animate-pulse"
                        : "bg-ink-faint/30"
                }`}
              />
            ))}
            <span className="text-mono-tech text-[9px] text-ink-faint ml-1 nums-tabular">
              {doneSubs}/{agent.subAgents.length}
            </span>
          </span>
        )}

        {agent.error && (
          <span
            className="block text-[10.5px] text-accent-red/90 mt-0.5 truncate"
            title={agent.error}
          >
            {agent.error}
          </span>
        )}
        {model && agent.phase === "done" && (
          <span className="block text-mono-tech text-[9px] text-ink-faint mt-0.5 truncate">
            {model}
          </span>
        )}
      </span>
    </li>
  );
}

export function LivePipelineConsole({ run, fixtures }: Props) {
  const { status, agents, caseId, elapsedMs, error, reconnecting, inlineFallback } = run;

  const isIdle = status === "idle";
  const isBusy = status === "starting" || status === "running";

  const doneCount = useMemo(() => agents.filter((a) => a.phase === "done").length, [agents]);
  const subTotal = useMemo(
    () => agents.reduce((n, a) => n + a.subAgents.length, 0),
    [agents],
  );

  return (
    <div className="w-full lg:w-[372px] shrink-0 rounded-xl border border-surface-border bg-surface-raised-hi/60 overflow-hidden flex flex-col">
      {/* Header */}
      <div className="px-4 py-2.5 border-b border-surface-border flex items-center justify-between gap-2">
        <span className="flex items-center gap-2 min-w-0">
          <Activity size={13} className="text-accent-brand-glow shrink-0" />
          <span className="text-compact text-[10px] text-ink-muted truncate">
            LIVE AGENT PIPELINE
          </span>
        </span>
        <StatusChip status={status} reconnecting={reconnecting} />
      </div>

      {/* Agent list */}
      <ul className="px-4 py-2 flex-1">
        {agents.map((a, i) => (
          <AgentRow key={a.name} agent={a} index={i} />
        ))}
      </ul>

      {/* Degradation notices — surfaced, never silent. */}
      {(reconnecting || inlineFallback || error) && (
        <div className="px-4 pb-2 space-y-1">
          {reconnecting && (
            <p className="text-[10.5px] text-ink-muted">
              Stream dropped — reconnecting, replaying from the audit trail.
            </p>
          )}
          {inlineFallback && !reconnecting && (
            <p className="text-[10.5px] text-ink-muted">
              No queue worker attached — running inline.
            </p>
          )}
          {error && (
            <p className="text-[10.5px] text-accent-red/90 truncate" title={error}>
              {error}
            </p>
          )}
        </div>
      )}

      {/* Footer / controls */}
      <div className="px-4 py-2.5 border-t border-surface-border bg-surface-panel/40">
        {isIdle ? (
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className="text-mono-tech text-[10px] text-ink-muted mr-0.5">run live:</span>
            {(fixtures ?? []).map((f) => (
              <button
                key={f.name}
                type="button"
                onClick={() => run.start(f.name)}
                title={f.label}
                className="text-mono-tech text-[10px] px-2 py-1 rounded-md border border-surface-border text-ink-body hover:border-accent-brand hover:text-ink-primary transition-colors"
              >
                {f.expected_verdict}
              </button>
            ))}
            {(!fixtures || fixtures.length === 0) && (
              <span className="text-[10.5px] text-ink-faint">loading fixtures…</span>
            )}
          </div>
        ) : (
          <div className="flex items-center gap-3">
            <span className="text-mono-tech text-[10px] text-ink-muted nums-tabular">
              {doneCount}/{agents.length} agents
              {subTotal > 0 ? ` · ${subTotal} sub` : ""}
            </span>
            <span className="text-mono-tech text-[10px] text-ink-primary nums-tabular ml-auto">
              {(elapsedMs / 1000).toFixed(1)}s
            </span>
            {!isBusy && (
              <button
                type="button"
                onClick={run.reset}
                aria-label="Reset pipeline"
                className="text-ink-muted hover:text-ink-primary transition-colors"
              >
                <RotateCcw size={12} />
              </button>
            )}
            {caseId && (
              <Link
                to={`/cases/${caseId}`}
                className="text-mono-tech text-[10px] text-accent-brand-glow hover:text-ink-primary inline-flex items-center gap-1 transition-colors"
              >
                case <ArrowRight size={10} />
              </Link>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
