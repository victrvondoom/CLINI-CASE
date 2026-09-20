/**
 * Drives one live run of the 7-agent prior-authorisation DAG and exposes its
 * progress as React state.
 *
 * The backend already publishes per-agent progress (app/observability/trace.py
 * calls app.streaming.publish on every agent entry/exit) and already persists
 * every step to the `agent_runs` table. Until now the dashboard used neither:
 * the demo buttons created a case and navigated away. This hook connects the
 * two so the pipeline can be watched where it matters.
 *
 * Three behaviours here are deliberate and load-bearing:
 *
 *   1. ATTACH BEFORE TRIGGER. The first agent emits within ~50ms of the run
 *      starting, so subscribing after the trigger reliably loses the opening
 *      events. We wait for the EventSource to open (bounded) before firing.
 *
 *   2. WORKER DETECTION WITH SYNCHRONOUS FALLBACK. `POST /run-async` only
 *      enqueues; it needs `python -m app.workers.case_runner` running to make
 *      progress. If no worker is deployed the job sits at status=queued with
 *      claimed_at=null forever and the user watches nothing happen. We detect
 *      exactly that (unclaimed past a grace window) and fall back to the
 *      synchronous `POST /run`, which executes in-request and publishes the
 *      same trace events. The console therefore works with or without a
 *      worker, which is the difference between a demo that runs and one that
 *      silently hangs.
 *
 *   3. RECOVERY FROM THE AUDIT TRAIL. If the stream drops mid-run, any agent
 *      that completed while the socket was down is missing from the UI. On
 *      reconnect we re-read `GET /cases/{id}/audit` and merge the persisted
 *      agent_runs rows over local state, so the pipeline heals instead of
 *      showing a permanently stalled step.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { api } from "./api";
import { openTraceStream, type StreamHandle } from "./sse";
import type { AgentRun, TraceEvent } from "./types";

/**
 * `not_required` and `aborted` are deliberately distinct.
 *
 * `not_required` means a conditional branch was legitimately not taken (the
 * appeals drafter does not run when the verdict is APPROVE) — the pipeline is
 * whole. `aborted` means the agent should have run and did not, because the
 * run ended early. Collapsing the two into one "skipped" state would let a
 * pipeline that died at agent 1 look exactly like a clean run, which on a
 * cancer-treatment authorisation screen is a patient-safety problem.
 */
export type AgentPhase =
  | "pending"
  | "running"
  | "done"
  | "error"
  | "not_required"
  | "aborted";

export type PipelineStatus =
  | "idle"
  | "starting"
  | "running"
  | "complete"
  /** Finished, but at least one agent errored. */
  | "degraded"
  /** Ended without error yet without running every required agent. */
  | "incomplete"
  /** Halted at the human-in-the-loop gate; a reviewer must decide. */
  | "paused"
  | "failed";

export interface SubAgentState {
  name: string;
  phase: AgentPhase;
  latencyMs: number | null;
  error: string | null;
}

export interface PipelineAgentState {
  name: string;
  display: string;
  phase: AgentPhase;
  latencyMs: number | null;
  modelId: string | null;
  error: string | null;
  subAgents: SubAgentState[];
}

/**
 * The full DAG in execution order (app/graph/build.py build_full_graph).
 * `appeals_drafter` and `patient_communicator` sit behind the DENY branch, so
 * they legitimately may not run: they end as "skipped", not "pending".
 */
export const PIPELINE_AGENTS: ReadonlyArray<{
  name: string;
  display: string;
  /** Sits behind a conditional edge, so not running it can be correct. */
  conditional?: boolean;
}> = [
  { name: "clinical_extractor", display: "Clinical Extractor" },
  { name: "policy_retriever", display: "Policy Retriever" },
  { name: "necessity_reasoner", display: "Necessity Reasoner" },
  { name: "decision_composer", display: "Decision Composer" },
  { name: "denial_forecaster", display: "Denial Forecaster" },
  { name: "appeals_drafter", display: "Appeals Drafter", conditional: true },
  { name: "patient_communicator", display: "Patient Communicator", conditional: true },
];

const CONDITIONAL_AGENTS = new Set(
  PIPELINE_AGENTS.filter((a) => a.conditional).map((a) => a.name),
);

const RESUME_KEY = "clincase_pipeline_run";
/** How long to wait for a worker to claim the job before running it inline. */
const WORKER_GRACE_MS = 4000;
const WORKER_POLL_MS = 1000;
/** How long to wait for the SSE socket to open before triggering anyway. */
const ATTACH_TIMEOUT_MS = 1500;
/** A stored run older than this is stale and is not resumed on reload. */
const RESUME_MAX_AGE_MS = 10 * 60 * 1000;
/** How long a worker-presence probe result stays trusted before re-probing. */
const WORKER_PROBE_TTL_MS = 5 * 60 * 1000;

/**
 * Remembers whether a queue worker is actually consuming jobs.
 *
 * Without this, every run pays the full WORKER_GRACE_MS waiting for a worker
 * that may not be deployed at all. Deployment topology does not change per
 * click, so the answer is cached for the tab. It still expires, so an operator
 * who starts `app.workers.case_runner` mid-session gets picked up rather than
 * being ignored until the page is reloaded.
 */
let workerPresence: { known: "present" | "absent"; at: number } | null = null;

function cachedWorkerPresence(): "present" | "absent" | "unknown" {
  if (!workerPresence) return "unknown";
  if (Date.now() - workerPresence.at > WORKER_PROBE_TTL_MS) return "unknown";
  return workerPresence.known;
}

function rememberWorkerPresence(known: "present" | "absent") {
  workerPresence = { known, at: Date.now() };
}

interface ResumeRecord {
  caseId: string;
  fixture: string;
  startedAt: number;
}

interface InternalAgent {
  phase: AgentPhase;
  latencyMs: number | null;
  modelId: string | null;
  error: string | null;
  subAgents: Map<string, SubAgentState>;
}

function emptyAgentMap(): Map<string, InternalAgent> {
  const m = new Map<string, InternalAgent>();
  for (const a of PIPELINE_AGENTS) {
    m.set(a.name, {
      phase: "pending",
      latencyMs: null,
      modelId: null,
      error: null,
      subAgents: new Map(),
    });
  }
  return m;
}

/** Trace events name sub-agents as "parent.child"; split them back apart. */
function splitAgentName(raw: string): { parent: string; child: string | null } {
  const dot = raw.indexOf(".");
  if (dot === -1) return { parent: raw, child: null };
  return { parent: raw.slice(0, dot), child: raw.slice(dot + 1) };
}

function ensure(map: Map<string, InternalAgent>, parent: string): InternalAgent {
  let entry = map.get(parent);
  if (!entry) {
    entry = { phase: "pending", latencyMs: null, modelId: null, error: null, subAgents: new Map() };
    map.set(parent, entry);
  }
  return entry;
}

export interface UsePipelineRun {
  status: PipelineStatus;
  agents: PipelineAgentState[];
  caseId: string | null;
  fixture: string | null;
  /** Wall-clock ms since the run started, live while running. */
  elapsedMs: number;
  error: string | null;
  /** Set when the socket dropped and is being re-established. */
  reconnecting: boolean;
  /** True when the run is executing inline because no worker claimed the job. */
  inlineFallback: boolean;
  start: (fixtureName: string) => void;
  reset: () => void;
}

export function usePipelineRun(): UsePipelineRun {
  const [status, setStatus] = useState<PipelineStatus>("idle");
  const [agentMap, setAgentMap] = useState<Map<string, InternalAgent>>(emptyAgentMap);
  const [caseId, setCaseId] = useState<string | null>(null);
  const [fixture, setFixture] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reconnecting, setReconnecting] = useState(false);
  const [inlineFallback, setInlineFallback] = useState(false);
  const [elapsedMs, setElapsedMs] = useState(0);
  // The graph can halt at the human-in-the-loop gate. That is a legitimate
  // outcome, but it is NOT a completed authorisation and must not read as one.
  const [paused, setPaused] = useState(false);

  const streamRef = useRef<StreamHandle | null>(null);
  const startedAtRef = useRef<number | null>(null);
  const tickRef = useRef<ReturnType<typeof setInterval> | null>(null);
  // Guards every async continuation: bumped on reset/unmount so a late
  // response from an abandoned run cannot write into current state.
  const runIdRef = useRef(0);
  const mountedRef = useRef(true);

  const stopTimer = useCallback(() => {
    if (tickRef.current !== null) {
      clearInterval(tickRef.current);
      tickRef.current = null;
    }
  }, []);

  const teardown = useCallback(() => {
    streamRef.current?.close();
    streamRef.current = null;
    stopTimer();
  }, [stopTimer]);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      runIdRef.current += 1;
      streamRef.current?.close();
      streamRef.current = null;
      if (tickRef.current !== null) clearInterval(tickRef.current);
    };
  }, []);

  const applyEvent = useCallback((ev: TraceEvent) => {
    setAgentMap((prev) => {
      // The done event carries no per-agent data, so returning prev avoids a
      // pointless Map allocation and a full re-render of the console.
      if (ev.type === "done") return prev;
      const next = new Map(prev);

      const name = (ev as { agent_name?: string }).agent_name;
      if (!name) return next;

      const { parent, child } = splitAgentName(name);
      const entry = { ...ensure(next, parent) };
      entry.subAgents = new Map(entry.subAgents);

      if (ev.type === "agent_started") {
        if (child) {
          entry.subAgents.set(child, { name: child, phase: "running", latencyMs: null, error: null });
          // A sub-agent starting implies its parent is active.
          if (entry.phase === "pending") entry.phase = "running";
        } else {
          entry.phase = "running";
        }
      } else if (ev.type === "agent_finished") {
        const fin = ev as { latency_ms?: number; model_id?: string | null };
        if (child) {
          entry.subAgents.set(child, {
            name: child,
            phase: "done",
            latencyMs: fin.latency_ms ?? null,
            error: null,
          });
        } else {
          entry.phase = "done";
          entry.latencyMs = fin.latency_ms ?? null;
          entry.modelId = fin.model_id ?? entry.modelId;
        }
      } else if (ev.type === "agent_error") {
        const errText = (ev as { error?: string }).error ?? "agent failed";
        if (child) {
          entry.subAgents.set(child, { name: child, phase: "error", latencyMs: null, error: errText });
        } else {
          entry.phase = "error";
          entry.error = errText;
        }
      }

      next.set(parent, entry);
      return next;
    });
  }, []);

  /**
   * Merge the persisted agent_runs rows over local state. Used after a
   * reconnect: rows are authoritative for anything that already finished.
   */
  const resyncFromAudit = useCallback(async (id: string, myRun: number) => {
    let rows: AgentRun[];
    try {
      const audit = await api.getAudit(id);
      rows = audit.agent_runs ?? [];
    } catch {
      // Recovery is best-effort; the live stream is still the primary source.
      return;
    }
    // Re-check AFTER the await, not just before the call. mountedRef stays true
    // for the whole component lifetime, so on its own it would happily merge a
    // late response for a previous case into the run now on screen.
    if (runIdRef.current !== myRun || !mountedRef.current) return;

    setAgentMap((prev) => {
      const next = new Map(prev);
      for (const row of rows) {
        const { parent, child } = splitAgentName(row.agent_name);
        const entry = { ...ensure(next, parent) };
        entry.subAgents = new Map(entry.subAgents);

        const phase: AgentPhase = row.error_text
          ? "error"
          : row.finished_at
            ? "done"
            : "running";

        if (child) {
          entry.subAgents.set(child, {
            name: child,
            phase,
            latencyMs: row.latency_ms,
            error: row.error_text,
          });
          if (entry.phase === "pending") entry.phase = "running";
        } else {
          entry.phase = phase;
          entry.latencyMs = row.latency_ms ?? entry.latencyMs;
          entry.modelId = row.model_id ?? entry.modelId;
          entry.error = row.error_text ?? entry.error;
        }
        next.set(parent, entry);
      }
      return next;
    });
  }, []);

  /** Mark the run terminal, and settle any agent still shown as pending. */
  const finish = useCallback(
    (myRun: number) => {
      if (runIdRef.current !== myRun || !mountedRef.current) return;
      stopTimer();
      setAgentMap((prev) => {
        const next = new Map(prev);
        // If nothing failed, an unrun conditional agent simply was not needed.
        // If anything failed, every unrun agent was cut short by that failure.
        const anyError = Array.from(next.values()).some((a) => a.phase === "error");
        for (const [name, entry] of next) {
          if (entry.phase === "pending" || entry.phase === "running") {
            const notNeeded = !anyError && CONDITIONAL_AGENTS.has(name);
            next.set(name, { ...entry, phase: notNeeded ? "not_required" : "aborted" });
          }
        }
        return next;
      });
      setStatus((s) => (s === "failed" ? s : "complete"));
      try {
        sessionStorage.removeItem(RESUME_KEY);
      } catch {
        /* private mode */
      }
    },
    [stopTimer],
  );

  /** Subscribe to the case trace stream, with drop recovery. */
  const attach = useCallback(
    (id: string, myRun: number): Promise<void> =>
      new Promise((resolve) => {
        let settled = false;
        const settleOnce = () => {
          if (!settled) {
            settled = true;
            resolve();
          }
        };

        const handle = openTraceStream(
          id,
          (ev) => {
            if (runIdRef.current !== myRun || !mountedRef.current) return;
            applyEvent(ev);
            if (ev.type === "done") finish(myRun);
          },
          undefined,
          () => {
            if (runIdRef.current === myRun && mountedRef.current) setReconnecting(false);
            settleOnce();
          },
          {
            onReconnect: () => {
              if (runIdRef.current !== myRun || !mountedRef.current) return;
              setReconnecting(true);
              // Heal the gap from the persisted audit trail.
              void resyncFromAudit(id, myRun);
            },
            onGiveUp: () => {
              if (runIdRef.current !== myRun || !mountedRef.current) return;
              setReconnecting(false);
              // The socket is gone for good, but the run itself may well have
              // finished server-side, so reconcile from the audit trail.
              void resyncFromAudit(id, myRun).then(() => finish(myRun));
            },
            onDone: () => {
              if (runIdRef.current === myRun && mountedRef.current) setReconnecting(false);
            },
          },
        );
        streamRef.current = handle;

        // Never block the trigger indefinitely on the socket opening.
        setTimeout(settleOnce, ATTACH_TIMEOUT_MS);
      }),
    [applyEvent, finish, resyncFromAudit],
  );

  /**
   * Enqueue the run, then watch whether a worker actually claims it. Returns
   * true if a worker took it, false if we should run inline instead.
   */
  const tryWorkerRun = useCallback(async (id: string, myRun: number): Promise<boolean> => {
    // Skip the probe entirely when we already know nothing is consuming jobs.
    if (cachedWorkerPresence() === "absent") return false;

    let jobId: string;
    try {
      const job = await api.runAsync(id);
      jobId = job.job_id;
    } catch {
      // No async endpoint, or it rejected: inline is the fallback.
      rememberWorkerPresence("absent");
      return false;
    }

    const deadline = Date.now() + WORKER_GRACE_MS;
    while (Date.now() < deadline) {
      if (runIdRef.current !== myRun || !mountedRef.current) return true;
      await new Promise((r) => setTimeout(r, WORKER_POLL_MS));
      try {
        const st = await api.getJob(jobId);
        // claimed_at is set the moment a worker picks the job up.
        if (st.claimed_at || st.status === "running" || st.status === "done") {
          rememberWorkerPresence("present");
          return true;
        }
        if (st.status === "error") return false;
      } catch {
        return false;
      }
    }
    // Enqueued cleanly, but nothing claimed it inside the grace window.
    rememberWorkerPresence("absent");
    return false;
  }, []);

  const begin = useCallback(
    async (id: string, fixtureName: string, myRun: number) => {
      setCaseId(id);
      setFixture(fixtureName);
      startedAtRef.current = Date.now();
      setElapsedMs(0);
      stopTimer();
      tickRef.current = setInterval(() => {
        if (startedAtRef.current !== null) setElapsedMs(Date.now() - startedAtRef.current);
      }, 100);

      try {
        sessionStorage.setItem(
          RESUME_KEY,
          JSON.stringify({ caseId: id, fixture: fixtureName, startedAt: Date.now() }),
        );
      } catch {
        /* private mode: resume is a convenience, not a requirement */
      }

      // 1. Attach first so the opening events are not missed.
      await attach(id, myRun);
      if (runIdRef.current !== myRun || !mountedRef.current) return;
      setStatus("running");

      // 2. Prefer the durable queued path; fall back to inline if unclaimed.
      const claimed = await tryWorkerRun(id, myRun);
      if (runIdRef.current !== myRun || !mountedRef.current) return;

      if (!claimed) {
        setInlineFallback(true);
        try {
          const result = await api.runFull(id);
          // A run that stopped at the review gate is not an authorisation.
          if (result?.paused_for_review) setPaused(true);
        } catch (e) {
          if (runIdRef.current !== myRun || !mountedRef.current) return;
          // Agent-level errors already arrived over the stream; this is the
          // request-level failure. Keep whatever the stream showed.
          setError(String(e instanceof Error ? e.message : e));
          setStatus("failed");
        }
        if (runIdRef.current !== myRun || !mountedRef.current) return;
        // The sync endpoint returns only after the graph is done; if the
        // `done` event was missed, reconcile and settle.
        await resyncFromAudit(id, myRun);
        finish(myRun);
      }
    },
    [attach, finish, resyncFromAudit, stopTimer, tryWorkerRun],
  );

  const start = useCallback(
    (fixtureName: string) => {
      runIdRef.current += 1;
      const myRun = runIdRef.current;
      teardown();

      setStatus("starting");
      setAgentMap(emptyAgentMap());
      setError(null);
      setReconnecting(false);
      setInlineFallback(false);
      setPaused(false);
      setCaseId(null);

      void (async () => {
        let id: string;
        try {
          const created = await api.createFromFixture(fixtureName);
          id = created.case_id;
        } catch (e) {
          if (runIdRef.current !== myRun || !mountedRef.current) return;
          setError(String(e instanceof Error ? e.message : e));
          setStatus("failed");
          return;
        }
        if (runIdRef.current !== myRun || !mountedRef.current) return;
        await begin(id, fixtureName, myRun);
      })();
    },
    [begin, teardown],
  );

  const reset = useCallback(() => {
    runIdRef.current += 1;
    teardown();
    setStatus("idle");
    setAgentMap(emptyAgentMap());
    setCaseId(null);
    setFixture(null);
    setError(null);
    setReconnecting(false);
    setInlineFallback(false);
    setPaused(false);
    setElapsedMs(0);
    startedAtRef.current = null;
    try {
      sessionStorage.removeItem(RESUME_KEY);
    } catch {
      /* private mode */
    }
  }, [teardown]);

  // Resume a run that was in flight when the page reloaded. The pipeline keeps
  // running server-side, so we re-attach and rebuild from the audit trail.
  useEffect(() => {
    let record: ResumeRecord | null = null;
    try {
      const raw = sessionStorage.getItem(RESUME_KEY);
      record = raw ? (JSON.parse(raw) as ResumeRecord) : null;
    } catch {
      record = null;
    }
    if (!record || !record.caseId) return;

    const resumed = record;
    if (Date.now() - resumed.startedAt > RESUME_MAX_AGE_MS) {
      try {
        sessionStorage.removeItem(RESUME_KEY);
      } catch {
        /* ignore */
      }
      return;
    }

    runIdRef.current += 1;
    const myRun = runIdRef.current;
    setStatus("running");
    setCaseId(resumed.caseId);
    setFixture(resumed.fixture);
    startedAtRef.current = resumed.startedAt;
    // begin() normally owns this interval, and the resume path skips begin(),
    // so without this the elapsed clock stays frozen for the rest of the run.
    setElapsedMs(Date.now() - resumed.startedAt);
    if (tickRef.current !== null) clearInterval(tickRef.current);
    tickRef.current = setInterval(() => {
      if (startedAtRef.current !== null) setElapsedMs(Date.now() - startedAtRef.current);
    }, 100);

    void (async () => {
      await resyncFromAudit(resumed.caseId, myRun);
      if (runIdRef.current !== myRun || !mountedRef.current) return;
      await attach(resumed.caseId, myRun);
    })();
    // Intentionally mount-only: this restores a single in-flight run.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const agents = useMemo<PipelineAgentState[]>(
    () =>
      PIPELINE_AGENTS.map(({ name, display }) => {
        const entry = agentMap.get(name);
        return {
          name,
          display,
          phase: entry?.phase ?? "pending",
          latencyMs: entry?.latencyMs ?? null,
          modelId: entry?.modelId ?? null,
          error: entry?.error ?? null,
          subAgents: entry ? Array.from(entry.subAgents.values()) : [],
        };
      }),
    [agentMap],
  );

  /**
   * `complete` must mean the pipeline actually completed.
   *
   * Local bookkeeping alone is not enough to claim success: a run can end
   * without a single error row and still not have executed the agents that
   * produce the decision. So "complete" is granted only when every
   * non-conditional agent reached `done`; anything else downgrades to
   * `degraded` (something errored), `paused` (stopped at the review gate) or
   * `incomplete` (ended early, cause unrecorded). Never the reassuring one by
   * default.
   */
  const effectiveStatus = useMemo<PipelineStatus>(() => {
    if (status !== "complete") return status;
    if (paused) return "paused";
    if (agents.some((a) => a.phase === "error")) return "degraded";

    const requiredDone = PIPELINE_AGENTS.filter((a) => !a.conditional).every(
      (a) => agents.find((x) => x.name === a.name)?.phase === "done",
    );
    if (!requiredDone) return "incomplete";
    return "complete";
  }, [status, agents, paused]);

  return {
    status: effectiveStatus,
    agents,
    caseId,
    fixture,
    elapsedMs,
    error,
    reconnecting,
    inlineFallback,
    start,
    reset,
  };
}
