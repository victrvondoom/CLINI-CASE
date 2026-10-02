import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../components/AuthContext";
import { journeyApi, type JourneySummary } from "../journey/api";
export function JourneyCases() {
  const { user } = useAuth();
  const [items, setItems] = useState<JourneySummary[]>([]);
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(true);
  const allowed = user?.role === "reviewer" || user?.role === "admin";
  useEffect(() => {
    if (!allowed) return;
    let cancelled = false;
    journeyApi
      .list()
      .then((data) => {
        if (!cancelled) setItems(data.journeys);
      })
      .catch(() => {
        if (!cancelled) setError(true);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [allowed]);
  if (!allowed) return null;
  return (
    <section className="mb-6" aria-label="Evidence cases">
      <h2 className="mb-3 text-lg font-semibold">Evidence cases</h2>
      {loading && (
        <p role="status" className="text-sm text-ink-muted">
          Loading evidence cases...
        </p>
      )}
      {error && (
        <p role="alert" className="text-sm text-accent-red">
          Evidence cases could not be loaded.{" "}
          <Link to="/journey" className="underline">
            Open Journey to retry
          </Link>
        </p>
      )}
      {!loading && !error && !items.length && (
        <Link className="text-sm text-accent-brand" to="/journey">
          Start an evidence journey
        </Link>
      )}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {items.map((item) => (
          <Link
            key={item.job_id}
            to={`/journey/${encodeURIComponent(item.job_id)}/${item.current_stage ?? "verify"}`}
            className="rounded-xl border border-surface-border bg-surface-panel p-4 hover:border-accent-brand focus-visible:ring-2 focus-visible:ring-accent-brand"
          >
            <div className="font-medium break-words">
              {item.source.record_id}
            </div>
            <p className="mt-1 text-xs text-ink-muted">
              {item.source.system} /{" "}
              {item.source.synthetic ? "Synthetic" : "External evidence"}
            </p>
            <p className="my-2 text-sm">{item.current_summary}</p>
            <p className="text-xs">
              Stage: {item.current_stage?.replaceAll("_", " ") ?? "Complete"} /{" "}
              {item.current_status}
            </p>
            <p className="text-xs text-ink-muted">
              {item.progress.complete}/{item.progress.total} complete / Updated:{" "}
              {item.last_activity
                ? new Date(item.last_activity).toLocaleString()
                : "Not recorded"}
            </p>
            <p className="mt-3 text-sm text-accent-brand">
              Continue case journey &rarr;
            </p>
          </Link>
        ))}
      </div>
    </section>
  );
}
