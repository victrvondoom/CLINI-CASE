// EventSource wrapper for the ClinCase agent trace stream.
//
// Beyond opening the socket, this manages the two lifecycle facts that make
// the raw EventSource API unsafe here:
//
//   1. The backend *closes* the stream after it emits `done`
//      (app/api/stream.py breaks out of its generator). A browser EventSource
//      treats a server-side close as a failure and reconnects forever, so a
//      stream that is simply finished would otherwise reconnect in a loop for
//      as long as the page stays open. We close it ourselves on `done`.
//
//   2. A mid-run drop is silent. EventSource reconnects on its own but replays
//      nothing, so any agent that finished while the socket was down is lost
//      from the UI forever. We surface drops through `onReconnect` so the
//      caller can re-sync from the persisted `agent_runs` audit trail instead
//      of showing a permanently half-finished pipeline.
//
// Reconnection is handled manually (rather than leaning on the native retry)
// so attempts are bounded, backed off, and observable.
import { getToken } from "./auth";
import type { TraceEvent } from "./types";

export interface StreamHandle {
  close(): void;
}

export interface TraceStreamOptions {
  /** Fired when the socket dropped and a re-connect is being attempted. */
  onReconnect?: (attempt: number) => void;
  /** Fired once the retry budget is exhausted. The stream is closed. */
  onGiveUp?: () => void;
  /** Fired on the terminal `done` event, just before the stream is closed. */
  onDone?: () => void;
  /** Retry budget. Default 6 (~25s of backoff in total). */
  maxRetries?: number;
}

const EVENT_TYPES = [
  "agent_started",
  "agent_finished",
  "agent_error",
  "hitl_pause",
  "hitl_resume",
  "done",
] as const;

const BASE_DELAY_MS = 500;
const MAX_DELAY_MS = 8000;

/** Exponential backoff with jitter, so many tabs don't retry in lockstep. */
function backoffDelay(attempt: number): number {
  const exponential = Math.min(BASE_DELAY_MS * 2 ** attempt, MAX_DELAY_MS);
  return exponential * (0.7 + Math.random() * 0.6);
}

export function openTraceStream(
  caseId: string,
  onEvent: (event: TraceEvent) => void,
  onError?: (err: Event) => void,
  onOpen?: () => void,
  options: TraceStreamOptions = {},
): StreamHandle {
  const { onReconnect, onGiveUp, onDone, maxRetries = 6 } = options;

  // Use fetch streaming so the access token stays in an Authorization header.
  // Native EventSource cannot set headers and would leak query tokens into
  // proxy logs and copied URLs.
  const token = getToken();
  const url = `/api/v1/cases/${caseId}/stream`;
  let controller: AbortController | null = null;
  let retries = 0;
  let closedByCaller = false;
  let finished = false;
  let retryTimer: ReturnType<typeof setTimeout> | null = null;

  const teardown = () => {
    if (retryTimer !== null) {
      clearTimeout(retryTimer);
      retryTimer = null;
    }
    if (controller) {
      controller.abort();
      controller = null;
    }
  };

  const scheduleRetry = (error: unknown) => {
    if (closedByCaller || finished) return;
    if (onError) onError(new ErrorEvent("error", { error }));
    if (retries >= maxRetries) {
      if (onGiveUp) onGiveUp();
      return;
    }
    const attempt = retries + 1;
    retries = attempt;
    if (onReconnect) onReconnect(attempt);
    retryTimer = setTimeout(connect, backoffDelay(attempt - 1));
  };

  const dispatchFrame = (frame: string) => {
    let eventType = "message";
    const dataLines: string[] = [];
    for (const line of frame.split(/\r?\n/)) {
      if (line.startsWith("event:")) eventType = line.slice(6).trim();
      if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
    }
    if (!dataLines.length || !EVENT_TYPES.includes(eventType as typeof EVENT_TYPES[number])) return;
    let data: Record<string, unknown>;
    try {
      data = JSON.parse(dataLines.join("\n"));
    } catch (error) {
      console.warn("Failed to parse SSE event", eventType, error);
      return;
    }
    onEvent({ ...data, type: eventType } as TraceEvent);
    if (eventType === "done") {
      finished = true;
      if (onDone) onDone();
      teardown();
    }
  };

  const connect = async () => {
    if (closedByCaller || finished) return;
    controller = new AbortController();
    try {
      const response = await fetch(url, {
        headers: {
          Accept: "text/event-stream",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        signal: controller.signal,
      });
      if (!response.ok || !response.body) {
        throw new Error(`Trace stream failed: ${response.status}`);
      }
      // A successful connection resets the retry budget, so a long run that
      // drops a few times over several minutes is not penalised cumulatively.
      retries = 0;
      if (onOpen) onOpen();
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (!closedByCaller && !finished) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const frames = buffer.split(/\r?\n\r?\n/);
        buffer = frames.pop() ?? "";
        frames.forEach(dispatchFrame);
      }
      if (!closedByCaller && !finished) {
        throw new Error("Trace stream closed before done");
      }
    } catch (error) {
      if (!(error instanceof DOMException && error.name === "AbortError")) {
        scheduleRetry(error);
      }
    }
  };

  void connect();

  return {
    close: () => {
      closedByCaller = true;
      teardown();
    },
  };
}
