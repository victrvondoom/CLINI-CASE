/**
 * Identifier-screening receipt. It distinguishes backend-supplied Guardrail
 * evidence from the deterministic example used by the local demonstration.
 *
 * Renders on CaseDetail every time a run completes so reviewers see the
 * redaction pipeline without clicking anything. The transient PHIBanner is
 * the cinematic alternative for demo emphasis; this component is the boring
 * always-on receipt that an enterprise architect actually wants to see.
 *
 * When no entities and Guardrail identifier are supplied, the component is
 * visibly marked illustrative and must not be treated as compliance evidence.
 *
 * Reference: AWS Bedrock Guardrails — Sensitive information policy.
 */
import { Eye, EyeOff, ShieldCheck } from "lucide-react";
import { useState } from "react";

interface RedactedEntity {
  type: "NAME" | "DOB" | "SSN" | "MRN" | "PHONE" | "ADDRESS" | "EMAIL";
  masked: string;
  detected_at: string;     // e.g. "physician_note:char_142"
  action: "MASK" | "BLOCK"; // Guardrail outcome
}

interface Props {
  caseId: string;
  /** If omitted, falls back to a deterministic per-case demo set. */
  entities?: RedactedEntity[];
  /** Bedrock Guardrail identifier from settings.BEDROCK_GUARDRAIL_ID. */
  guardrailId?: string;
  guardrailVersion?: string;
}

const ENTITY_TINT: Record<RedactedEntity["type"], string> = {
  NAME:    "bg-accent-violet/15 text-accent-violet border-accent-violet/30",
  DOB:     "bg-accent-amber/15  text-accent-amber  border-accent-amber/30",
  SSN:     "bg-accent-red/15    text-accent-red    border-accent-red/30",
  MRN:     "bg-accent-cyan/15   text-accent-cyan   border-accent-cyan/30",
  PHONE:   "bg-accent-blue/15   text-accent-blue   border-accent-blue/30",
  ADDRESS: "bg-accent-brand/15  text-accent-brand  border-accent-brand/30",
  EMAIL:   "bg-accent-green/15  text-accent-green  border-accent-green/30",
};

function _deterministicEntities(caseId: string): RedactedEntity[] {
  // Deterministic from caseId so the same case always shows the same
  // redaction set in screenshots / videos.
  const seed = Array.from(caseId).reduce((s, c) => s + c.charCodeAt(0), 0);
  const ringPositions = [38, 76, 114, 142, 188, 230, 268];
  const all: RedactedEntity[] = [
    { type: "NAME",    masked: "{NAME}",                detected_at: `physician_note:char_${ringPositions[seed % 7]}`, action: "MASK" },
    { type: "DOB",     masked: "{DATE_OF_BIRTH}",       detected_at: `physician_note:char_${ringPositions[(seed + 1) % 7]}`, action: "MASK" },
    { type: "MRN",     masked: "{MRN}",                 detected_at: `physician_note:char_${ringPositions[(seed + 2) % 7]}`, action: "MASK" },
    { type: "SSN",     masked: "{US_SOCIAL_SECURITY_NUMBER}", detected_at: `physician_note:char_${ringPositions[(seed + 3) % 7]}`, action: "MASK" },
    { type: "PHONE",   masked: "{PHONE}",               detected_at: `physician_note:char_${ringPositions[(seed + 4) % 7]}`, action: "MASK" },
  ];
  // Vary the count 3-5 entries by case
  return all.slice(0, 3 + (seed % 3));
}

export function PHIRedactionReceipt({
  caseId,
  entities,
  guardrailId,
  guardrailVersion = "1",
}: Props) {
  const [reveal, setReveal] = useState(false);
  const verified = Boolean(entities?.length && guardrailId);
  const list = entities && entities.length > 0 ? entities : _deterministicEntities(caseId);
  const guardrail = guardrailId || "local-screening-example";

  return (
    <div className="bg-surface-raised border border-surface-border rounded-2xl overflow-hidden">
      <div className={`px-5 py-2.5 border-b border-surface-border flex items-center gap-2 flex-wrap ${verified ? "bg-accent-green/5" : "bg-accent-amber/5"}`}>
        <ShieldCheck size={14} className={verified ? "text-accent-green" : "text-accent-amber"} />
        <h3 className="text-sm font-semibold text-ink-primary">
          {verified ? "Guardrail identifier screening receipt" : "Illustrative identifier screening"}
        </h3>
        <span className={`text-[10px] text-compact ${verified ? "text-accent-green" : "text-accent-amber"}`}>
          {verified ? "AWS Bedrock Guardrail" : "DEMO OUTPUT"} · {guardrail} v{guardrailVersion}
        </span>
        <span className="ml-auto text-[10px] text-mono-tech text-ink-muted">
          {list.length} entit{list.length === 1 ? "y" : "ies"} masked
        </span>
      </div>

      <div className="px-5 py-3">
        <div className="flex flex-wrap gap-1.5 mb-3">
          {list.map((e, i) => (
            <span
              key={i}
              title={`${e.type} detected at ${e.detected_at} → ${e.action}`}
              className={`text-[11px] text-mono-tech px-2 py-0.5 rounded border ${ENTITY_TINT[e.type]}`}
            >
              {e.type}
              <span className="opacity-60 ml-1">→ {e.masked}</span>
            </span>
          ))}
        </div>

        <button
          type="button"
          onClick={() => setReveal((r) => !r)}
          className="text-[11px] text-mono-tech text-ink-muted hover:text-ink-body flex items-center gap-1"
        >
          {reveal ? <EyeOff size={11} /> : <Eye size={11} />}
          {reveal ? "Hide" : "Show"} per-entity provenance
        </button>

        {reveal && (
          <div className="mt-3 bg-surface-panel/40 border border-surface-border rounded-lg overflow-hidden">
            <table className="w-full text-xs">
              <thead className="bg-surface-panel text-[10px] text-compact text-ink-muted">
                <tr>
                  <th className="text-left px-3 py-1.5">Entity</th>
                  <th className="text-left px-3 py-1.5">Masked</th>
                  <th className="text-left px-3 py-1.5">Detected at</th>
                  <th className="text-left px-3 py-1.5">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-border">
                {list.map((e, i) => (
                  <tr key={i}>
                    <td className={`px-3 py-1.5 text-mono-tech ${ENTITY_TINT[e.type].split(" ")[1]}`}>
                      {e.type}
                    </td>
                    <td className="px-3 py-1.5 text-mono-tech text-ink-body">{e.masked}</td>
                    <td className="px-3 py-1.5 text-mono-tech text-ink-muted">{e.detected_at}</td>
                    <td className="px-3 py-1.5 text-mono-tech text-accent-green">{e.action}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="px-5 py-2 border-t border-surface-border bg-surface-panel/40 text-[10px] text-mono-tech text-ink-muted leading-relaxed">
        {verified
          ? "Backend-supplied screening evidence. Identifier screening reduces exposure but is not certified de-identification; deployment controls and human review remain required."
          : "Illustrative entities generated from the case identifier. This is not evidence that the source document was de-identified or that a cloud Guardrail ran."}
      </div>
    </div>
  );
}
