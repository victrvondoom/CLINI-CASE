/**
 * /twin/:patientId — OncoTwin Digital Twin dashboard (and /twin/demo, the
 * guided 3–5 minute demo on synthetic patient OT-001).
 *
 * Everything shown is computed by the backend twin from the synthetic feed;
 * the twin clock only moves forward when the clinician (or the demo guide)
 * advances it, and every committed evaluation lands in the audit ledger.
 */
import clsx from "clsx";
import { ArrowLeft, ChevronRight, FastForward, FileJson, Loader2, RotateCcw, Sparkles, X, Zap } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { useAuth } from "../components/AuthContext";
import { type InjectionKind, ot } from "../oncotwin/api";
import {
  AlertPanel,
  AncChart,
  AuditPanel,
  ConfidencePanel,
  ExplainPanel,
  LatentChart,
  ReplayBar,
  RiskChart,
  ScenarioPanel,
  Section,
  SignalGrid,
  TierBadge,
  TimelinePanel,
  TwinCardView,
  pct,
} from "../oncotwin/panels";
import type { Dashboard } from "../oncotwin/types";

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
const BTN = "inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md border border-surface-border bg-surface-raised text-[12px] text-ink-body hover:border-accent-brand/60 disabled:opacity-40";

function scrollTo(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
}

export default function TwinDashboard({ demo = false }: { demo?: boolean }) {
  const params = useParams();
  const pid = demo ? "ot-001" : params.patientId ?? "ot-001";
  const { user } = useAuth();
  const canAct = user?.role === "reviewer" || user?.role === "admin";

  const [d, setD] = useState<Dashboard | null>(null);
  const [asOf, setAsOf] = useState<number | undefined>(undefined);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [selectedAlert, setSelectedAlert] = useState<string | null>(null);
  const [fhirOpen, setFhirOpen] = useState(false);
  const [simTrigger, setSimTrigger] = useState(0);
  const loadSeq = useRef(0);

  const load = useCallback(async (day?: number) => {
    const seq = ++loadSeq.current;
    try {
      const res = await ot.dashboard(pid, day);
      if (seq === loadSeq.current) { setD(res); setErr(null); }
      return res;
    } catch (e) {
      if (seq === loadSeq.current) setErr((e as Error).message);
      return null;
    }
  }, [pid]);

  useEffect(() => { void load(asOf); }, [load, asOf]);
  useEffect(() => { setAsOf(undefined); setSelectedAlert(null); }, [pid]);

  // Replay animation: step the twin-clock view forward one day at a time.
  useEffect(() => {
    if (!playing || !d) return;
    if ((asOf ?? d.live_day) >= d.live_day) { setPlaying(false); setAsOf(undefined); return; }
    const t = setTimeout(() => setAsOf((a) => Math.min((a ?? 1) + 1, d.live_day)), 650);
    return () => clearTimeout(t);
  }, [playing, asOf, d]);

  const refreshAll = async () => { setAsOf(undefined); await load(); setRefreshKey((k) => k + 1); };

  const run = async (label: string, fn: () => Promise<string | void>) => {
    setBusy(label); setNotice(null);
    try { const msg = await fn(); if (msg) setNotice(msg); } catch (e) { setErr((e as Error).message); } finally { setBusy(null); }
  };

  const advance = (n: number) => run(`advance${n}`, async () => {
    const r = await ot.advance(pid, n);
    await refreshAll();
    if (r.alerts.length) setSelectedAlert(r.alerts.at(-1) ?? null);
    const last = r.evaluations.at(-1);
    return last
      ? `Twin clock → Day ${r.live_day}: ${last.tier} (${pct(last.risk, 1)})${r.alerts.length ? " — ALERT raised" : ""}`
      : "End of synthetic feed.";
  });

  const advanceUntilAlert = () => run("until", async () => {
    for (let i = 0; i < 10; i++) {
      const r = await ot.advance(pid, 1);
      await refreshAll();
      if (r.alerts.length) { setSelectedAlert(r.alerts[0]); return `Day ${r.live_day}: the twin escalated and raised an alert.`; }
      if (!r.evaluations.length) return "End of synthetic feed.";
      await sleep(450);
    }
    return "No alert within 10 days.";
  });

  const inject = (kind: InjectionKind) => run(`inject-${kind}`, async () => {
    const r = await ot.inject(pid, kind);
    await refreshAll();
    return `${r.injection.label} from Day ${r.injection.effective_from_day} (past data unchanged: ${r.injection.past_data_unchanged ? "yes" : "no"}). Advance the clock to watch the twin respond.`;
  });

  const reset = () => run("reset", async () => {
    await ot.reset(); setSelectedAlert(null); await refreshAll(); return "Demo state reset (audit ledger kept).";
  });

  if (!d) {
    return (
      <div className="px-6 py-10 text-ink-muted text-sm flex items-center gap-2">
        {err ? <span className="text-accent-red">{err}</span> : <><Loader2 size={16} className="animate-spin" /> Building the digital twin…</>}
      </div>
    );
  }

  const alerts = d.alerts;
  return (
    <div className="px-4 sm:px-6 py-5 space-y-4">
      <header className="flex items-start justify-between gap-3 flex-wrap">
        <div>
          <Link to="/twin" className="text-[11px] text-ink-muted hover:text-ink-primary inline-flex items-center gap-1"><ArrowLeft size={12} /> OncoTwin</Link>
          <h1 className="text-2xl font-semibold text-ink-primary leading-tight flex items-center gap-2 flex-wrap">
            {d.patient.label} · Digital Twin <TierBadge tier={d.card.current_state.tier} />
          </h1>
          <p className="text-[12px] text-ink-muted max-w-3xl">{d.patient.narrative}</p>
          <p className="text-[11px] text-mono-tech text-ink-muted mt-1">
            twin clock Day {d.live_day}/{d.n_days} · {d.state.as_of_time.slice(0, 10)} · model {d.provenance.model.model_id} v{d.provenance.model.version}
            {d.provenance.model.integrity_verified ? " (artifact verified)" : " (ARTIFACT UNVERIFIED)"} · inputs {d.provenance.input_sha256.slice(0, 10)}…
          </p>
        </div>
        <div className="flex flex-wrap gap-2 items-center">
          <button type="button" onClick={() => setFhirOpen(true)} className={BTN}><FileJson size={13} /> EHR / FHIR</button>
          <button type="button" onClick={() => advance(1)} disabled={busy !== null || d.live_day >= d.n_days} className={BTN}>
            {busy === "advance1" ? <Loader2 size={13} className="animate-spin" /> : <ChevronRight size={13} />} +1 day
          </button>
          <button type="button" onClick={() => advance(3)} disabled={busy !== null || d.live_day >= d.n_days} className={BTN}>
            {busy === "advance3" ? <Loader2 size={13} className="animate-spin" /> : <FastForward size={13} />} +3 days
          </button>
          <select aria-label="Introduce deterioration (demo control)" disabled={busy !== null} value=""
            onChange={(e) => { if (e.target.value) void inject(e.target.value as InjectionKind); }}
            className="text-[12px] rounded-md border border-surface-border bg-surface-raised px-2 py-1.5">
            <option value="">Introduce deterioration…</option>
            <option value="infection">New infection</option>
            <option value="dehydration">Acute GI illness</option>
            <option value="nonadherence">Adherence drops</option>
          </select>
          {canAct && <button type="button" onClick={reset} disabled={busy !== null} className={BTN}><RotateCcw size={13} /> Reset demo</button>}
        </div>
      </header>

      <div className="text-[11px] px-3 py-1.5 rounded-md border border-dashed border-surface-border-hi text-ink-body">
        {d.synthetic_notice} Clinical decision support only — every alert requires clinician review.
      </div>
      {notice && <div className="text-[12px] px-3 py-2 rounded-md bg-accent-brand/10 border border-accent-brand/40" role="status">{notice}</div>}
      {err && <div className="text-[12px] text-accent-red" role="alert">{err}</div>}

      {demo && (
        <DemoGuide
          canAct={canAct}
          actions={{
            reset: canAct ? reset : undefined,
            openFhir: () => setFhirOpen(true),
            replay: () => { setAsOf(1); setPlaying(true); scrollTo("ot-risk"); },
            advanceUntilAlert,
            runSim: () => { scrollTo("ot-whatif"); setSimTrigger((n) => n + 1); },
            accept: async () => {
              const id = selectedAlert ?? alerts[0]?.id;
              if (!id) return;
              await ot.act(id, "accept", "Reviewed twin evidence; urgent clinic review arranged (demo).");
              await refreshAll();
            },
            handoff: async () => {
              const id = selectedAlert ?? alerts[0]?.id;
              if (!id) return;
              await ot.handoff(id);
              await refreshAll();
            },
          }}
        />
      )}

      <ReplayBar asOf={d.as_of_day} live={d.live_day} moments={d.key_moments} playing={playing}
        onSeek={(day) => { setPlaying(false); setAsOf(day >= d.live_day ? undefined : day); }}
        onPlay={() => { if (playing) setPlaying(false); else { if (d.as_of_day >= d.live_day) setAsOf(1); setPlaying(true); } }}
        onLive={() => { setPlaying(false); setAsOf(undefined); }} />
      {d.is_replay && (
        <div className="text-[11.5px] text-ink-body">
          Replaying Day {d.as_of_day}: everything below is what the twin knew with data available up to that day.
        </div>
      )}

      <Section id="ot-card" eyebrow="Patient Digital Twin" title="Continuously evolving patient state">
        <TwinCardView d={d} />
      </Section>

      <div className="grid gap-4 xl:grid-cols-[1.5fr_1fr]">
        <Section id="ot-risk" eyebrow="Historical → current → predicted" title={`7-day risk of unplanned acute care (${d.prediction.outcome_id})`}>
          <RiskChart d={d} alerts={alerts} />
        </Section>
        <Section id="ot-confidence" eyebrow="Prediction confidence & data quality" title="How much to trust this prediction">
          <ConfidencePanel d={d} />
        </Section>
      </div>

      <Section id="ot-explain" eyebrow="Explainability" title="What changed? Why?">
        <ExplainPanel d={d} />
      </Section>

      <Section id="ot-signals" eyebrow="Personalised baseline engine" title="Signals against this patient's own normal"
        right={<span className="text-[11px] text-ink-muted hidden md:block">{d.trajectory.analysed_as}</span>}>
        <SignalGrid d={d} />
      </Section>

      <div className="grid gap-4 xl:grid-cols-2">
        <Section id="ot-anc" eyebrow="Mechanistic twin core" title="Neutrophil twin (Friberg model fitted to this patient)">
          <AncChart d={d} />
        </Section>
        <Section id="ot-latent" eyebrow="Physiological state" title="Latent loads inferred from all signals">
          <LatentChart d={d} />
        </Section>
      </div>

      <Section id="ot-whatif" eyebrow="Risk-trajectory simulator" title="What if…? (decision-support simulation)">
        <ScenarioPanel pid={pid} asOf={d.as_of_day} autoRun={simTrigger} />
      </Section>

      <Section id="ot-alerts" eyebrow="Clinician in the loop" title="Alerts, review & ClinCase handoff">
        <AlertPanel alerts={alerts} canAct={canAct} selected={selectedAlert} onSelect={setSelectedAlert}
          onChanged={() => { void load(asOf); setRefreshKey((k) => k + 1); }} />
      </Section>

      <div className="grid gap-4 xl:grid-cols-[1.4fr_1fr]">
        <Section id="ot-timeline" eyebrow="Multimodal timeline" title="EHR · pathology · genomics · labs · treatment · wearables · symptoms · adherence · twin">
          <TimelinePanel pid={pid} asOf={d.as_of_day} refreshKey={refreshKey} />
        </Section>
        <Section id="ot-audit" eyebrow="Security & provenance" title="Prediction audit trail">
          <AuditPanel pid={pid} refreshKey={refreshKey} />
        </Section>
      </div>

      {fhirOpen && <FhirDrawer pid={pid} asOf={d.as_of_day} onClose={() => setFhirOpen(false)} />}
    </div>
  );
}

// =============================================================================
// EHR / FHIR drawer
// =============================================================================

type FhirResource = { resourceType: string; id: string } & Record<string, unknown>;

function describe(r: FhirResource): string {
  const code = (r.code ?? r.medicationCodeableConcept) as { text?: string } | undefined;
  const vq = r.valueQuantity as { value?: number; unit?: string } | undefined;
  const when = (r.effectiveDateTime ?? r.onsetDateTime ?? r.authoredOn ?? r.created ?? r.performedDateTime
    ?? (r.period as { start?: string } | undefined)?.start) as string | undefined;
  return [code?.text ?? (r.title as string | undefined) ?? (r.conclusion as string | undefined) ?? "",
    vq?.value != null ? `${vq.value} ${vq.unit ?? ""}` : "", when?.slice(0, 10) ?? ""].filter(Boolean).join(" · ");
}

function FhirDrawer({ pid, asOf, onClose }: { pid: string; asOf: number; onClose: () => void }) {
  const [entries, setEntries] = useState<FhirResource[]>([]);
  useEffect(() => { ot.fhir(pid, asOf).then((b) => setEntries(b.entry.map((e) => e.resource))).catch(() => undefined); }, [pid, asOf]);
  const counts = entries.reduce<Record<string, number>>((acc, r) => { acc[r.resourceType] = (acc[r.resourceType] ?? 0) + 1; return acc; }, {});
  const shown = entries.filter((r) => r.resourceType !== "MedicationAdministration" || !describe(r).includes("ondansetron"));
  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/30" role="dialog" aria-modal="true" aria-label="EHR and FHIR history" onClick={onClose}>
      <div className="w-full max-w-xl h-full bg-surface-raised border-l border-surface-border p-4 overflow-auto" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-base font-semibold">EHR / FHIR R4 history (as of Day {asOf})</h2>
          <button type="button" onClick={onClose} aria-label="Close" className="p-1 rounded hover:bg-surface-panel"><X size={16} /></button>
        </div>
        <p className="text-[11px] text-ink-muted mb-2">
          Synthetic resources tagged SYNTHETIC. Daily wearable Observations are omitted here for brevity
          (full bundle: GET /api/v1/oncotwin/patients/{pid}/fhir).
        </p>
        <div className="flex flex-wrap gap-1.5 mb-3">
          {Object.entries(counts).map(([t, n]) => (
            <span key={t} className="text-[10.5px] px-2 py-0.5 rounded border border-surface-border text-mono-tech">{t} × {n}</span>
          ))}
        </div>
        <ol className="space-y-1">
          {shown.map((r) => (
            <li key={`${r.resourceType}/${r.id}`} className="text-[11.5px] border-b border-surface-border/60 pb-1">
              <b className="text-mono-tech text-[10.5px]">{r.resourceType}</b> <span className="text-ink-body">{describe(r)}</span>
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
}

// =============================================================================
// Guided demo (3–5 minutes)
// =============================================================================

interface DemoActions {
  reset?: () => Promise<void>;
  openFhir: () => void;
  replay: () => void;
  advanceUntilAlert: () => Promise<void>;
  runSim: () => void;
  accept: () => Promise<void>;
  handoff: () => Promise<void>;
}

function DemoGuide({ actions, canAct }: { actions: DemoActions; canAct: boolean }) {
  const [step, setStep] = useState(0);
  const [running, setRunning] = useState(false);
  const steps: { title: string; say: string; go: () => void | Promise<void> }[] = [
    { title: "Select a synthetic cancer patient",
      say: "OT-001: 52-year-old woman, HER2+ breast cancer, neoadjuvant TCHP. Synthetic — no real person.",
      go: async () => { if (actions.reset) await actions.reset(); scrollTo("ot-card"); } },
    { title: "Show the EHR / FHIR history",
      say: "Diagnosis, pathology, genomics, echo, CarePlan, orders — the static world, as FHIR R4.", go: actions.openFhir },
    { title: "Open the Digital Twin",
      say: "Not a record: a continuously updated state — baseline, treatment, physiology, symptoms, adherence, risk.",
      go: () => scrollTo("ot-card") },
    { title: "Replay the wearable stream",
      say: "Time-travel from Day 1: every day is recomputed with only the data available that day.", go: actions.replay },
    { title: "Show the personalised baseline",
      say: "Each signal is judged against HER normal (Days 1–13), not a population threshold.", go: () => scrollTo("ot-signals") },
    { title: "Introduce the deterioration",
      say: "Advance the twin clock day by day as new wearable, PRO and lab data arrive…", go: actions.advanceUntilAlert },
    { title: "Early warning appears",
      say: "Temperature, resting HR and HRV move together during the neutrophil nadir — one trajectory, not five alarms.",
      go: () => scrollTo("ot-risk") },
    { title: "Why? → evidence",
      say: "What changed, why, versus which baseline, over what period, exact contributions, what to review.",
      go: () => scrollTo("ot-explain") },
    { title: "Run what-if simulations",
      say: "Roll the personalised twin forward: current trajectory vs early intervention and other scenarios.", go: actions.runSim },
    { title: "Clinician HITL decision",
      say: canAct ? "The clinician accepts the alert — recorded with identity and note." : "Sign in as a reviewer to accept.",
      go: async () => { if (canAct) await actions.accept(); scrollTo("ot-alerts"); } },
    { title: "Connect to ClinCase",
      say: "Accepted alert → FHIR bundle + RiskAssessment → ClinCase case for pegfilgrastim → 7-agent PA pipeline.",
      go: async () => { if (canAct) await actions.handoff(); scrollTo("ot-alerts"); } },
    { title: "Complete audit trail",
      say: "Every evaluation, alert, decision and handoff: hash-chained, model-versioned, input-hashed.", go: () => scrollTo("ot-audit") },
  ];
  const s = steps[step];
  const doStep = async () => {
    setRunning(true);
    try { await s.go(); } finally { setRunning(false); }
  };
  return (
    <div className="sticky top-16 z-30 rounded-xl border border-accent-brand bg-surface-raised p-3" style={{ boxShadow: "var(--shadow-raise)" }}>
      <div className="flex items-center gap-3 flex-wrap">
        <Sparkles size={16} aria-hidden />
        <div className="text-[10px] text-compact text-ink-muted">DEMO {step + 1}/{steps.length}</div>
        <div className="flex-1 min-w-[220px]">
          <div className="text-[13px] font-semibold">{s.title}</div>
          <div className="text-[11.5px] text-ink-muted">{s.say}</div>
        </div>
        <button type="button" onClick={doStep} disabled={running}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-accent-brand text-ink-invert text-[12px] font-medium disabled:opacity-60">
          {running ? <Loader2 size={13} className="animate-spin" /> : <Zap size={13} />} Do it
        </button>
        <button type="button" onClick={() => setStep((n) => Math.max(0, n - 1))} disabled={step === 0} className={BTN}>Back</button>
        <button type="button" onClick={() => setStep((n) => Math.min(steps.length - 1, n + 1))} disabled={step === steps.length - 1} className={BTN}>Next</button>
      </div>
      <ol className="mt-2 flex flex-wrap gap-1" aria-label="Demo steps">
        {steps.map((st, i) => (
          <li key={st.title}>
            <button type="button" onClick={() => setStep(i)} aria-current={i === step ? "step" : undefined}
              className={clsx("text-[10px] px-1.5 py-0.5 rounded border", i === step ? "border-accent-brand font-semibold" : "border-surface-border text-ink-muted")}>
              {i + 1}
            </button>
          </li>
        ))}
      </ol>
    </div>
  );
}
