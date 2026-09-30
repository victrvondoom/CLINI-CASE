/** Scenario picker + grouped patient input form, generated from the backend feature catalog. */
import clsx from "clsx";
import { ChevronDown } from "lucide-react";
import { useState } from "react";

import { CARD } from "./panels";
import type { FeatureCatalog, FeatureSpec, PatientValues, Scenario } from "./types";

const INPUT =
  "w-full rounded-md border border-surface-border bg-surface-bg px-2 py-1 text-[12.5px] text-ink-body focus:outline-none focus:ring-2 focus:ring-accent-brand";

export function binaryState(v: unknown): "yes" | "no" | "" {
  if (v === null || v === undefined || v === "") return "";
  const s = String(v).toLowerCase();
  if (s === "1" || s === "y" || s === "yes" || s === "true") return "yes";
  if (s === "0" || s === "n" || s === "no" || s === "false") return "no";
  return "";
}

function Field({ spec, value, onChange }: { spec: FeatureSpec; value: unknown; onChange: (v: number | string | null) => void }) {
  const id = `ct-${spec.name.replace(/\W+/g, "-")}`;
  let control: React.ReactNode;
  if (spec.kind === "numeric") {
    control = (
      <input
        id={id}
        type="number"
        className={INPUT}
        value={value === null || value === undefined ? "" : String(value)}
        min={spec.min ?? undefined}
        max={spec.max ?? undefined}
        step="any"
        onChange={(e) => onChange(e.target.value === "" ? null : Number(e.target.value))}
      />
    );
  } else if (spec.kind === "binary") {
    control = (
      <select id={id} className={INPUT} value={binaryState(value)} onChange={(e) => onChange(e.target.value === "" ? null : e.target.value === "yes" ? 1 : 0)}>
        <option value="">— (not provided)</option>
        <option value="no">No</option>
        <option value="yes">Yes</option>
      </select>
    );
  } else {
    control = (
      <select id={id} className={INPUT} value={value === null || value === undefined ? "" : String(value)} onChange={(e) => onChange(e.target.value === "" ? null : e.target.value)}>
        <option value="">— (not provided)</option>
        {spec.options.map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </select>
    );
  }
  return (
    <div>
      <label htmlFor={id} className="block text-[11px] text-ink-muted mb-0.5">
        {spec.label}
        {spec.unit ? ` (${spec.unit})` : ""}
        {spec.ref_low != null || spec.ref_high != null ? (
          <span className="ml-1 text-ink-faint">
            ref {spec.ref_low ?? "…"}–{spec.ref_high ?? "…"}
          </span>
        ) : null}
      </label>
      {control}
    </div>
  );
}

interface Props {
  catalog: FeatureCatalog;
  scenarios: Scenario[];
  scenarioNote: string;
  activeScenario: string | null;
  patient: PatientValues;
  onScenario: (s: Scenario) => void;
  onChange: (name: string, v: number | string | null) => void;
  onClear: () => void;
}

export function PatientPanel({ catalog, scenarios, scenarioNote, activeScenario, patient, onScenario, onChange, onClear }: Props) {
  const [open, setOpen] = useState(false);
  const [more, setMore] = useState(false);
  const active = scenarios.find((s) => s.id === activeScenario) ?? null;
  return (
    <section className={clsx(CARD, "p-3 space-y-3")} aria-label="Patient input" data-testid="patient-panel">
      <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label="Demo scenarios">
        <span className="text-[11px] uppercase tracking-wide text-ink-muted mr-1">Scenario</span>
        {scenarios.map((s) => (
          <button
            key={s.id}
            type="button"
            title={s.description}
            aria-pressed={activeScenario === s.id}
            data-testid={`scenario-${s.id}`}
            onClick={() => onScenario(s)}
            className={clsx(
              "px-2.5 py-1 rounded-md border text-[12px] focus:outline-none focus:ring-2 focus:ring-accent-brand",
              activeScenario === s.id ? "border-accent-brand bg-accent-brand/10 text-ink-primary" : "border-surface-border text-ink-body hover:border-accent-brand/60",
            )}
          >
            {s.id} · {s.title}
          </button>
        ))}
        <button type="button" onClick={onClear} className="px-2 py-1 rounded-md text-[12px] text-ink-muted underline">
          Clear
        </button>
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          data-testid="toggle-form"
          className="ml-auto inline-flex items-center gap-1 px-2.5 py-1 rounded-md border border-surface-border text-[12px] text-ink-body"
        >
          Edit patient values <ChevronDown size={13} className={clsx(open && "rotate-180")} aria-hidden />
        </button>
      </div>

      {active && (
        <div className="text-[11.5px] text-ink-muted space-y-0.5" data-testid="scenario-detail">
          <p>{active.description}</p>
          <p>
            {active.source === "synthetic"
              ? "Synthetic profile constructed for this demo — not a real patient."
              : `De-identified dataset record #${active.dataset_row} (public research data).`}
          </p>
          {active.reference_labels && (
            <details>
              <summary className="cursor-pointer underline">Dataset angiography labels for this record (shown for honesty)</summary>
              <p className="mt-1">
                Overall: <b>{active.reference_labels.Cath}</b> · LAD <b>{active.reference_labels.LAD}</b> · LCX{" "}
                <b>{active.reference_labels.LCX}</b> · RCA <b>{active.reference_labels.RCA}</b>. {scenarioNote}
              </p>
            </details>
          )}
        </div>
      )}

      {open && (
        <div className="space-y-3">
          {catalog.groups.map((g) => {
            const specs = catalog.features.filter((f) => f.group === g.id && (more || f.core));
            if (!specs.length) return null;
            return (
              <fieldset key={g.id}>
                <legend className="text-[11px] font-semibold text-ink-primary mb-1">{g.label}</legend>
                <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-2">
                  {specs.map((f) => (
                    <Field key={f.name} spec={f} value={patient[f.name]} onChange={(v) => onChange(f.name, v)} />
                  ))}
                </div>
              </fieldset>
            );
          })}
          <button type="button" onClick={() => setMore((v) => !v)} className="text-[12px] underline text-ink-muted">
            {more ? "Show core fields only" : "Show all fields"}
          </button>
          <p className="text-[11px] text-ink-muted">
            Leave a field empty to let the model impute the training median; the dashboard reports feature completeness.
          </p>
        </div>
      )}
    </section>
  );
}
