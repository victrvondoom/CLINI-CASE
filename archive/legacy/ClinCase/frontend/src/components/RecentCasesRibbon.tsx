/**
 * Recent cases ribbon — compact rows showing the latest 6 PA cases.
 * Status pill | Patient | Treatment | Payer | Submitted (time-ago) → click row to open.
 *
 * For Phase 2 uses synthetic data; Phase 3 swaps to GET /api/v1/cases?limit=6.
 */
import clsx from "clsx";
import { ArrowRight } from "lucide-react";
import { Link } from "react-router-dom";

interface CaseRow {
  case_id: string;
  status: "approved" | "denied" | "referred" | "appealed" | "running" | "pending";
  patient: string;
  treatment: string;
  j_code?: string;
  payer: string;
  ago: string;
}

const SYNTHETIC: CaseRow[] = [
  { case_id: "case_8f4ad9c2", status: "approved", patient: "S.D.", treatment: "trastuzumab",      j_code: "J9355", payer: "AETNA", ago: "2m ago" },
  { case_id: "case_b8d84d77", status: "appealed", patient: "M.D.", treatment: "trastuzumab",      j_code: "J9355", payer: "AETNA", ago: "8m ago" },
  { case_id: "case_a8f23910", status: "approved", patient: "R.K.", treatment: "osimertinib",      j_code: "J9335", payer: "UHC",   ago: "27m ago" },
  { case_id: "case_3d44e1b9", status: "referred", patient: "P.N.", treatment: "pembrolizumab",    j_code: "J9271", payer: "BCBS",  ago: "1h ago" },
  { case_id: "case_9c12fa70", status: "approved", patient: "T.O.", treatment: "olaparib",         j_code: "J9305", payer: "AETNA", ago: "3h ago" },
  { case_id: "case_5e87bb31", status: "denied",   patient: "L.W.", treatment: "trastuzumab",      j_code: "J9355", payer: "AETNA", ago: "5h ago" },
];

const STATUS_TINT: Record<CaseRow["status"], string> = {
  approved: "bg-accent-green/10 text-accent-green",
  denied:   "bg-accent-red/10   text-accent-red",
  referred: "bg-accent-amber/10 text-accent-amber",
  appealed: "bg-accent-violet/10 text-accent-violet",
  running:  "bg-accent-brand/10 text-accent-brand",
  pending:  "bg-surface-border text-ink-muted",
};

export function RecentCasesRibbon() {
  return (
    <div className="bg-surface-raised border border-surface-border rounded-2xl overflow-hidden">
      <div className="flex items-center justify-between px-5 py-3 border-b border-surface-border">
        <h3 className="text-sm font-semibold text-ink-primary">Recent cases</h3>
        <Link to="/cases" className="text-xs text-accent-brand hover:underline flex items-center gap-1">
          View all 47 →
        </Link>
      </div>

      <div className="divide-y divide-surface-border">
        {SYNTHETIC.map((c) => (
          <Link
            key={c.case_id}
            to={`/cases/${c.case_id}`}
            className="flex items-center gap-3 px-5 py-2.5 hover:bg-surface-raised-hi transition-colors group"
          >
            <span
              className={clsx(
                "text-[10px] text-mono-tech uppercase px-2 py-0.5 rounded tracking-wide",
                STATUS_TINT[c.status],
              )}
            >
              {c.status}
            </span>
            <span className="text-mono-tech text-xs text-ink-muted shrink-0 w-12">{c.patient}</span>
            <div className="flex-1 min-w-0 text-sm text-ink-body truncate">
              <span className="font-medium text-ink-primary">{c.treatment}</span>
              {c.j_code && (
                <span className="ml-1.5 text-[10px] text-mono-tech text-ink-faint">
                  {c.j_code}
                </span>
              )}
            </div>
            <span className="text-[11px] text-mono-tech text-ink-muted shrink-0">{c.payer}</span>
            <span className="text-[11px] text-ink-faint shrink-0 w-16 text-right">{c.ago}</span>
            <ArrowRight size={14} className="text-ink-faint group-hover:text-accent-brand transition-colors shrink-0" />
          </Link>
        ))}
      </div>
    </div>
  );
}
