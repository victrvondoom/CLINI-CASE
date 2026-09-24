/**
 * /twin — OncoTwin hub: the one outcome, the four synthetic twins, and the
 * model card (synthetic-validation metrics next to honest comparators).
 */
import { ArrowRight, HeartPulse, PlayCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ot } from "../oncotwin/api";
import { RiskSpark, Section, TierBadge, pct } from "../oncotwin/panels";
import type { EventLevel, ModelCard, Overview, PatientSummary } from "../oncotwin/types";

const ARCHETYPE: Record<string, string> = {
  recovery: "Recovery", gradual_deterioration: "Gradual deterioration", sudden_deterioration: "Sudden deterioration", stable: "Stable",
  closed_loop: "Closed loop (flagship)", delayed_deterioration: "Delayed deterioration", relapse: "Relapse",
  noisy_sensor_missing_data: "Noisy sensor / missing data",
};

const FLOW = [
  "FHIR / EHR · pathology · genomics · labs · treatment",
  "Wearables · home devices · symptoms · adherence",
  "Patient Digital Twin (state vector)",
  "Personal baseline engine",
  "Temporal ML + mechanistic neutrophil twin",
  "What-if simulator",
  "Explainable alert",
  "Clinician review (HITL)",
  "ClinCase 7-agent prior-auth",
  "Hash-chained audit trail",
];

export default function TwinHub() {
  const [ov, setOv] = useState<Overview | null>(null);
  const [card, setCard] = useState<ModelCard | null>(null);
  const [patients, setPatients] = useState<PatientSummary[] | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    ot.overview().then(setOv).catch((e) => setErr((e as Error).message));
    ot.model().then(setCard).catch(() => undefined);
    ot.patients().then((r) => setPatients(r.patients)).catch((e) => setErr((e as Error).message));
  }, []);

  const ew = card?.metrics.event_level.early_warning_or_higher;
  const cmp = card?.comparators;
  return (
    <div className="px-4 sm:px-6 py-6 space-y-5">
      <header className="flex items-start justify-between gap-4 flex-wrap">
        <div className="max-w-3xl">
          <Link to="/twin" className="text-[11px] text-ink-muted hover:text-ink-primary">← Command Center</Link>
          <h1 className="text-2xl font-semibold text-ink-primary flex items-center gap-2">
            <HeartPulse size={22} aria-hidden /> OncoTwin · outcome & model card
          </h1>
          <p className="text-[14px] text-ink-body mt-1">
            {ov?.tagline ?? "A dynamic digital twin for predicting treatment-related deterioration in cancer patients."}
          </p>
          <p className="text-[11.5px] text-ink-muted mt-1">
            Runs on top of ClinCase: a clinician-accepted twin alert becomes a ClinCase prior-authorisation case.
            All patients here are synthetic. Clinical decision support only.
          </p>
        </div>
        <Link to="/twin/demo" className="inline-flex items-center gap-2 px-4 py-2 rounded-md bg-accent-brand text-ink-invert text-[13px] font-medium">
          <PlayCircle size={16} aria-hidden /> Start the 3-minute demo
        </Link>
      </header>
      {err && <div className="text-[12px] text-accent-red" role="alert">{err}</div>}

      {ov && (
        <Section eyebrow="The one outcome OncoTwin predicts" title={`${ov.outcome.id} — ${ov.outcome.name}`}>
          <p className="text-[12.5px] text-ink-body">{ov.outcome.definition}</p>
          <p className="text-[11px] text-ink-muted mt-1">Label rule: {ov.outcome.label_rule} · Basis: {ov.outcome.measure_basis}</p>
        </Section>
      )}

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {(patients ?? []).map((p) => (
          <Link key={p.patient.patient_id} to={`/twin/${p.patient.patient_id}`}
            className="card-premium block bg-surface-raised border border-surface-border rounded-2xl p-4 hover:border-accent-brand/60">
            <div className="flex items-center justify-between gap-2">
              <div>
                <div className="text-[15px] font-semibold text-ink-primary">{p.patient.label}</div>
                <div className="text-[10px] text-compact text-ink-muted">{ARCHETYPE[p.patient.archetype] ?? p.patient.archetype} · synthetic</div>
              </div>
              <TierBadge tier={p.tier} size="sm" />
            </div>
            <div className="text-[11.5px] text-ink-body mt-2">
              {p.patient.age}{p.patient.sex === "female" ? "F" : "M"} · {p.patient.cancer} · {p.patient.regimen_code}
            </div>
            <div className="flex items-end justify-between mt-2 gap-2">
              <div>
                <div className="text-data-numeric text-2xl nums-tabular">{pct(p.risk, 1)}</div>
                <div className="text-[10px] text-ink-muted">7-day risk · Day {p.live_day}/{p.n_days}</div>
              </div>
              <div className="text-[10.5px] text-ink-muted text-right">
                {p.pattern}
                {p.open_alerts > 0 && <div className="font-semibold text-ink-primary">{p.open_alerts} open alert(s)</div>}
              </div>
            </div>
            <div className="mt-1 text-ink-primary"><RiskSpark series={p.risk_series} /></div>
            <div className="text-[11px] text-ink-muted inline-flex items-center gap-1 mt-1">Open twin <ArrowRight size={11} aria-hidden /></div>
          </Link>
        ))}
        {!patients && !err && <div className="text-[12px] text-ink-muted">Building twins…</div>}
      </div>

      {card && ew && cmp && (
        <Section eyebrow="Model card — synthetic held-out validation, NOT clinical performance" title={`${card.model_id} v${card.version}`}
          right={<span className="text-[10.5px] text-mono-tech text-ink-muted">sha256 {card.artifact_sha256.slice(0, 12)}… {card.integrity_verified ? "verified" : "UNVERIFIED"}</span>}>
          <div className="overflow-x-auto">
            <table className="w-full text-[12px] min-w-[560px]">
              <thead>
                <tr className="text-left text-[10.5px] text-ink-muted">
                  <th className="py-1 font-medium">Held-out test cohort ({String(card.training.n_test)} synthetic patients)</th>
                  <th className="font-medium text-right">Events caught (≥ EARLY WARNING)</th>
                  <th className="font-medium text-right">Median lead time</th>
                  <th className="font-medium text-right">False alerts / 100 patient-days</th>
                  <th className="font-medium text-right">AUROC</th>
                </tr>
              </thead>
              <tbody>
                <MetricRow label="OncoTwin (personal baseline + twin + ML + rules)" ev={ew} auroc={card.metrics.day_level.auroc} bold />
                {cmp.same_model_without_personal_baseline?.early_warning_or_higher && (
                  <MetricRow label="Same model without personal baseline" ev={cmp.same_model_without_personal_baseline.early_warning_or_higher}
                    auroc={cmp.same_model_without_personal_baseline.test_auroc} />
                )}
                {cmp.population_threshold_rule && (
                  <MetricRow label="Population vital-sign thresholds (temp ≥ 38, HR ≥ 100, SpO₂ < 92, SBP < 90)"
                    ev={cmp.population_threshold_rule as unknown as EventLevel} />
                )}
              </tbody>
            </table>
          </div>
          <div className="grid md:grid-cols-2 gap-3 mt-3 text-[11.5px]">
            <div>
              <div className="text-[10px] text-compact text-ink-faint mb-1">Algorithm</div>
              <p className="text-ink-body">{card.algorithm}. {card.features.length} named features; tier thresholds derived on a separate validation cohort.</p>
            </div>
            <div>
              <div className="text-[10px] text-compact text-ink-faint mb-1">Limitations</div>
              <ul className="list-disc pl-4 text-ink-body">{card.limitations.map((l) => <li key={l}>{l}</li>)}</ul>
            </div>
          </div>
        </Section>
      )}

      <Section eyebrow="Architecture" title="From data to decision — ClinCase is extended, not replaced">
        <ol className="flex flex-wrap items-center gap-1.5 text-[11.5px]">
          {FLOW.map((f, i) => (
            <li key={f} className="inline-flex items-center gap-1.5">
              <span className="px-2 py-1 rounded-md border border-surface-border bg-surface-bg">{f}</span>
              {i < FLOW.length - 1 && <ArrowRight size={12} className="text-ink-faint" aria-hidden />}
            </li>
          ))}
        </ol>
      </Section>
    </div>
  );
}

function MetricRow({ label, ev, auroc, bold }: { label: string; ev: EventLevel; auroc?: number; bold?: boolean }) {
  return (
    <tr className={bold ? "border-t border-surface-border font-semibold" : "border-t border-surface-border"}>
      <td className="py-1.5 pr-2">{label}</td>
      <td className="text-right text-mono-tech">{ev.events_detected}/{ev.events} ({pct(ev.sensitivity)})</td>
      <td className="text-right text-mono-tech">{ev.median_lead_time_days ?? "—"} d</td>
      <td className="text-right text-mono-tech">{ev.false_alert_onsets_per_100_patient_days}</td>
      <td className="text-right text-mono-tech">{auroc != null ? auroc.toFixed(3) : "—"}</td>
    </tr>
  );
}
