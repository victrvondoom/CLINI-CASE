/**
 * The results a judge looks for first, read straight from the server's stage facts:
 * validation, exchange, semantic preservation, passport signature and the optional third-party check.
 * Nothing here is computed on the client.
 */
import clsx from "clsx";

import type { Stage } from "./api";

function fact(stage: Stage | undefined, label: string): string | undefined {
  const value = stage?.facts.find((f) => f.label === label)?.value;
  return value === undefined ? undefined : String(value);
}

export function ProofStrip({ stages }: { stages: Stage[] }) {
  const by = (id: Stage["id"]) => stages.find((s) => s.id === id);
  const validate = by("validate");
  const exchange = by("exchange");
  const verify = by("verify");
  if (![validate, exchange, verify].some((s) => s?.status === "complete")) return null;

  const done = (s: Stage | undefined) => s?.status === "complete";
  const signature = fact(verify, "Passport signature");
  const external = fact(verify, "Third-party FHIR server");
  const preserved = fact(verify, "Fields preserved");
  const items: { label: string; value: string; ok: boolean }[] = [
    { label: "Validation", value: validate && done(validate) ? validate.summary : "not yet", ok: done(validate) },
    { label: "Exchange", value: exchange && done(exchange) ? exchange.summary : "not yet", ok: done(exchange) },
    {
      label: "Semantic round trip",
      value: preserved ? `${preserved} fields preserved` : "not yet",
      ok: done(verify),
    },
    { label: "Passport signature", value: signature ?? "not yet", ok: !!signature?.startsWith("Ed25519") },
    {
      label: "Third-party FHIR server",
      value: external ?? "not run (optional)",
      ok: !!external?.startsWith("passed"),
    },
  ];
  return (
    <section aria-label="Proof summary" className="rounded-2xl border border-surface-border bg-surface-raised p-4">
      <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        {items.map((item) => (
          <li key={item.label} className="min-w-0">
            <p className="text-[11px] uppercase tracking-wider text-ink-faint">{item.label}</p>
            <p className={clsx("mt-0.5 break-words text-sm", item.ok ? "text-accent-green" : "text-ink-muted")}>
              {item.ok ? "✓ " : ""}
              {item.value}
            </p>
          </li>
        ))}
      </ul>
    </section>
  );
}
