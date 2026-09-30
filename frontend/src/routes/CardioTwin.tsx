/**
 * /cardiotwin — CardioTwin: patient physiology → calibrated vessel-level estimates → evidence → schematic anatomy.
 *
 * The 3D view is a semantic display of MODEL OUTPUT. It does not localise, size or characterise any lesion.
 */
import { Activity, ArrowRight } from "lucide-react";
import { Suspense, lazy, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ExposureContext } from "../onehealth/ContextPanel";

import { cardio } from "../cardiotwin/api";
import { PatientPanel } from "../cardiotwin/PatientPanel";
import { SensitivityPanel } from "../cardiotwin/Sensitivity";
import {
  CARD,
  CadCard,
  EvidenceChain,
  EvidencePanel,
  Legend,
  SafetyBanner,
  TrustPanel,
  VesselCard,
  WarningList,
} from "../cardiotwin/panels";
import {
  VESSELS,
  type CounterfactualResult,
  type FeatureCatalog,
  type PatientValues,
  type Prediction,
  type Scenario,
  type TargetId,
  type VesselId,
} from "../cardiotwin/types";
import { pct } from "../cardiotwin/vesselMapping";

const HeartViewer = lazy(() => import("../cardiotwin/HeartViewer"));

export default function CardioTwin() {
  const [searchParams] = useSearchParams();
  const [catalog, setCatalog] = useState<FeatureCatalog | null>(null);
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [scenarioNote, setScenarioNote] = useState("");
  const [patient, setPatient] = useState<PatientValues>({});
  const [scenarioId, setScenarioId] = useState<string | null>(null);
  const [pred, setPred] = useState<Prediction | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [selected, setSelected] = useState<TargetId>("LAD");
  const [cfActive, setCfActive] = useState(false);
  const [cf, setCf] = useState<CounterfactualResult | null>(null);
  const [view, setView] = useState<"baseline" | "perturbed">("perturbed");
  const [preset, setPreset] = useState<Record<string, number | string> | null>(null);
  const seq = useRef(0);
  const firstLoad = useRef(true);
  const pickTop = useRef(true); // after a scenario loads, select its highest-probability vessel

  // ---- bootstrap: feature catalog + demo scenarios ------------------------------------------
  useEffect(() => {
    let live = true;
    Promise.all([cardio.features(), cardio.scenarios()])
      .then(([f, s]) => {
        if (!live) return;
        setCatalog(f);
        setScenarios(s.scenarios);
        setScenarioNote(s.note);
      })
      .catch((e) => live && setErr((e as Error).message));
    return () => {
      live = false;
    };
  }, []);

  const loadScenario = useCallback((s: Scenario) => {
    setScenarioId(s.id);
    setPatient({ ...s.patient });
    setCf(null);
    setPreset(s.perturbation ?? null);
    setCfActive(!!s.perturbation);
    setView("perturbed");
    pickTop.current = true;
  }, []);

  useEffect(() => {
    if (firstLoad.current && scenarios.length) {
      firstLoad.current = false;
      loadScenario(scenarios.find((s) => s.id === "C") ?? scenarios[0]);
    }
  }, [scenarios, loadScenario]);

  // ---- live prediction (debounced; stale responses are dropped) ------------------------------
  useEffect(() => {
    if (!Object.keys(patient).length) {
      setPred(null);
      return;
    }
    const id = ++seq.current;
    setBusy(true);
    const h = setTimeout(async () => {
      try {
        const r = await cardio.predict(patient, scenarioId);
        if (id !== seq.current) return;
        setPred(r);
        setErr(null);
        if (pickTop.current) {
          pickTop.current = false;
          setSelected(VESSELS.reduce((a, b) => (r.vessels[b].probability > r.vessels[a].probability ? b : a), "LAD" as VesselId));
        }
      } catch (e) {
        if (id === seq.current) setErr((e as Error).message);
      } finally {
        if (id === seq.current) setBusy(false);
      }
    }, 300);
    return () => clearTimeout(h);
  }, [patient, scenarioId]);

  const shown: Prediction | null = cfActive && cf && view === "perturbed" ? cf.perturbed : pred;
  const viz = shown ? shown.visualization.vessels : null;
  const selectedVessel: VesselId | null = selected === "CAD" ? null : selected;

  const onEdit = (name: string, v: number | string | null) => {
    setScenarioId(null);
    setPatient((p) => ({ ...p, [name]: v }));
  };

  const chips = useMemo(
    () => (shown ? ([["CAD", shown.cad], ...VESSELS.map((v) => [v, shown.vessels[v]] as const)] as const) : []),
    [shown],
  );

  return (
    <div className="px-4 sm:px-6 py-6 space-y-4 max-w-[1500px]">
      <header className="space-y-2">
        <div className="flex flex-wrap items-end justify-between gap-2">
          <div>
            <h1 className="text-2xl font-semibold text-ink-primary flex items-center gap-2">
              <Activity size={22} aria-hidden /> CardioTwin
            </h1>
            <p className="text-[12.5px] text-ink-body">Cardiovascular risk visualization and vessel-level prediction</p>
          </div>
          <Link
            to="/cardiotwin/evaluation"
            className="text-[12px] inline-flex items-center gap-1 text-ink-muted hover:text-ink-primary"
          >
            Evaluation &amp; methods <ArrowRight size={12} aria-hidden />
          </Link>
        </div>
        <SafetyBanner />
      </header>

      <ExposureContext exposureId={searchParams.get("exposure") ?? undefined} independentCardio />

      {err && (
        <div role="alert" data-testid="cardiotwin-error" className="rounded-lg border border-accent-red/50 bg-accent-red/10 px-3 py-2 text-[12.5px]">
          {err}
        </div>
      )}

      {catalog && (
        <PatientPanel
          catalog={catalog}
          scenarios={scenarios}
          scenarioNote={scenarioNote}
          activeScenario={scenarioId}
          patient={patient}
          onScenario={loadScenario}
          onChange={onEdit}
          onClear={() => {
            setPatient({});
            setScenarioId(null);
            setCf(null);
            setCfActive(false);
          }}
        />
      )}

      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)] gap-4">
        {/* ---------------- left: 3D ---------------- */}
        <div className="space-y-3 min-w-0">
          <div className={`${CARD} relative overflow-hidden`} data-testid="viewer-card">
            <div
              data-testid="viewer-disclaimer"
              className="absolute z-10 left-2 top-2 max-w-[70%] rounded-md bg-surface-bg/85 border border-accent-amber/50 px-2 py-1 text-[10.5px] text-ink-primary"
            >
              Schematic anatomy · estimated probability per vessel · <b>not a lesion location</b> · not diagnostic imaging
            </div>
            <div className="h-[420px] sm:h-[540px]">
              <Suspense fallback={<div className="h-full grid place-items-center text-[12px] text-ink-muted">Loading 3D view…</div>}>
                <HeartViewer viz={viz} selected={selectedVessel} onSelect={(id) => setSelected(id ?? "CAD")} />
              </Suspense>
            </div>
            {busy && <div className="absolute right-2 bottom-2 text-[11px] text-ink-muted" role="status">updating…</div>}
            {cfActive && cf && (
              <div className="absolute left-2 bottom-2 rounded-md bg-surface-bg/85 border border-surface-border px-2 py-0.5 text-[11px]" data-testid="viewer-mode">
                Showing: <b>{view === "perturbed" ? "perturbed (sensitivity simulation)" : "baseline"}</b>
              </div>
            )}
          </div>

          {/* keyboard / screen-reader path to the same selection the 3D view offers */}
          <div className="flex flex-wrap gap-1.5" role="group" aria-label="Select vessel">
            {chips.map(([id, t]) => (
              <button
                key={id}
                type="button"
                aria-pressed={selected === id}
                data-testid={`select-${id}`}
                onClick={() => setSelected(id as TargetId)}
                className={`px-2.5 py-1 rounded-md border text-[12px] tabular-nums focus:outline-none focus:ring-2 focus:ring-accent-brand ${
                  selected === id ? "border-accent-brand bg-accent-brand/10 text-ink-primary" : "border-surface-border text-ink-body"
                }`}
              >
                {id} {pct(t.probability)}
              </button>
            ))}
          </div>
          <Legend />
          <EvidenceChain target={selected} />
        </div>

        {/* ---------------- right: dashboard ---------------- */}
        <div className="space-y-3 min-w-0">
          {shown ? (
            <>
              <WarningList warnings={shown.warnings} />
              <CadCard t={shown.cad} selected={selected === "CAD"} onSelect={() => setSelected("CAD")} />
              <div className="grid grid-cols-1 sm:grid-cols-3 xl:grid-cols-1 2xl:grid-cols-3 gap-2">
                {VESSELS.map((v) => (
                  <VesselCard key={v} t={shown.vessels[v]} selected={selected === v} onSelect={() => setSelected(v)} />
                ))}
              </div>
              <EvidencePanel pred={shown} target={selected} />
            </>
          ) : (
            <div className={`${CARD} p-6 text-[13px] text-ink-muted`}>
              Load a scenario or enter patient values to see predicted CAD probability and estimated vessel-level
              stenosis probabilities.
            </div>
          )}
        </div>
      </div>

      {catalog && pred && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <SensitivityPanel
            catalog={catalog}
            patient={patient}
            active={cfActive}
            onActive={(v) => {
              setCfActive(v);
              if (!v) setCf(null);
            }}
            preset={preset}
            view={view}
            onView={setView}
            onResult={setCf}
            selectedTarget={selected}
          />
          {shown && <TrustPanel pred={shown} />}
        </div>
      )}
    </div>
  );
}
