/**
 * Runs the 8-step OAH-Bridge decision chain on the server and replays it step by step.
 * Stage timings are the server's measured engine times (sub-millisecond, shown as-is); the
 * replay is slowed to human speed and says so. Auto-run re-executes the chain every 20 s,
 * which the system monitor counts.
 */
import { CheckCircle2, Circle, Loader2, Play, Repeat, XCircle } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { oahBridge } from "./api";
import { formatInstant, formatMs } from "./format";
import type { DemoRunResponse } from "./types";

interface Props {
  scenarioId: string;
  run: DemoRunResponse | null;
  /** Called once the replay finishes; pass a stable callback. */
  onRun: (run: DemoRunResponse) => void;
  onRunningChange?: (running: boolean) => void;
}

const STEP_MS = 520;
const AUTO_RUN_MS = 20_000;

type StepState = "pending" | "running" | "done" | "failed";

export default function LivePipeline({ scenarioId, run, onRun, onRunningChange }: Props) {
  const [replay, setReplay] = useState<DemoRunResponse | null>(null);
  const [waiting, setWaiting] = useState(false);
  const [completed, setCompleted] = useState(0);
  const [autoRun, setAutoRun] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const busy = waiting || replay !== null;
  const mounted = useRef(true);
  const busyRef = useRef(false);
  busyRef.current = busy;

  useEffect(
    () => () => {
      mounted.current = false;
    },
    [],
  );

  useEffect(() => {
    onRunningChange?.(busy);
  }, [busy, onRunningChange]);

  const start = useCallback(async () => {
    if (busyRef.current || !scenarioId) return;
    busyRef.current = true;
    setError(null);
    setWaiting(true);
    setCompleted(0);
    try {
      const result = await oahBridge.run(scenarioId);
      if (mounted.current) setReplay(result);
    } catch (e) {
      if (mounted.current) setError(e instanceof Error ? e.message : "Run failed");
    } finally {
      if (mounted.current) setWaiting(false);
    }
  }, [scenarioId]);

  // Reveal one step per STEP_MS, then hand the finished run to the page.
  useEffect(() => {
    if (!replay) return;
    if (completed >= replay.steps.length) {
      const t = setTimeout(() => {
        onRun(replay);
        setReplay(null);
      }, 300);
      return () => clearTimeout(t);
    }
    const t = setTimeout(() => setCompleted((c) => c + 1), STEP_MS);
    return () => clearTimeout(t);
  }, [replay, completed, onRun]);

  useEffect(() => {
    if (!autoRun || busy) return;
    const t = setTimeout(() => void start(), AUTO_RUN_MS);
    return () => clearTimeout(t);
  }, [autoRun, busy, start]);

  const shown = replay ?? run;
  const steps = shown?.steps ?? [];

  function stateOf(index: number, status: string): StepState {
    if (replay) {
      if (index < completed) return status === "FAILED" ? "failed" : "done";
      return index === completed ? "running" : "pending";
    }
    if (waiting) return index === 0 ? "running" : "pending";
    return status === "FAILED" ? "failed" : "done";
  }

  const summary = shown?.validation_report.summary;
  const finished = !busy && shown;

  return (
    <div className="space-y-3" data-testid="live-pipeline">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <div className="text-sm text-ink-primary">Live decision chain</div>
          <p className="mt-0.5 text-[11px] text-ink-muted">
            {shown
              ? `${shown.run.id} · ${formatInstant(shown.run.ran_at)} · engine time ${formatMs(shown.run.total_ms)}`
              : "Run the chain to execute it on the server."}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {finished && summary && (
            <span
              className={`rounded-full px-2.5 py-0.5 text-[11px] ${
                shown.validation_report.all_passed ? "bg-emerald-500/10 text-emerald-300" : "bg-red-500/10 text-red-300"
              }`}
            >
              {summary.passed_checks}/{summary.total_checks} checks passed
            </span>
          )}
          <button
            type="button"
            onClick={() => void start()}
            disabled={busy || !scenarioId}
            className="flex items-center gap-1.5 rounded-md border border-accent-cyan/40 bg-accent-cyan/15 px-3 py-1.5 text-[11px] text-accent-cyan hover:bg-accent-cyan/25 disabled:opacity-50"
          >
            {busy ? <Loader2 size={12} className="animate-spin" /> : <Play size={12} />}
            {busy ? "Running…" : "Run chain live"}
          </button>
          <button
            type="button"
            aria-pressed={autoRun}
            onClick={() => {
              const next = !autoRun;
              setAutoRun(next);
              if (next) void start();
            }}
            className={`flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-[11px] ${
              autoRun ? "border-emerald-400/50 text-emerald-300" : "border-surface-border text-ink-body hover:border-accent-cyan"
            }`}
          >
            <Repeat size={12} /> Auto-run {autoRun ? "on (20 s)" : "off"}
          </button>
        </div>
      </div>

      {error && <p role="alert" className="text-xs text-red-300">Run failed: {error}</p>}

      <ol className="grid gap-2 md:grid-cols-2">
        {steps.map((step, i) => {
          const state = stateOf(i, step.status);
          return (
            <li
              key={step.step}
              data-state={state}
              className={`rounded-lg border p-2.5 transition-colors ${
                state === "running"
                  ? "border-accent-cyan bg-accent-cyan/10"
                  : state === "pending"
                    ? "border-surface-border bg-surface-bg opacity-50"
                    : "border-surface-border bg-surface-bg"
              }`}
            >
              <div className="flex items-start gap-2">
                <StepIcon state={state} />
                <div className="min-w-0">
                  <p className="text-[10px] uppercase tracking-wider text-ink-faint">
                    Step {step.step} · {step.stage} · {shown ? formatMs(shown.run.timings_ms[step.stage]) : "—"}
                  </p>
                  <p className="text-[12px] text-ink-primary">{step.title}</p>
                  {state !== "pending" && <p className="mt-0.5 text-[11px] text-ink-muted">{step.detail}</p>}
                </div>
              </div>
            </li>
          );
        })}
      </ol>
      <p className="text-[10px] text-ink-faint">
        Each run executes on the server; stage times are measured there. The step-by-step reveal is slowed to about
        half a second per step so it can be followed. Synthetic demonstration scenarios.
      </p>
    </div>
  );
}

function StepIcon({ state }: { state: StepState }) {
  if (state === "running") return <Loader2 size={14} className="mt-0.5 shrink-0 animate-spin text-accent-cyan" aria-label="running" />;
  if (state === "done") return <CheckCircle2 size={14} className="mt-0.5 shrink-0 text-emerald-400" aria-label="done" />;
  if (state === "failed") return <XCircle size={14} className="mt-0.5 shrink-0 text-red-400" aria-label="failed" />;
  return <Circle size={14} className="mt-0.5 shrink-0 text-ink-faint" aria-label="pending" />;
}
