/**
 * Stage detail cards. Each renders server state only; review decisions go through the
 * existing gateway endpoints, which enforce every rule.
 */
import clsx from "clsx";
import { ArrowRight, Check, Download, Lock, Minus, X } from "lucide-react";
import { useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import type { MappingRow, Stage, StageDetail, StageEvidence } from "./api";

export const BUTTON =
  "inline-flex items-center justify-center gap-1.5 rounded-md border border-surface-border bg-surface-bg px-3 py-1.5 text-xs font-medium text-ink-primary hover:border-accent-brand hover:text-accent-brand disabled:cursor-not-allowed disabled:opacity-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent-brand";
export const PRIMARY_BUTTON =
  "inline-flex items-center justify-center gap-1.5 rounded-md bg-accent-brand px-3.5 py-2 text-sm font-medium text-ink-invert hover:bg-accent-brand/90 disabled:cursor-not-allowed disabled:opacity-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent-brand focus-visible:ring-offset-2 focus-visible:ring-offset-surface-bg";
const SECTION = "rounded-xl border border-surface-border bg-surface-raised p-4";

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className={SECTION} aria-label={title}>
      <h3 className="text-[11px] font-semibold uppercase tracking-wider text-ink-faint">{title}</h3>
      <div className="mt-3 text-sm text-ink-body">{children}</div>
    </section>
  );
}

function Chips({ items, tone = "neutral" }: { items: string[]; tone?: "neutral" | "warn" }) {
  if (!items.length) return <span className="text-ink-muted">None</span>;
  return (
    <ul className="flex flex-wrap gap-1.5">
      {items.map((item) => (
        <li
          key={item}
          className={clsx(
            "rounded px-1.5 py-0.5 text-xs text-mono-tech",
            tone === "warn" ? "bg-accent-amber/15 text-accent-amber" : "bg-surface-bg text-ink-body",
          )}
        >
          {item}
        </li>
      ))}
    </ul>
  );
}

function Mark({ ok }: { ok: boolean | null }) {
  if (ok === null) return <Minus size={14} className="text-ink-faint" aria-label="not run" />;
  return ok ? (
    <Check size={14} className="text-accent-green" aria-label="passed" />
  ) : (
    <X size={14} className="text-accent-red" aria-label="failed" />
  );
}

export function EvidenceTimeline({ evidence }: { evidence: StageEvidence[] }) {
  if (!evidence.length) return null;
  return (
    <Section title="Proof from the event log">
      <ol className="space-y-2">
        {evidence.map((e) => (
          <li key={`${e.event_type}-${e.timestamp}`} className="text-xs">
            <span className="text-mono-tech text-accent-cyan">{e.event_type}</span>
            <span className="text-ink-muted"> · {new Date(e.timestamp).toLocaleString()} · {e.actor}</span>
            <div className="text-[11px] text-ink-faint text-mono-tech break-all">correlation {e.correlation_id}</div>
          </li>
        ))}
      </ol>
    </Section>
  );
}

export function EvidenceCard({ detail }: { detail: StageDetail }) {
  return (
    <>
      <Section title={`Source fields (${detail.fields?.length ?? 0})`}>
        <ul className="grid grid-cols-2 gap-x-4 gap-y-1">
          {(detail.fields ?? []).map((f) => (
            <li key={f.name} className="flex justify-between gap-2 text-xs">
              <span className="text-mono-tech text-ink-primary">{f.name}</span>
              <span className="text-ink-faint">{f.detected_type}</span>
            </li>
          ))}
        </ul>
      </Section>
      <Section title="Required targets not yet mapped">
        <Chips items={detail.missing_required_fields ?? []} tone="warn" />
      </Section>
      <Section title="Ambiguous fields">
        <Chips items={detail.ambiguities ?? []} tone="warn" />
      </Section>
    </>
  );
}

const GENERIC_ARSENIC = (field: string) => field.trim().toLowerCase().replace(/ /g, "_") === "arsenic";

function MappingDecision({
  row,
  targets,
  busy,
  onDecide,
}: {
  row: MappingRow;
  targets: Record<string, string>;
  busy: boolean;
  onDecide: (row: MappingRow, decision: "approve" | "reject", target: string | null, concept: string | null) => void;
}) {
  const [target, setTarget] = useState(row.target ?? "");
  const [concept, setConcept] = useState(row.concept ?? "");
  const needsConcept = GENERIC_ARSENIC(row.source_field);
  const canApprove = !!target && (!needsConcept || !!concept);
  return (
    <div className="mt-2 flex flex-wrap items-center gap-2">
      <label className="sr-only" htmlFor={`target-${row.source_field}`}>
        Target for {row.source_field}
      </label>
      <select
        id={`target-${row.source_field}`}
        value={target}
        onChange={(e) => setTarget(e.target.value)}
        className="rounded-md border border-surface-border bg-surface-bg px-2 py-1 text-xs focus:outline-none focus-visible:ring-2 focus-visible:ring-accent-brand"
      >
        <option value="">Choose a target…</option>
        {Object.keys(targets).map((t) => (
          <option key={t} value={t}>
            {t}
          </option>
        ))}
      </select>
      {needsConcept && (
        <>
          <label className="sr-only" htmlFor={`concept-${row.source_field}`}>
            Arsenic concept for {row.source_field}
          </label>
          <select
            id={`concept-${row.source_field}`}
            value={concept}
            onChange={(e) => setConcept(e.target.value)}
            className="rounded-md border border-accent-amber/50 bg-surface-bg px-2 py-1 text-xs focus:outline-none focus-visible:ring-2 focus-visible:ring-accent-brand"
          >
            <option value="">Confirm total or inorganic…</option>
            <option value="total_arsenic">Total arsenic</option>
            <option value="inorganic_arsenic">Inorganic arsenic</option>
          </select>
        </>
      )}
      <button
        type="button"
        className={BUTTON}
        disabled={busy || !canApprove}
        onClick={() => onDecide(row, "approve", target, needsConcept ? concept : null)}
      >
        Approve
      </button>
      <button type="button" className={BUTTON} disabled={busy} onClick={() => onDecide(row, "reject", null, null)}>
        Reject
      </button>
    </div>
  );
}

export function MappingCard({
  detail,
  busy = false,
  onDecide,
}: {
  detail: StageDetail;
  busy?: boolean;
  onDecide?: (row: MappingRow, decision: "approve" | "reject", target: string | null, concept: string | null) => void;
}) {
  const rows = detail.mappings ?? [];
  const firewall = detail.semantic_firewall;
  return (
    <>
      {firewall && (
        <Section title="Semantic firewall">
          <p>{firewall.ai_authority}</p>
          <p className="mt-1 text-xs text-ink-muted">AI input: {firewall.ai_input}</p>
          {!!firewall.blocked_inferences?.length && (
            <ul className="mt-2 list-disc space-y-0.5 pl-4 text-xs text-ink-muted">
              {firewall.blocked_inferences.map((b) => (
                <li key={b}>{b}</li>
              ))}
            </ul>
          )}
        </Section>
      )}
      <Section title={`Mappings (${rows.length})`}>
        <ul className="divide-y divide-surface-border" aria-label="Field mappings">
          {rows.map((row) => (
            <li key={row.source_field} className="py-2.5">
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <span className="text-mono-tech text-ink-primary">{row.source_field}</span>
                <ArrowRight size={12} className="text-ink-faint" aria-hidden="true" />
                <span className="text-mono-tech">{row.target ?? "unresolved"}</span>
                <span className="text-ink-faint">{row.fhir_target ?? ""}</span>
                <span className="ml-auto text-ink-muted">
                  {Math.round(row.confidence * 100)}% · {row.origin.replace("_", " ")}
                </span>
                <span
                  className={clsx(
                    "rounded px-1.5 py-0.5 text-[10px] uppercase",
                    row.decision === "accepted" && "bg-accent-green/15 text-accent-green",
                    row.decision === "rejected" && "bg-accent-red/15 text-accent-red",
                    row.decision === "pending" && "bg-accent-amber/15 text-accent-amber",
                  )}
                >
                  {row.decision}
                </span>
              </div>
              {row.concept && <p className="mt-1 text-[11px] text-ink-muted">Concept: {row.concept.replace("_", " ")}</p>}
              {row.decision === "pending" && onDecide && (
                <MappingDecision row={row} targets={detail.targets ?? {}} busy={busy} onDecide={onDecide} />
              )}
            </li>
          ))}
        </ul>
      </Section>
    </>
  );
}

export function FHIRBundleCard({ detail }: { detail: StageDetail }) {
  const types = Object.entries(detail.resource_types ?? {});
  return (
    <Section title="Generated FHIR R4 collection Bundle">
      <ul className="grid grid-cols-2 gap-2">
        {types.map(([type, count]) => (
          <li key={type} className="flex justify-between rounded-md bg-surface-bg px-2 py-1 text-xs">
            <span className="text-mono-tech">{type}</span>
            <span className="text-ink-muted">×{count}</span>
          </li>
        ))}
      </ul>
    </Section>
  );
}

export function ValidationCard({ detail }: { detail: StageDetail }) {
  return (
    <>
      {!!detail.checks?.length && (
        <Section title="Checks">
          <ul className="space-y-1.5">
            {detail.checks.map((c) => (
              <li key={c.name} className="flex items-center gap-2 text-xs">
                <Mark ok={c.passed} />
                {c.name}
              </li>
            ))}
          </ul>
        </Section>
      )}
      <Section title="OperationOutcome">
        <ul className="space-y-1.5">
          {(detail.issues ?? []).map((issue, i) => (
            <li key={`${issue.severity}-${i}`} className="text-xs">
              <span
                className={clsx(
                  "mr-2 rounded px-1.5 py-0.5 text-[10px] uppercase",
                  issue.severity === "error" ? "bg-accent-red/15 text-accent-red" : "bg-surface-bg text-ink-muted",
                )}
              >
                {issue.severity}
              </span>
              {issue.diagnostics}
            </li>
          ))}
        </ul>
      </Section>
      {detail.standards?.validation_scope && (
        <p className="text-xs text-ink-muted">Scope: {detail.standards.validation_scope}</p>
      )}
    </>
  );
}

export function ExchangeCard({ detail }: { detail: StageDetail }) {
  const transfers = detail.transfers ?? [];
  const challenges = detail.challenges ?? [];
  return (
    <>
      <Section title="System A → System B">
        <div className="flex items-center gap-3 text-xs">
          <div className="flex-1 rounded-lg border border-surface-border bg-surface-bg p-3">
            <div className="font-medium text-ink-primary">CLINI-CASE gateway</div>
            <div className="text-ink-muted">Validated collection Bundle</div>
          </div>
          <ArrowRight size={18} className="shrink-0 text-accent-cyan" aria-hidden="true" />
          <div className="flex-1 rounded-lg border border-surface-border bg-surface-bg p-3">
            <div className="font-medium text-ink-primary">System B receiver</div>
            <div className="text-ink-muted">Independent process · own storage · reassigns IDs</div>
          </div>
        </div>
      </Section>
      <Section title={`Transfers (${transfers.length})`}>
        {transfers.length ? (
          <ul className="space-y-2">
            {transfers.map((t) => (
              <li key={t.id} className="text-xs">
                <span className="font-medium text-ink-primary">{t.status}</span>
                {t.resources_acknowledged !== null && <span> · {t.resources_acknowledged} resources acknowledged</span>}
                {t.processing_ms !== null && <span className="text-ink-muted"> · {t.processing_ms} ms in System B</span>}
                {t.error && <div className="text-accent-red">{t.error}</div>}
                <div className="text-[11px] text-mono-tech text-ink-faint">
                  sha256 {t.sha256} · {t.correlation_id}
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-ink-muted">No transfer yet.</p>
        )}
      </Section>
      {!!challenges.length && (
        <Section title="Invalid packages sent to System B">
          <ul className="space-y-1 text-xs">
            {challenges.map((c) => (
              <li key={c.id}>
                {c.status === "rejected" ? "Rejected" : c.status} by System B
                {c.receiver_http ? ` (HTTP ${c.receiver_http})` : ""}
              </li>
            ))}
          </ul>
        </Section>
      )}
    </>
  );
}

export function RoundTripCard({ detail }: { detail: StageDetail }) {
  const fields = detail.roundtrip_fields ?? [];
  const kept = fields.filter((f) => f.preserved).length;
  return (
    <Section title={`Semantic round trip (${kept}/${fields.length})`}>
      <ul className="grid grid-cols-2 gap-x-4 gap-y-1">
        {fields.map((f) => (
          <li key={f.field} className="flex items-center gap-2 text-xs">
            <Mark ok={f.preserved} />
            <span className="text-mono-tech">{f.field}</span>
          </li>
        ))}
      </ul>
    </Section>
  );
}

export function EvidencePassportCard({
  passport,
  busy = false,
  onExport,
}: {
  passport: StageDetail["passport"];
  busy?: boolean;
  onExport?: () => void;
}) {
  if (!passport) return null;
  return (
    <Section title="Evidence Passport">
      <dl className="grid grid-cols-[auto,1fr] gap-x-3 gap-y-1 text-xs">
        <dt className="text-ink-muted">Hash chain</dt>
        <dd className={passport.valid ? "text-accent-green" : "text-accent-red"}>{passport.status ?? "unknown"}</dd>
        <dt className="text-ink-muted">Revisions</dt>
        <dd>{passport.revision_count ?? 0}</dd>
        <dt className="text-ink-muted">Head</dt>
        <dd className="break-all text-mono-tech">{passport.head ?? "—"}</dd>
      </dl>
      {onExport && (
        <button type="button" className={clsx(BUTTON, "mt-3")} disabled={busy} onClick={onExport}>
          <Download size={13} aria-hidden="true" /> Export Evidence Passport
        </button>
      )}
    </Section>
  );
}

export function ClinicalContextCard({ detail }: { detail: StageDetail }) {
  const ceiling = detail.epistemic_ceiling;
  return (
    <>
      <Section title="Connected capabilities">
        <ul className="space-y-2">
          {(detail.connections ?? []).map((c) => (
            <li key={c.capability} className="text-xs">
              {c.href ? (
                <Link to={c.href} className="font-medium text-accent-cyan underline-offset-2 hover:underline">
                  {c.capability}
                </Link>
              ) : (
                <span className="inline-flex items-center gap-1 text-ink-muted">
                  <Lock size={11} aria-hidden="true" /> {c.capability} — closed until consent is recorded
                </span>
              )}
              {c.binding && <div className="text-[11px] text-ink-faint">{c.binding}</div>}
            </li>
          ))}
        </ul>
      </Section>
      {ceiling && (
        <Section title="What this evidence allows us to conclude">
          <p>{ceiling.allowed}</p>
          <ul className="mt-2 list-disc space-y-0.5 pl-4 text-xs text-ink-muted">
            {ceiling.not_allowed.map((text) => (
              <li key={text}>{text}</li>
            ))}
          </ul>
        </Section>
      )}
      {!!detail.assessment_gates?.length && (
        <Section title="Evidence gates">
          <ul className="space-y-1">
            {detail.assessment_gates.map((g) => (
              <li key={g.id} className="flex items-center gap-2 text-xs">
                <Mark ok={g.passed} /> {g.label}
              </li>
            ))}
          </ul>
        </Section>
      )}
    </>
  );
}

export function RetestCard({ detail }: { detail: StageDetail }) {
  const comparison = detail.retest_comparison;
  return (
    <Section title="Retest comparison">
      {comparison ? (
        <>
          <p>
            {comparison.comparable
              ? `Measured change: ${comparison.change_ug_l} µg/L`
              : "Not directly comparable"}
          </p>
          <p className="mt-1 text-xs text-ink-muted">{comparison.meaning}</p>
        </>
      ) : (
        <p className="text-ink-muted">No laboratory retest has been recorded for this evidence yet.</p>
      )}
    </Section>
  );
}

/** The detail body for one stage, assembled from the cards above. */
export function StageDetailBody({
  stage,
  busy,
  onDecide,
  onExport,
}: {
  stage: Stage;
  busy: boolean;
  onDecide?: (row: MappingRow, decision: "approve" | "reject", target: string | null, concept: string | null) => void;
  onExport?: () => void;
}) {
  const d = stage.detail;
  const body: Record<Stage["id"], ReactNode> = {
    ingest: null,
    understand: <EvidenceCard detail={d} />,
    map: <MappingCard detail={d} />,
    review: <MappingCard detail={d} busy={busy} onDecide={onDecide} />,
    standardize: <FHIRBundleCard detail={d} />,
    validate: <ValidationCard detail={d} />,
    exchange: <ExchangeCard detail={d} />,
    verify: (
      <>
        <RoundTripCard detail={d} />
        <EvidencePassportCard passport={d.passport} busy={busy} onExport={onExport} />
      </>
    ),
    clinical_context: <ClinicalContextCard detail={d} />,
    follow_up: <RetestCard detail={d} />,
  };
  return (
    <>
      {body[stage.id]}
      <EvidenceTimeline evidence={stage.evidence} />
    </>
  );
}
