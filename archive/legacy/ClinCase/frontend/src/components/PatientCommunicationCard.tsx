/**
 * Patient Communication card — output of the 7th agent (Patient Communicator).
 *
 * Shows the patient-facing explanation of the case outcome, calibrated to
 * a 6th-grade reading level, with concrete next-step actions. Per CMS-0057-F
 * § IV.C patient-accessible decision rationale.
 */
import { ChevronDown, ChevronUp, Heart, Mail, Printer } from "lucide-react";
import { useState } from "react";

import type { PatientCommunication } from "../lib/types";

interface Props {
  communication: PatientCommunication;
  patientInitials?: string;
}

const TONE_BG: Record<PatientCommunication["tone"], string> = {
  reassuring: "bg-accent-green/10 border-accent-green/30 text-accent-green",
  neutral:    "bg-accent-cyan/10  border-accent-cyan/30  text-accent-cyan",
  urgent:     "bg-accent-amber/10 border-accent-amber/30 text-accent-amber",
};

const TIMING_LABEL: Record<string, string> = {
  today: "Today",
  this_week: "This week",
  this_month: "This month",
  after_decision: "After the final decision",
};

export function PatientCommunicationCard({ communication, patientInitials }: Props) {
  const [expanded, setExpanded] = useState(true);
  const grade = communication.reading_level_grade;
  const gradeOk = grade <= 7.0;

  return (
    <div className="bg-surface-raised border border-surface-border rounded-2xl overflow-hidden">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center justify-between px-5 py-3 border-b border-surface-border hover:bg-surface-raised-hi transition-colors"
      >
        <div className="flex items-center gap-2">
          <Heart size={16} className="text-accent-pink" />
          <h3 className="text-sm font-semibold text-ink-primary">
            Patient Communication
          </h3>
          <span className="text-[10px] text-compact text-ink-muted">
            agent 7 / 7
          </span>
          <span className={`text-[10px] text-mono-tech uppercase tracking-wide px-1.5 py-0.5 rounded border ${TONE_BG[communication.tone]}`}>
            {communication.tone}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span
            className={`text-[10px] text-mono-tech ${gradeOk ? "text-accent-green" : "text-accent-amber"}`}
            title={gradeOk ? "Below the 7.0 reading-level target" : "Above the 7.0 reading-level target — consider rerunning"}
          >
            grade {grade.toFixed(1)} {gradeOk ? "✓" : "⚠"}
          </span>
          {expanded ? <ChevronUp size={14} className="text-ink-muted" /> : <ChevronDown size={14} className="text-ink-muted" />}
        </div>
      </button>

      {expanded && (
        <>
          <div className="px-5 py-4 border-b border-surface-border">
            {patientInitials && (
              <div className="text-[10px] text-mono-tech text-ink-faint mb-2">
                For: <span className="text-ink-body">{patientInitials}</span>
              </div>
            )}
            <h4 className="text-base font-semibold text-ink-primary leading-snug mb-3">
              {communication.headline}
            </h4>
            <div className="text-sm text-ink-body leading-relaxed space-y-2 whitespace-pre-line">
              {communication.body}
            </div>
          </div>

          {communication.next_steps.length > 0 && (
            <div className="px-5 py-3 border-b border-surface-border">
              <div className="text-[10px] text-compact text-ink-muted mb-2">
                What you can do next
              </div>
              <ul className="space-y-1.5">
                {communication.next_steps.map((s) => (
                  <li key={s.step_number} className="flex items-start gap-3 text-sm">
                    <span className="text-[10px] text-mono-tech text-ink-faint w-4 shrink-0 mt-1">
                      {s.step_number}.
                    </span>
                    <div className="flex-1">
                      <div className="text-ink-body">{s.text}</div>
                      <div className="text-[10px] text-mono-tech text-ink-muted mt-0.5">
                        {TIMING_LABEL[s.timing] ?? s.timing}
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="px-5 py-2 bg-surface-panel/40 flex items-center justify-between text-[10px] text-mono-tech text-ink-muted">
            <span>
              sub-agents: reading_level_tuner · empathy_layer · action_step_writer
            </span>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => window.print()}
                className="flex items-center gap-1 hover:text-ink-body transition-colors"
                title="Print this for the patient"
              >
                <Printer size={11} />
                Print
              </button>
              <button
                type="button"
                onClick={() => {
                  const subj = encodeURIComponent("Your insurance update");
                  const body = encodeURIComponent(
                    communication.headline + "\n\n" + communication.body,
                  );
                  window.location.href = `mailto:?subject=${subj}&body=${body}`;
                }}
                className="flex items-center gap-1 hover:text-ink-body transition-colors"
                title="Email this to the patient (mail client)"
              >
                <Mail size={11} />
                Email
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
