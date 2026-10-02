/**
 * Runtime / deployment topology for the whole CLINI-CASE application.
 *
 * Everything shown comes from GET /api/v1/runtime: the API's own environment (incl. the
 * Kubernetes Downward API), server configuration, the live route table and live probes of
 * server-configured services. It is labelled "Live cluster topology" only inside Kubernetes.
 */
import clsx from "clsx";
import { ArrowDown, Boxes, Container, Database, Globe, Loader2, RadioTower, RefreshCw, Server } from "lucide-react";
import { useState, type KeyboardEvent } from "react";

import { BUTTON } from "../journey/cards";
import { Drawer } from "../journey/Drawer";
import { useLive } from "../lib/useLive";
import { fetchRuntime, type ProbeStatus, type RuntimeService, type RuntimeTopology } from "../runtime/api";

const STATUS: Record<ProbeStatus, { label: string; tone: string; dot: string }> = {
  up: { label: "Healthy", tone: "text-accent-green", dot: "bg-accent-green" },
  down: { label: "Unreachable", tone: "text-accent-red", dot: "bg-accent-red" },
  embedded: { label: "In-process", tone: "text-accent-cyan", dot: "bg-accent-cyan" },
  not_probed: { label: "Not probed", tone: "text-ink-muted", dot: "bg-ink-faint" },
  misconfigured: { label: "Misconfigured", tone: "text-accent-amber", dot: "bg-accent-amber" },
};

const ICONS: Record<RuntimeService["id"], typeof Server> = {
  frontend: Globe,
  api: Server,
  receiver: RadioTower,
  database: Database,
  redis: Boxes,
};

const TABS = ["Services", "Routes", "Health"] as const;
type Tab = (typeof TABS)[number];

function statusFor(service: RuntimeService) {
  // The API cannot see the browser; if it did not probe the frontend, this page itself proves it is serving.
  if (service.id === "frontend" && service.status === "not_probed")
    return { label: "Serving this page", tone: "text-accent-green", dot: "bg-accent-green" };
  return STATUS[service.status];
}

export function RuntimeTopologyCard({ service, onOpen }: { service: RuntimeService; onOpen: () => void }) {
  const Icon = ICONS[service.id] ?? Server;
  const status = statusFor(service);
  return (
    <button
      type="button"
      onClick={onOpen}
      className="w-full rounded-xl border border-surface-border bg-surface-raised p-4 text-left transition-colors hover:border-accent-brand/60 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent-brand"
      aria-label={`${service.name}: ${status.label}. Open details`}
    >
      <div className="flex items-center gap-2">
        <Icon size={16} className="text-accent-cyan" aria-hidden="true" />
        <span className="font-medium text-ink-primary">{service.name}</span>
        <span className={clsx("ml-auto flex items-center gap-1.5 text-[11px]", status.tone)}>
          <span className={clsx("h-2 w-2 rounded-full", status.dot)} aria-hidden="true" />
          {status.label}
        </span>
      </div>
      <p className="mt-1.5 text-xs text-ink-muted">{service.role}</p>
      <dl className="mt-2 grid grid-cols-[auto,1fr] gap-x-2 gap-y-0.5 text-[11px]">
        {service.image && (
          <>
            <dt className="text-ink-faint">Image</dt>
            <dd className="truncate text-mono-tech">{service.image}</dd>
          </>
        )}
        {service.endpoint && (
          <>
            <dt className="text-ink-faint">Endpoint</dt>
            <dd className="truncate text-mono-tech">{service.endpoint}</dd>
          </>
        )}
        {service.workload && (
          <>
            <dt className="text-ink-faint">Workload</dt>
            <dd>{service.workload}</dd>
          </>
        )}
      </dl>
    </button>
  );
}

function Edge({ label }: { label?: string }) {
  return (
    <div className="flex flex-col items-center py-1 text-[10px] text-ink-faint" aria-hidden="true">
      <ArrowDown size={14} />
      {label && <span className="text-mono-tech">{label}</span>}
    </div>
  );
}

function Orchestration({ data }: { data: RuntimeTopology }) {
  const kind = data.platform.kind;
  const steps = [
    { label: "Docker", active: kind !== "process", icon: Container },
    { label: "Kubernetes", active: kind === "kubernetes", icon: Boxes },
    { label: data.platform.provider ?? "kind", active: kind === "kubernetes" && !!data.platform.provider, icon: Server },
  ];
  return (
    <section aria-label="Orchestration" className="rounded-xl border border-surface-border bg-surface-raised p-4">
      <h2 className="text-[11px] font-semibold uppercase tracking-wider text-ink-faint">Orchestration</h2>
      <ol className="mt-2 flex flex-wrap items-center gap-2 text-sm">
        {steps.map((step, i) => (
          <li key={step.label} className="flex items-center gap-2">
            <span
              className={clsx(
                "inline-flex items-center gap-1.5 rounded-md border px-2 py-1",
                step.active ? "border-accent-green/50 text-accent-green" : "border-surface-border text-ink-faint",
              )}
            >
              <step.icon size={13} aria-hidden="true" /> {step.label}
              <span className="sr-only">{step.active ? "(active)" : "(not detected)"}</span>
            </span>
            {i < steps.length - 1 && <span aria-hidden="true" className="text-ink-faint">→</span>}
          </li>
        ))}
      </ol>
      <p className="mt-2 text-xs text-ink-muted">
        {kind === "kubernetes"
          ? `Namespace ${data.platform.namespace ?? "—"} · pod ${data.platform.pod ?? "—"} · node ${data.platform.node ?? "—"}`
          : kind === "container"
            ? `Container ${data.platform.hostname}; not running in Kubernetes.`
            : `Local process on ${data.platform.hostname}; not containerised. Deploy with python k8s/cluster.py up to run on kind.`}
      </p>
    </section>
  );
}

export default function Runtime() {
  const live = useLive(fetchRuntime, [], 15_000);
  const [tab, setTab] = useState<Tab>("Services");
  const [selected, setSelected] = useState<RuntimeService | null>(null);
  const data = live.data;

  function onTabKey(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
    event.preventDefault();
    const next = TABS[(TABS.indexOf(tab) + (event.key === "ArrowRight" ? 1 : -1) + TABS.length) % TABS.length];
    setTab(next);
    event.currentTarget.querySelector<HTMLButtonElement>(`#runtime-tab-${next}`)?.focus();
  }

  const service = (id: RuntimeService["id"]) => data?.services.find((s) => s.id === id);
  const edge = (to: string) => data?.edges.find((e) => e.to === to)?.protocol;
  const backends = data?.services.filter((s) => s.id !== "frontend" && s.id !== "api") ?? [];

  return (
    <div className="mx-auto max-w-6xl space-y-6 px-4 py-6 sm:px-6">
      <header className="flex flex-wrap items-end gap-3">
        <div className="flex-1">
          <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-accent-cyan">CLINI-CASE runtime</p>
          <h1 className="text-2xl font-semibold text-ink-primary">{data?.label ?? "Deployment topology"}</h1>
          <p className="mt-1 text-sm text-ink-muted">
            One application: frontend, API, independent System B receiver and evidence store.
          </p>
        </div>
        <button type="button" className={BUTTON} onClick={live.reload} disabled={live.loading}>
          <RefreshCw size={13} className={clsx(live.loading && "motion-safe:animate-spin")} aria-hidden="true" />
          Re-check now
        </button>
      </header>

      {live.error && (
        <p role="alert" className="rounded-xl border border-accent-red/40 bg-accent-red/5 p-4 text-sm text-ink-primary">
          {live.error}
          {data ? " Showing the last successful check." : ""}
        </p>
      )}
      {!data && live.loading && (
        <p className="flex items-center gap-2 text-sm text-ink-muted" aria-live="polite">
          <Loader2 size={14} className="motion-safe:animate-spin" aria-hidden="true" /> Probing services…
        </p>
      )}

      {data && (
        <>
          <Orchestration data={data} />

          <div role="tablist" aria-label="Runtime views" className="flex gap-1 border-b border-surface-border" onKeyDown={onTabKey}>
            {TABS.map((name) => (
              <button
                key={name}
                id={`runtime-tab-${name}`}
                type="button"
                role="tab"
                aria-selected={tab === name}
                aria-controls={`runtime-panel-${name}`}
                tabIndex={tab === name ? 0 : -1}
                onClick={() => setTab(name)}
                className={clsx(
                  "-mb-px border-b-2 px-3 py-2 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-accent-brand",
                  tab === name ? "border-accent-brand text-accent-brand" : "border-transparent text-ink-muted hover:text-ink-primary",
                )}
              >
                {name}
              </button>
            ))}
          </div>

          <div role="tabpanel" id={`runtime-panel-${tab}`} aria-labelledby={`runtime-tab-${tab}`}>
            {tab === "Services" && (
              <div className="mx-auto max-w-3xl">
                {service("frontend") && (
                  <RuntimeTopologyCard service={service("frontend")!} onOpen={() => setSelected(service("frontend")!)} />
                )}
                <Edge label={edge("api")} />
                {service("api") && <RuntimeTopologyCard service={service("api")!} onOpen={() => setSelected(service("api")!)} />}
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {backends.map((s) => (
                    <div key={s.id}>
                      <Edge label={edge(s.id)} />
                      <RuntimeTopologyCard service={s} onOpen={() => setSelected(s)} />
                    </div>
                  ))}
                </div>
              </div>
            )}

            {tab === "Routes" && (
              <table className="w-full text-sm">
                <caption className="pb-2 text-left text-xs text-ink-muted">
                  {data.route_count} API routes served by this process, grouped by prefix.
                </caption>
                <thead>
                  <tr className="text-left text-[11px] uppercase tracking-wider text-ink-faint">
                    <th scope="col" className="py-1.5">Prefix</th>
                    <th scope="col" className="py-1.5">Routes</th>
                    <th scope="col" className="py-1.5">Methods</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-surface-border">
                  {data.routes.map((group) => (
                    <tr key={group.prefix}>
                      <td className="py-1.5 text-mono-tech text-ink-primary">{group.prefix}</td>
                      <td className="py-1.5">{group.routes}</td>
                      <td className="py-1.5 text-xs text-ink-muted">{group.methods.join(", ")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}

            {tab === "Health" && (
              <ul className="space-y-2">
                {data.services.map((s) => {
                  const status = statusFor(s);
                  return (
                    <li key={s.id} className="flex flex-wrap items-center gap-3 rounded-lg border border-surface-border bg-surface-raised p-3 text-sm">
                      <span className={clsx("h-2 w-2 rounded-full", status.dot)} aria-hidden="true" />
                      <span className="font-medium text-ink-primary">{s.name}</span>
                      <span className={status.tone}>{status.label}</span>
                      <span className="text-xs text-ink-muted">{s.detail}</span>
                      <span className="ml-auto text-[11px] text-ink-faint">
                        {s.probe_ms !== null ? `${s.probe_ms} ms probe · ` : ""}
                        checked {new Date(s.checked_at).toLocaleTimeString()}
                      </span>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>

          <p className="text-xs text-ink-faint">{data.notice}</p>
        </>
      )}

      <Drawer
        open={selected !== null}
        title={selected?.name ?? ""}
        subtitle={selected?.role}
        onClose={() => setSelected(null)}
      >
        {selected && (
          <dl className="grid grid-cols-[auto,1fr] gap-x-4 gap-y-2 text-sm">
            {(
              [
                ["Status", statusFor(selected).label],
                ["Detail", selected.detail],
                ["Image", selected.image],
                ["Endpoint", selected.endpoint],
                ["Health check", selected.health_path],
                ["Workload", selected.workload],
                ["Engine", selected.engine],
                ["Probe", selected.probe_ms !== null ? `${selected.probe_ms} ms` : null],
                ["Checked", new Date(selected.checked_at).toLocaleString()],
                ["Connections", data?.edges
                  .filter((e) => e.from === selected.id || e.to === selected.id)
                  .map((e) => `${e.from} → ${e.to} (${e.protocol})`)
                  .join("; ")],
              ] as [string, string | null | undefined][]
            )
              .filter(([, value]) => value)
              .map(([label, value]) => (
                <div key={label} className="contents">
                  <dt className="text-ink-muted">{label}</dt>
                  <dd className="break-words text-ink-primary">{value}</dd>
                </div>
              ))}
          </dl>
        )}
      </Drawer>
    </div>
  );
}
