import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../components/AuthContext";
import { BUTTON, INPUT } from "../onehealth/Forms";
import { interop, type Job, type Mapping } from "../interop/api";
const CARD = "rounded-2xl border border-surface-border bg-surface-raised p-5";
const json = (v: unknown) => JSON.stringify(v, null, 2);

export default function Interop() {
  const { user } = useAuth();
  const [job, setJob] = useState<Job | null>(null);
  const [source, setSource] = useState("");
  const [format, setFormat] = useState("json");
  const [system, setSystem] = useState("Synthetic Environmental Lab A");
  const [recordId, setRecordId] = useState("SYN-AS-001");
  const [synthetic, setSynthetic] = useState(true);
  const [bundle, setBundle] = useState("");
  const [checkedBundle, setCheckedBundle] = useState("");
  const [targets, setTargets] = useState<Record<string, string>>({});
  const [receiverMode, setReceiverMode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [returned, setReturned] = useState<unknown>(null);
  const [useAI, setUseAI] = useState(false);
  const [resume, setResume] = useState("");
  const canReview = user?.role === "reviewer" || user?.role === "admin";
  useEffect(() => {
    if (canReview)
      interop<{ targets: Record<string, string>; receiver_mode: string }>(
        "/meta",
      )
        .then((m) => {
          setTargets(m.targets);
          setReceiverMode(m.receiver_mode);
        })
        .catch((e) => setError(String(e)));
  }, [canReview]);
  const command = () => ({ job_id: job!.id, expected_version: job!.version });
  async function run(
    action: () => Promise<Job>,
    updateBundle = false,
    validationText?: string,
  ) {
    setBusy(true);
    setError("");
    try {
      const j = await action();
      setJob(j);
      if (updateBundle) {
        const text = j.bundle ? json(j.bundle) : "";
        setBundle(text);
        setCheckedBundle(j.validation ? text : "");
      } else if (validationText !== undefined) {
        setCheckedBundle(validationText);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }
  if (!canReview)
    return (
      <div className="p-8">
        Track 7 gateway requires a reviewer or administrator.{" "}
        <Link to="/onehealth">Open One Health</Link>
      </div>
    );
  const button = (label: string, action: () => void, disabled = false) => (
    <button className={BUTTON} disabled={busy || disabled} onClick={action}>
      {label}
    </button>
  );
  return (
    <div className="max-w-7xl mx-auto p-6 space-y-6 text-ink-primary">
      <header>
        <p className="text-accent-cyan text-sm">
          TRACK 7 | DIGITAL HEALTH STANDARDS
        </p>
        <h1 className="text-3xl mt-2">
          ONEAQUAHEALTH INTEROPERABILITY GATEWAY
        </h1>
        <p className="text-ink-muted mt-3">
          Move One Health evidence between systems without losing meaning,
          provenance, consent or review state.
        </p>
        <Link className="text-accent-cyan underline" to="/onehealth">
          Existing One Health evidence workbench
        </Link>
      </header>
      <div
        className={`${CARD} flex flex-wrap gap-4 justify-between`}
        aria-label="Interoperability pipeline"
      >
        {[
          "SYSTEM A",
          "AI MAPPING",
          "HUMAN REVIEW",
          "FHIR/OAH",
          "VALIDATION",
          "SYSTEM B",
        ].map((s, i) => (
          <span key={s}>
            {i > 0 && "-> "}
            {s}
          </span>
        ))}
      </div>
      <p className="text-sm text-ink-muted">
        FHIR R4-targeted OAH exchange with pinned profile-aware contract checks
        and round-trip validation. Not full HL7 R4 profile/terminology
        certification. Synthetic simulator: {receiverMode}.
      </p>
      {error && (
        <div
          role="alert"
          className="border border-red-500 rounded-xl p-4 text-red-400"
        >
          {error}
        </div>
      )}
      <div className="flex flex-wrap gap-3">
        {button(
          "Start Track 7 Interoperability Demo",
          () =>
            void run(async () => {
              const j = await interop<Job>("/demo", {});
              setSource(json(j.source.payload));
              setReturned(null);
              return j;
            }, true),
        )}
        <input
          aria-label="Resume job ID"
          className={INPUT}
          value={resume}
          onChange={(e) => setResume(e.target.value)}
        />
        {button(
          "Resume transaction",
          () =>
            void run(
              () => interop<Job>(`/jobs/${encodeURIComponent(resume)}`),
              true,
            ),
          !resume,
        )}
      </div>
      {job && (
        <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
          {Object.entries(job.metrics).map(([k, v]) => (
            <div className={CARD} key={k}>
              <strong className="text-2xl text-accent-cyan">{v}</strong>
              <p className="text-xs">{k.replaceAll("_", " ")}</p>
            </div>
          ))}
        </div>
      )}
      <section className={CARD}>
        <h2 className="text-xl mb-3">1 | Source Data | System A</h2>
        <p className="text-sm text-ink-muted">
          One laboratory record per transaction. Unknown source fields are
          retained even when excluded from the narrow exchange contract.
        </p>
        <div className="flex gap-3 flex-wrap my-3">
          <select
            aria-label="Source format"
            className={INPUT}
            value={format}
            onChange={(e) => setFormat(e.target.value)}
          >
            <option>json</option>
            <option>csv</option>
            <option>fhir</option>
          </select>
          <input
            aria-label="Source system"
            className={INPUT}
            value={system}
            onChange={(e) => setSystem(e.target.value)}
          />
          <input
            aria-label="Original record ID"
            className={INPUT}
            value={recordId}
            onChange={(e) => setRecordId(e.target.value)}
          />
          <label>
            <input
              type="checkbox"
              checked={synthetic}
              onChange={(e) => setSynthetic(e.target.checked)}
            />{" "}
            Synthetic data
          </label>
        </div>
        <textarea
          aria-label="Source data"
          className={`${INPUT} w-full font-mono h-52`}
          value={source}
          onChange={(e) => setSource(e.target.value)}
        />
        {button(
          "Import source package",
          () =>
            void run(
              () =>
                interop<Job>("/import", {
                  source_system: system,
                  original_record_id: recordId,
                  format,
                  payload: format === "csv" ? source : JSON.parse(source),
                  synthetic,
                }),
              true,
            ),
        )}
      </section>
      {job && (
        <>
          <section className={CARD}>
            <h2 className="text-xl">2 | AI Mapping / Schema Discovery</h2>
            <p className="my-2 text-sm">
              Schema discovery and pinned aliases run locally. Optional AI sends
              field names only through the existing governed model gateway.
              Model failure is reported; unknown fields remain unresolved.
            </p>
            <label>
              <input
                type="checkbox"
                checked={useAI}
                onChange={(e) => setUseAI(e.target.checked)}
              />{" "}
              Request model semantic suggestions
            </label>
            <div className="my-3">
              {button(
                "Analyze schema and propose mappings",
                () =>
                  void run(
                    () =>
                      interop<Job>("/analyze-schema", {
                        ...command(),
                        use_ai: useAI,
                      }),
                    true,
                  ),
              )}
            </div>
            <p>{job.ai_status}</p>
            <p>
              Missing required mapped fields:{" "}
              {job.schema?.missing_required_fields.join(", ") || "None"}
            </p>
            <p>
              Ambiguous or unresolved fields:{" "}
              {job.schema?.ambiguities.join(", ") || "None"}
            </p>
          </section>
          <section className={CARD}>
            <h2 className="text-xl mb-3">3 | Human Review</h2>
            <p className="text-sm mb-3">
              Confidence values for deterministic rules are rule scores, not
              measured model accuracy. Every mapping requires an explicit
              decision. Local arsenic codes have no verified LOINC/SNOMED
              mapping.
            </p>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr>
                    {[
                      "Field",
                      "FHIR target / edit",
                      "Confidence / origin",
                      "Review",
                    ].map((x) => (
                      <th key={x} className="text-left p-2">
                        {x}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {job.mappings.map((m) => (
                    <MappingRow
                      key={`${m.source_field}-${job.mapping_version}`}
                      mapping={m}
                      targets={targets}
                      busy={busy}
                      decide={(decision, target, concept) =>
                        void run(
                          () =>
                            interop<Job>(`/mappings/${job.id}/${decision}`, {
                              ...command(),
                              source_field: m.source_field,
                              target,
                              concept,
                            }),
                          true,
                        )
                      }
                    />
                  ))}
                </tbody>
              </table>
            </div>
          </section>
          <section className={CARD}>
            <h2 className="text-xl">4 | FHIR/OAH Bundle</h2>
            <div className="my-3">
              {button(
                "Generate reviewed FHIR/OAH bundle",
                () =>
                  void run(
                    () => interop<Job>("/generate-fhir", command()),
                    true,
                  ),
                !job.mappings.length ||
                  job.mappings.some((m) => m.decision === "pending"),
              )}
            </div>
            <textarea
              aria-label="Editable FHIR bundle"
              className={`${INPUT} w-full h-80 font-mono text-xs`}
              value={bundle}
              onChange={(e) => setBundle(e.target.value)}
            />
            <p className="text-sm">
              Only semantically justified resources are generated. Mapping
              review never verifies a laboratory result or creates patient
              consent.
            </p>
          </section>
          <section className={CARD}>
            <h2 className="text-xl">5 | Validation / Break It</h2>
            <div className="flex gap-3 my-3">
              {button(
                "Validate edited bundle",
                () =>
                  void run(
                    () =>
                      interop<Job>("/validate", {
                        ...command(),
                        bundle: JSON.parse(bundle),
                      }),
                    false,
                    bundle,
                  ),
                !bundle,
              )}
              {button(
                "Run validation failure",
                () =>
                  void run(async () => {
                    const broken = JSON.parse(bundle);
                    const o = broken.entry.find(
                      (e: { resource: { resourceType: string } }) =>
                        e.resource.resourceType === "Observation",
                    ).resource;
                    o.valueQuantity.code = "ppm";
                    o.valueQuantity.unit = "ppm";
                    setBundle(json(broken));
                    const validated = await interop<Job>("/validate", {
                      ...command(),
                      bundle: broken,
                    });
                    setCheckedBundle(json(broken));
                    return validated;
                  }),
                !bundle,
              )}
              {button(
                "Restore generated bundle",
                () => {
                  setBundle(json(job.bundle));
                },
                !job.bundle,
              )}
            </div>
            {job.validation && bundle === checkedBundle && (
              <>
                <strong
                  className={
                    job.validation.valid ? "text-green-400" : "text-red-400"
                  }
                >
                  {job.validation.valid
                    ? "VALIDATION PASSED"
                    : "VALIDATION FAILED"}
                </strong>
                <p className="text-xs break-all">
                  SHA-256: {job.validation.sha256}
                </p>
                {job.validation.operation_outcome.issue.map((i, n) => (
                  <p key={n}>{i.diagnostics}</p>
                ))}
                {job.validation.roundtrip && (
                  <pre className="text-xs overflow-auto">
                    {json(job.validation.roundtrip)}
                  </pre>
                )}
              </>
            )}
            {job.validation && bundle !== checkedBundle && (
              <p role="status">
                Bundle changed | validate this version before transfer.
              </p>
            )}
          </section>
          <section className={CARD}>
            <h2 className="text-xl mb-3">6 | Transfer | 7 | Receiver</h2>
            {button(
              "Transfer to independent Clinical System B / retry",
              () => void run(() => interop<Job>("/transfer", command())),
              !job.validation?.valid ||
                !job.bundle ||
                bundle !== json(job.bundle) ||
                bundle !== checkedBundle,
            )}
            {job.transfers.map((t) => (
              <div
                key={t.id}
                className="my-3 border-t border-surface-border pt-3"
              >
                <strong>{t.status.toUpperCase()}</strong>
                <p className="text-xs break-all">
                  Approved package receipt: {t.id} | SHA-256: {t.sha256}
                </p>
                <p>{t.error}</p>
                {t.acknowledgement && (
                  <>
                    <p>
                      {t.acknowledgement.resources_acknowledged} resources
                      acknowledged
                    </p>
                    <pre className="text-xs max-h-64 overflow-auto">
                      {json(t.acknowledgement.representation)}
                    </pre>
                  </>
                )}
              </div>
            ))}
            <div className="my-3">
              {button(
                "Return FHIR/OAH from System B to Lab A",
                () => {
                  setBusy(true);
                  setError("");
                  interop<{
                    job: Job;
                    lab_representation: unknown;
                    returned_bundle: unknown;
                  }>("/return", command())
                    .then((r) => {
                      setJob(r.job);
                      setReturned(r);
                    })
                    .catch((e) => setError(String(e)))
                    .finally(() => setBusy(false));
                },
                !job.transfers.some((t) => t.status === "delivered"),
              )}
            </div>
            {returned !== null && (
              <pre className="text-xs max-h-72 overflow-auto">
                {json(returned)}
              </pre>
            )}
          </section>
          {job.assessment && (
            <section className={CARD}>
              <h2 className="text-xl">Evidence-aware interoperability</h2>
              <p className="my-2">
                The six trust gates remain visible after exchange. Foreign
                review is never local approval. Clinical follow-up remains in
                the existing One Health workflow.
              </p>
              {job.assessment.gates.map((g) => (
                <p key={g.id}>
                  {g.passed ? "Passed:" : "Missing:"} {g.label}
                </p>
              ))}
              <p className="text-sm mt-3">{job.assessment.notice}</p>
            </section>
          )}
          <section className={CARD}>
            <h2 className="text-xl">8 | Provenance / Audit</h2>
            <p className="text-xs break-all my-3">
              Correlation ID: {job.id} | Version: {job.version} | Mapping
              version: {job.mapping_version}
            </p>
            <ol className="space-y-3">
              {job.events.map((e, i) => (
                <li key={i} className="border-l-2 border-accent-cyan pl-4">
                  <time>{e.timestamp}</time> | {e.event_type} | {e.actor} |{" "}
                  {e.status}
                  <pre className="text-xs overflow-auto">
                    {json(e.provenance)}
                  </pre>
                </li>
              ))}
            </ol>
          </section>
        </>
      )}
    </div>
  );
}
function MappingRow({
  mapping: m,
  targets,
  busy,
  decide,
}: {
  mapping: Mapping;
  targets: Record<string, string>;
  busy: boolean;
  decide: (
    decision: string,
    target: string | null,
    concept: string | null,
  ) => void;
}) {
  const [target, setTarget] = useState(m.target ?? "");
  const [concept, setConcept] = useState(m.concept ?? "");
  return (
    <tr className="border-t border-surface-border">
      <td className="p-2">
        {m.source_field}
        <p className="text-xs text-ink-muted">{m.reason}</p>
      </td>
      <td className="p-2">
        <select
          aria-label={`Target for ${m.source_field}`}
          className={INPUT}
          value={target}
          onChange={(e) => setTarget(e.target.value)}
        >
          <option value="">Unresolved</option>
          {Object.entries(targets).map(([k, v]) => (
            <option value={k} key={k}>
              {v} ({k})
            </option>
          ))}
        </select>
        {m.source_field.trim().toLowerCase() === "arsenic" && (
          <select
            aria-label="Confirm arsenic speciation"
            className={INPUT}
            value={concept}
            onChange={(e) => setConcept(e.target.value)}
          >
            <option value="">Confirm local concept</option>
            <option value="total_arsenic">Total arsenic | local code</option>
            <option value="inorganic_arsenic">
              Inorganic arsenic | local code
            </option>
          </select>
        )}
      </td>
      <td className="p-2">
        {Math.round(m.confidence * 100)}% | {m.origin}
        <p>{m.terminology_status}</p>
      </td>
      <td className="p-2">
        <p>
          {m.decision} {m.reviewer}
        </p>
        <button
          className={BUTTON}
          disabled={
            busy ||
            !target ||
            (m.source_field.trim().toLowerCase() === "arsenic" && !concept)
          }
          onClick={() => decide("approve", target, concept || null)}
        >
          Accept mapping
        </button>
        <button
          className={BUTTON}
          disabled={busy}
          onClick={() => decide("reject", null, null)}
        >
          Reject mapping
        </button>
      </td>
    </tr>
  );
}
