import { Link, useLocation } from "react-router-dom";
import { areas } from "../workflow/areas";
export default function WorkflowArea() {
  const { pathname } = useLocation();
  const area = areas.find((a) => a.path === pathname);
  if (!area) return null;
  return (
    <section className="mx-auto max-w-5xl p-6">
      <p className="text-xs uppercase text-accent-brand">
        CLINI-CASE / One connected evidence journey
      </p>
      <h1 className="mt-2 text-3xl font-semibold text-ink-primary">
        {area.label}
      </h1>
      <p className="my-4 max-w-3xl text-ink-muted">{area.summary}</p>
      <h2 className="mb-3 font-semibold">
        Choose{" "}
        {area.label === "Clinical Context" ? "clinical context" : "a tool"}
      </h2>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {area.links.map(([label, href]) => (
          <Link
            key={href}
            to={href}
            className="rounded-xl border border-surface-border bg-surface-panel p-5 hover:border-accent-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-brand"
          >
            <span className="font-medium">{label}</span>
            <span aria-hidden="true" className="float-right">
              &rarr;
            </span>
          </Link>
        ))}
      </div>
    </section>
  );
}
