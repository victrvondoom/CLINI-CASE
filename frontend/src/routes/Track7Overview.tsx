import { Link } from "react-router-dom";
import { BUTTON } from "../onehealth/Forms";

export default function Track7Overview() {
  return (
    <main className="min-h-screen bg-surface-bg text-ink-primary px-6 py-16">
      <div className="max-w-5xl mx-auto space-y-10">
        <header className="space-y-5">
          <p className="text-accent-cyan tracking-widest text-xs">
            ONEAQUAHEALTH · TRACK 7 · DIGITAL HEALTH STANDARDS
          </p>
          <h1 className="text-4xl sm:text-6xl">CLINI-CASE</h1>
          <p className="text-xl max-w-3xl">
            One Health Interoperability Gateway
          </p>
          <p className="text-ink-muted max-w-3xl">
            From Evidence to Action, Through One Connected Clinical Journey.
            CLINI-CASE connects intake, evidence, interoperability, review, clinical context and follow-up in one traceable workflow.
          </p>
          <div className="flex flex-wrap gap-4">
            <Link
              className="inline-flex items-center rounded-md bg-accent-brand px-4 py-2 font-medium text-ink-invert hover:bg-accent-brand/90 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent-brand focus-visible:ring-offset-2 focus-visible:ring-offset-surface-bg"
              to="/journey"
            >
              Start the evidence journey
            </Link>
            <Link className={BUTTON} to="/onehealth">
              Open the One Health journey
            </Link>
            <Link className={BUTTON} to="/interop">
              Start Track 7 Interoperability Demo
            </Link>
            <Link className={BUTTON} to="/login">
              Sign in
            </Link>
          </div>
        </header>
        <section className="rounded-2xl border border-accent-cyan/40 p-6 space-y-4">
          <h2 className="text-2xl">
            One observation. One continuous evidence journey.
          </h2>
          <p className="text-accent-cyan">
            Citizen observation → laboratory evidence → human-confirmed mapping
            → FHIR/OAH → independent receiver → retest → updated evidence
            passport
          </p>
          <p className="text-ink-muted">
            Meet Mira, a synthetic community volunteer investigating a
            household's drinking-water outlet. She reports a concern; a lab
            measures arsenic; a reviewer checks the evidence and consent; an
            environmental team retests. A photo never identifies arsenic, and a
            laboratory observation never becomes a disease prediction.
          </p>
        </section>
        <div className="grid sm:grid-cols-3 gap-5">
          {[
            [
              "Evidence Passport",
              "Versioned source, mapping, review, consent and exchange receipts with a persisted hash-chain manifest and offline integrity verification.",
            ],
            [
              "Epistemic ceiling",
              "The same six evidence gates determine what the record supports and what still requires human review.",
            ],
            [
              "Closed-loop retest",
              "A new sample closes the original environmental task, preserves history and starts fresh verification and review.",
            ],
          ].map(([title, text]) => (
            <section
              className="rounded-xl border border-surface-border p-5"
              key={title}
            >
              <h2 className="text-lg text-accent-cyan">{title}</h2>
              <p className="text-sm text-ink-muted mt-3">{text}</p>
            </section>
          ))}
        </div>
        <p className="text-sm text-ink-muted">
          Synthetic demonstration. FHIR R4-targeted OAH exchange with pinned
          profile-aware contract checks and round-trip validation. Not full HL7
          R4 profile/terminology certification. Reference mappings are
          deterministic; optional live AI uses the existing governed model
          service.
        </p>
        <details className="rounded-xl border border-surface-border p-5">
          <summary className="cursor-pointer">Shared platform context</summary>
          <p className="text-sm text-ink-muted mt-3">
            AquaHealth provides citizen observations. One Health governs
            evidence and sharing. CLINI-CASE, OncoTwin and CardioTwin retain their
            existing clinical workflows and can display consented evidence
            context; environmental measurements do not alter clinical
            conclusions.
          </p>
          <Link
            className="block mt-3 text-accent-cyan underline"
            to="/platform"
          >
            Explore all existing platform capabilities
          </Link>
        </details>
      </div>
    </main>
  );
}
