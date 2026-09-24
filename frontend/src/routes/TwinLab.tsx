/**
 * /twin/lab — OncoTwin Research Lab. Shows the committed benchmark (research/results/benchmark_v1.json):
 * modality benchmark, ablation, personalisation, comparators, horizons, lead time, change-point
 * detection, neutrophil-twin forecasting and latent-state recovery, each with patient-bootstrap CIs and
 * paired differences against the multimodal twin. Admins can run a new experiment on the same split.
 * Everything is a SYNTHETIC identical-twin experiment: it demonstrates the method, not clinical performance.
 */
import clsx from "clsx";
import { ArrowLeft, FlaskConical, Loader2, Play } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { useAuth } from "../components/AuthContext";
import { ot } from "../oncotwin/api";
import { Chip, KV, Note } from "../oncotwin/intel";
import { Section, pct } from "../oncotwin/panels";
import type { Json } from "../oncotwin/types2";

const BTN = "inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md border border-surface-border bg-surface-raised text-[12px] text-ink-body hover:border-accent-brand/60 disabled:opacity-40 focus:outline-none focus:ring-2 focus:ring-accent-brand";
const TH = "text-right px-2 py-1 font-medium text-ink-muted text-[10.5px] whitespace-nowrap";
const TD = "text-right px-2 py-1 nums-tabular whitespace-nowrap";
const f3 = (v: number | null | undefined) => (v == null ? "—" : v.toFixed(3));
// A rule-based arm (no continuous score) has no AUROC: the backend reports null and we show "—".
const ci = (c?: (number | null)[] | null) =>
  (c && c.length === 2 && c[0] != null && c[1] != null ? `${c[0].toFixed(3)}–${c[1].toFixed(3)}` : "—");

interface Arm { config: Json; metrics: Json; paired_vs_multimodal?: Json; paired_vs_reference?: Json }

export default function TwinLab() {
  const [r, setR] = useState<Json | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { ot.researchResults().then(setR).catch((e) => setErr((e as Error).message)); }, []);
  const refArm: Arm | undefined = r?.modality_benchmark?.find((a: Arm) => a.config.name === r.reference_arm);

  return (
    <div className="px-4 sm:px-6 py-6 space-y-4">
      <header className="max-w-3xl">
        <Link to="/twin" className="text-[11px] text-ink-muted hover:text-ink-primary inline-flex items-center gap-1"><ArrowLeft size={12} aria-hidden /> Command Center</Link>
        <h1 className="text-2xl font-semibold text-ink-primary flex items-center gap-2"><FlaskConical size={22} aria-hidden /> OncoTwin Research Lab</h1>
        <p className="text-[12.5px] text-ink-body mt-1">Does the digital twin earn its complexity? Every arm is trained and tested on the same patients, and every difference is paired.</p>
      </header>
      {err && <div className="text-[12px] text-accent-red" role="alert">{err}</div>}
      {!r && !err && <div className="text-[12px] text-ink-muted flex items-center gap-2"><Loader2 size={14} className="animate-spin" aria-hidden /> Loading results…</div>}

      {r && (
        <>
          <div className="text-[11.5px] px-3 py-1.5 rounded-md border border-dashed border-surface-border-hi text-ink-body">{r.data_notice}</div>
          <div className="grid gap-2 md:grid-cols-4 text-[12px]">
            <KV label="Dataset" v={`${r.dataset.dataset_id} · version ${r.dataset.version}`} />
            <KV label="Patients / test events" v={`${r.dataset.n_patients} synthetic patients · ${r.dataset.n_events} test events`} />
            <KV label="Split" v={r.dataset.split_rule} />
            <KV label="Reference arm" v={`${r.reference_arm} · deployed ${r.deployed_model.model_id} v${r.deployed_model.version}`} />
          </div>

          <Section eyebrow="Modality benchmark" title="Static context vs clinical-only vs wearable-only vs remote monitoring vs the multimodal twin">
            <ForestPlot arms={r.modality_benchmark} reference={r.reference_arm} />
            <ArmTable arms={r.modality_benchmark} reference={r.reference_arm} />
          </Section>

          <Section eyebrow="Ablation" title="Remove one modality at a time from the multimodal twin">
            <ForestPlot arms={r.ablation} reference={r.reference_arm} refAuroc={refArm?.metrics.auroc} />
            <ArmTable arms={r.ablation} reference={r.reference_arm} />
          </Section>

          <div className="grid gap-4 xl:grid-cols-2">
            <Section eyebrow="Personalisation benchmark" title={r.personalization.question}>
              <ArmTable arms={[r.personalization.personal, r.personalization.population]} compact reference={r.reference_arm} />
              <Note>A non-significant difference is reported as a finding, not hidden.</Note>
            </Section>
            <Section eyebrow="Comparators" title="Simpler systems on the same patients">
              <ArmTable arms={r.comparators} compact reference={r.reference_arm} />
            </Section>
          </div>

          <div className="grid gap-4 xl:grid-cols-2">
            <Section eyebrow="Calibration" title={`Reliability of the ${r.reference_arm}`}>
              <Calibration bins={refArm?.metrics.calibration ?? []} />
            </Section>
            <Section eyebrow="Lead-time metric" title="How many days before the event did the twin first alert?">
              <LeadTime lt={r.lead_time} />
            </Section>
          </div>

          <Section eyebrow="Multi-horizon prediction" title="Per-horizon logistic models vs the monotone survival model">
            <ArmTable arms={r.horizons.per_horizon_logistic} compact />
            <div className="overflow-x-auto mt-2"><table className="w-full text-[11.5px]">
              <thead><tr><th className={clsx(TH, "text-left")}>Survival model (held-out)</th><th className={TH}>AUROC (95% CI)</th><th className={TH}>AUPRC</th><th className={TH}>Brier</th><th className={TH}>Positives</th><th className={TH}>Prevalence</th></tr></thead>
              <tbody>{Object.entries(r.horizons.survival_model_test_metrics as Record<string, Json>).filter(([k]) => k !== "data").map(([k, m]) => (
                <tr key={k} className="border-t border-surface-border/60"><td className="px-2 py-1">{k}</td><td className={TD}>{f3(m.auroc)} ({ci(m.auroc_95ci_patient_bootstrap)})</td>
                  <td className={TD}>{f3(m.auprc)}</td><td className={TD}>{m.brier}</td><td className={TD}>{m.n_positive}</td><td className={TD}>{pct(m.prevalence, 2)}</td></tr>))}</tbody>
            </table></div>
            <Note>{r.horizons.survival_model_test_metrics.data}. No 6-hour horizon is offered because the signals are daily aggregates.</Note>
          </Section>

          <div className="grid gap-4 xl:grid-cols-3">
            <Section eyebrow="Change-point detection" title="BOCPD vs CUSUM against generator onsets">
              <table className="w-full text-[11.5px]">
                <thead><tr><th className={clsx(TH, "text-left")}>Method</th><th className={TH}>Sensitivity</th><th className={TH}>Median delay</th><th className={TH}>False / 100 pd</th></tr></thead>
                <tbody>{(["bocpd", "cusum"] as const).map((k) => {
                  const m = r.change_point_detection[k];
                  return (<tr key={k} className="border-t border-surface-border/60"><td className="px-2 py-1 uppercase">{k}</td><td className={TD}>{pct(m.sensitivity, 1)} ({m.detected}/{r.change_point_detection.n_truth_onsets})</td>
                    <td className={TD}>{m.median_detection_delay_days} d</td><td className={TD}>{m.false_detections_per_100_patient_days}</td></tr>);
                })}</tbody>
              </table>
              <Note>{r.change_point_detection.truth_definition}; {r.change_point_detection.match_rule}. {r.change_point_detection.treatment_explained_change_points} change points coincided with chemotherapy and were not counted as false.</Note>
            </Section>
            <Section eyebrow="Neutrophil twin" title="Forecasting the next ANC lab">
              <table className="w-full text-[11.5px]">
                <thead><tr><th className={clsx(TH, "text-left")}>Method</th><th className={TH}>MAE (log ANC)</th><th className={TH}>Median fold error</th></tr></thead>
                <tbody>{Object.keys(r.neutrophil_twin.mae_log_anc).map((k) => (
                  <tr key={k} className={clsx("border-t border-surface-border/60", k === "twin" && "font-semibold")}><td className="px-2 py-1">{k.replace(/_/g, " ")}</td>
                    <td className={TD}>{f3(r.neutrophil_twin.mae_log_anc[k])}</td><td className={TD}>{f3(r.neutrophil_twin.median_fold_error[k])}</td></tr>))}</tbody>
              </table>
              <Note>{r.neutrophil_twin.n_predictions} predictions. 80% interval coverage: latent {pct(r.neutrophil_twin.coverage_of_80pct_intervals.latent_anc_interval, 1)}, predictive {pct(r.neutrophil_twin.coverage_of_80pct_intervals.predictive_interval_incl_lab_noise, 1)}. {r.neutrophil_twin.interpretation}</Note>
            </Section>
            <Section eyebrow="Latent-state recovery" title="Estimated vs true hidden loads">
              <table className="w-full text-[11.5px]"><tbody>{Object.entries(r.latent_state_recovery.pearson_r_estimated_vs_true as Record<string, number>).map(([k, v]) => (
                <tr key={k} className="border-t border-surface-border/60"><td className="px-2 py-1">{k}</td><td className={TD}>r = {v.toFixed(2)}</td></tr>))}</tbody></table>
              <Note>{r.latent_state_recovery.n_patient_days} patient-days. {r.latent_state_recovery.note}</Note>
            </Section>
          </div>

          <ExperimentRunner />

          <Note>{r.event_metric_note} Generated {String(r.generated_at).slice(0, 19).replace("T", " ")} UTC in {r.runtime_seconds} s · results SHA-256 {String(r.sha256).slice(0, 16)}…</Note>
        </>
      )}
    </div>
  );
}

function ForestPlot({ arms, reference, refAuroc }: { arms: Arm[]; reference: string; refAuroc?: number }) {
  const rows = arms.filter((a) => a.metrics?.auroc != null);
  if (!rows.length) return null;
  const ref = refAuroc ?? rows.find((a) => a.config.name === reference)?.metrics.auroc;
  const lo = Math.min(...rows.map((a) => a.metrics.auroc_95ci?.[0] ?? a.metrics.auroc)) - 0.02;
  const hi = Math.min(1, Math.max(...rows.map((a) => a.metrics.auroc_95ci?.[1] ?? a.metrics.auroc)) + 0.02);
  const W = 640, L = 250, R = 20, rowH = 22, H = rows.length * rowH + 26;
  const sx = (v: number) => L + ((v - lo) / Math.max(1e-6, hi - lo)) * (W - L - R);
  const ticks = Array.from({ length: 5 }, (_, i) => lo + ((hi - lo) * i) / 4);
  return (
    <div className="overflow-x-auto mb-3">
      <svg width={W} height={H} role="img" aria-label="AUROC with 95% confidence intervals per arm" className="text-ink-primary">
        {ticks.map((t) => (<g key={t}><line x1={sx(t)} x2={sx(t)} y1={4} y2={H - 18} stroke="currentColor" strokeOpacity={0.08} />
          <text x={sx(t)} y={H - 4} fontSize={9} textAnchor="middle" className="fill-ink-muted">{t.toFixed(2)}</text></g>))}
        {ref != null && <line x1={sx(ref)} x2={sx(ref)} y1={4} y2={H - 18} stroke="currentColor" strokeDasharray="3 3" strokeOpacity={0.6} />}
        {rows.map((a, i) => {
          const y = 12 + i * rowH;
          const [c0, c1] = a.metrics.auroc_95ci ?? [a.metrics.auroc, a.metrics.auroc];
          const isRef = a.config.name === reference;
          const sig = a.paired_vs_multimodal?.significant;
          return (
            <g key={a.config.name}>
              <text x={L - 8} y={y + 3.5} fontSize={10.5} textAnchor="end" className={isRef ? "fill-ink-primary" : "fill-ink-body"} fontWeight={isRef ? 700 : 400}>{a.config.name}</text>
              <line x1={sx(c0)} x2={sx(c1)} y1={y} y2={y} stroke="currentColor" strokeWidth={1.4} />
              {isRef ? <rect x={sx(a.metrics.auroc) - 4} y={y - 4} width={8} height={8} fill="currentColor" />
                : <circle cx={sx(a.metrics.auroc)} cy={y} r={3.8} fill={sig ? "currentColor" : "rgb(var(--surface-raised))"} stroke="currentColor" strokeWidth={1.4} />}
            </g>);
        })}
      </svg>
      <div className="text-[10.5px] text-ink-muted">AUROC with 95% patient-bootstrap CI. Dashed line = {reference}. Filled marker = significantly different from it (paired bootstrap); open marker = not significant.</div>
    </div>
  );
}

// `reference` names the arm the paired Δ is measured against; any other arm without a paired Δ is "not paired".
function ArmTable({ arms, compact = false, reference }: { arms: Arm[]; compact?: boolean; reference?: string }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-[11.5px] min-w-[720px]">
        <thead><tr>
          <th className={clsx(TH, "text-left")}>Arm</th><th className={TH}>AUROC (95% CI)</th><th className={TH}>Δ vs reference (95% CI)</th><th className={TH}>AUPRC</th>
          {!compact && <><th className={TH}>Brier</th><th className={TH}>ECE</th><th className={TH}>Precision</th><th className={TH}>Recall</th><th className={TH}>F1</th></>}
          <th className={TH}>Events caught</th><th className={TH}>Median lead</th><th className={TH}>False alerts / 100 pd</th>
        </tr></thead>
        <tbody>{arms.map((a) => {
          const m = a.metrics ?? {};
          const p = a.paired_vs_multimodal ?? a.paired_vs_reference;
          return (
            <tr key={a.config.name} className="border-t border-surface-border/60">
              <td className="px-2 py-1 text-left"><div className="font-medium text-ink-primary">{a.config.name}</div>
                <div className="text-[10px] text-ink-muted">{a.config.model_label}{a.config.baseline === "population" ? " · population baseline" : ""}{a.config.horizon_days !== 7 ? ` · ${a.config.horizon_days}-day horizon` : ""}</div></td>
              <td className={TD}>{f3(m.auroc)} ({ci(m.auroc_95ci)})</td>
              <td className={TD}>{p ? <span className={p.significant ? "font-semibold text-ink-primary" : "text-ink-muted"}>{p.delta_auroc > 0 ? "+" : ""}{f3(p.delta_auroc)} ({ci(p.ci95)}){p.significant ? "" : " ns"}</span>
                : a.config.name === reference ? "reference" : <span className="text-ink-muted">not paired</span>}</td>
              <td className={TD}>{f3(m.auprc)}</td>
              {!compact && <><td className={TD}>{m.brier ?? "—"}</td><td className={TD}>{m.ece ?? "—"}</td><td className={TD}>{m.precision ?? "—"}</td><td className={TD}>{m.recall ?? "—"}</td><td className={TD}>{m.f1 ?? "—"}</td></>}
              <td className={TD}>{m.events_detected ?? "—"}/{m.events ?? "—"}</td>
              <td className={TD}>{m.median_lead_time_days == null ? "—" : `${m.median_lead_time_days} d`}</td>
              <td className={TD}>{m.false_alert_onsets_per_100_patient_days ?? "—"}</td>
            </tr>);
        })}</tbody>
      </table>
    </div>
  );
}

function Calibration({ bins }: { bins: { mean_predicted: number; observed_rate: number; n: number }[] }) {
  if (!bins.length) return <div className="text-[12px] text-ink-muted">No calibration bins.</div>;
  const mx = Math.max(0.05, ...bins.map((b) => Math.max(b.mean_predicted, b.observed_rate))) * 1.1;
  const S = 240, P = 30;
  const sx = (v: number) => P + (v / mx) * (S - P - 8);
  const sy = (v: number) => S - P - (v / mx) * (S - P - 8);
  return (
    <div className="flex flex-wrap gap-4 items-start">
      <svg width={S} height={S} role="img" aria-label="Calibration: mean predicted risk vs observed event rate per decile" className="text-ink-primary">
        <line x1={sx(0)} y1={sy(0)} x2={sx(mx)} y2={sy(mx)} stroke="currentColor" strokeDasharray="3 3" strokeOpacity={0.5} />
        <line x1={P} x2={S - 8} y1={sy(0)} y2={sy(0)} stroke="currentColor" strokeOpacity={0.3} />
        <line x1={P} x2={P} y1={sy(0)} y2={sy(mx)} stroke="currentColor" strokeOpacity={0.3} />
        <polyline fill="none" stroke="currentColor" strokeWidth={1.5} points={bins.map((b) => `${sx(b.mean_predicted)},${sy(b.observed_rate)}`).join(" ")} />
        {bins.map((b, i) => <circle key={i} cx={sx(b.mean_predicted)} cy={sy(b.observed_rate)} r={3} fill="currentColor"><title>{`predicted ${pct(b.mean_predicted, 1)} · observed ${pct(b.observed_rate, 1)} · n ${b.n}`}</title></circle>)}
        <text x={S / 2} y={S - 8} fontSize={9} textAnchor="middle" className="fill-ink-muted">mean predicted (0–{pct(mx, 0)})</text>
        <text x={10} y={S / 2} fontSize={9} textAnchor="middle" transform={`rotate(-90 10 ${S / 2})`} className="fill-ink-muted">observed rate</text>
      </svg>
      <Note>Deciles of predicted risk on held-out synthetic patients; the dashed diagonal is perfect calibration.</Note>
    </div>
  );
}

function LeadTime({ lt }: { lt: Json }) {
  const d = lt.deployed_system;
  const h: number[] = d.histogram_0_to_7_days;
  const mx = Math.max(1, ...h);
  return (
    <div className="space-y-2">
      <div className="text-[12.5px]"><b className="text-ink-primary">{d.events_detected}/{d.events}</b> events alerted in advance · median lead <b className="text-ink-primary">{d.median_lead_time_days} days</b> <span className="text-ink-muted">({d.source})</span></div>
      <svg width={300} height={120} role="img" aria-label="Histogram of lead times in days" className="text-ink-primary">
        {h.map((v, i) => (
          <g key={i}>
            <rect x={10 + i * 35} y={100 - (v / mx) * 85} width={26} height={(v / mx) * 85} fill="currentColor" opacity={0.75}><title>{`${i} days: ${v} events`}</title></rect>
            <text x={23 + i * 35} y={114} fontSize={9} textAnchor="middle" className="fill-ink-muted">{i}d</text>
            {v > 0 && <text x={23 + i * 35} y={96 - (v / mx) * 85} fontSize={9} textAnchor="middle" className="fill-ink-body">{v}</text>}
          </g>))}
      </svg>
      <div className="overflow-x-auto"><table className="w-full text-[11px]">
        <thead><tr><th className={clsx(TH, "text-left")}>Arm</th><th className={TH}>Caught</th><th className={TH}>Median lead</th><th className={TH}>False alerts / 100 pd</th></tr></thead>
        <tbody>{lt.arms.map((a: Json) => (
          <tr key={a.name} className="border-t border-surface-border/60"><td className="px-2 py-0.5">{a.name}</td><td className={TD}>{a.events_detected}/{a.events}</td>
            <td className={TD}>{a.median_lead_time_days == null ? "—" : `${a.median_lead_time_days} d`}</td><td className={TD}>{a.false_alert_onsets_per_100_patient_days}</td></tr>))}</tbody>
      </table></div>
      <Note>{lt.definition}</Note>
    </div>
  );
}

function ExperimentRunner() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [opt, setOpt] = useState<Json | null>(null);
  const [cfg, setCfg] = useState<Json>({ name: "Custom experiment", groups: [], baseline: "personal", horizon: 7, model: "logistic", compare_to_reference: true });
  const [job, setJob] = useState<Json | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    ot.researchOptions().then((o) => { setOpt(o); setCfg((c: Json) => ({ ...c, groups: o.groups.map((g: Json) => g.id) })); }).catch(() => undefined);
    return () => { if (timer.current) clearTimeout(timer.current); };
  }, []);

  const poll = (id: string) => {
    ot.experiment(id).then((j) => {
      setJob(j);
      if (j.status !== "done" && j.status !== "error") timer.current = setTimeout(() => poll(id), 2000);
    }).catch((e) => setErr((e as Error).message));
  };
  const start = async () => {
    setErr(null); setJob(null);
    try { const r = await ot.startExperiment(cfg); setJob(r.job); poll(r.job.id); } catch (e) { setErr((e as Error).message); }
  };
  const running = job != null && job.status !== "done" && job.status !== "error";
  if (!opt) return null;
  return (
    <Section eyebrow="Experiment runner" title="Run your own arm on the same synthetic split">
      {!isAdmin && <div className="text-[12px] text-ink-muted mb-2">Only admins can run experiments, because they train models on the server. The configuration is shown read-only.</div>}
      <fieldset disabled={!isAdmin || running} className="grid gap-3 md:grid-cols-[1.4fr_1fr] text-[12px]">
        <div>
          <div className="text-[11px] text-ink-muted mb-1">Modalities (feature groups)</div>
          <div className="flex flex-wrap gap-x-4 gap-y-1">
            {opt.groups.map((g: Json) => (
              <label key={g.id} className="inline-flex items-center gap-1.5">
                <input type="checkbox" checked={cfg.groups.includes(g.id)}
                  onChange={(e) => setCfg({ ...cfg, groups: e.target.checked ? [...cfg.groups, g.id] : cfg.groups.filter((x: string) => x !== g.id) })} />
                {g.label}
              </label>))}
          </div>
        </div>
        <div className="grid grid-cols-2 gap-2">
          <label className="flex flex-col gap-0.5 col-span-2">Name<input maxLength={80} className="rounded border border-surface-border bg-surface-bg px-2 py-1" value={cfg.name} onChange={(e) => setCfg({ ...cfg, name: e.target.value })} /></label>
          <label className="flex flex-col gap-0.5">Model<select className="rounded border border-surface-border bg-surface-bg px-2 py-1" value={cfg.model} onChange={(e) => setCfg({ ...cfg, model: e.target.value })}>
            {Object.entries(opt.models as Record<string, string>).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
          <label className="flex flex-col gap-0.5">Baseline<select className="rounded border border-surface-border bg-surface-bg px-2 py-1" value={cfg.baseline} onChange={(e) => setCfg({ ...cfg, baseline: e.target.value })}>
            {opt.baselines.map((b: string) => <option key={b} value={b}>{b}</option>)}</select></label>
          <label className="flex flex-col gap-0.5">Horizon<select className="rounded border border-surface-border bg-surface-bg px-2 py-1" value={cfg.horizon} onChange={(e) => setCfg({ ...cfg, horizon: Number(e.target.value) })}>
            {opt.horizons.map((h: number) => <option key={h} value={h}>{h} day{h === 1 ? "" : "s"}</option>)}</select></label>
          <label className="inline-flex items-center gap-1.5 mt-5"><input type="checkbox" checked={cfg.compare_to_reference} onChange={(e) => setCfg({ ...cfg, compare_to_reference: e.target.checked })} /> Paired comparison with the multimodal twin</label>
        </div>
        <div className="md:col-span-2 flex items-center gap-3 flex-wrap">
          <button type="button" onClick={start} className={BTN} disabled={!isAdmin || running || cfg.groups.length === 0}>
            {running ? <Loader2 size={13} className="animate-spin" aria-hidden /> : <Play size={13} aria-hidden />} Run experiment
          </button>
          <span className="text-[11px] text-ink-muted">Dataset: {opt.datasets.map((d: Json) => d.label).join("; ")}. Metrics: {opt.metrics.join(", ")}.</span>
        </div>
      </fieldset>
      {err && <div className="text-[12px] text-accent-red mt-2" role="alert">{err}</div>}
      {job && (
        <div className="mt-3 text-[12px] space-y-2" aria-live="polite">
          <div className="flex items-center gap-2"><Chip strong={job.status === "error"}>{job.status}</Chip>
            {running && <span className="text-ink-muted">{pct(job.progress)} (the first run builds the cohort cache; later runs take seconds)</span>}</div>
          {job.error && <div className="text-accent-red">{job.error}</div>}
          {job.result && (
            <>
              <ArmTable arms={[{ config: job.result.config, metrics: job.result.metrics, paired_vs_reference: job.result.paired_vs_reference },
                ...(job.result.reference ? [{ config: job.result.reference.config, metrics: job.result.reference.metrics }] : [])]}
                reference={job.result.reference?.config.name} />
              <Note>Trained in {job.result.seconds} s on dataset {job.result.dataset?.version}. Δ is paired against the multimodal reference on the same test patients.</Note>
            </>)}
        </div>)}
    </Section>
  );
}
