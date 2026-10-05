/**
 * Multi-city demonstration matrix: one row per OneAquaHealth research city, with the columns of
 * the OAH-Bridge README, but every value computed live by the engine (GET /scenarios) rather than
 * copied from prose. Clicking a row flies the globe to that city.
 */
import { EPISTEMIC_EXPLAINER, EPISTEMIC_HEX, EPISTEMIC_LABEL, humanize } from "./format";
import type { ScenarioSummary } from "./types";

export const SCENARIO_COUNTRY: Record<string, string> = {
  "coimbra-cyanobacteria": "Portugal",
  "toulouse-diptera": "France",
  "mondego-storm-surge": "Portugal",
};

type KeyInput = ScenarioSummary["key_inputs"][number];

export function keyInputText(k: KeyInput): string {
  const value = Math.abs(k.value) >= 100 ? k.value.toLocaleString("en-GB") : String(k.value);
  const label = k.kind === "model" ? k.label : humanize(k.label);
  return `${label}: ${value}${k.unit ? ` ${k.unit}` : ""}${k.kind === "lab" ? " (lab)" : ""}`;
}

export function outcomeText(s: ScenarioSummary): string {
  const display = s.snomed_outcome_display;
  const preferred = s.snomed_preferred_term ?? display;
  return `${s.snomed_outcome_code} | ${preferred}${preferred !== display ? ` (display: ${display})` : ""}`;
}

interface Props {
  scenarios: ScenarioSummary[];
  selectedId: string;
  onSelect: (id: string) => void;
}

export default function CityMatrix({ scenarios, selectedId, onSelect }: Props) {
  if (scenarios.length === 0) return null;
  return (
    <div className="overflow-x-auto" data-testid="city-matrix">
      <table className="w-full min-w-[920px] border-collapse text-left text-xs">
        <thead>
          <tr className="border-b border-surface-border text-[11px] text-ink-faint">
            <th className="py-2 pr-3 font-medium">City &amp; water basin</th>
            <th className="py-2 pr-3 font-medium">Target hazard</th>
            <th className="py-2 pr-3 font-medium">Key telemetry inputs</th>
            <th className="py-2 pr-3 font-medium">Epistemic status &amp; score</th>
            <th className="py-2 pr-3 font-medium">Exposed cohort</th>
            <th className="py-2 font-medium">Clinical outcome context (SNOMED CT 20260301)</th>
          </tr>
        </thead>
        <tbody>
          {scenarios.map((s) => {
            const active = s.id === selectedId;
            const sub = s.sub_scores;
            return (
              <tr
                key={s.id}
                onClick={() => onSelect(s.id)}
                className={`cursor-pointer border-b border-surface-border align-top transition-colors ${
                  active ? "bg-accent-cyan/10" : "hover:bg-surface-bg"
                }`}
              >
                <td className="py-3 pr-3">
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      onSelect(s.id);
                    }}
                    className="text-left text-sm text-ink-primary underline-offset-2 hover:underline"
                  >
                    {s.city.split(" / ")[0]}
                  </button>
                  <div className="text-ink-muted">({s.river_system})</div>
                  <div className="mt-1 text-[10px] uppercase tracking-wider text-ink-faint">{SCENARIO_COUNTRY[s.id] ?? ""}</div>
                </td>
                <td className="py-3 pr-3 text-ink-body">{s.hazard_display}</td>
                <td className="py-3 pr-3 text-ink-body">
                  <ul className="space-y-0.5">
                    {(s.key_inputs ?? []).map((k) => (
                      <li key={`${k.kind}-${k.label}`}>{keyInputText(k)}</li>
                    ))}
                  </ul>
                </td>
                <td className="py-3 pr-3 text-ink-body" title={EPISTEMIC_EXPLAINER[s.epistemic_status]}>
                  <span className="flex items-center gap-1.5">
                    <span className="inline-block h-2 w-2 rounded-full" style={{ background: EPISTEMIC_HEX[s.epistemic_status] }} />
                    {s.is_lab_confirmed ? "Lab-confirmed (lab override)" : EPISTEMIC_LABEL[s.epistemic_status]}
                  </span>
                  <div className="mt-0.5 text-ink-primary">Score: {s.evidence_score.toFixed(2)}</div>
                  {sub && (
                    <div className="text-ink-muted">
                      (Cs = {sub.sensor_corroboration.toFixed(2)}, Cc = {sub.citizen_agreement.toFixed(2)}, Ct ={" "}
                      {sub.temporal_consistency.toFixed(2)})
                    </div>
                  )}
                </td>
                <td className="py-3 pr-3 text-ink-body">
                  ~{s.site.estimated_exposed_population.toLocaleString("en-GB")} people
                  <div className="text-ink-muted">{humanize(s.site.recreational_use_category)}</div>
                  <div className="text-ink-faint">FHIR Group (actual = false)</div>
                </td>
                <td className="py-3 text-ink-body">{outcomeText(s)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="mt-2 text-[10px] text-ink-faint">
        Every value is computed live by the OAH-Bridge engine (S = 0.40·Cs + 0.30·Cc + 0.30·Ct). Synthetic demonstration
        scenarios; informational context, not a diagnosis.
      </p>
    </div>
  );
}
