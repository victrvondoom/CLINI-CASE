/**
 * /twin/:patientId/:tab — the patient's Digital Twin, in five views over one shared twin clock:
 *   state      Living Twin State · WHAT CHANGED? · personal baseline · uncertainty · consistency
 *   trajectory risk history + multi-horizon · dynamics · change points · cross-signal · Twin Memory
 *   whatif     what-if builder · counterfactual twin · closed-loop intervention recorder
 *   evidence   WHY NOW? · safety-gated explanation · Patient State Graph · SHOW YOUR WORK · features
 *   clincase   HITL alerts → ClinCase case · clinical/policy context · "what did the twin know?" · audit
 *
 * /twin/demo renders the same page on the flagship synthetic patient OT-005 with a guided,
 * closed-loop walkthrough. Every number on the page comes from the backend twin.
 */
import clsx from "clsx";
import { ArrowLeft, CheckCircle2, ChevronRight, FastForward, History, Loader2, RotateCcw, Sparkles, XCircle, Zap } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { useAuth } from "../components/AuthContext";
import { ot } from "../oncotwin/api";
import {
  ChangePointPanel, Chip, ConflictsPanel, CorrelationPanel, CounterfactualPanel, ExplanationPanel, FeatureTable, HorizonPanel,
  InterventionRecorder, KV, MemoryPanel, Note, ScenarioBuilder, ShowYourWork, StatePanel, StateGraph, TrajectoryNarrative,
  TransitionLedger, UncertaintyPanel, WhatChangedPanel, WhyNowPanel,
} from "../oncotwin/intel";
import {
  AlertPanel, AncChart, AuditPanel, LatentChart, ReplayBar, RiskChart, Section, SignalGrid, TierBadge, TimelinePanel, pct,
} from "../oncotwin/panels";
import type { Dashboard } from "../oncotwin/types";
import type { Intel, Json } from "../oncotwin/types2";

const BTN = "inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md border border-surface-border bg-surface-raised text-[12px] text-ink-body hover:border-accent-brand/60 disabled:opacity-40 focus:outline-none focus:ring-2 focus:ring-accent-brand";
const FLAGSHIP = "ot-005";

export const TABS = [
  { id: "state", label: "Living twin" },
  { id: "trajectory", label: "Trajectory" },
  { id: "whatif", label: "What-if" },
  { id: "evidence", label: "Evidence" },
  { id: "clincase", label: "ClinCase" },
] as const;
type TabId = (typeof TABS)[number]["id"];

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
function scrollTo(id: string) {
  // The target may mount on the next render (after a tab switch); retry briefly.
  let n = 0;
  const go = () => {
    const el = document.getElementById(id);
    if (!el) { if (n++ < 20) setTimeout(go, 100); return; }
    // Land below the sticky demo guide (top-16 = 64 px + its height) when it is on screen.
    const guide = document.querySelector<HTMLElement>("[data-demo-guide]");
    el.style.scrollMarginTop = `${guide ? 64 + guide.offsetHeight + 12 : 96}px`;
    el.scrollIntoView({ behavior: "smooth", block: "start" });
  };
  go();
}

export default function TwinPatient({ demo = false }: { demo?: boolean }) {
  const params = useParams();
  const navigate = useNavigate();
  const pid = demo ? FLAGSHIP : params.patientId ?? FLAGSHIP;
  const [demoTab, setDemoTab] = useState<TabId>("state");
  const tab: TabId = demo ? demoTab : (TABS.some((t) => t.id === params.tab) ? params.tab as TabId : "state");
  const setTab = (t: TabId) => (demo ? setDemoTab(t) : navigate(`/twin/${pid}/${t}`));

  const { user } = useAuth();
  const canAct = user?.role === "reviewer" || user?.role === "admin";

  const [d, setD] = useState<Dashboard | null>(null);
  const [intel, setIntel] = useState<Intel | null>(null);
  const [asOf, setAsOf] = useState<number | undefined>(undefined);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [selectedAlert, setSelectedAlert] = useState<string | null>(null);
  const loadSeq = useRef(0);

  const load = useCallback(async (day?: number) => {
    const seq = ++loadSeq.current;
    try {
      const [dash, it] = await Promise.all([ot.dashboard(pid, day), ot.intelligence(pid, day)]);
      if (seq === loadSeq.current) { setD(dash); setIntel(it); setErr(null); }
      return { dash, it };
    } catch (e) {
      if (seq === loadSeq.current) setErr((e as Error).message);
      return null;
    }
  }, [pid]);

  useEffect(() => { void load(asOf); }, [load, asOf]);
  useEffect(() => { setAsOf(undefined); setSelectedAlert(null); setNotice(null); }, [pid]);

  useEffect(() => {
    if (!playing || !d) return;
    if ((asOf ?? d.live_day) >= d.live_day) { setPlaying(false); setAsOf(undefined); return; }
    const t = setTimeout(() => setAsOf((a) => Math.min((a ?? 1) + 1, d.live_day)), 900);
    return () => clearTimeout(t);
  }, [playing, asOf, d]);

  const refreshAll = async () => { setAsOf(undefined); const r = await load(); setRefreshKey((k) => k + 1); return r; };
  const run = async (label: string, fn: () => Promise<string | void>) => {
    setBusy(label); setNotice(null); setErr(null);
    try { const msg = await fn(); if (msg) setNotice(msg); } catch (e) { setErr((e as Error).message); } finally { setBusy(null); }
  };

  const advance = (n: number) => run(`advance${n}`, async () => {
    const r = await ot.advance(pid, n);
    await refreshAll();
    if (r.alerts.length) setSelectedAlert(r.alerts.at(-1) ?? null);
    const last = r.evaluations.at(-1);
    return last
      ? `Twin clock → Day ${r.live_day}: ${last.tier} (${pct(last.risk, 1)})${r.alerts.length ? ". ALERT raised." : "."}`
      : "End of the synthetic feed.";
  });

  if (!d || !intel) {
    return (
      <div className="px-6 py-10 text-ink-muted text-sm flex items-center gap-2">
        {err ? <span className="text-accent-red" role="alert">{err}</span> : <><Loader2 size={16} className="animate-spin" aria-hidden /> Building the digital twin…</>}
      </div>
    );
  }

  const alerts = d.alerts;
  const who = `${d.patient.label}: ${d.patient.age}${d.patient.sex === "female" ? "F" : "M"}, ${d.patient.cancer}, ${d.patient.regimen_code}`;
  const demoActions: DemoActions = {
    setTab,
    reset: async () => { await ot.reset(); setSelectedAlert(null); await refreshAll(); },
    advanceUntilAlert: async () => {
      for (let i = 0; i < 10; i++) {
        const r = await ot.advance(pid, 1);
        await refreshAll();
        if (r.alerts.length) {
          setSelectedAlert(r.alerts[0]);
          const e = r.evaluations.at(-1);
          return `Day ${r.live_day}: the twin escalated to ${e?.tier ?? "an alert tier"} (${pct(e?.risk, 1)}) and raised an alert.`;
        }
        if (!r.evaluations.length) return "End of the synthetic feed.";
        await sleep(350);
      }
      return "No alert within 10 days.";
    },
    acceptAndIntervene: async () => {
      const id = selectedAlert ?? alerts.find((a) => a.status === "open")?.id ?? alerts[0]?.id;
      if (!id) return "No alert to act on yet: advance the clock first.";
      await ot.act(id, "accept", "Reviewed twin evidence; patient seen urgently (synthetic demo).");
      const a = await ot.recordIntervention(pid, "urgent_eval_abx", "Urgent evaluation; empiric oral antibiotics started (synthetic demo).", id);
      await ot.recordIntervention(pid, "gcsf", "G-CSF given (synthetic demo).", id);
      await refreshAll();
      return `Alert accepted. Interventions recorded, effective from Day ${a.intervention.effective_from_day}; past data verified unchanged: ${a.intervention.past_data_unchanged ? "yes" : "NO"}.`;
    },
    advanceAfterIntervention: async () => {
      const r = await ot.advance(pid, 4);
      await refreshAll();
      return `Twin clock → Day ${r.live_day}: ${r.evaluations.map((e) => `D${e.as_of_day} ${e.tier} ${pct(e.risk, 1)}`).join(" · ")}`;
    },
    handoff: async () => {
      const id = alerts.find((a) => a.status === "accepted")?.id ?? selectedAlert ?? alerts[0]?.id;
      if (!id) return "No accepted alert to hand off.";
      const h = await ot.handoff(id);
      await refreshAll();
      return `ClinCase case ${h.handoff.case_id} created for ${h.handoff.requested_treatment.name} with ${h.handoff.policy_preview.length} retrieved policy sections${h.already_handed_off ? " (already handed off)" : ""}.`;
    },
  };

  return (
    <div className="px-4 sm:px-6 py-5 space-y-4">
      <header className="flex items-start justify-between gap-3 flex-wrap">
        <div className="min-w-0">
          <Link to="/twin" className="text-[11px] text-ink-muted hover:text-ink-primary inline-flex items-center gap-1"><ArrowLeft size={12} aria-hidden /> Command Center</Link>
          <h1 className="text-2xl font-semibold text-ink-primary leading-tight flex items-center gap-2 flex-wrap">
            {d.patient.label} · Digital Twin <TierBadge tier={d.card.current_state.tier} />
            <Chip strong={intel.triage.category !== "Stable"}>{intel.triage.category}</Chip>
          </h1>
          <p className="text-[12px] text-ink-muted max-w-3xl">{d.patient.age}{d.patient.sex === "female" ? "F" : "M"} · {d.patient.cancer} · {d.patient.regimen_code}. {d.patient.narrative}</p>
          <p className="text-[11px] text-mono-tech text-ink-muted mt-1">
            twin clock Day {d.live_day}/{d.n_days} · state …{intel.state.sha256.slice(0, 10)} · readiness {pct(intel.readiness.score)} ({intel.readiness.label}) ·
            model {d.provenance.model.model_id} v{d.provenance.model.version}{d.provenance.model.integrity_verified ? " (verified)" : " (UNVERIFIED)"}
          </p>
        </div>
        <div className="flex flex-wrap gap-2 items-center">
          <button type="button" onClick={() => advance(1)} disabled={busy !== null || d.live_day >= d.n_days} className={BTN}>
            {busy === "advance1" ? <Loader2 size={13} className="animate-spin" aria-hidden /> : <ChevronRight size={13} aria-hidden />} +1 day
          </button>
          <button type="button" onClick={() => advance(3)} disabled={busy !== null || d.live_day >= d.n_days} className={BTN}>
            {busy === "advance3" ? <Loader2 size={13} className="animate-spin" aria-hidden /> : <FastForward size={13} aria-hidden />} +3 days
          </button>
          <Link to={demo ? "/twin/demo/classic" : `/twin/${pid}/classic`} className={BTN}><History size={13} aria-hidden /> Classic view</Link>
          {canAct && (
            <button type="button" onClick={() => run("reset", async () => { await demoActions.reset(); return "Demo state reset (the audit ledger is kept)."; })}
              disabled={busy !== null} className={BTN}><RotateCcw size={13} aria-hidden /> Reset demo</button>
          )}
        </div>
      </header>

      <div className="text-[11px] px-3 py-1.5 rounded-md border border-dashed border-surface-border-hi text-ink-body">
        {intel.synthetic_notice} Clinical decision support only: every alert requires clinician review, and nothing here is a diagnosis.
      </div>
      {notice && <div className="text-[12px] px-3 py-2 rounded-md bg-accent-brand/10 border border-accent-brand/40" role="status">{notice}</div>}
      {err && <div className="text-[12px] text-accent-red" role="alert">{err}</div>}

      {demo && <FlagshipGuide who={who} canAct={canAct} actions={demoActions} busy={busy !== null} run={run} />}

      <ReplayBar asOf={d.as_of_day} live={d.live_day} moments={d.key_moments} playing={playing}
        onSeek={(day) => { setPlaying(false); setAsOf(day >= d.live_day ? undefined : day); }}
        onPlay={() => { if (playing) setPlaying(false); else { if (d.as_of_day >= d.live_day) setAsOf(1); setPlaying(true); } }}
        onLive={() => { setPlaying(false); setAsOf(undefined); }} />
      {d.is_replay && <div className="text-[11.5px] text-ink-body">Replaying Day {d.as_of_day}: everything below is what the twin knew with data available up to that day.</div>}

      <nav className="flex gap-1 border-b border-surface-border overflow-x-auto" aria-label="Twin views">
        {TABS.map((t) => (
          <button key={t.id} type="button" onClick={() => setTab(t.id)} aria-current={tab === t.id ? "page" : undefined}
            className={clsx("px-3 py-2 text-[12.5px] -mb-px border-b-2 whitespace-nowrap focus:outline-none focus:ring-2 focus:ring-accent-brand rounded-t",
              tab === t.id ? "border-ink-primary text-ink-primary font-semibold" : "border-transparent text-ink-muted hover:text-ink-primary")}>
            {t.label}
          </button>
        ))}
      </nav>

      {tab === "state" && (
        <>
          <Section id="ot-state" eyebrow="Living Twin State · 19 dimensions · never overwritten" title="The patient, as the twin understands them today">
            <StatePanel intel={intel} />
          </Section>
          <div className="grid gap-4 xl:grid-cols-[1fr_1.4fr]">
            <Section id="ot-what-changed" eyebrow="WHAT CHANGED?" title="Previous twin state → current twin state">
              <WhatChangedPanel wc={intel.what_changed} />
            </Section>
            <Section id="ot-transitions" eyebrow="Twin state ledger" title="Recent transitions (timestamp · source · reason · confidence)">
              <TransitionLedger rows={intel.transitions_recent} />
            </Section>
          </div>
          <Section id="ot-signals" eyebrow="Personalised baseline" title="Every signal against this patient's own normal"
            right={<span className="text-[11px] text-ink-muted hidden md:block">{d.trajectory.analysed_as}</span>}>
            <SignalGrid d={d} />
          </Section>
          <Section id="ot-uncertainty" eyebrow="Uncertainty engine · Twin Readiness (Twin Data Quality)" title="How much to trust the twin today">
            <UncertaintyPanel u={intel.uncertainty} rd={intel.readiness} />
          </Section>
          <Section id="ot-consistency" eyebrow="Trajectory conflicts · twin consistency" title="Do the data sources agree with each other?">
            <ConflictsPanel conflicts={intel.conflicts} consistency={intel.consistency} />
          </Section>
          <Section id="ot-timeline" eyebrow="Multimodal temporal fusion" title="EHR · pathology · genomics · labs · treatment · wearables · symptoms · adherence · twin">
            <TimelinePanel pid={pid} asOf={d.as_of_day} refreshKey={refreshKey} />
          </Section>
        </>
      )}

      {tab === "trajectory" && (
        <>
          <div className="grid gap-4 xl:grid-cols-[1.5fr_1fr]">
            <Section id="ot-risk" eyebrow="Historical → current → predicted" title={`7-day risk of unplanned acute care (${d.prediction.outcome_id})`}>
              <RiskChart d={d} alerts={alerts} />
            </Section>
            <Section id="ot-horizons" eyebrow="Multi-horizon prediction" title="Only the horizons the data can support">
              <HorizonPanel hz={intel.horizons} />
            </Section>
          </div>
          <Section id="ot-dynamics" eyebrow="Trajectory engine" title="Where the patient is heading">
            <TrajectoryNarrative tr={intel.trajectory} />
          </Section>
          <Section id="ot-changepoints" eyebrow="Change-point intelligence (BOCPD)" title="When did this patient's trajectory change?">
            <ChangePointPanel cp={intel.change_points} />
          </Section>
          <Section id="ot-correlation" eyebrow="Cross-signal intelligence" title="Which signals moved together (associations, not causes)">
            <CorrelationPanel co={intel.correlation} />
          </Section>
          <Section id="ot-memory" eyebrow="Twin Memory · recovery velocity" title="How this patient responded to previous cycles">
            <MemoryPanel mem={intel.memory} />
          </Section>
          <div className="grid gap-4 xl:grid-cols-2">
            <Section id="ot-anc" eyebrow="Mechanistic twin core" title="Neutrophil twin (Friberg model fitted to this patient)">
              <AncChart d={d} />
            </Section>
            <Section id="ot-latent" eyebrow="Physiological state" title="Latent loads inferred from all signals">
              <LatentChart d={d} />
            </Section>
          </div>
        </>
      )}

      {tab === "whatif" && (
        <>
          <Section id="ot-whatif" eyebrow="What-if simulation" title="Configure a scenario and compare it with the predefined ones">
            <ScenarioBuilder pid={pid} asOf={d.as_of_day} />
          </Section>
          <Section id="ot-counterfactual" eyebrow="Counterfactual twin" title="Observed twin vs a twin in which nothing changed">
            <CounterfactualPanel pid={pid} live={d.live_day} />
          </Section>
          <Section id="ot-loop" eyebrow="Clinical digital-twin loop" title="Record a clinical intervention (the twin then observes the response)">
            <InterventionRecorder pid={pid} canAct={canAct} alerts={alerts.map((a) => ({ id: a.id, tier: a.tier, as_of_day: a.as_of_day }))}
              onDone={() => { void load(asOf); setRefreshKey((k) => k + 1); }} />
            {intel.interventions.length > 0 && (
              <ul className="mt-3 text-[12px] list-disc ml-4">
                {intel.interventions.map((i: Json) => (
                  <li key={i.id}>{i.label}: effective Day {i.effective_from_day}, recorded on twin Day {i.recorded_at_twin_day}{i.note ? `: “${i.note}”` : ""}</li>
                ))}
              </ul>
            )}
          </Section>
        </>
      )}

      {tab === "evidence" && (
        <>
          <Section id="ot-why-now" eyebrow="WHY NOW?" title={`${intel.why_now.tier} on Day ${intel.why_now.as_of_day}`}>
            <WhyNowPanel w={intel.why_now} readiness={intel.readiness} />
          </Section>
          <Section id="ot-explanation" eyebrow="Explanation agent · safety gates" title="Plain-language explanation (every number traceable)">
            <ExplanationPanel pid={pid} asOf={d.as_of_day} />
          </Section>
          <Section id="ot-graph" eyebrow="Patient State Graph" title="Facts, measurements, model estimates and how they relate">
            <StateGraph graph={intel.graph} />
          </Section>
          <Section id="ot-review" eyebrow="Evidence" title="What a clinician may want to review">
            <ul className="text-[12.5px] list-disc ml-4 space-y-0.5">{intel.review.map((r) => <li key={r}>{r}</li>)}</ul>
          </Section>
          <ShowYourWork sw={intel.show_your_work} />
          <Section id="ot-features" eyebrow="Feature store" title="Timestamped, versioned, traceable features for this patient-day">
            <FeatureTable pid={pid} asOf={d.as_of_day} />
          </Section>
        </>
      )}

      {tab === "clincase" && (
        <>
          <Section id="ot-alerts" eyebrow="Clinician in the loop" title="Alerts, review & ClinCase handoff">
            <AlertPanel alerts={alerts} canAct={canAct} selected={selectedAlert} onSelect={setSelectedAlert}
              onChanged={() => { void load(asOf); setRefreshKey((k) => k + 1); }} />
          </Section>
          <Section id="ot-context" eyebrow="Clinical context agent · ClinCase reuse" title="What a ClinCase case would contain">
            <ClinicalContextPanel pid={pid} asOf={d.as_of_day} refreshKey={refreshKey} />
          </Section>
          <Section id="ot-knowledge" eyebrow="Audit" title="What did the Digital Twin know at that moment?">
            <KnowledgePanel pid={pid} defaultDay={d.as_of_day} refreshKey={refreshKey} />
          </Section>
          <Section id="ot-audit" eyebrow="Security & provenance" title="Hash-chained audit ledger">
            <AuditPanel pid={pid} refreshKey={refreshKey} />
          </Section>
        </>
      )}
    </div>
  );
}

// =============================================================================
// ClinCase integration panels
// =============================================================================

function ClinicalContextPanel({ pid, asOf, refreshKey }: { pid: string; asOf: number; refreshKey: number }) {
  const [c, setC] = useState<Json | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    let live = true;
    ot.clinicalContext(pid, asOf).then((r) => live && setC(r)).catch((e) => live && setErr((e as Error).message));
    return () => { live = false; };
  }, [pid, asOf, refreshKey]);
  if (err) return <div className="text-[12px] text-accent-red" role="alert">{err}</div>;
  if (!c) return <div className="text-[12px] text-ink-muted flex items-center gap-2"><Loader2 size={13} className="animate-spin" aria-hidden /> Loading…</div>;
  const t = c.treatment;
  const req = c.clincase_request_if_accepted;
  return (
    <div className="space-y-3">
      <div className="grid gap-2 md:grid-cols-3 text-[12px]">
        <KV label="Regimen" v={`${t.regimen.name} (${t.regimen.code}) · myelosuppression ${t.regimen.myelosuppression_tier} (${t.regimen.tier_basis})`} />
        <KV label="Cycle" v={`cycle ${t.cycle_number}, day ${t.day_of_cycle ?? "—"} · last dose Day ${t.last_dose_day ?? "—"} · next Day ${t.next_planned_dose_day ?? "—"}${t.in_expected_nadir_window ? " · nadir window" : ""}`} />
        <KV label="Current twin tier" v={`${c.tier} (Day ${c.as_of_day})`} />
      </div>
      {req ? (
        <div className="rounded-lg border border-surface-border p-3 text-[12px]">
          <div className="text-[10px] text-compact text-ink-faint">If a clinician accepts the alert, the ClinCase case would request</div>
          <div className="text-ink-primary font-semibold">{req.name} · {req.hcpcs_code} · {req.dose}</div>
          <div className="text-ink-muted">{req.intent}</div>
          <div className="text-ink-body mt-1">{c.rationale}</div>
        </div>
      ) : <div className="text-[12px] text-ink-muted">{c.rationale ?? "No ClinCase request applies to the current twin state."}</div>}
      {c.policy_preview?.length > 0 && (
        <div>
          <div className="text-[11px] text-ink-muted mb-1">Policy sections retrieved by the existing ClinCase policy retrieval ({c.payer_id})</div>
          <ul className="space-y-1">{c.policy_preview.map((p: Json, i: number) => (
            <li key={i} className="text-[11.5px] border-l-2 border-surface-border-hi pl-2">
              <b>{p.policy_title}</b> · {p.section_heading}{p.page_number ? ` · p.${p.page_number}` : ""}<div className="text-ink-muted">{p.excerpt}</div>
            </li>))}</ul>
        </div>)}
      <ol className="flex flex-wrap items-center gap-1 text-[11px]" aria-label="Integration flow">
        {c.flow.map((f: string, i: number) => (
          <li key={f} className="inline-flex items-center gap-1"><span className="px-2 py-0.5 rounded border border-surface-border bg-surface-bg">{f}</span>
            {i < c.flow.length - 1 && <ChevronRight size={11} className="text-ink-faint" aria-hidden />}</li>))}
      </ol>
      {c.handoffs.length > 0 && (
        <div className="text-[12px]"><div className="text-[11px] text-ink-muted">ClinCase cases created from this twin</div>
          <ul className="list-disc ml-4">{c.handoffs.map((h: Json) => (
            <li key={h.case_id}><Link className="underline" to={`/cases/${h.case_id}`}>{h.case_id}</Link>: {h.requested_treatment?.name}, created {String(h.created_at).slice(0, 16).replace("T", " ")} by {h.created_by}</li>))}</ul>
        </div>)}
      <Note>{c.note}</Note>
    </div>
  );
}

function KnowledgePanel({ pid, defaultDay, refreshKey }: { pid: string; defaultDay: number; refreshKey: number }) {
  const [day, setDay] = useState<number>(defaultDay);
  const [k, setK] = useState<Json | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const fetchK = async (q: { day?: number; entry_id?: string }) => {
    setBusy(true); setErr(null);
    try { setK(await ot.knowledge(pid, q)); } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  };
  useEffect(() => { setDay(defaultDay); void fetchK({ day: defaultDay }); }, [pid, defaultDay, refreshKey]); // eslint-disable-line react-hooks/exhaustive-deps
  const knew = k?.what_the_twin_knew;
  return (
    <div className="space-y-3 text-[12px]">
      <div className="flex flex-wrap items-end gap-2">
        <label className="flex flex-col gap-0.5">Twin day<input type="number" min={1} value={day} onChange={(e) => setDay(Number(e.target.value) || 1)}
          className="rounded border border-surface-border bg-surface-bg px-2 py-1 w-28" /></label>
        <button type="button" className={BTN} onClick={() => fetchK({ day })} disabled={busy}>{busy ? <Loader2 size={13} className="animate-spin" aria-hidden /> : <History size={13} aria-hidden />} Show</button>
      </div>
      {err && <div className="text-accent-red" role="alert">{err}</div>}
      {k && knew && (
        <>
          <div className="grid gap-2 md:grid-cols-3">
            <KV label="Twin time" v={`${k.twin_time} (Day ${k.as_of_day})`} />
            <KV label="Prediction then" v={`${knew.prediction.tier} · ${pct(knew.prediction.risk, 1)} (80% ${pct(knew.prediction.risk_p10, 1)}–${pct(knew.prediction.risk_p90, 1)})`} />
            <KV label="Inputs" v={`${knew.inputs.length} observations/events, Days ${knew.feature_window_days[0]}–${knew.feature_window_days[1]} · state …${String(knew.state.sha256).slice(0, 12)}`} />
          </div>
          <div>
            <div className="text-[11px] text-ink-muted mb-1">Ledgered evaluations on Day {k.as_of_day}: select one to reproduce it bit-for-bit</div>
            {k.evaluations_on_this_day.length === 0 ? <div className="text-ink-muted">No evaluation was committed on this day (the twin clock has not passed it in this session).</div> : (
              <ul className="space-y-1">{k.evaluations_on_this_day.map((e: Json) => (
                <li key={e.id} className="flex flex-wrap items-center gap-2">
                  <span className="text-mono-tech text-[11px]">{e.id}</span><span>{e.tier} · {pct(e.risk, 1)}</span>
                  <span className="text-ink-muted text-[11px]">{e.trigger}</span>
                  <button type="button" className={BTN} onClick={() => fetchK({ entry_id: e.id })} disabled={busy}>Reproduce</button>
                </li>))}</ul>)}
          </div>
          {k.reproduction && (
            <div className="rounded-lg border border-ink-primary/60 p-3">
              <div className="flex items-center gap-2 font-semibold text-ink-primary">
                {k.reproduction.reproduced ? <CheckCircle2 size={15} aria-hidden /> : <XCircle size={15} aria-hidden />}
                {k.reproduction.reproduced ? "Reproduced exactly" : "Not reproduced"}
              </div>
              <div className="flex flex-wrap gap-1.5 mt-1">{Object.entries(k.reproduction.checks as Record<string, boolean | null>).map(([name, ok]) => (
                <Chip key={name} strong={ok === false}>{ok == null ? "–" : ok ? "✓" : "✗"} {name.replace(/_/g, " ")}</Chip>))}</div>
              <Note>{k.reproduction.explanation} Ledger chain {k.chain_verification?.valid ? "valid" : "INVALID"} ({k.chain_verification?.entries} entries); entry hash …{String(k.recorded?.hash).slice(0, 12)}.</Note>
            </div>)}
        </>
      )}
    </div>
  );
}

// =============================================================================
// Flagship guided demo (OT-005, closed loop)
// =============================================================================

interface DemoActions {
  setTab: (t: TabId) => void;
  reset: () => Promise<void>;
  advanceUntilAlert: () => Promise<string>;
  acceptAndIntervene: () => Promise<string>;
  advanceAfterIntervention: () => Promise<string>;
  handoff: () => Promise<string>;
}

function FlagshipGuide({ who, actions, canAct, busy, run }: {
  who: string; actions: DemoActions; canAct: boolean; busy: boolean; run: (label: string, fn: () => Promise<string | void>) => Promise<void>;
}) {
  const [step, setStep] = useState(0);
  const view = (t: TabId, id: string) => async () => { actions.setTab(t); scrollTo(id); };
  const steps: { title: string; say: string; go: () => Promise<string | void> }[] = [
    { title: "Meet the flagship synthetic patient",
      say: `${who}. Not a real person. The demo starts from a clean state.`,
      go: async () => {
        if (canAct) await actions.reset();
        actions.setTab("state"); scrollTo("ot-state");
        return canAct ? "Demo state reset." : "Sign in as a reviewer or admin to reset; continuing with the current state.";
      } },
    { title: "The Living Twin State",
      say: "19 dimensions: recorded facts, measurements against this patient's own baseline, and model estimates, each with its source, confidence and data quality. States are ledgered, never overwritten.",
      go: view("state", "ot-state") },
    { title: "The personal baseline",
      say: "Every signal is judged against this patient's own normal, not a population threshold.", go: view("state", "ot-signals") },
    { title: "Advance the twin clock",
      say: "New wearable, home, symptom and lab data arrive as events; the twin updates incrementally each day until it escalates.",
      go: async () => { actions.setTab("trajectory"); const m = await actions.advanceUntilAlert(); scrollTo("ot-risk"); return m; } },
    { title: "WHY NOW?",
      say: "Which signals moved against the baseline, for how long, in which treatment phase, under which model, and with what confidence.",
      go: view("evidence", "ot-why-now") },
    { title: "WHAT CHANGED? + change points",
      say: "The Bayesian change point that marks when this patient's trajectory shifted.",
      go: view("trajectory", "ot-changepoints") },
    { title: "Twin Memory",
      say: "How this cycle compares with the patient's earlier response. Similarity is statistical, not clinical equivalence.", go: view("trajectory", "ot-memory") },
    { title: "WHAT IF?",
      say: "Configure a scenario and roll the personalised twin forward. This is a simulation, not a prediction or a recommendation.",
      go: view("whatif", "ot-whatif") },
    { title: "The clinician decides (HITL)",
      say: canAct ? "The clinician accepts the alert and records urgent evaluation with antibiotics, then G-CSF. Past data stays verified unchanged."
        : "Sign in as a reviewer to accept the alert and record interventions.",
      go: async () => { if (!canAct) return "Reviewer or admin role required."; actions.setTab("whatif"); const m = await actions.acceptAndIntervene(); scrollTo("ot-loop"); return m; } },
    { title: "The twin observes the response",
      say: "Advance four days: the twin sees the recorded intervention take effect in the incoming data.",
      go: async () => { actions.setTab("trajectory"); const m = await actions.advanceAfterIntervention(); scrollTo("ot-risk"); return m; } },
    { title: "Counterfactual twin",
      say: "The observed twin against a twin in which nothing changed, checked against the generator's ground truth (possible only for synthetic patients).",
      go: view("whatif", "ot-counterfactual") },
    { title: "ClinCase handoff",
      say: "The accepted alert becomes a ClinCase prior-authorisation case, reusing ClinCase's FHIR, policy-retrieval and agent pipeline.",
      go: async () => { if (!canAct) return "Reviewer or admin role required."; actions.setTab("clincase"); const m = await actions.handoff(); scrollTo("ot-context"); return m; } },
    { title: "What did the twin know?",
      say: "Pick a ledgered evaluation and reproduce it bit-for-bit: inputs, model artifact, state hash, risk and tier.",
      go: view("clincase", "ot-knowledge") },
  ];
  const s = steps[step];
  return (
    <div data-demo-guide className="sticky top-16 z-30 rounded-xl border border-accent-brand bg-surface-raised p-3" style={{ boxShadow: "var(--shadow-raise)" }}>
      <div className="flex items-center gap-3 flex-wrap">
        <Sparkles size={16} aria-hidden />
        <div className="text-[10px] text-compact text-ink-muted">GUIDED DEMO {step + 1}/{steps.length}</div>
        <div className="flex-1 min-w-[220px]">
          <div className="text-[13px] font-semibold">{s.title}</div>
          <div className="text-[11.5px] text-ink-muted">{s.say}</div>
        </div>
        <button type="button" disabled={busy}
          onClick={() => run(`demo${step}`, async () => { const m = await s.go(); setStep((n) => Math.min(steps.length - 1, n + 1)); return m; })}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-accent-brand text-ink-invert text-[12px] font-medium disabled:opacity-60">
          {busy ? <Loader2 size={13} className="animate-spin" aria-hidden /> : <Zap size={13} aria-hidden />} Do it
        </button>
        <button type="button" onClick={() => setStep((n) => Math.max(0, n - 1))} disabled={step === 0} className={BTN}>Back</button>
        <button type="button" onClick={() => setStep((n) => Math.min(steps.length - 1, n + 1))} disabled={step === steps.length - 1} className={BTN}>Next</button>
      </div>
      <ol className="mt-2 flex flex-wrap gap-1" aria-label="Demo steps">
        {steps.map((st, i) => (
          <li key={st.title}>
            <button type="button" onClick={() => setStep(i)} aria-current={i === step ? "step" : undefined} title={st.title}
              className={clsx("text-[10px] px-1.5 py-0.5 rounded border", i === step ? "border-accent-brand font-semibold" : i < step ? "border-surface-border-hi" : "border-surface-border text-ink-muted")}>
              {i + 1}
            </button>
          </li>
        ))}
      </ol>
    </div>
  );
}
