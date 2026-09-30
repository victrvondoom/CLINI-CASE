import { useState, type FormEvent, type ReactNode } from "react";
import type {
  ExposureHistory,
  ExposureRecord,
  LabSample,
  Patient,
} from "./api";

export const INPUT =
  "mt-1 block w-full rounded-lg border border-surface-border bg-surface-panel px-3 py-2 text-sm text-ink-primary focus:outline-none focus:ring-2 focus:ring-accent-cyan";
export const BUTTON =
  "rounded-lg border border-accent-cyan/40 bg-accent-cyan/10 px-3 py-2 text-xs text-accent-cyan disabled:opacity-40 hover:bg-accent-cyan/20 focus:outline-none focus:ring-2 focus:ring-accent-cyan";
export function Field({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <label className="block text-xs text-ink-muted">
      {label}
      {children}
    </label>
  );
}
function values(e: FormEvent<HTMLFormElement>) {
  e.preventDefault();
  return new FormData(e.currentTarget);
}
const str = (data: FormData, key: string) => String(data.get(key) ?? "").trim();
const timestamp = (s: string) => new Date(s).toISOString();

export function LabForm({
  observations,
  persistence,
  busy,
  onSubmit,
}: {
  observations: {
    id: string;
    reference: string;
    waterbody_name: string;
    is_demo: boolean;
  }[];
  persistence: string;
  busy: boolean;
  onSubmit: (id: string, sample: LabSample) => void;
}) {
  const [error, setError] = useState("");
  function submit(e: FormEvent<HTMLFormElement>) {
    const data = values(e);
    try {
      setError("");
      onSubmit(str(data, "observation"), {
        sample_id: str(data, "sample_id"),
        location_name: str(data, "location_name"),
        kind: str(data, "kind") as LabSample["kind"],
        laboratory: str(data, "laboratory"),
        collector: str(data, "collector"),
        report_reference: str(data, "report_reference"),
        method: str(data, "method"),
        collected_at: timestamp(str(data, "collected_at")),
        reported_at: timestamp(str(data, "reported_at")),
        analyte: str(data, "analyte") as LabSample["analyte"],
        value: Number(str(data, "value")),
        unit: str(data, "unit") as LabSample["unit"],
        qualifier: str(data, "qualifier") as LabSample["qualifier"],
      });
    } catch {
      setError("Please enter valid sample and report dates.");
    }
  }
  return (
    <form onSubmit={submit} className="space-y-4">
      <p className="text-xs text-ink-muted">
        Record a laboratory report, not a contaminant inferred from a photo.
        Saved samples are immutable; corrections require a new evidence record.
      </p>
      <Field label="Citizen observation">
        <select required name="observation" className={INPUT} defaultValue="">
          <option value="" disabled>
            Select a source observation
          </option>
          {observations.map((o) => (
            <option
              key={o.id}
              value={o.id}
              disabled={persistence !== "postgresql" && !o.is_demo}
            >
              {o.is_demo ? "DEMO · " : ""}
              {o.reference} · {o.waterbody_name}
              {persistence !== "postgresql" && !o.is_demo ? " · PostgreSQL required" : ""}
            </option>
          ))}
        </select>
      </Field>
      {persistence !== "postgresql" && (
        <p className="text-xs text-accent-amber" role="status">
          This workspace is in volatile demo mode. Only synthetic observations can be linked until PostgreSQL persistence is available.
        </p>
      )}
      <div className="grid sm:grid-cols-2 gap-3">
        {[
          ["sample_id", "Sample identifier"],
          ["location_name", "Exact sampling location"],
          ["laboratory", "Laboratory"],
          ["collector", "Sample collector"],
          ["report_reference", "Laboratory report reference"],
          ["method", "Measurement method"],
        ].map(([name, label]) => (
          <Field key={name} label={label}>
            <input required maxLength={200} name={name} className={INPUT} />
          </Field>
        ))}
        <Field label="Sample matrix">
          <select name="kind" className={INPUT}>
            <option value="stream">Stream water</option>
            <option value="source_water">Source water, before treatment</option>
            <option value="drinking_water">
              Drinking water at point of use
            </option>
          </select>
        </Field>
        <Field label="Analyte">
          <select name="analyte" className={INPUT}>
            <option value="total_arsenic">Total arsenic</option>
            <option value="inorganic_arsenic">Inorganic arsenic</option>
          </select>
        </Field>
        <Field label="Collected at (your local time)">
          <input
            required
            type="datetime-local"
            name="collected_at"
            className={INPUT}
          />
        </Field>
        <Field label="Reported at (your local time)">
          <input
            required
            type="datetime-local"
            name="reported_at"
            className={INPUT}
          />
        </Field>
        <Field label="Result or reporting limit">
          <input
            required
            type="number"
            step="any"
            min="0"
            max="100000"
            name="value"
            className={INPUT}
          />
        </Field>
        <Field label="Unit">
          <select name="unit" className={INPUT}>
            <option value="ug/L">µg/L</option>
            <option value="mg/L">mg/L</option>
          </select>
        </Field>
        <Field label="Result qualifier">
          <select name="qualifier" className={INPUT}>
            <option value="eq">Measured value</option>
            <option value="lt">Below reporting limit (&lt;)</option>
          </select>
        </Field>
      </div>
      {error && (
        <p role="alert" className="text-accent-red text-xs">
          {error}
        </p>
      )}
      <button
        disabled={busy || !observations.some((o) => persistence === "postgresql" || o.is_demo)}
        className={BUTTON}
      >
        Save unverified laboratory evidence
      </button>
    </form>
  );
}

export function HistoryForm({
  record,
  patients,
  busy,
  onSubmit,
}: {
  record: ExposureRecord;
  patients: Patient[];
  busy: boolean;
  onSubmit: (history: ExposureHistory) => void;
}) {
  const h = record.history;
  const [error, setError] = useState("");
  function submit(e: FormEvent<HTMLFormElement>) {
    const data = values(e);
    try {
      setError("");
      onSubmit({
        patient_id: str(data, "patient_id"),
        consent_reference: str(data, "consent_reference"),
        consent_recorded: data.has("consent"),
        route: str(data, "route") as ExposureHistory["route"],
        pathway_confirmed: data.has("pathway_confirmed"),
        pathway_evidence: str(data, "pathway_evidence"),
        treatment_context: str(data, "treatment_context"),
        started_on: timestamp(str(data, "started_on")),
        ended_on: timestamp(str(data, "ended_on")),
      });
    } catch {
      setError("Please enter valid exposure dates.");
    }
  }
  return (
    <form onSubmit={submit} className="space-y-3">
      <p className="text-xs text-ink-muted">
        Record actual water use and treatment. Residence near a stream is not
        evidence of drinking-water exposure. Consent is recorded here; it is not
        independently verified by the software.
      </p>
      <Field label="Patient in this organisation">
        <select
          required
          name="patient_id"
          className={INPUT}
          defaultValue={h?.patient_id ?? ""}
        >
          <option value="" disabled>
            Select a patient
          </option>
          {patients
            .filter(
              (p) =>
                p.synthetic === record.synthetic &&
                (!h || p.id === h.patient_id),
            )
            .map((p) => (
              <option key={p.id} value={p.id}>
                {p.synthetic ? "SYNTHETIC · " : ""}
                {p.label} ({p.id})
              </option>
            ))}
        </select>
      </Field>
      <Field label="Consent record reference">
        <input
          name="consent_reference"
          required
          maxLength={200}
          defaultValue={h?.consent_reference}
          className={INPUT}
        />
      </Field>
      <label className="flex gap-2 text-xs text-ink-body">
        <input
          type="checkbox"
          name="consent"
          required
          defaultChecked={h?.consent_recorded}
        />{" "}
        I attest that consent for this evidence link is recorded.
      </label>
      <Field label="Exposure route">
        <select
          name="route"
          className={INPUT}
          defaultValue={h?.route ?? "unknown"}
        >
          <option value="unknown">Unknown</option>
          <option value="drinking">Drinking</option>
          <option value="other">Other contact</option>
        </select>
      </Field>
      <Field label="Source-to-person evidence">
        <textarea
          name="pathway_evidence"
          maxLength={1000}
          defaultValue={h?.pathway_evidence}
          className={INPUT}
          placeholder="How was actual use of this water source established?"
        />
      </Field>
      <label className="flex gap-2 text-xs text-ink-body">
        <input
          type="checkbox"
          name="pathway_confirmed"
          defaultChecked={h?.pathway_confirmed}
        />{" "}
        Source-to-person pathway confirmed from the evidence above.
      </label>
      <Field label="Treatment and water-use context">
        <textarea
          name="treatment_context"
          maxLength={500}
          defaultValue={h?.treatment_context}
          className={INPUT}
          placeholder="Treatment, point of use, frequency and limits of the history"
        />
      </Field>
      <div className="grid sm:grid-cols-2 gap-3">
        <Field label="Exposure start">
          <input
            type="date"
            required
            name="started_on"
            className={INPUT}
            defaultValue={h?.started_on.slice(0, 10)}
          />
        </Field>
        <Field label="Exposure history through">
          <input
            type="date"
            required
            name="ended_on"
            className={INPUT}
            defaultValue={h?.ended_on.slice(0, 10)}
          />
        </Field>
      </div>
      {error && (
        <p role="alert" className="text-xs text-accent-red">
          {error}
        </p>
      )}
      <button className={BUTTON} disabled={busy || record.consent_withdrawn}>
        Save consented exposure history
      </button>
    </form>
  );
}
