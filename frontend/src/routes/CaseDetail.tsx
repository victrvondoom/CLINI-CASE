import { ArrowLeft, Loader2, Play, Scale, ShieldCheck } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { AppealLetterEditor } from "../components/AppealLetterEditor";
import { AuditLogViewer } from "../components/AuditLogViewer";
import { BusinessValuePanel } from "../components/BusinessValuePanel";
import { CaseEconomicsStrip } from "../components/CaseEconomicsStrip";
import { ComplianceScorecardCard } from "../components/ComplianceScorecardCard";
import { DenialForecastCard } from "../components/DenialForecastCard";
import { EvidencePackButton } from "../components/EvidencePackButton";
import { PatientCommunicationCard } from "../components/PatientCommunicationCard";
import { CitationChip } from "../components/CitationChip";
import { CitationModal } from "../components/CitationModal";
import { ClinicalSummaryCard } from "../components/ClinicalSummaryCard";
import { DecisionBadge } from "../components/DecisionBadge";
import { DocGapPanel } from "../components/DocGapPanel";
import { PayerCell } from "../components/PayerCell";
import { PHIBanner } from "../components/PHIBanner";
import { PHIRedactionReceipt } from "../components/PHIRedactionReceipt";
import { ReasoningTracePanel } from "../components/ReasoningTracePanel";
import { TrizettoSubmitPanel } from "../components/TrizettoSubmitPanel";
import { api } from "../lib/api";
import { openTraceStream, type StreamHandle } from "../lib/sse";
import type { Citation, RunResult, TraceEvent } from "../lib/types";

interface CaseInfo {
  payer_id: string;
  patient_initials: string;
  status: string;
  physician_note: string | null;
  requested_treatment: { name: string; j_code: string | null };
  created_at: string | null;
}

export default function CaseDetail() {
  const { caseId } = useParams<{ caseId: string }>();
  const [caseInfo, setCaseInfo] = useState<CaseInfo | null>(null);
  const [events, setEvents] = useState<TraceEvent[]>([]);
  const [result, setResult] = useState<RunResult | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [phiBannerOpen, setPhiBannerOpen] = useState(false);
  const [citationOpen, setCitationOpen] = useState<Citation | null>(null);
  const streamRef = useRef<StreamHandle | null>(null);

  useEffect(() => {
    if (!caseId) return;
    api.getCase(caseId).then(setCaseInfo).catch((e) => setError(String(e)));
    return () => {
      streamRef.current?.close();
    };
  }, [caseId]);

  const runClinCase = useCallback(async () => {
    if (!caseId || running) return;
    setRunning(true);
    setEvents([]);
    setResult(null);
    setError(null);

    await new Promise<void>((resolve) => {
      const stream = openTraceStream(
        caseId,
        (ev) => setEvents((prev) => [...prev, ev]),
        (err) => console.warn("SSE error", err),
        () => resolve(),
      );
      streamRef.current = stream;
      setTimeout(() => resolve(), 1500);
    });

    try {
      const r = await api.runFull(caseId);
      setResult(r);
    } catch (e) {
      setError(String(e));
    } finally {
      streamRef.current?.close();
      streamRef.current = null;
      setRunning(false);
    }
  }, [caseId, running]);

  if (!caseId) return null;

  return (
    <div className="mx-auto max-w-7xl px-6 py-6 relative">
      <PHIBanner open={phiBannerOpen} onClose={() => setPhiBannerOpen(false)} />
      <CitationModal citation={citationOpen} onClose={() => setCitationOpen(null)} />
      <div className="flex items-center justify-between mb-5">
        <Link
          to="/cases"
          className="text-sm text-ink-muted hover:text-ink-primary flex items-center gap-1 transition-colors"
        >
          <ArrowLeft size={14} />
          All cases
        </Link>
        <div className="text-xs text-mono-tech text-ink-muted">
          case <span className="bg-surface-panel px-1.5 py-0.5 rounded text-ink-body">{caseId}</span>
        </div>
      </div>

      {/* Top row: case header + Run button */}
      <div className="bg-surface-raised border border-surface-border rounded-2xl p-5 mb-5 flex items-center justify-between gap-4 flex-wrap">
        <div className="min-w-0">
          <div className="text-[10px] text-compact text-ink-muted mb-1.5">
            Prior Authorisation Request
          </div>
          {caseInfo ? (
            <div>
              <div className="font-semibold text-lg text-ink-primary">
                {caseInfo.requested_treatment.name}
                {caseInfo.requested_treatment.j_code && (
                  <span className="ml-2 text-mono-tech text-xs px-2 py-0.5 rounded bg-surface-panel text-ink-body align-middle">
                    {caseInfo.requested_treatment.j_code}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-3 mt-1.5 text-sm text-ink-muted flex-wrap">
                <span>Patient <span className="text-mono-tech text-ink-body">{caseInfo.patient_initials}</span></span>
                <span className="text-ink-faint">·</span>
                <PayerCell payer_id={caseInfo.payer_id} />
                <span className="text-ink-faint">·</span>
                <span>status <span className="text-mono-tech text-ink-body">{caseInfo.status}</span></span>
              </div>
            </div>
          ) : (
            <Loader2 size={16} className="animate-spin text-ink-faint" />
          )}
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setPhiBannerOpen(true)}
            className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg border border-accent-red/30 text-sm text-accent-red hover:bg-accent-red/10 transition-colors"
            title="Simulate Bedrock Guardrails firing on a PHI-laden physician note"
          >
            <ShieldCheck size={14} />
            Test PHI Guardrail
          </button>
          <Link
            to={`/cases/${caseId}/compare`}
            className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg border border-surface-border text-sm text-ink-body hover:bg-surface-raised-hi transition-colors"
          >
            <Scale size={14} />
            Compare payers
          </Link>

          <button
            type="button"
            onClick={runClinCase}
            disabled={running}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-accent-brand text-ink-invert font-semibold hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {running ? (
              <>
                <Loader2 size={16} className="animate-spin" />
                Running 7-agent graph...
              </>
            ) : (
              <>
                <Play size={16} />
                Run ClinCase
                <kbd className="text-[9px] text-mono-tech px-1 py-0.5 rounded bg-white/20">R</kbd>
              </>
            )}
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-5 p-3 rounded-lg bg-accent-red/10 border border-accent-red/30 text-accent-red text-sm">
          {error}
        </div>
      )}

      <div className="grid lg:grid-cols-[1fr_400px] gap-5">
        <div className="space-y-5">
          {caseInfo && (
            <DocGapPanel
              treatmentName={caseInfo.requested_treatment.name}
              physicianNote={caseInfo.physician_note}
            />
          )}

          {result?.clinical_snapshot && (
            <ClinicalSummaryCard snapshot={result.clinical_snapshot} />
          )}

          {result?.decision && (
            <DecisionBadge
              decision={result.decision}
              appealInProgress={Boolean(result.appeal_draft)}
            />
          )}

          {result?.decision && result.decision.citations.length > 0 && (
            <div className="bg-surface-raised border border-surface-border rounded-2xl p-5">
              <div className="text-[10px] text-compact text-ink-muted mb-2">
                Citation Chain ({result.decision.citations.length})
              </div>
              <div className="flex flex-wrap gap-1.5">
                {result.decision.citations.map((c, i) => (
                  <CitationChip
                    key={i}
                    citation={c}
                    onClick={() => setCitationOpen(c)}
                  />
                ))}
              </div>
            </div>
          )}

          {result?.denial_forecast && (
            <DenialForecastCard forecast={result.denial_forecast} />
          )}

          {result?.appeal_draft && (
            <AppealLetterEditor appeal={result.appeal_draft} caseId={caseId} />
          )}

          {result?.patient_communication && (
            <PatientCommunicationCard
              communication={result.patient_communication}
              patientInitials={caseInfo?.patient_initials}
            />
          )}

          {result && <PHIRedactionReceipt caseId={caseId} />}

          {/* Live Business Value strip — pulls /business-value/case live. */}
          {result && (
            <BusinessValuePanel caseId={caseId} refreshKey={1} />
          )}

          {/* Live CMS-0057-F + state-AI-law scorecard. */}
          {result && (
            <ComplianceScorecardCard caseId={caseId} refreshKey={1} />
          )}

          {/* TriZetto AI Gateway one-click submit. */}
          {result?.decision && (
            <TrizettoSubmitPanel caseId={caseId} hasDecision={Boolean(result.decision)} />
          )}

          {/* Auditor-grade evidence pack download. */}
          {result && (
            <EvidencePackButton caseId={caseId} />
          )}

          {result && (
            <CaseEconomicsStrip caseId={caseId} refreshKey={1} />
          )}

          {result && (
            <AuditLogViewer
              caseId={caseId}
              refreshKey={result ? 1 : 0}
            />
          )}

          {!result && !running && (
            <div className="bg-surface-raised border border-dashed border-surface-border rounded-2xl p-8 text-center text-ink-muted">
              <p className="text-sm">
                Click <strong className="text-ink-primary">Run ClinCase</strong> (or press R) to start the 7-agent pipeline.
                <br />
                You'll see the clinical snapshot, decision, and (if denied) appeal letter appear here.
              </p>
            </div>
          )}
        </div>

        <div className="lg:sticky lg:top-20 lg:self-start lg:max-h-[calc(100vh-6rem)]">
          <ReasoningTracePanel events={events} isRunning={running} />
        </div>
      </div>
    </div>
  );
}
