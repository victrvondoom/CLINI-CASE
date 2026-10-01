import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { interop, type Job } from "../interop/api";
import { onehealth, type ExposureRecord, type Journey } from "./api";
import { BUTTON, Field, INPUT, LabForm } from "./Forms";

export function downloadPassport(value: unknown, id: string) {
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(value, null, 2)], { type: "application/json" }),
  );
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${id}-evidence-passport.json`;
  anchor.click();
  URL.revokeObjectURL(url);
}

export function EvidenceJourney({
  record: r,
  busy,
  mutate,
}: {
  record: ExposureRecord;
  busy: boolean;
  mutate: (action: () => Promise<ExposureRecord>) => Promise<void>;
}) {
  const navigate = useNavigate();
  const [journey, setJourney] = useState<Journey | null>(null);
  const [error, setError] = useState("");
  const [working, setWorking] = useState(false);
  const [note, setNote] = useState("");
  async function action(fn: () => Promise<void>) {
    setWorking(true);
    setError("");
    try {
      await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setWorking(false);
    }
  }
  return (
    <section
      className="rounded-2xl border border-accent-cyan/40 bg-surface-raised p-5 space-y-4"
      aria-label="Continuous One Health journey"
    >
      <h2 className="text-xl">One evidence journey</h2>
      <p className="text-sm text-ink-muted">
        Citizen observation → lab → reviewed exchange → consented clinical
        context → environmental retest. All capabilities share this evidence
        identity.
      </p>
      {r.epistemic_ceiling && (
        <div
          aria-label="Evidence ceiling"
          className="rounded-xl border border-surface-border p-4"
        >
          <h3 className="text-sm text-accent-cyan">
            WHAT THIS DATA ALLOWS US TO CONCLUDE
          </h3>
          <p className="mt-2">{r.epistemic_ceiling.allowed}</p>
          <p className="text-xs text-ink-muted mt-2">
            Evidence level: {r.epistemic_ceiling.level.replaceAll("_", " ")}
          </p>
          <ul className="text-xs text-ink-muted list-disc pl-4 mt-2">
            {r.epistemic_ceiling.not_allowed.map((text) => (
              <li key={text}>{text}</li>
            ))}
          </ul>
        </div>
      )}
      <div className="flex flex-wrap gap-3">
        <button
          className={BUTTON}
          disabled={working || busy}
          onClick={() =>
            void action(async () => {
              setJourney(await onehealth.journey(r.id));
            })
          }
        >
          Open continuous journey
        </button>
        <button
          className={BUTTON}
          disabled={working || busy || r.consent_withdrawn}
          onClick={() =>
            void action(async () => {
              downloadPassport(await onehealth.passport(r.id), r.id);
            })
          }
        >
          Export Evidence Passport
        </button>
        <button
          className={BUTTON}
          disabled={working || busy || r.consent_withdrawn}
          onClick={() =>
            void action(async () => {
              const j = await interop<Job>("/from-evidence", {
                exposure_id: r.id,
                expected_version: r.version,
              });
              navigate(`/interop?job=${encodeURIComponent(j.id)}`);
            })
          }
        >
          Exchange this evidence update
        </button>
      </div>
      {r.passport_integrity && (
        <p role="status" className="text-xs">
          Passport: {r.passport_integrity.status} ·{" "}
          {r.passport_integrity.revision_count ?? 0} revisions · {r.persistence}
        </p>
      )}
      <p className="text-xs text-ink-muted">{r.trust_states?.join(" → ")}</p>
      {journey && (
        <>
          <p className="text-sm">Sharing consent: {journey.consent_status}</p>
          <div className="grid sm:grid-cols-2 gap-3">
            {journey.connections.map((c) => (
              <div
                key={c.capability}
                className="rounded-lg border border-surface-border p-3 text-sm"
              >
                {c.href ? (
                  <Link className="text-accent-cyan underline" to={c.href}>
                    {c.capability}
                  </Link>
                ) : (
                  <span>
                    {c.capability} · awaiting an explicit consented connection
                  </span>
                )}
                <p className="text-xs text-ink-muted mt-1">{c.binding}</p>
              </div>
            ))}
          </div>
          {journey.retest_comparison && (
            <div aria-label="Retest comparison">
              <Link
                to={`/onehealth?record=${journey.retest_comparison.previous_record_id}`}
                className="text-accent-cyan underline"
              >
                Original measurement
              </Link>
              <p>
                Measured change:{" "}
                {journey.retest_comparison.comparable
                  ? `${journey.retest_comparison.change_ug_l} ug/L`
                  : "Not directly comparable"}
              </p>
              <p className="text-xs text-ink-muted">
                {journey.retest_comparison.meaning}
              </p>
            </div>
          )}
        </>
      )}
      {r.successor_id && (
        <Link
          className="block text-accent-cyan underline"
          to={`/onehealth?record=${r.successor_id}`}
        >
          Open linked retest; original measurement retained
        </Link>
      )}
      {!r.successor_id && !r.consent_withdrawn && (
        <details>
          <summary className="cursor-pointer text-accent-cyan">
            Close the loop with a new laboratory retest
          </summary>
          <p className="text-xs mt-3">
            The original sample stays intact. The new sample needs its own
            verification, consent/pathway confirmation and review.
          </p>
          <Field label="Retest reviewer note">
            <input
              className={INPUT}
              value={note}
              onChange={(e) => setNote(e.target.value)}
              minLength={8}
            />
          </Field>
          <div className="mt-3">
            <LabForm
              observations={[
                {
                  id: r.observation_id,
                  reference: r.observation_id,
                  waterbody_name: r.waterbody_name,
                  is_demo: r.synthetic,
                },
              ]}
              persistence={r.persistence}
              busy={busy || working || note.trim().length < 8}
              onSubmit={(_, sample) =>
                void mutate(() =>
                  onehealth.action(r, "retest", { sample, note }),
                )
              }
            />
          </div>
        </details>
      )}
      {error && (
        <p role="alert" className="text-red-400">
          {error}
        </p>
      )}
    </section>
  );
}
