/**
 * CLINI-CASE unified evidence journey.
 *
 * /journey                     start a journey or resume a recent one
 * /journey/:jobId              redirects to the stage that needs work next
 * /journey/:jobId/:stageId     one stage, with its proof, details and next legal action
 *
 * State is the server-side projection; actions call the existing gateway endpoints and then
 * re-read the projection, so the page can never show progress the backend has not recorded.
 */
import clsx from "clsx";
import { ArrowRight, FlaskConical, Loader2, Network, RefreshCw, Upload } from "lucide-react";
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { Link, Navigate, useNavigate, useParams } from "react-router-dom";

import {
  isStageId,
  journeyActions,
  journeyApi,
  type ActionId,
  type JourneyView,
  type MappingRow,
} from "../journey/api";
import { BUTTON, PRIMARY_BUTTON, StageDetailBody } from "../journey/cards";
import { Drawer } from "../journey/Drawer";
import { JourneyStageCard } from "../journey/JourneyStageCard";
import { JourneyStepper, STATUS_TEXT, STATUS_TONE, StatusIcon } from "../journey/JourneyStepper";
import { useLive } from "../lib/useLive";
import { downloadPassport } from "../onehealth/Journey";

const PAGE = "mx-auto max-w-6xl space-y-6 px-4 py-6 sm:px-6";

export default function Journey() {
  const { jobId } = useParams();
  return jobId ? <JourneyRun key={jobId} jobId={jobId} /> : <JourneyHome />;
}

function Header({ children }: { children?: ReactNode }) {
  return (
    <header className="space-y-1">
      <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-accent-cyan">CLINI-CASE</p>
      <h1 className="text-2xl font-semibold text-ink-primary">One Health Evidence &amp; Interoperability Journey</h1>
      {children}
    </header>
  );
}

function ProgressBar({ complete, total }: { complete: number; total: number }) {
  return (
    <div
      role="progressbar"
      aria-label="Journey progress"
      aria-valuemin={0}
      aria-valuemax={total}
      aria-valuenow={complete}
      className="h-1.5 w-full overflow-hidden rounded-full bg-surface-border"
    >
      <div
        className="h-full rounded-full bg-accent-green motion-safe:transition-[width] motion-safe:duration-500"
        style={{ width: `${(complete / Math.max(total, 1)) * 100}%` }}
      />
    </div>
  );
}

/* ------------------------------------------------------------------------------------------ */
/* Home: start or resume                                                                       */
/* ------------------------------------------------------------------------------------------ */

const DEMOS = [
  {
    variant: "dissolved" as const,
    title: "Dissolved arsenic laboratory export",
    note: "Maps to the verified OAH term; the cleanest end-to-end path.",
  },
  {
    variant: "ambiguous" as const,
    title: "Generic “arsenic” laboratory export",
    note: "The reviewer must confirm total vs inorganic; AI cannot decide it.",
  },
];

function JourneyHome() {
  const navigate = useNavigate();
  const recent = useLive(journeyApi.list, [], 30_000);
  const [variant, setVariant] = useState<"dissolved" | "ambiguous">("dissolved");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [payload, setPayload] = useState("");
  const [sourceSystem, setSourceSystem] = useState("Laboratory export");
  const [recordId, setRecordId] = useState("");

  async function start(run: () => Promise<{ id: string }>) {
    setBusy(true);
    setError("");
    try {
      const job = await run();
      navigate(`/journey/${encodeURIComponent(job.id)}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  function importJson() {
    let parsed: unknown;
    try {
      parsed = JSON.parse(payload);
    } catch {
      setError("The source must be a JSON object.");
      return;
    }
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      setError("The source must be a JSON object.");
      return;
    }
    void start(() =>
      journeyActions.importSource({
        source_system: sourceSystem.trim() || "Laboratory export",
        original_record_id: recordId.trim() || "imported-record",
        format: "json",
        payload: parsed as Record<string, unknown>,
        synthetic: true,
      }),
    );
  }

  const stages = recent.data?.stages ?? [];
  return (
    <div className={PAGE}>
      <Header>
        <p className="max-w-3xl text-sm text-ink-muted">
          One continuous journey: ingest external data, understand and map it, put every mapping through
          human review, standardise to OAH/FHIR, validate, exchange with an independent System B, verify the
          round trip, then open consented clinical context and follow up. Every step runs on the existing
          CLINI-CASE capabilities.
        </p>
      </Header>

      {!!stages.length && (
        <section aria-label="How the journey works">
          <ol className="grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
            {stages.map((stage, i) => (
              <li key={stage.id} className="rounded-lg border border-surface-border bg-surface-raised p-3">
                <span className="text-[10px] text-mono-tech text-ink-faint">{String(i + 1).padStart(2, "0")}</span>
                <p className="text-sm font-medium text-ink-primary">{stage.label}</p>
                <p className="mt-0.5 text-[11px] leading-snug text-ink-muted">{stage.owner}</p>
              </li>
            ))}
          </ol>
        </section>
      )}

      <section aria-labelledby="start-title" className="rounded-2xl border border-accent-brand/40 bg-surface-raised p-5">
        <h2 id="start-title" className="text-lg font-semibold text-ink-primary">
          Start an evidence journey
        </h2>
        <fieldset className="mt-3 grid gap-3 sm:grid-cols-2">
          <legend className="sr-only">Synthetic laboratory source</legend>
          {DEMOS.map((demo) => (
            <label
              key={demo.variant}
              className={clsx(
                "flex cursor-pointer gap-3 rounded-xl border p-4 focus-within:ring-2 focus-within:ring-accent-brand",
                variant === demo.variant ? "border-accent-brand bg-accent-brand/5" : "border-surface-border",
              )}
            >
              <input
                type="radio"
                name="demo-variant"
                value={demo.variant}
                checked={variant === demo.variant}
                onChange={() => setVariant(demo.variant)}
                className="mt-1 accent-[rgb(var(--accent-brand))]"
              />
              <span>
                <span className="flex items-center gap-1.5 text-sm font-medium text-ink-primary">
                  <FlaskConical size={14} aria-hidden="true" /> {demo.title}
                </span>
                <span className="mt-1 block text-xs text-ink-muted">{demo.note}</span>
              </span>
            </label>
          ))}
        </fieldset>
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <button
            type="button"
            className={PRIMARY_BUTTON}
            disabled={busy}
            onClick={() => void start(() => journeyActions.startDemo(variant))}
          >
            {busy && <Loader2 size={14} className="motion-safe:animate-spin" aria-hidden="true" />}
            Start evidence journey <ArrowRight size={14} aria-hidden="true" />
          </button>
          <span className="text-xs text-ink-muted">Synthetic data only; no health causation is inferred.</span>
        </div>

        <details className="mt-5 rounded-xl border border-surface-border p-4">
          <summary className="cursor-pointer text-sm font-medium text-accent-cyan">
            <Upload size={13} className="mr-1 inline" aria-hidden="true" />
            Or import your own JSON laboratory record
          </summary>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <label className="text-xs text-ink-muted">
              Source system
              <input
                value={sourceSystem}
                onChange={(e) => setSourceSystem(e.target.value)}
                className="mt-1 w-full rounded-md border border-surface-border bg-surface-bg px-2 py-1.5 text-sm text-ink-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-accent-brand"
              />
            </label>
            <label className="text-xs text-ink-muted">
              Original record ID
              <input
                value={recordId}
                onChange={(e) => setRecordId(e.target.value)}
                className="mt-1 w-full rounded-md border border-surface-border bg-surface-bg px-2 py-1.5 text-sm text-ink-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-accent-brand"
              />
            </label>
            <label className="text-xs text-ink-muted sm:col-span-2">
              JSON record (imported as synthetic)
              <textarea
                value={payload}
                onChange={(e) => setPayload(e.target.value)}
                rows={6}
                spellCheck={false}
                className="mt-1 w-full rounded-md border border-surface-border bg-surface-bg px-2 py-1.5 text-xs text-mono-tech text-ink-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-accent-brand"
              />
            </label>
          </div>
          <button type="button" className={clsx(BUTTON, "mt-3")} disabled={busy || !payload.trim()} onClick={importJson}>
            Import and start
          </button>
        </details>
        {error && (
          <p role="alert" className="mt-3 text-sm text-accent-red">
            {error}
          </p>
        )}
      </section>

      <section aria-labelledby="recent-title" className="space-y-3">
        <div className="flex items-center justify-between gap-3">
          <h2 id="recent-title" className="text-lg font-semibold text-ink-primary">
            Recent journeys
          </h2>
          <button type="button" className={BUTTON} onClick={recent.reload} disabled={recent.loading}>
            <RefreshCw size={13} className={clsx(recent.loading && "motion-safe:animate-spin")} aria-hidden="true" />
            Refresh
          </button>
        </div>
        {recent.error && !recent.data && (
          <div role="alert" className="rounded-xl border border-accent-amber/40 bg-accent-amber/5 p-4 text-sm">
            <p className="text-ink-primary">{recent.error}</p>
            <p className="mt-1 text-xs text-ink-muted">
              You can still use the <Link to="/aquahealth" className="text-accent-cyan underline">AquaHealth</Link> and{" "}
              <Link to="/dashboard" className="text-accent-cyan underline">clinical</Link> capabilities.
            </p>
          </div>
        )}
        {recent.loading && !recent.data && !recent.error && (
          <p className="text-sm text-ink-muted" aria-live="polite">
            Loading journeys…
          </p>
        )}
        {recent.data && !recent.data.journeys.length && (
          <p className="rounded-xl border border-dashed border-surface-border p-6 text-center text-sm text-ink-muted">
            No journeys yet. Start one above.
          </p>
        )}
        <ul className="space-y-2">
          {(recent.data?.journeys ?? []).map((row) => (
            <li key={row.job_id}>
              <Link
                to={`/journey/${encodeURIComponent(row.job_id)}`}
                className="block rounded-xl border border-surface-border bg-surface-raised p-4 hover:border-accent-brand/60 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent-brand"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <StatusIcon status={row.current_status} />
                  <span className="font-medium text-ink-primary">{row.source.system}</span>
                  <span className="text-xs text-mono-tech text-ink-muted">{row.source.record_id}</span>
                  {row.source.synthetic && (
                    <span className="rounded bg-accent-cyan/10 px-1.5 py-0.5 text-[10px] text-accent-cyan">SYNTHETIC</span>
                  )}
                  <span className="ml-auto text-xs text-ink-muted">
                    {row.progress.complete}/{row.progress.total} stages
                  </span>
                </div>
                <p className="mt-2 text-sm text-ink-body">{row.current_summary}</p>
                <div className="mt-3">
                  <ProgressBar complete={row.progress.complete} total={row.progress.total} />
                </div>
              </Link>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

/* ------------------------------------------------------------------------------------------ */
/* One journey                                                                                 */
/* ------------------------------------------------------------------------------------------ */

function useJourney(jobId: string) {
  const [view, setView] = useState<JourneyView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const seq = useRef(0);
  const load = useCallback(async (): Promise<JourneyView | null> => {
    const id = ++seq.current;
    setLoading(true);
    try {
      const fresh = await journeyApi.get(jobId);
      if (id !== seq.current) return null;
      setView(fresh);
      setError(null);
      return fresh;
    } catch (e) {
      if (id === seq.current) setError(e instanceof Error ? e.message : String(e));
      return null;
    } finally {
      if (id === seq.current) setLoading(false);
    }
  }, [jobId]);
  useEffect(() => {
    void load();
    const onFocus = () => void load(); // another reviewer may have advanced the job
    window.addEventListener("focus", onFocus);
    return () => {
      seq.current++;
      window.removeEventListener("focus", onFocus);
    };
  }, [load]);
  return { view, error, loading, load };
}

function JourneyRun({ jobId }: { jobId: string }) {
  const { stageId } = useParams();
  const navigate = useNavigate();
  const { view, error, loading, load } = useJourney(jobId);
  const [busy, setBusy] = useState<ActionId | null>(null);
  const [actionError, setActionError] = useState("");
  const [drawerOpen, setDrawerOpen] = useState(false);

  if (!view) {
    if (error)
      return (
        <div className={PAGE}>
          <Header />
          <div role="alert" className="rounded-xl border border-accent-amber/40 bg-accent-amber/5 p-5">
            <p className="text-ink-primary">{error}</p>
            <Link to="/journey" className={clsx(BUTTON, "mt-3")}>
              Back to evidence journeys
            </Link>
          </div>
        </div>
      );
    return (
      <div className={PAGE} aria-busy="true">
        <Header />
        <p className="text-sm text-ink-muted" aria-live="polite">
          Loading journey…
        </p>
      </div>
    );
  }

  if (!isStageId(stageId)) {
    return <Navigate to={`/journey/${encodeURIComponent(jobId)}/${view.current_stage ?? "follow_up"}`} replace />;
  }
  const journey = view;
  const stage = journey.stages.find((s) => s.id === stageId) ?? journey.stages[0];
  const isCurrent = stage.id === journey.current_stage;
  const next = journey.stages.find((s) => s.id === journey.current_stage);

  async function perform(action: ActionId, run: () => Promise<unknown>, follow = true) {
    setBusy(action);
    setActionError("");
    try {
      await run();
      const fresh = await load();
      if (follow && fresh?.current_stage && fresh.current_stage !== stage.id) {
        navigate(`/journey/${encodeURIComponent(jobId)}/${fresh.current_stage}`);
      }
    } catch (e) {
      setActionError(e instanceof Error ? e.message : String(e));
      await load(); // e.g. 409: someone else changed the job — show the server's current state
    } finally {
      setBusy(null);
    }
  }

  function onAction(action: ActionId) {
    switch (action) {
      case "review":
        setDrawerOpen(true);
        return;
      case "open_evidence":
        if (journey.exposure_id) navigate(`/onehealth?record=${encodeURIComponent(journey.exposure_id)}`);
        return;
      case "export_passport":
        void perform(action, async () => downloadPassport(await journeyActions.passport(journey), journey.job_id), false);
        return;
      case "map":
        void perform(action, () => journeyActions.map(journey));
        return;
      case "generate":
        void perform(action, () => journeyActions.generate(journey));
        return;
      case "validate":
        void perform(action, () => journeyActions.validate(journey));
        return;
      case "transfer":
        void perform(action, () => journeyActions.transfer(journey));
        return;
      case "return":
        void perform(action, () => journeyActions.returnTrip(journey));
        return;
      case "bind":
        void perform(action, () => journeyActions.bind(journey));
        return;
    }
  }

  function onDecide(row: MappingRow, decision: "approve" | "reject", target: string | null, concept: string | null) {
    void perform("review", () => journeyActions.decide(journey, row, decision, target, concept), false);
  }

  const reviewPending = journey.stages.find((s) => s.id === "review")?.status === "ready";
  return (
    <div className={PAGE}>
      <Header>
        <nav aria-label="Breadcrumb" className="text-xs text-ink-muted">
          <Link to="/journey" className="text-accent-cyan hover:underline">
            Evidence journeys
          </Link>
          <span aria-hidden="true"> / </span>
          <span>
            {journey.source.system} · {journey.source.record_id}
          </span>
        </nav>
      </Header>

      <section aria-label="Journey status" className="rounded-2xl border border-surface-border bg-surface-raised p-4">
        <div className="flex flex-wrap items-center gap-2 text-xs">
          {journey.source.synthetic && (
            <span className="rounded bg-accent-cyan/10 px-1.5 py-0.5 text-accent-cyan">SYNTHETIC</span>
          )}
          {journey.consent_status && (
            <span className="rounded bg-surface-bg px-1.5 py-0.5 text-ink-muted">
              Consent: {journey.consent_status.replace(/_/g, " ").toLowerCase()}
            </span>
          )}
          <span className="text-ink-muted">
            {journey.progress.complete} of {journey.progress.total} stages complete
          </span>
          <span className="ml-auto flex gap-2">
            <button type="button" className={BUTTON} onClick={() => void load()} disabled={loading}>
              <RefreshCw size={13} className={clsx(loading && "motion-safe:animate-spin")} aria-hidden="true" /> Refresh
            </button>
            <Link to={`/interop?job=${encodeURIComponent(journey.job_id)}`} className={BUTTON}>
              <Network size={13} aria-hidden="true" /> Interop workbench
            </Link>
          </span>
        </div>
        <div className="mt-3">
          <ProgressBar complete={journey.progress.complete} total={journey.progress.total} />
        </div>
        {!!journey.trust_states.length && (
          <p className="mt-2 break-words text-[11px] text-mono-tech text-ink-faint" aria-label="Trust states">
            {journey.trust_states.join(" → ")}
          </p>
        )}
      </section>

      <JourneyStepper
        jobId={journey.job_id}
        stages={journey.stages}
        activeStage={stage.id}
        currentStage={journey.current_stage}
      />

      {actionError && (
        <div role="alert" className="rounded-xl border border-accent-red/40 bg-accent-red/5 p-4 text-sm">
          <p className="text-ink-primary">{actionError}</p>
          <p className="mt-1 text-xs text-ink-muted">The journey has been refreshed from the server; review it and retry.</p>
        </div>
      )}

      <JourneyStageCard
        stage={stage}
        total={journey.stages.length}
        isCurrent={isCurrent}
        busyAction={busy}
        onAction={onAction}
        onOpenDetails={() => setDrawerOpen(true)}
      />

      {!isCurrent && next && (
        <p className="text-sm text-ink-muted">
          Next to complete:{" "}
          <Link
            to={`/journey/${encodeURIComponent(journey.job_id)}/${next.id}`}
            className={clsx("font-medium underline-offset-2 hover:underline", STATUS_TONE[next.status])}
          >
            {next.label} ({STATUS_TEXT[next.status]})
          </Link>
        </p>
      )}
      {!journey.current_stage && (
        <p role="status" className="text-sm text-accent-green">
          Every stage of this journey is complete.
        </p>
      )}

      <Drawer
        open={drawerOpen}
        title={`${stage.index}. ${stage.label}`}
        subtitle={stage.owner}
        onClose={() => setDrawerOpen(false)}
      >
        {stage.id === "review" && !reviewPending && journey.current_stage !== "review" && (
          <p role="status" className="text-sm text-accent-green">
            Review complete. Next: {next?.label ?? "journey complete"}.
          </p>
        )}
        <StageDetailBody
          stage={stage}
          busy={busy !== null}
          onDecide={onDecide}
          onExport={() => onAction("export_passport")}
        />
      </Drawer>
    </div>
  );
}
