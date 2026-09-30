/**
 * useLive — fetch on mount / when deps change, optionally poll, and expose loading / error / reload state.
 *
 * Every dashboard module reads real backend data through this hook so pages stay current without a manual
 * refresh. Stale responses (an older request resolving after a newer one) are dropped, polling pauses while
 * the tab is hidden, and the last good data is kept on screen if a refresh fails.
 */
import { useCallback, useEffect, useRef, useState } from "react";

export interface Live<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
  /** last successful load */
  updatedAt: Date | null;
  reload: () => void;
}

export function useLive<T>(load: () => Promise<T>, deps: unknown[] = [], pollMs = 0): Live<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);
  const seq = useRef(0);
  const loadRef = useRef(load);
  loadRef.current = load;

  const run = useCallback(async () => {
    const id = ++seq.current;
    setLoading(true);
    try {
      const r = await loadRef.current();
      if (id !== seq.current) return;
      setData(r);
      setError(null);
      setUpdatedAt(new Date());
    } catch (e) {
      if (id !== seq.current) return;
      setError((e as Error)?.message || "Request failed");
    } finally {
      if (id === seq.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    void run();
    return () => {
      seq.current++; // invalidate in-flight request on unmount / dep change
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    if (!pollMs) return;
    const t = setInterval(() => {
      if (typeof document === "undefined" || document.visibilityState === "visible") void run();
    }, pollMs);
    return () => clearInterval(t);
  }, [pollMs, run]);

  return { data, error, loading, updatedAt, reload: () => void run() };
}
