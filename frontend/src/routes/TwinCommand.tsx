/**
 * /twin — OncoTwin Clinician Command Center: every synthetic patient's twin, triaged into
 * High Priority / Early Warning / Watch / Data Quality Issue / Stable (/ In acute care), each
 * with the one-line WHY NOW?, the top state change, the trajectory and the twin's readiness.
 * Triage is decision support for prioritising review — not an acuity score.
 */
import clsx from "clsx";
import { Activity, ArrowRight, FlaskConical, Gauge, HeartPulse, Loader2, PlayCircle, RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ot } from "../oncotwin/api";
import { Chip, Note, SevMark } from "../oncotwin/intel";
import { RiskSpark, Section, TierBadge, pct } from "../oncotwin/panels";
import type { CCRow, CommandCenter } from "../oncotwin/types2";

const BTN = "inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md border border-surface-border bg-surface-raised text-[12px] text-ink-body hover:border-accent-brand/60 disabled:opacity-40 focus:outline-none focus:ring-2 focus:ring-accent-brand";

const CATEGORY_HELP: Record<string, string> = {
  "High Priority": "Twin tier HIGH PRIORITY",
  "Early Warning": "Twin tier EARLY WARNING",
  "Watch": "Twin tier WATCH",
  "Data Quality Issue": "Inputs too incomplete or conflicting to trust the twin",
  "Stable": "No deviation needing review",
  "In acute care": "Currently admitted / in the ED",
};

export default function TwinCommand() {
  const [cc, setCc] = useState<CommandCenter | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [filter, setFilter] = useState<string | null>(null);

  const load = async () => {
    setBusy(true); setErr(null);
    try { setCc(await ot.commandCenter()); } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  };
  useEffect(() => { void load(); }, []);

  const rows = (cc?.patients ?? []).filter((r) => !filter || r.category === filter);
  return (
    <div className="px-4 sm:px-6 py-6 space-y-4">
      <header className="flex items-start justify-between gap-4 flex-wrap">
        <div className="max-w-3xl">
          <h1 className="text-2xl font-semibold text-ink-primary flex items-center gap-2"><HeartPulse size={22} aria-hidden /> OncoTwin Command Center</h1>
          <p className="text-[13.5px] text-ink-body mt-1">
            A dynamic, explainable, predictive digital twin for each patient's treatment trajectory, triaged for clinician review.
          </p>
          <p className="text-[11.5px] text-ink-muted mt-1">
            All patients are synthetic. Clinical decision support only; accepted alerts become ClinCase prior-authorisation cases.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link to="/twin/demo" className="inline-flex items-center gap-2 px-3.5 py-2 rounded-md bg-accent-brand text-ink-invert text-[13px] font-medium">
            <PlayCircle size={15} aria-hidden /> Guided demo
          </Link>
          <Link to="/twin/overview" className={BTN}><Activity size={13} aria-hidden /> Model card</Link>
          <Link to="/twin/lab" className={BTN}><FlaskConical size={13} aria-hidden /> Research Lab</Link>
          <Link to="/twin/ops" className={BTN}><Gauge size={13} aria-hidden /> Observability</Link>
          <button type="button" onClick={load} disabled={busy} className={BTN}>
            {busy ? <Loader2 size={13} className="animate-spin" aria-hidden /> : <RefreshCw size={13} aria-hidden />} Refresh
          </button>
        </div>
      </header>
      {err && <div className="text-[12px] text-accent-red" role="alert">{err}</div>}
      {!cc && !err && <div className="text-[12px] text-ink-muted flex items-center gap-2"><Loader2 size={14} className="animate-spin" aria-hidden /> Building every patient's twin…</div>}

      {cc && (
        <>
          <div className="grid gap-2 grid-cols-2 md:grid-cols-3 xl:grid-cols-6" role="group" aria-label="Filter by triage category">
            {cc.categories.map((c) => (
              <button key={c} type="button" onClick={() => setFilter(filter === c ? null : c)} aria-pressed={filter === c}
                className={clsx("text-left rounded-xl border px-3 py-2 bg-surface-raised hover:border-accent-brand/60 focus:outline-none focus:ring-2 focus:ring-accent-brand",
                  filter === c ? "border-accent-brand" : (cc.counts[c] ?? 0) > 0 && c !== "Stable" ? "border-ink-primary/60" : "border-surface-border")}>
                <div className="text-[10px] text-compact text-ink-muted">{c}</div>
                <div className="text-2xl nums-tabular text-ink-primary font-semibold">{cc.counts[c] ?? 0}</div>
                <div className="text-[10px] text-ink-faint leading-tight">{CATEGORY_HELP[c] ?? ""}</div>
              </button>
            ))}
          </div>

          <div className="grid gap-2 md:grid-cols-2 text-[11.5px]">
            <div className="rounded-lg border border-surface-border px-3 py-2 bg-surface-raised flex gap-2 items-start">
              <span className="mt-0.5"><SevMark s={cc.drift?.status === "drift" ? "alert" : cc.drift?.status === "watch" ? "attention" : "normal"} /></span>
              <div><b>Population drift monitor: {cc.drift?.status ?? "unavailable"}</b> <span className="text-ink-muted">{cc.drift?.message}</span>{" "}
                <Link to="/twin/ops" className="underline decoration-dotted">details</Link></div>
            </div>
            <div className="rounded-lg border border-surface-border px-3 py-2 bg-surface-raised flex gap-2 items-start">
              <span className="mt-0.5"><SevMark s={cc.ledger.valid ? "normal" : "alert"} /></span>
              <div><b>Audit ledger {cc.ledger.valid ? "verified" : "INVALID"}</b> <span className="text-ink-muted">{cc.ledger.entries} hash-chained entries in this session</span></div>
            </div>
          </div>

          <Section eyebrow={filter ? `Filtered: ${filter}` : "All patients · most urgent first"} title={`${rows.length} digital twin${rows.length === 1 ? "" : "s"}`}
            right={filter ? <button type="button" className={BTN} onClick={() => setFilter(null)}>Clear filter</button> : undefined}>
            <div className="space-y-2">
              {rows.map((r) => <PatientRow key={r.patient.patient_id} r={r} />)}
              {rows.length === 0 && <div className="text-[12px] text-ink-muted">No patient in this category.</div>}
            </div>
            <Note>{cc.note}</Note>
          </Section>
        </>
      )}
    </div>
  );
}

function PatientRow({ r }: { r: CCRow }) {
  const urgent = r.category === "High Priority" || r.category === "Early Warning";
  return (
    <Link to={`/twin/${r.patient.patient_id}`}
      className={clsx("block rounded-xl border p-3 bg-surface-bg hover:border-accent-brand/60 focus:outline-none focus:ring-2 focus:ring-accent-brand",
        urgent ? "border-ink-primary/70" : "border-surface-border")}>
      <div className="grid gap-3 lg:grid-cols-[210px_140px_1fr_200px] items-start">
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-[15px] font-semibold text-ink-primary">{r.patient.label}</span>
            <Chip strong={r.category !== "Stable"}>{r.category}</Chip>
          </div>
          <div className="text-[11px] text-ink-muted truncate">{r.patient.age}{r.patient.sex === "female" ? "F" : "M"} · {r.patient.cancer}</div>
          <div className="text-[11px] text-ink-muted">{r.patient.regimen_code} · Day {r.live_day}/{r.n_days}</div>
        </div>
        <div>
          <TierBadge tier={r.tier} size="sm" />
          <div className="text-xl nums-tabular text-ink-primary mt-1">{pct(r.risk, 1)}</div>
          <div className="text-[10px] text-ink-muted">7-day risk · 80% {pct(r.risk_p10, 1)}–{pct(r.risk_p90, 1)}</div>
        </div>
        <div className="min-w-0 space-y-1 text-[11.5px]">
          {/* Triage list stays scannable: the full WHY NOW? lives on the patient's Evidence tab. */}
          <div className="text-ink-body line-clamp-3" title={r.why_now}><b className="text-ink-primary">WHY NOW?</b> {r.why_now}</div>
          {r.top_change && (
            <div className="flex items-start gap-1.5"><span className="mt-0.5"><SevMark s={r.top_change.severity} /></span>
              <span><b>{r.top_change.label}</b>: {r.top_change.previous} → {r.top_change.current}
                <span className="text-ink-muted"> ({r.n_changes_3d} state change{r.n_changes_3d === 1 ? "" : "s"} in 3 days)</span></span></div>
          )}
          <div className="flex flex-wrap gap-1.5">
            <Chip>{r.trajectory}</Chip>
            <Chip>{r.pattern}</Chip>
            {r.change_point && <Chip>change point D{r.change_point.day} ({r.change_point.kind})</Chip>}
            {r.conflicts.map((c) => <Chip key={c} strong>conflict: {c}</Chip>)}
            {r.consistency !== "consistent" && <Chip>consistency: {r.consistency}</Chip>}
            {r.category_reasons.map((c) => <Chip key={c} strong>{c}</Chip>)}
            {r.open_alerts > 0 && <Chip strong>{r.open_alerts} open alert{r.open_alerts === 1 ? "" : "s"}</Chip>}
          </div>
        </div>
        <div className="text-ink-primary">
          <RiskSpark series={r.risk_series} />
          <div className="flex justify-between text-[10px] text-ink-muted mt-1">
            <span>readiness {pct(r.readiness.score)} ({r.readiness.label})</span>
            <span>data {r.data_quality}</span>
          </div>
          <div className="text-[11px] text-ink-muted inline-flex items-center gap-1 mt-1">Open twin <ArrowRight size={11} aria-hidden /></div>
        </div>
      </div>
    </Link>
  );
}
