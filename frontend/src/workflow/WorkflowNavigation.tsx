import { Link, useLocation } from "react-router-dom";
import { areas, areaFor } from "./areas";
export function WorkflowNavigation() {
  const { pathname } = useLocation();
  if (pathname.startsWith("/journey")) return null;
  let journeyPath = "/journey";
  try {
    const remembered = sessionStorage.getItem("clini-current-journey");
    if (remembered?.startsWith("/journey/")) journeyPath = remembered;
  } catch {
    /* storage unavailable */
  }
  const area = areaFor(pathname);
  const index = area ? areas.indexOf(area) : -1;
  const previous = index > 0 ? areas[index - 1] : null;
  const next = index >= 0 && index < 5 ? areas[index + 1] : null;
  return (
    <nav
      aria-label="Workflow context"
      className="flex flex-wrap items-center gap-3 border-b border-surface-border px-6 py-3 text-xs"
    >
      <Link className="hover:underline focus-visible:ring-2" to={journeyPath}>
        Back to Journey
      </Link>
      {previous && (
        <Link className="hover:underline" to={previous.path}>
          Previous: {previous.label}
        </Link>
      )}
      {area && (
        <Link className="font-semibold text-accent-brand" to={area.path}>
          {area.label} / Choose tools
        </Link>
      )}
      {next && (
        <Link className="ml-auto hover:underline" to={next.path}>
          Continue to {next.label} &rarr;
        </Link>
      )}
    </nav>
  );
}
export function WorkflowOverview() {
  return (
    <section aria-label="One connected evidence journey" className="mb-6">
      <h2 className="mb-3 text-lg font-semibold">
        One connected evidence journey
      </h2>
      <div className="grid gap-2 sm:grid-cols-3 lg:grid-cols-6">
        {areas.slice(0, 6).map((a, i) => (
          <Link
            key={a.path}
            to={a.path}
            className="rounded-xl border border-surface-border bg-surface-panel p-4 hover:border-accent-brand focus-visible:ring-2 focus-visible:ring-accent-brand"
          >
            <span className="text-xs text-ink-muted">{i + 1}</span>
            <div className="font-semibold">{a.label}</div>
          </Link>
        ))}
      </div>
      <Link
        to="/journey"
        className="mt-3 inline-block text-accent-brand hover:underline"
      >
        Open Evidence Journey &rarr;
      </Link>
    </section>
  );
}
