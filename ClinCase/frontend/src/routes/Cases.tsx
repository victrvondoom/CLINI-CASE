/**
 * /cases — All Cases table. Filter pills + payer dropdown + search + table.
 *
 * Hybrid data source: live cases from GET /api/v1/cases (real backend) merged
 * with synthetic historical cases for breadth. Live cases marked with a green
 * "live" pill; synthetic with a faint "demo" pill.
 */
import clsx from "clsx";
import { ArrowRight, ChevronDown, Loader2, Play, Plus, Search, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { authHeader } from "../lib/auth";

import { PayerCell } from "../components/PayerCell";
import { SLABadge } from "../components/SLABadge";
import { StatusPill } from "../components/StatusPill";
import { api, type CaseListItem } from "../lib/api";
import {
  PAYERS,
  STATUSES,
  SYNTHETIC_CASES,
  type CaseStatus,
  type SyntheticCase,
} from "../lib/syntheticCases";

type StatusFilter = "all" | CaseStatus;
type PayerFilter = "all" | "aetna" | "uhc" | "bcbs" | "anthem";

function liveToCase(item: CaseListItem): SyntheticCase {
  const ms = item.created_at ? Date.now() - new Date(item.created_at).getTime() : 0;
  const ago =
    ms < 60_000   ? "just now" :
    ms < 3_600_000 ? `${Math.round(ms / 60_000)}m ago` :
    ms < 86_400_000 ? `${Math.round(ms / 3_600_000)}h ago` :
    `${Math.round(ms / 86_400_000)}d ago`;
  return {
    case_id: item.case_id,
    status: item.status as CaseStatus,
    patient_initials: item.patient_initials,
    treatment: item.treatment,
    j_code: item.j_code ?? "—",
    payer_id: (item.payer_id as SyntheticCase["payer_id"]) ?? "aetna",
    verdict: item.verdict,
    confidence: item.confidence ?? null,
    submitted_at: item.created_at ?? new Date().toISOString(),
    ago,
    diagnosis: "—",  // not in list response
    stage: "—",
    is_synthetic: false,
  };
}

const STATUS_PILLS: { value: StatusFilter; label: string }[] = [
  { value: "all",        label: "All" },
  { value: "pending",    label: "Pending" },
  { value: "running",    label: "Running" },
  { value: "approved",   label: "Approved" },
  { value: "denied",     label: "Denied" },
  { value: "referred",   label: "Referred" },
  { value: "appealed",   label: "Appealed" },
  { value: "overturned", label: "Overturned" },
];

export default function Cases() {
  const navigate = useNavigate();
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [payerFilter, setPayerFilter] = useState<PayerFilter>("all");
  const [search, setSearch] = useState("");
  const [liveCases, setLiveCases] = useState<SyntheticCase[]>([]);
  const [loadingLive, setLoadingLive] = useState(true);
  const [showNewCase, setShowNewCase] = useState(false);

  // Fetch real backend cases on mount
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const d = await api.listCases({ limit: 50 });
        if (cancelled) return;
        const mapped = (d.cases || []).map(liveToCase);
        setLiveCases(mapped);
      } catch (e) {
        if (cancelled) return;
        console.warn("Cases: list endpoint failed", e);
      } finally {
        if (!cancelled) setLoadingLive(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // Merge: live cases first (deduped against synthetic), synthetic for breadth
  const allCases: SyntheticCase[] = useMemo(() => {
    if (liveCases.length === 0) return SYNTHETIC_CASES;
    const liveIds = new Set(liveCases.map((c) => c.case_id));
    const synthFiltered = SYNTHETIC_CASES.filter((c) => !liveIds.has(c.case_id));
    return [...liveCases, ...synthFiltered];
  }, [liveCases]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return allCases.filter((c) => {
      if (statusFilter !== "all" && c.status !== statusFilter) return false;
      if (payerFilter !== "all" && c.payer_id !== payerFilter) return false;
      if (q) {
        const blob =
          `${c.case_id} ${c.patient_initials} ${c.treatment} ${c.j_code} ${c.diagnosis}`.toLowerCase();
        if (!blob.includes(q)) return false;
      }
      return true;
    });
  }, [allCases, statusFilter, payerFilter, search]);

  const counts = useMemo(() => {
    const c: Partial<Record<StatusFilter, number>> = { all: allCases.length };
    for (const cs of STATUSES) {
      c[cs] = allCases.filter((x) => x.status === cs).length;
    }
    return c;
  }, [allCases]);

  const liveCount = liveCases.length;

  const activeCount = (counts.running ?? 0) + (counts.pending ?? 0);

  return (
    <div className="px-6 py-6">
      {/* Header */}
      <header className="mb-5 flex items-end justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-semibold text-ink-primary leading-tight">
            All cases
          </h1>
          <p className="text-sm text-ink-muted mt-1">
            <span className="text-mono-tech nums-tabular text-ink-body">{allCases.length}</span> total
            <span className="mx-2 text-ink-faint">·</span>
            <span className="text-mono-tech nums-tabular text-accent-green">{liveCount}</span> live
            {loadingLive && <Loader2 size={11} className="inline-block animate-spin ml-1 text-ink-faint" />}
            <span className="mx-2 text-ink-faint">·</span>
            <span className="text-mono-tech nums-tabular text-ink-body">{activeCount}</span> active
            <span className="mx-2 text-ink-faint">·</span>
            <span className="text-mono-tech nums-tabular text-ink-body">{counts.appealed ?? 0}</span> in appeal
          </p>
        </div>

        <button
          type="button"
          onClick={() => setShowNewCase(true)}
          className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-accent-brand text-ink-invert text-sm font-medium hover:opacity-90 transition-opacity"
        >
          <Plus size={14} strokeWidth={2.5} />
          New case
        </button>
      </header>

      {/* Filter bar */}
      <div className="bg-surface-raised border border-surface-border rounded-2xl mb-4 overflow-hidden">
        <div className="flex flex-wrap items-center gap-1.5 p-3 border-b border-surface-border">
          {STATUS_PILLS.map((p) => (
            <button
              key={p.value}
              type="button"
              onClick={() => setStatusFilter(p.value)}
              className={clsx(
                "px-2.5 py-1 rounded-full text-xs font-medium transition-all flex items-center gap-1.5",
                statusFilter === p.value
                  ? "bg-accent-brand text-ink-invert"
                  : "bg-surface-panel text-ink-body hover:bg-surface-raised-hi",
              )}
            >
              {p.label}
              <span
                className={clsx(
                  "text-[10px] text-mono-tech",
                  statusFilter === p.value ? "opacity-80" : "text-ink-faint",
                )}
              >
                {counts[p.value] ?? 0}
              </span>
            </button>
          ))}
        </div>

        <div className="flex items-center gap-3 p-3">
          <div className="flex-1 flex items-center gap-2 px-3 py-1.5 rounded-lg border border-surface-border bg-surface-bg">
            <Search size={14} className="text-ink-faint" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search treatment, patient, case_id, diagnosis..."
              className="flex-1 bg-transparent outline-none text-sm text-ink-primary placeholder:text-ink-faint"
            />
          </div>

          <div className="relative">
            <select
              value={payerFilter}
              onChange={(e) => setPayerFilter(e.target.value as PayerFilter)}
              className="appearance-none pl-3 pr-8 py-1.5 rounded-lg border border-surface-border bg-surface-bg text-sm text-ink-body cursor-pointer hover:bg-surface-raised-hi"
            >
              <option value="all">All payers</option>
              {PAYERS.map((p) => (
                <option key={p.id} value={p.id}>{p.label}</option>
              ))}
            </select>
            <ChevronDown
              size={14}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-ink-faint pointer-events-none"
            />
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="bg-surface-raised border border-surface-border rounded-2xl overflow-hidden">
        {filtered.length === 0 ? (
          <div className="p-10 text-center text-ink-muted text-sm">
            No cases match your filters.
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-surface-panel text-[10px] text-compact text-ink-muted">
              <tr>
                <th className="text-left px-4 py-2.5 w-28">Status</th>
                <th className="text-left px-4 py-2.5 w-32">Case ID</th>
                <th className="text-left px-4 py-2.5 w-16">Patient</th>
                <th className="text-left px-4 py-2.5">Treatment</th>
                <th className="text-left px-4 py-2.5">Diagnosis</th>
                <th className="text-left px-4 py-2.5 w-20">Payer</th>
                <th className="text-left px-4 py-2.5 w-24">Verdict</th>
                <th className="text-left px-4 py-2.5 w-32">Confidence</th>
                <th className="text-right px-4 py-2.5 w-24">Submitted</th>
                <th
                  className="text-left px-3 py-2.5 w-24"
                  title="CMS-0057-F § IV.B — 7-day standard / 72-hour expedited turnaround"
                >
                  SLA
                </th>
                <th className="px-4 py-2.5 w-8"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-border">
              {filtered.map((c) => (
                <tr
                  key={c.case_id}
                  onClick={() => {
                    if (!c.is_synthetic) navigate(`/cases/${c.case_id}`);
                  }}
                  className={clsx(
                    "transition-colors group",
                    c.is_synthetic
                      ? "opacity-70"
                      : "hover:bg-surface-raised-hi cursor-pointer",
                  )}
                >
                  <td className="px-4 py-2.5">
                    <StatusPill status={c.status} />
                  </td>
                  <td className="px-4 py-2.5 text-mono-tech text-xs text-ink-muted">
                    {c.case_id}
                    {c.is_synthetic && (
                      <span className="ml-1.5 text-[9px] uppercase tracking-wider text-ink-faint">
                        demo
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-2.5 text-mono-tech text-xs text-ink-body">
                    {c.patient_initials}
                  </td>
                  <td className="px-4 py-2.5">
                    <div className="text-ink-primary font-medium leading-tight">
                      {c.treatment}
                    </div>
                    <div className="text-[10px] text-mono-tech text-ink-faint mt-0.5">
                      {c.j_code}
                    </div>
                  </td>
                  <td className="px-4 py-2.5">
                    <div className="text-xs text-ink-body">{c.diagnosis}</div>
                    <div className="text-[10px] text-mono-tech text-ink-faint mt-0.5">
                      Stage {c.stage}
                    </div>
                  </td>
                  <td className="px-4 py-2.5">
                    <PayerCell payer_id={c.payer_id} showLabel={false} />
                  </td>
                  <td className="px-4 py-2.5">
                    {c.verdict ? (
                      <VerdictText verdict={c.verdict} />
                    ) : (
                      <span className="text-ink-faint">—</span>
                    )}
                  </td>
                  <td className="px-4 py-2.5">
                    {c.confidence !== null ? (
                      <ConfidenceBar value={c.confidence} verdict={c.verdict} />
                    ) : (
                      <span className="text-ink-faint">—</span>
                    )}
                  </td>
                  <td className="px-4 py-2.5 text-right text-[11px] text-ink-muted">
                    {c.ago}
                  </td>
                  <td className="px-3 py-2.5">
                    <SLABadge
                      createdAt={c.submitted_at}
                      decidedAt={
                        c.status === "approved" ||
                        c.status === "denied" ||
                        c.status === "overturned"
                          ? c.submitted_at
                          : null
                      }
                    />
                  </td>
                  <td className="px-4 py-2.5">
                    {c.is_synthetic ? (
                      <ArrowRight size={14} className="text-ink-faint opacity-30" />
                    ) : (
                      <Link
                        to={`/cases/${c.case_id}`}
                        className="inline-flex text-ink-faint hover:text-accent-brand transition-colors"
                      >
                        <ArrowRight size={14} />
                      </Link>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {/* Footer */}
        <div className="flex items-center justify-between px-4 py-2.5 border-t border-surface-border text-[11px] text-ink-muted">
          <span>
            Showing <span className="text-mono-tech text-ink-body">{filtered.length}</span> of{" "}
            <span className="text-mono-tech text-ink-body">{SYNTHETIC_CASES.length}</span> cases
          </span>
          <span className="text-mono-tech">page 1 of 1</span>
        </div>
      </div>
      {showNewCase && (
        <NewCaseModal
          onClose={() => setShowNewCase(false)}
          onCreated={(c) => {
            setLiveCases((prev) => [c, ...prev]);
            setShowNewCase(false);
            navigate(`/cases/${c.case_id}`);
          }}
        />
      )}
    </div>
  );
}

function VerdictText({ verdict }: { verdict: "APPROVE" | "DENY" | "REFER" }) {
  const tint =
    verdict === "APPROVE" ? "text-accent-green" :
    verdict === "DENY"    ? "text-accent-red"   :
                            "text-accent-amber";
  return (
    <span className={clsx("text-[11px] text-mono-tech font-semibold", tint)}>
      {verdict}
    </span>
  );
}

function ConfidenceBar({
  value,
  verdict,
}: {
  value: number;
  verdict: "APPROVE" | "DENY" | "REFER" | null;
}) {
  const pct = Math.round(value * 100);
  const fill =
    verdict === "APPROVE" ? "bg-accent-green" :
    verdict === "DENY"    ? "bg-accent-red"   :
    verdict === "REFER"   ? "bg-accent-amber" :
                            "bg-accent-brand";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 rounded-full bg-surface-border overflow-hidden">
        <div
          className={clsx("h-full rounded-full", fill)}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-[10px] text-mono-tech text-ink-muted w-7 text-right nums-tabular">
        {pct}%
      </span>
    </div>
  );
}

// =============================================================================
// New Case Modal
// =============================================================================

const TREATMENT_JCODES: Record<string, string> = {
  "trastuzumab":                    "J9355",
  "osimertinib":                    "J9335",
  "pembrolizumab":                  "J9271",
  "olaparib":                       "J9305",
  "T-DXd (trastuzumab deruxtecan)": "J9358",
  "nivolumab":                      "J9299",
  "bevacizumab":                    "J9035",
  "ribociclib":                     "J9999",
  "enzalutamide":                   "J9180",
  "lorlatinib":                     "J9999",
  "brentuximab vedotin":            "J9042",
  "dabrafenib + trametinib":        "J9999",
};
const TREATMENT_LIST = Object.keys(TREATMENT_JCODES);

function toInitials(name: string): string {
  return (
    name
      .trim()
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((p) => (p[0]?.toUpperCase() ?? "") + ".")
      .join("") || "P.N."
  );
}

interface NewCaseModalProps {
  onClose: () => void;
  onCreated: (c: SyntheticCase) => void;
}

function NewCaseModal({ onClose, onCreated }: NewCaseModalProps) {
  const [patientName, setPatientName] = useState("");
  const [treatment, setTreatment]     = useState("trastuzumab");
  const [payer, setPayer]             = useState<SyntheticCase["payer_id"]>("aetna");
  const [diagnosis, setDiagnosis]     = useState("");
  const [stage, setStage]             = useState("IIIA");
  const [busy, setBusy]               = useState(false);
  const firstRef                      = useRef<HTMLInputElement>(null);

  useEffect(() => { firstRef.current?.focus(); }, []);

  const jCode    = TREATMENT_JCODES[treatment] ?? "J9999";
  const initials = toInitials(patientName);
  const canSubmit = patientName.trim().length > 0 && diagnosis.trim().length > 0;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit || busy) return;
    setBusy(true);

    const localId = `case_${Math.random().toString(36).slice(2, 10)}`;
    const newCase: SyntheticCase = {
      case_id:          localId,
      status:           "running",
      patient_initials: initials,
      treatment,
      j_code:           jCode,
      payer_id:         payer,
      verdict:          null,
      confidence:       null,
      submitted_at:     new Date().toISOString(),
      ago:              "just now",
      diagnosis,
      stage,
      is_synthetic:     false,
    };

    try {
      const body = {
        payer_id:            payer,
        patient_initials:    initials,
        requested_treatment: { name: treatment, j_code: jCode },
        physician_note:      `${initials} — ${diagnosis} Stage ${stage}. Requesting ${treatment} (${jCode}).`,
        fhir_bundle:         { resourceType: "Bundle", type: "document", entry: [] },
      };
      const res = await fetch("/api/v1/cases", {
        method:  "POST",
        headers: { ...authHeader(), "Content-Type": "application/json" },
        body:    JSON.stringify(body),
      });
      if (res.ok) {
        const json = await res.json();
        newCase.case_id = json.case_id;
      }
    } catch {
      // fail-soft: keep the locally-generated ID
    } finally {
      setBusy(false);
    }

    // Stash demo case text so verdict-routing in api.ts can pick the realistic verdict.
    try {
      localStorage.setItem(
        `clincase_demo_case_${newCase.case_id}`,
        JSON.stringify({
          text: `${patientName} ${diagnosis} Stage ${stage} treatment ${treatment} payer ${payer}`,
          treatment,
          payer_id: payer,
          diagnosis,
        }),
      );
    } catch { /* ignore quota */ }

    onCreated(newCase);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Panel */}
      <div className="relative z-10 w-full max-w-md bg-surface-panel border border-surface-border rounded-2xl shadow-2xl">
        {/* Header */}
        <div className="flex items-start justify-between px-5 py-4 border-b border-surface-border">
          <div>
            <h2 className="text-sm font-semibold text-ink-primary">
              New prior-authorization case
            </h2>
            <p className="text-[11px] text-ink-muted mt-0.5">
              ClinCase 7-agent DAG will begin evaluation immediately
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded text-ink-muted hover:text-ink-primary hover:bg-surface-raised transition-colors"
          >
            <X size={15} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          {/* Patient name */}
          <div>
            <label className="block text-xs font-medium text-ink-body mb-1">
              Patient name <span className="text-accent-red">*</span>
            </label>
            <input
              ref={firstRef}
              value={patientName}
              onChange={(e) => setPatientName(e.target.value)}
              placeholder="e.g. Priya Sharma"
              required
              className="w-full px-3 py-2 rounded-lg border border-surface-border bg-surface-bg text-sm text-ink-primary placeholder:text-ink-faint focus:outline-none focus:ring-2 focus:ring-accent-brand/40"
            />
            {patientName.trim() && (
              <p className="text-[10px] text-mono-tech text-ink-faint mt-1">
                Initials:{" "}
                <span className="text-accent-cyan font-semibold">{initials}</span>
              </p>
            )}
          </div>

          {/* Treatment + J-code */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-ink-body mb-1">
                Treatment <span className="text-accent-red">*</span>
              </label>
              <select
                value={treatment}
                onChange={(e) => setTreatment(e.target.value)}
                className="w-full px-3 py-2 rounded-lg border border-surface-border bg-surface-bg text-sm text-ink-primary focus:outline-none focus:ring-2 focus:ring-accent-brand/40"
              >
                {TREATMENT_LIST.map((t) => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-ink-body mb-1">
                J-code (auto)
              </label>
              <div className="px-3 py-2 rounded-lg border border-surface-border bg-surface-raised text-sm text-mono-tech text-accent-amber">
                {jCode}
              </div>
            </div>
          </div>

          {/* Diagnosis */}
          <div>
            <label className="block text-xs font-medium text-ink-body mb-1">
              Diagnosis / ICD-10 <span className="text-accent-red">*</span>
            </label>
            <input
              value={diagnosis}
              onChange={(e) => setDiagnosis(e.target.value)}
              placeholder="e.g. Breast cancer (C50.911)"
              required
              className="w-full px-3 py-2 rounded-lg border border-surface-border bg-surface-bg text-sm text-ink-primary placeholder:text-ink-faint focus:outline-none focus:ring-2 focus:ring-accent-brand/40"
            />
          </div>

          {/* Stage + Payer */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-ink-body mb-1">
                Stage
              </label>
              <select
                value={stage}
                onChange={(e) => setStage(e.target.value)}
                className="w-full px-3 py-2 rounded-lg border border-surface-border bg-surface-bg text-sm text-ink-primary focus:outline-none focus:ring-2 focus:ring-accent-brand/40"
              >
                {["I", "II", "IIIA", "IIIB", "IV"].map((s) => (
                  <option key={s} value={s}>Stage {s}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-ink-body mb-1">
                Payer
              </label>
              <select
                value={payer}
                onChange={(e) => setPayer(e.target.value as SyntheticCase["payer_id"])}
                className="w-full px-3 py-2 rounded-lg border border-surface-border bg-surface-bg text-sm text-ink-primary focus:outline-none focus:ring-2 focus:ring-accent-brand/40"
              >
                {PAYERS.map((p) => (
                  <option key={p.id} value={p.id}>{p.label}</option>
                ))}
              </select>
            </div>
          </div>

          {/* Actions */}
          <div className="flex items-center justify-between pt-1">
            <button
              type="button"
              onClick={onClose}
              className="text-sm text-ink-muted hover:text-ink-primary transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={busy || !canSubmit}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-accent-brand text-ink-invert text-sm font-medium hover:opacity-90 disabled:opacity-40 transition-opacity"
            >
              {busy ? (
                <Loader2 size={13} className="animate-spin" />
              ) : (
                <Play size={13} />
              )}
              {busy ? "Creating…" : "Create & run ClinCase →"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
