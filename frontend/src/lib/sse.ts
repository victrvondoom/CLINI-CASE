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

  // The stream is authenticated and org-scoped. EventSource cannot set an
  // Authorization header, so the token rides as a query param -- the backend
  // get_current_user dependency accepts ?token= for exactly this reason.
  const token = getToken();
  const url = token
    ? `/api/v1/cases/${caseId}/stream?token=${encodeURIComponent(token)}`
    : `/api/v1/cases/${caseId}/stream`;
  let es: EventSource | null = null;
  let retries = 0;
  let closedByCaller = false;
  let finished = false;
  let retryTimer: ReturnType<typeof setTimeout> | null = null;

  const teardown = () => {
    if (retryTimer !== null) {
      clearTimeout(retryTimer);
      retryTimer = null;
    }
    if (es) {
      es.close();
      es = null;
    }
  };

  const connect = () => {
    if (closedByCaller || finished) return;

    es = new EventSource(url);

    es.addEventListener("open", () => {
      // A successful connection resets the retry budget, so a long run that
      // drops a few times over several minutes is not penalised cumulatively.
      retries = 0;
      if (onOpen) onOpen();
    });

    for (const eventType of EVENT_TYPES) {
      es.addEventListener(eventType, (ev) => {
        let data: Record<string, unknown>;
        try {
          data = JSON.parse((ev as MessageEvent).data);
        } catch (e) {
          // A truncated frame is not fatal; skip it and keep the stream open.
          console.warn("Failed to parse SSE event", eventType, e);
          return;
        }

        if (eventType === "done") {
          // Terminal. Mark finished *before* tearing down so the error handler
          // that fires on the server-side close does not trigger a reconnect.
          finished = true;
          onEvent({ ...data, type: eventType } as TraceEvent);
          if (onDone) onDone();
          teardown();
          return;
        }

        onEvent({ ...data, type: eventType } as TraceEvent);
      });
    }

    es.addEventListener("error", (ev) => {
      if (closedByCaller || finished) return;
      if (onError) onError(ev);

      // Drop the broken socket before scheduling our own retry, otherwise the
      // native reconnect races with it and we end up with two live streams.
      if (es) {
        es.close();
        es = null;
      }

      if (retries >= maxRetries) {
        if (onGiveUp) onGiveUp();
        return;
      }

      const attempt = retries + 1;
      retries = attempt;
      if (onReconnect) onReconnect(attempt);
      retryTimer = setTimeout(connect, backoffDelay(attempt - 1));
    });
  };

  connect();

  return {
    close: () => {
      closedByCaller = true;
      teardown();
    },
  };
}
