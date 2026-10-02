import { Link, useLocation } from "react-router-dom";
import { areas, areaFor } from "./areas";
export function WorkflowNavigation() {
  const { pathname } = useLocation();
  // Sub-pages only: Dashboard, Cases, the journey itself and the public front door stay clean.
  if (["/", "/dashboard", "/cases", "/platform", "/track7"].includes(pathname) || pathname.startsWith("/journey")) {
    return null;
  }
  let journeyPath = "/journey";
  try {
    const remembered = sessionStorage.getItem("clini-current-journey");
    if (remembered?.startsWith("/journey/")) journeyPath = remembered;
  } catch {
    /* storage unavailable */
  }
  const area = areaFor(pathname);
  const index = area ? areas.indexOf(area) : -1;
  const steps = areas.slice(0, 6);
  const previous = index > 0 ? areas[index - 1] : null;
  const next = index >= 0 && index < 5 ? areas[index + 1] : null;
  return (
    <nav
      aria-label="Workflow context"
      className="mx-6 mt-5 rounded-2xl border border-surface-border bg-surface-panel p-4 sm:p-5 reveal-go"
    >
      <div className="flex flex-wrap items-center gap-3">
        <p className="text-compact text-[11px] text-accent-cyan">
          Where you are in the CLINI-CASE workflow
        </p>
        <Link
          className="ml-auto rounded-md border border-surface-border px-3 py-1.5 text-xs font-medium text-ink-primary hover:border-accent-brand focus-visible:ring-2"
          to={journeyPath}
        >
          Back to Journey
        </Link>
      </div>
      <ol className="mt-4 grid gap-2 sm:grid-cols-3 lg:grid-cols-6">
        {steps.map((step, i) => {
          const active = i === index;
          const done = index >= 0 && i < index;
          return (
            <li key={step.path}>
              <Link
                to={step.path}
                aria-current={active ? "step" : undefined}
                className={
                  "block h-full rounded-xl border p-3 transition-colors focus-visible:ring-2 focus-visible:ring-accent-brand " +
                  (active
                    ? "border-accent-brand bg-accent-brand/10"
                    : done
                      ? "border-accent-green/40 bg-surface-raised hover:border-accent-green"
                      : "border-surface-border hover:border-accent-brand/60")
                }
              >
                <span className="text-mono-tech text-[10px] text-ink-faint">
                  {String(i + 1).padStart(2, "0")}
                  {done ? " · done" : active ? " · you are here" : ""}
                </span>
                <span className={"mt-0.5 block text-sm font-semibold " + (active ? "text-accent-brand" : "text-ink-primary")}>
                  {step.label}
                </span>
                <span className="mt-1 block text-[11px] leading-snug text-ink-muted">{step.summary}</span>
              </Link>
            </li>
          );
        })}
      </ol>
      {(previous || next || area) && (
        <div className="mt-4 flex flex-wrap items-center gap-3 text-sm">
          {previous && (
            <Link
              className="rounded-md border border-surface-border px-4 py-2 font-medium text-ink-primary hover:border-accent-brand focus-visible:ring-2"
              to={previous.path}
            >
              &larr; Previous: {previous.label}
            </Link>
          )}
          {area && (
            <Link className="font-semibold text-accent-brand hover:underline" to={area.path}>
              {area.label} / Choose tools
            </Link>
          )}
          {next && (
            <Link
              className="ml-auto rounded-md bg-accent-brand px-4 py-2 font-medium text-ink-invert hover:opacity-90 focus-visible:ring-2"
              to={next.path}
            >
              Continue to {next.label} &rarr;
            </Link>
          )}
        </div>
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
