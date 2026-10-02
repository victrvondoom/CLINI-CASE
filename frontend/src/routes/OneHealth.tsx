import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  ArrowRight,
  CheckCircle2,
  Database,
  FileJson2,
  GitBranch,
  ShieldCheck,
} from "lucide-react";
import { aqua } from "../aquahealth/api";
import type { Observation, ObservationSummary } from "../aquahealth/types";
import { useAuth } from "../components/AuthContext";
import {
  onehealth,
  type ExposureRecord,
  type CaseCandidate,
  type Meta,
  type Patient,
  type Validation,
} from "../onehealth/api";
import { BUTTON, Field, HistoryForm, INPUT, LabForm } from "../onehealth/Forms";
import { EvidenceJourney } from "../onehealth/Journey";

const CARD = "rounded-2xl border border-surface-border bg-surface-raised p-5";
const pretty = (s: string) => s.replaceAll("_", " ");

export default function OneHealth() {
  const { user } = useAuth();
  const canReview = user?.role === "reviewer" || user?.role === "admin";
  return canReview ? (
    <Workbench />
  ) : (
    <div className="p-8 max-w-4xl">
      <h1 className="text-2xl text-ink-primary">CLINI-CASE / One Health</h1>
      <p className="mt-3 text-ink-muted">
        Track 7 · Digital Health Standards. Patient-linked exposure evidence is
        restricted to reviewers and administrators.
      </p>
      <Link
        to="/aquahealth"
        className="inline-block mt-4 text-accent-cyan underline"
      >
        Continue with citizen freshwater observations
      </Link>
    </div>
  );
}

function Workbench() {
  const [query, setQuery] = useSearchParams();
  const selectedId = query.get("record");
  const [meta, setMeta] = useState<Meta | null>(null);
  const [records, setRecords] = useState<ExposureRecord[]>([]);
  const [patients, setPatients] = useState<Patient[]>([]);
  const [observations, setObservations] = useState<ObservationSummary[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [showLab, setShowLab] = useState(false);
  const [tab, setTab] = useState("connection");
  const seq = useRef(0);
  const load = useCallback(async () => {
    const generation = ++seq.current;
    setError("");
    try {
      const [m, rows, people, obs] = await Promise.all([
        onehealth.meta(),
        onehealth.list(),
        onehealth.patients(),
        aqua.listObservations({ limit: 500, includeDemo: true }),
      ]);
      if (generation !== seq.current) return;
      setMeta(m);
      setRecords(rows.records);
      setPatients(people.patients);
      setObservations(obs.observations);
    } catch (e) {
      if (generation === seq.current) {
        setError(
          e instanceof Error ? e.message : "Failed to load evidence workspace",
        );
      }
      throw e;
    }
  }, []);
  useEffect(() => {
    let active = true;
    load()
      .catch((e) => {
        if (active) setError(String(e.message));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
      seq.current++;
    };
  }, [load]);
  const selected =
    records.find((r) => r.id === selectedId) ??
    (selectedId ? null : records[0]);
  async function mutate(fn: () => Promise<ExposureRecord>) {
    setBusy(true);
    setError("");
    try {
      const result = await fn();
      await load();
      setQuery({ record: result.id });
      setShowLab(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Operation failed");
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="p-4 sm:p-7 max-w-[1500px] mx-auto space-y-5">
      <header className="rounded-2xl border border-accent-cyan/30 bg-gradient-to-br from-accent-cyan/10 via-surface-raised to-surface-panel p-6 sm:p-8">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="text-mono-tech text-[10px] tracking-widest text-accent-cyan">
              PRIMARY TRACK 7 · DIGITAL HEALTH STANDARDS
            </div>
            <h1 className="text-display text-3xl text-ink-primary mt-2">
              CLINI-CASE / One Health
            </h1>
            <p className="text-sm text-ink-body mt-2">
              Evidence-aware One Health interoperability.
            </p>
            <p className="text-xs text-ink-muted mt-2 max-w-2xl">
              One traceable connection across AquaHealth, OncoTwin, CardioTwin
              and CLINI-CASE. Evidence and consent travel with the record;
              clinical judgment stays with the reviewer.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link className={BUTTON} to="/interop">
              Start Track 7 Interoperability Demo
            </Link>
            <button
              disabled={busy}
              className={BUTTON}
              onClick={() => void mutate(onehealth.demo)}
            >
              <Database size={13} className="inline mr-1" aria-hidden />
              Start synthetic journey
            </button>
            <button
              disabled={busy}
              className={BUTTON}
              onClick={() => setShowLab(!showLab)}
            >
              Add laboratory evidence
            </button>
          </div>
        </div>
        <div className="mt-5 flex flex-wrap gap-2 text-[10px] text-ink-muted">
          <Chip>FHIR R4 target · pinned OAH draft</Chip>
          <Chip>Consent, review and evidence travel together</Chip>
          <Chip>
            {meta?.persistence === "postgresql"
              ? "PostgreSQL persistence"
              : meta?.persistence === "sqlite_synthetic_demo_only"
                ? "Durable synthetic demo storage"
                : "Demo mode · volatile synthetic data only"}
          </Chip>
        </div>
      </header>
      <div className="rounded-xl border border-accent-amber/30 bg-accent-amber/5 p-4 text-xs text-ink-body">
        {meta?.notice ??
          "Exposure decision support only. No cancer or cardiovascular diagnosis is inferred from stream observations."}{" "}
        {meta?.persistence === "volatile_synthetic_demo_only" &&
          "Demo evidence is lost on server restart. Non-synthetic writes are disabled without PostgreSQL."}
      </div>
      {error && (
        <div
          role="alert"
          className="rounded-xl border border-accent-red p-4 text-sm text-accent-red"
        >
          {error}
          <button
            className={`${BUTTON} ml-3`}
            disabled={busy}
            onClick={() => {
              setError("");
              void load().catch((e) => setError(e.message));
            }}
          >
            Reload evidence
          </button>
        </div>
      )}
      {loading && (
        <p role="status" className="text-sm text-ink-muted">
          Loading evidence workspace…
        </p>
      )}
      {busy && (
        <p role="status" className="text-xs text-accent-cyan">
          Saving evidence and audit together…
        </p>
      )}
      {showLab && (
        <Section title="New laboratory evidence">
          <LabForm
            observations={observations}
            persistence={meta?.persistence ?? "unavailable"}
            busy={busy}
            onSubmit={(id, sample) =>
              void mutate(() => onehealth.create(id, sample))
            }
          />
        </Section>
      )}
      {!loading && !records.length && (
        <div className={`${CARD} py-12 text-center`}>
          <GitBranch
            size={34}
            className="mx-auto text-accent-cyan"
            aria-hidden
          />
          <h2 className="text-lg text-ink-primary mt-4">
            Build the evidence connection
          </h2>
          <p className="text-sm text-ink-muted mt-2 max-w-xl mx-auto">
            Start a synthetic journey or attach laboratory evidence to a citizen
            observation. The system will show what is known, what is missing and
            which actions require a human.
          </p>
        </div>
      )}
      {records.length > 0 && (
        <div className="grid xl:grid-cols-[260px_minmax(0,1fr)] gap-5">
          <aside className="space-y-2" aria-label="Exposure records">
            <h2 className="text-xs text-ink-muted px-1">
              EVIDENCE RECORDS · {records.length}
            </h2>
            {records.map((r) => (
              <button
                key={r.id}
                disabled={busy}
                aria-pressed={selected?.id === r.id}
                onClick={() => setQuery({ record: r.id })}
                className={`w-full text-left rounded-xl border p-4 ${selected?.id === r.id ? "border-accent-cyan bg-accent-cyan/10" : "border-surface-border bg-surface-raised"}`}
              >
                <div className="text-[10px] text-accent-amber">
                  {r.synthetic
                    ? "SYNTHETIC DEMONSTRATION"
                    : "RECORDED LAB EVIDENCE"}
                </div>
                <div className="text-sm text-ink-primary mt-1">
                  {r.waterbody_name}
                </div>
                <div className="text-xs text-ink-muted mt-2">
                  {r.sample.sample_id} · v{r.version}
                </div>
                <div className="text-xs text-ink-body mt-1">
                  {pretty(r.assessment.state)}
                </div>
              </button>
            ))}
          </aside>
          <main className="min-w-0 space-y-4">
            {selectedId && !selected && (
              <p role="alert">
                This evidence record is unavailable in your organisation.
              </p>
            )}
            {selected && (
              <>
                <EvidenceJourney
                  key={`${selected.id}-${selected.version}`}
                  record={selected}
                  busy={busy}
                  mutate={mutate}
                />
                <div
                  className="flex flex-wrap gap-2"
                  role="group"
                  aria-label="Evidence workspace views"
                >
                  {[
                    ["connection", "Connection & review"],
                    ["exchange", "FHIR exchange"],
                    ["challenge", "Evidence challenge"],
                  ].map(([id, label]) => (
                    <button
                      key={id}
                      className={BUTTON}
                      aria-pressed={tab === id}
                      onClick={() => setTab(id)}
                    >
                      {label}
                    </button>
                  ))}
                </div>
                {tab === "connection" && (
                  <Connection
                    key={selected.id}
                    record={selected}
                    patients={patients}
                    observations={observations}
                    busy={busy}
                    mutate={mutate}
                  />
                )}
                {tab === "exchange" && (
                  <Exchange
                    key={`${selected.id}-${selected.version}`}
                    record={selected}
                    busy={busy}
                    mutate={mutate}
                  />
                )}
                {tab === "challenge" && <Challenge record={selected} />}
              </>
            )}
          </main>
        </div>
      )}
      {meta && (
        <details className={`${CARD} text-xs text-ink-muted`}>
          <summary className="cursor-pointer text-ink-primary">
            Standards contract & validation boundary
          </summary>
          <p className="mt-3">{meta.standards.validation_scope}</p>
          <p className="mt-2">{meta.standards.notice}</p>
          <a
            className="mt-2 inline-block text-accent-cyan underline break-all"
            href={meta.standards.source}
            target="_blank"
            rel="noreferrer"
          >
            Pinned OAH source · {meta.standards.oah_commit}
          </a>
        </details>
      )}
    </div>
  );
}

function Connection({
  record: r,
  patients,
  observations,
  busy,
  mutate,
}: {
  record: ExposureRecord;
  patients: Patient[];
  observations: ObservationSummary[];
  busy: boolean;
  mutate: (fn: () => Promise<ExposureRecord>) => Promise<void>;
}) {
  const [note, setNote] = useState("");
  const [caseId, setCaseId] = useState("");
  const [samePatient, setSamePatient] = useState(false);
  const [caseCandidates, setCaseCandidates] = useState<CaseCandidate[]>([]);
  const [caseCandidatesError, setCaseCandidatesError] = useState("");
  const [followupEvidence, setFollowupEvidence] = useState(recordEvidence(r));
  const [source, setSource] = useState<Observation | null>(null);
  const [sourceError, setSourceError] = useState("");
  useEffect(() => {
    let active = true;
    setSource(null);
    setSourceError("");
    aqua
      .getObservation(r.observation_id)
      .then((value) => {
        if (active) setSource(value);
      })
      .catch((e) => {
        if (active)
          setSourceError(
            e instanceof Error ? e.message : "Source observation unavailable",
          );
      });
    return () => {
      active = false;
    };
  }, [r.observation_id]);
  useEffect(() => {
    let active = true;
    setCaseCandidates([]);
    setCaseCandidatesError("");
    if (r.persistence !== "postgresql") return;
    onehealth
      .caseCandidates()
      .then((result) => {
        if (active) setCaseCandidates(result.cases);
      })
      .catch((e) => {
        if (active)
          setCaseCandidatesError(
            e instanceof Error ? e.message : "CLINI-CASE cases unavailable",
          );
      });
    return () => {
      active = false;
    };
  }, [r.persistence, r.id]);
  const action = (name: string, payload: Record<string, unknown> = {}) =>
    void mutate(() => onehealth.action(r, name, { note, ...payload }));
  const canNote = note.trim().length >= 8 && !busy;
  const linkedObservation = observations.find((o) => o.id === r.observation_id);
  return (
    <>
      <section className={CARD} aria-label="Evidence connection">
        <h2 className="text-sm text-ink-primary flex gap-2 items-center">
          <GitBranch size={16} className="text-accent-cyan" aria-hidden />{" "}
          Evidence connection
        </h2>
        <div className="grid sm:grid-cols-3 lg:grid-cols-6 gap-2 mt-4">
          {[
            [
              "01 · AQUAHEALTH",
              "Citizen observation",
              !!source || !!linkedObservation,
            ],
            ["02 · LABORATORY", "Verified sample", r.lab_verified],
            [
              "03 · EXPOSURE",
              "Consented pathway",
              r.assessment.eligible_for_review,
            ],
            [
              "04 · CLINICAL",
              "Human review",
              r.assessment.state === "reviewed_exposure_context",
            ],
            ["05 · CLINCASE", "Case linked", !!r.case_id],
            [
              "06 · AQUAHEALTH",
              "Retest completed",
              r.followup_status === "completed",
            ],
          ].map(([label, title, passed]) => (
            <div
              key={String(label)}
              className={`rounded-xl border p-3 ${passed ? "border-accent-cyan/40 bg-accent-cyan/5" : "border-dashed border-surface-border"}`}
            >
              <div className="text-[9px] text-ink-muted">{label}</div>
              <div className="text-xs text-ink-primary mt-2">{title}</div>
              <div className="text-[10px] mt-2 text-ink-muted">
                {passed ? "Evidence present" : "Not yet established"}
              </div>
            </div>
          ))}
        </div>
        <div className="mt-3 rounded-lg border border-surface-border p-3 text-xs">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="text-ink-primary">AquaHealth source record</span>
            {(source || linkedObservation) && (
              <Link
                className="text-accent-cyan underline"
                to={`/aquahealth/observations/${r.observation_id}`}
              >
                Open observation →
              </Link>
            )}
          </div>
          {source && (
            <p className="mt-2 text-ink-muted">
              {source.reference} · {source.waterbody_name} ·{" "}
              {pretty(source.review_status)} · {pretty(source.verification)}
            </p>
          )}
          {!source && linkedObservation && (
            <p className="mt-2 text-ink-muted">
              {linkedObservation.reference} · {linkedObservation.waterbody_name}{" "}
              · {pretty(linkedObservation.review_status)} ·{" "}
              {pretty(linkedObservation.verification)}
            </p>
          )}
          {sourceError && (
            <p role="status" className="mt-2 text-accent-amber">
              Source could not be refreshed: {sourceError}
            </p>
          )}
          {!source && !sourceError && (
            <p role="status" className="mt-2 text-ink-muted">
              Refreshing linked source observation…
            </p>
          )}
          {!source && sourceError && !linkedObservation && (
            <p className="mt-2 text-ink-muted">
              This exposure record cannot currently confirm its linked
              AquaHealth observation.
            </p>
          )}
        </div>
      </section>
      <div className="grid lg:grid-cols-2 gap-4">
        <Section title="Sample & measurement">
          <p className="text-3xl text-ink-primary">
            {r.sample.qualifier === "lt" ? "< " : ""}
            {r.assessment.concentration_ug_l}{" "}
            <span className="text-base text-ink-muted">µg/L</span>
          </p>
          <p className="text-xs text-ink-muted mt-1">
            {pretty(r.sample.analyte)} · {pretty(r.sample.kind)}
          </p>
          <dl className="text-xs grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 mt-4">
            <dt>Location</dt>
            <dd>{r.sample.location_name}</dd>
            <dt>Laboratory</dt>
            <dd>{r.sample.laboratory}</dd>
            <dt>Report</dt>
            <dd>{r.sample.report_reference}</dd>
            <dt>Collected</dt>
            <dd>{new Date(r.sample.collected_at).toLocaleString()}</dd>
            <dt>Method</dt>
            <dd>{r.sample.method}</dd>
            <dt>Review</dt>
            <dd>{r.lab_verified ? "Reviewer verified" : "Unverified"}</dd>
          </dl>
          <p className="text-xs text-accent-amber mt-4">
            {pretty(r.assessment.comparison)}
          </p>
          <p className="text-xs text-ink-muted mt-2">{r.assessment.meaning}</p>
          <a
            href={r.assessment.reference.url}
            rel="noreferrer"
            target="_blank"
            className="text-xs text-accent-cyan underline mt-2 inline-block"
          >
            {r.assessment.reference.name} · {r.assessment.reference.value}{" "}
            {r.assessment.reference.unit}
          </a>
        </Section>
        <Section title="Evidence required for clinical review">
          <ul className="space-y-3">
            {r.assessment.gates.map((g) => (
              <li key={g.id} className="flex gap-2 text-xs">
                <span
                  className={
                    g.passed ? "text-accent-green" : "text-accent-amber"
                  }
                >
                  {g.passed ? "✓" : "○"}
                </span>
                <span>
                  {g.label}
                  <span className="sr-only">
                    {g.passed ? " — present" : " — missing"}
                  </span>
                </span>
              </li>
            ))}
          </ul>
          <p className="text-xs text-ink-muted mt-4">
            These are evidence checks, not a disease probability or an
            ecological health score.
          </p>
        </Section>
      </div>
      <details className={CARD} open={!r.history}>
        <summary className="cursor-pointer text-sm text-ink-primary">
          Consented exposure history
        </summary>
        <div className="mt-4">
          <HistoryForm
            key={`${r.id}-${r.version}`}
            record={r}
            patients={patients}
            busy={busy}
            onSubmit={(history) =>
              void mutate(() => onehealth.action(r, "link", { history }))
            }
          />
        </div>
      </details>
      <Section title="Human review & environmental follow-up">
        <Field label="Reviewer note / supporting evidence (at least 8 characters)">
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            maxLength={1500}
            className={INPUT}
            placeholder="What did you check? Record uncertainty and the next action."
          />
        </Field>
        <div className="flex flex-wrap gap-2 mt-3">
          <button
            className={BUTTON}
            disabled={!canNote || r.lab_verified}
            onClick={() => action("verify")}
          >
            Verify laboratory report
          </button>
          <button
            className={BUTTON}
            disabled={!canNote || !r.assessment.eligible_for_review}
            onClick={() => action("review", { decision: "reviewed" })}
          >
            Record clinical review
          </button>
          <button
            className={BUTTON}
            disabled={!canNote}
            onClick={() => action("review", { decision: "more_information" })}
          >
            Request more information
          </button>
          <button
            className={BUTTON}
            disabled={!canNote}
            onClick={() => action("review", { decision: "rejected" })}
          >
            Reject clinical connection
          </button>
        </div>
        <div className="mt-4 border-t border-surface-border pt-4">
          <p className="text-xs text-ink-muted mb-3">
            Environmental task: {pretty(r.followup_status)}. The citizen-facing
            task contains no patient identifiers or clinical notes.
          </p>
          <Field label="Retest or investigation report reference">
            <input
              value={followupEvidence}
              maxLength={300}
              onChange={(e) => setFollowupEvidence(e.target.value)}
              className={INPUT}
            />
          </Field>
          <div className="flex gap-2 flex-wrap mt-3">
            <button
              className={BUTTON}
              disabled={!canNote}
              onClick={() =>
                action("followup", {
                  status: "in_progress",
                  evidence_reference: followupEvidence,
                })
              }
            >
              Start source investigation
            </button>
            <button
              className={BUTTON}
              disabled={!canNote || !followupEvidence.trim()}
              onClick={() =>
                action("followup", {
                  status: "completed",
                  evidence_reference: followupEvidence,
                })
              }
            >
              Record retest / follow-up completed
            </button>
            <button
              className={BUTTON}
              disabled={!canNote || !r.history || r.consent_withdrawn}
              onClick={() => action("withdraw-consent")}
            >
              Withdraw clinical-sharing consent
            </button>
          </div>
        </div>
      </Section>
      <Section title="One record, three clinical contexts">
        <div className="grid sm:grid-cols-3 gap-3">
          <ContextCard
            title="OncoTwin"
            text={r.assessment.clinical_context.oncology}
            href={
              r.history && !r.consent_withdrawn
                ? `/twin/${r.history.patient_id}/evidence`
                : undefined
            }
          />
          <ContextCard
            title="CardioTwin"
            text={r.assessment.clinical_context.cardiovascular}
            href={
              !r.consent_withdrawn ? `/cardiotwin?exposure=${r.id}` : undefined
            }
          />
          <ContextCard
            title="CLINI-CASE"
            text="Attach reviewed evidence to an existing case for the same patient. No treatment decision or authorization score changes."
            href={r.case_id ? `/cases/${r.case_id}` : undefined}
          />
        </div>
        <p className="text-xs text-ink-muted mt-3">
          {r.assessment.clinical_context.speciation}
        </p>
        <details className="mt-4">
          <summary className="text-xs cursor-pointer text-accent-cyan">
            Link reviewed evidence to an existing CLINI-CASE case
          </summary>
          <div className="mt-3 space-y-3">
            <Field label="Existing CLINI-CASE case (same organisation)">
              <select
                className={INPUT}
                value={caseId}
                onChange={(e) => {
                  setCaseId(e.target.value);
                  setSamePatient(false);
                }}
                disabled={
                  r.persistence !== "postgresql" || !caseCandidates.length
                }
              >
                <option value="">Select an existing case</option>
                {caseCandidates.map((candidate) => (
                  <option key={candidate.id} value={candidate.id}>
                    {candidate.id} · {candidate.patient_initials} ·{" "}
                    {candidate.treatment} · {candidate.status}
                  </option>
                ))}
              </select>
            </Field>
            {caseCandidatesError && (
              <p role="alert" className="text-xs text-accent-amber">
                Case list unavailable: {caseCandidatesError}
              </p>
            )}
            <label className="text-xs flex gap-2">
              <input
                type="checkbox"
                checked={samePatient}
                onChange={(e) => setSamePatient(e.target.checked)}
              />
              I verified this is the same patient and the same synthetic/real
              context.
            </label>
            <button
              className={BUTTON}
              disabled={
                !canNote ||
                !caseId ||
                !samePatient ||
                r.persistence !== "postgresql" ||
                !caseCandidates.some((candidate) => candidate.id === caseId) ||
                r.assessment.state !== "reviewed_exposure_context"
              }
              onClick={() =>
                action("case-link", {
                  case_id: caseId,
                  same_patient_confirmed: true,
                })
              }
            >
              Attach reviewed evidence
            </button>
            <p className="text-xs text-ink-muted">
              {r.persistence === "postgresql"
                ? "Requires an existing case in this organisation and reviewer confirmation of patient identity."
                : "Case linking is unavailable in volatile demo mode; connect PostgreSQL to enable persistent CLINI-CASE linkage."}
              Nothing is submitted to a payer.
            </p>
          </div>
        </details>
      </Section>
      <Section title="Evidence timeline & reviewer provenance">
        <ol className="space-y-4">
          {r.audit.map((a, i) => (
            <li
              key={`${a.at}-${i}`}
              className="border-l-2 border-accent-cyan/30 pl-4"
            >
              <div className="text-xs text-ink-primary">
                {pretty(a.action)}{" "}
                <span className="text-ink-muted">
                  · {new Date(a.at).toLocaleString()}
                </span>
              </div>
              <p className="text-xs text-ink-muted mt-1 break-words">
                {a.note}
              </p>
              <p className="text-[10px] text-ink-faint mt-1">
                Authenticated actor {a.actor_id}
              </p>
            </li>
          ))}
        </ol>
      </Section>
    </>
  );
}

function Exchange({
  record,
  busy,
  mutate,
}: {
  record: ExposureRecord;
  busy: boolean;
  mutate: (fn: () => Promise<ExposureRecord>) => Promise<void>;
}) {
  const [text, setText] = useState("");
  const [validation, setValidation] = useState<Validation | null>(null);
  const [error, setError] = useState("");
  const [working, setWorking] = useState(false);
  async function run(fn: () => Promise<void>) {
    setWorking(true);
    setError("");
    setValidation(null);
    try {
      await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Exchange failed");
    } finally {
      setWorking(false);
    }
  }
  function download() {
    const url = URL.createObjectURL(
      new Blob([text], { type: "application/fhir+json" }),
    );
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${record.id}.fhir.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  }
  return (
    <Section title="FHIR interoperability workbench">
      <p className="text-xs text-ink-muted">
        Native Location, Specimen, Observation, Consent, Patient,
        QuestionnaireResponse, Task and Provenance resources. Export, inspect,
        validate, then stage an import as new unverified evidence.
      </p>
      <div className="flex flex-wrap gap-2 mt-4">
        <button
          className={BUTTON}
          disabled={working || busy || record.consent_withdrawn}
          onClick={() =>
            void run(async () => {
              const result = await onehealth.export(record.id);
              setText(JSON.stringify(result.bundle, null, 2));
              setValidation(result.validation);
            })
          }
        >
          <FileJson2 size={13} className="inline mr-1" aria-hidden />
          Export & check round-trip
        </button>
        <button
          className={BUTTON}
          disabled={!text || working || busy}
          onClick={() =>
            void run(async () =>
              setValidation(await onehealth.validate(JSON.parse(text))),
            )
          }
        >
          Validate edited bundle
        </button>
        <button
          className={BUTTON}
          disabled={
            !validation?.valid || working || busy || record.consent_withdrawn
          }
          onClick={download}
        >
          Download FHIR JSON
        </button>
      </div>
      {error && (
        <p role="alert" className="text-xs text-accent-red mt-3">
          {error}
        </p>
      )}
      {working && (
        <p role="status" className="text-xs text-ink-muted mt-3">
          Checking exchange contract…
        </p>
      )}
      {validation && (
        <div className="rounded-xl border border-surface-border p-4 mt-4 text-xs space-y-2">
          <p
            className={
              validation.valid ? "text-accent-green" : "text-accent-red"
            }
          >
            {validation.valid
              ? "Selected contract checks passed"
              : "Exchange rejected"}
          </p>
          {validation.operation_outcome.issue.map((i, index) => (
            <p key={index}>{i.diagnostics}</p>
          ))}
          <p>{validation.standards.validation_scope}</p>
          <p className="text-accent-amber">
            Full HL7 profile validation: not performed. Draft alignment is not
            certification.
          </p>
          <p className="break-all text-ink-muted">
            Content SHA-256: {validation.sha256}
          </p>
          <p className="text-ink-muted">
            Digest identifies content; it is not a digital signature or proof of
            authenticity.
          </p>
          {validation.roundtrip && (
            <p>
              Round-trip: sample{" "}
              {validation.roundtrip.sample_preserved ? "preserved" : "CHANGED"}{" "}
              · exposure history{" "}
              {validation.roundtrip.history_preserved ? "preserved" : "CHANGED"}
              .
            </p>
          )}
        </div>
      )}
      <Field label="FHIR collection bundle JSON">
        <textarea
          aria-label="FHIR collection bundle JSON"
          className={`${INPUT} mt-4 font-mono text-[11px] min-h-80`}
          spellCheck={false}
          maxLength={500000}
          value={text}
          onChange={(e) => {
            setText(e.target.value);
            setValidation(null);
          }}
        />
      </Field>
      <div className="mt-4 border-t border-surface-border pt-4">
        <p className="text-xs text-ink-muted mb-3">
          Import binds to this record’s local citizen observation. Incoming
          provenance is archived, but laboratory verification and patient
          consent must be established again. Existing clinical records are never
          overwritten.
        </p>
        <button
          className={BUTTON}
          disabled={
            !validation?.valid || working || busy || record.consent_withdrawn
          }
          onClick={() =>
            void mutate(() =>
              onehealth.import(JSON.parse(text), record.observation_id),
            )
          }
        >
          Stage as new unverified evidence
        </button>
      </div>
    </Section>
  );
}

function Challenge({ record }: { record: ExposureRecord }) {
  return (
    <Section title="Evidence challenge · remove one dependency">
      <p className="text-xs text-ink-muted">
        A deterministic sensitivity check: remove one evidence link on an
        in-memory copy and recompute eligibility. This tests workflow gates—not
        biological causality or disease risk. Your stored record is unchanged.
      </p>
      <div className="overflow-x-auto mt-4">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-surface-border text-left text-ink-muted">
              <th className="p-3">Evidence withheld</th>
              <th className="p-3">Clinical-review eligibility</th>
            </tr>
          </thead>
          <tbody>
            {record.ablation.map((row) => (
              <tr key={row.removed} className="border-b border-surface-border">
                <td className="p-3">{row.removed}</td>
                <td
                  className={`p-3 ${row.eligible_for_review ? "text-accent-red" : "text-accent-amber"}`}
                >
                  {row.eligible_for_review
                    ? "Still eligible — investigate"
                    : "Withheld"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="mt-4 flex gap-2 text-xs text-ink-muted">
        <ShieldCheck
          size={18}
          className="shrink-0 text-accent-cyan"
          aria-hidden
        />
        A nearby address, stream photo or imported approval cannot supply a
        missing exposure pathway.
      </div>
    </Section>
  );
}
function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className={CARD}>
      <h2 className="text-sm font-semibold text-ink-primary mb-4">{title}</h2>
      {children}
    </section>
  );
}
function recordEvidence(record: ExposureRecord) {
  return record.followup_evidence_reference ?? "";
}
function Chip({ children }: { children: ReactNode }) {
  return (
    <span className="border border-surface-border rounded-full px-2.5 py-1">
      {children}
    </span>
  );
}
function ContextCard({
  title,
  text,
  href,
}: {
  title: string;
  text: string;
  href?: string;
}) {
  return (
    <div className="rounded-xl border border-surface-border p-4">
      <h3 className="text-sm text-ink-primary flex items-center gap-2">
        <CheckCircle2 size={13} className="text-accent-cyan" aria-hidden />
        {title}
      </h3>
      <p className="text-xs text-ink-muted mt-2">{text}</p>
      {href && (
        <Link
          className="text-xs text-accent-cyan mt-3 inline-flex items-center gap-1"
          to={href}
        >
          Open context <ArrowRight size={12} aria-hidden />
        </Link>
      )}
    </div>
  );
}
