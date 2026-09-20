/**
 * /cohorts — Cross-case analytics. Cohort insight cards + bar/distribution charts.
 *
 * "Across 124 cases, 67% of trastuzumab denials share missing LVEF documentation."
 * — the data flywheel signal.
 */
import { ArrowRight, BarChart3, Lightbulb } from "lucide-react";

interface Insight {
  id: string;
  title: string;
  detail: string;
  metric: string;
  metric_label: string;
  cta_label: string;
  accent: "amber" | "blue" | "violet" | "green";
}

const INSIGHTS: Insight[] = [
  {
    id: "her2-lvef-gap",
    title: "67% of trastuzumab denials share missing LVEF documentation",
    detail: "Across 12 trastuzumab denials in the last 30 days, 8 had no LVEF assessment within the payer window. Recommend pre-submission ECHO orders.",
    metric: "12",
    metric_label: "cases affected",
    cta_label: "View cases",
    accent: "amber",
  },
  {
    id: "aetna-vs-uhc-time",
    title: "Aetna takes 2.3× longer to approve than UHC for stage IIIA breast cancer",
    detail: "Avg time-to-decision: Aetna 18m, UHC 8m. Driver: Aetna's stricter LVEF window (60d vs UHC's lenient).",
    metric: "8 vs 18",
    metric_label: "minutes (UHC vs Aetna)",
    cta_label: "View comparison",
    accent: "blue",
  },
  {
    id: "ecog-correlation",
    title: "Patients with ECOG 2 have 34% lower approval rate vs ECOG 0–1",
    detail: "Across all payers and treatments. Driver: payers' performance-status thresholds are inconsistently enforced.",
    metric: "−34%",
    metric_label: "approval delta",
    cta_label: "Export cohort",
    accent: "violet",
  },
  {
    id: "appeal-success",
    title: "84% of ClinCase-drafted appeals are overturned (vs 67% manual baseline)",
    detail: "47 appeals drafted, 39 overturned. NCCN-grounded arguments + structured biomarker citations correlate with overturn.",
    metric: "84%",
    metric_label: "overturn rate",
    cta_label: "View appeals",
    accent: "green",
  },
];

const ACCENT_BG: Record<Insight["accent"], string> = {
  amber:  "bg-accent-amber/5  border-accent-amber/30",
  blue:   "bg-accent-blue/5   border-accent-blue/30",
  violet: "bg-accent-violet/5 border-accent-violet/30",
  green:  "bg-accent-green/5  border-accent-green/30",
};

const ACCENT_ICON: Record<Insight["accent"], string> = {
  amber:  "text-accent-amber",
  blue:   "text-accent-blue",
  violet: "text-accent-violet",
  green:  "text-accent-green",
};

// Approval rate by payer (synthetic)
const APPROVAL_BY_PAYER = [
  { payer: "Aetna",  rate: 71 },
  { payer: "UHC",    rate: 78 },
  { payer: "BCBS",   rate: 64 },
  { payer: "Anthem", rate: 69 },
];

// Time-to-decision distribution buckets (synthetic)
const TIME_DIST = [
  { bucket: "< 1m", count: 18 },
  { bucket: "1-3m", count: 42 },
  { bucket: "3-5m", count: 28 },
  { bucket: "5-10m", count: 22 },
  { bucket: "10-30m", count: 11 },
  { bucket: "> 30m", count: 3 },
];

const VERDICT_BY_TREATMENT = [
  { treatment: "trastuzumab",       approve: 22, deny: 4, refer: 6 },
  { treatment: "osimertinib",       approve: 15, deny: 1, refer: 3 },
  { treatment: "pembrolizumab",     approve: 12, deny: 2, refer: 5 },
  { treatment: "olaparib",          approve: 9,  deny: 0, refer: 2 },
  { treatment: "T-DXd",             approve: 6,  deny: 1, refer: 2 },
];

export default function Cohorts() {
  return (
    <div className="px-6 py-6">
      <header className="mb-6">
        <h1 className="text-2xl font-semibold text-ink-primary leading-tight flex items-center gap-2">
          <BarChart3 size={22} className="text-accent-brand" />
          Cohort insights
        </h1>
        <p className="text-sm text-ink-muted mt-1">
          Cross-case analytics across <span className="text-mono-tech text-ink-body">124</span> cases ·
          <span className="mx-2 text-ink-faint">·</span>
          <span className="text-accent-cyan font-medium">data flywheel · learning over time</span>
        </p>
      </header>

      {/* Insight cards */}
      <section className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        {INSIGHTS.map((it) => (
          <div
            key={it.id}
            className={`border-2 rounded-2xl p-5 ${ACCENT_BG[it.accent]} relative overflow-hidden`}
          >
            <Lightbulb size={16} className={`${ACCENT_ICON[it.accent]} mb-2`} />
            <div className="text-2xl font-bold text-ink-primary nums-tabular leading-none">
              {it.metric}
            </div>
            <div className="text-[11px] text-compact text-ink-muted mt-1">
              {it.metric_label}
            </div>
            <h3 className="text-sm font-semibold text-ink-primary mt-3 leading-snug">
              {it.title}
            </h3>
            <p className="text-xs text-ink-muted mt-2 leading-relaxed">
              {it.detail}
            </p>
            <button
              type="button"
              className={`mt-3 text-xs font-medium ${ACCENT_ICON[it.accent]} hover:underline flex items-center gap-1`}
            >
              {it.cta_label} <ArrowRight size={11} />
            </button>
          </div>
        ))}
      </section>

      {/* Charts grid */}
      <section className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <ChartCard title="Approval rate by payer" subtitle="last 30d">
          <BarsHorizontal data={APPROVAL_BY_PAYER.map((p) => ({ label: p.payer, value: p.rate, suffix: "%" }))} max={100} />
        </ChartCard>

        <ChartCard title="Time-to-decision distribution" subtitle="all cases">
          <BarsVertical data={TIME_DIST.map((t) => ({ label: t.bucket, value: t.count }))} />
        </ChartCard>

        <ChartCard title="Verdict mix by treatment" subtitle="last 90d">
          <StackedBars data={VERDICT_BY_TREATMENT} />
        </ChartCard>
      </section>
    </div>
  );
}

// =============================================================================
// Chart helpers (pure SVG / divs — no chart lib)
// =============================================================================

function ChartCard({ title, subtitle, children }: { title: string; subtitle: string; children: React.ReactNode }) {
  return (
    <div className="bg-surface-raised border border-surface-border rounded-2xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-ink-primary">{title}</h3>
        <span className="text-[10px] text-mono-tech text-ink-faint">{subtitle}</span>
      </div>
      {children}
    </div>
  );
}

function BarsHorizontal({ data, max }: { data: { label: string; value: number; suffix?: string }[]; max: number }) {
  return (
    <div className="space-y-2.5">
      {data.map((d) => (
        <div key={d.label} className="flex items-center gap-3 text-xs">
          <span className="text-ink-muted w-16 shrink-0">{d.label}</span>
          <div className="flex-1 h-5 bg-surface-panel rounded overflow-hidden">
            <div
              className="h-full bg-accent-brand rounded transition-all"
              style={{ width: `${(d.value / max) * 100}%` }}
            />
          </div>
          <span className="text-ink-body text-mono-tech w-10 text-right nums-tabular">
            {d.value}{d.suffix ?? ""}
          </span>
        </div>
      ))}
    </div>
  );
}

function BarsVertical({ data }: { data: { label: string; value: number }[] }) {
  const max = Math.max(...data.map((d) => d.value));
  return (
    <div className="mt-2">
      <div className="flex items-end gap-2 h-32">
        {data.map((d) => (
          <div
            key={d.label}
            className="flex-1 flex flex-col justify-end h-full"
            title={`${d.label}: ${d.value} cases`}
          >
            <div
              className="w-full bg-accent-cyan/80 rounded-t hover:bg-accent-cyan transition-colors"
              style={{ height: `${(d.value / max) * 100}%`, minHeight: 4 }}
            />
            <div className="text-center text-[9px] text-mono-tech text-ink-body mt-1 nums-tabular">
              {d.value}
            </div>
          </div>
        ))}
      </div>
      <div className="flex gap-2 mt-1">
        {data.map((d) => (
          <span key={d.label} className="flex-1 text-center text-[9px] text-mono-tech text-ink-faint">
            {d.label}
          </span>
        ))}
      </div>
    </div>
  );
}

function StackedBars({ data }: { data: { treatment: string; approve: number; deny: number; refer: number }[] }) {
  const max = Math.max(...data.map((d) => d.approve + d.deny + d.refer));
  return (
    <div className="space-y-2 mt-1">
      {data.map((d) => {
        const total = d.approve + d.deny + d.refer;
        return (
          <div key={d.treatment} className="text-xs">
            <div className="flex items-center justify-between mb-1">
              <span className="text-ink-body truncate">{d.treatment}</span>
              <span className="text-ink-muted text-mono-tech nums-tabular">{total}</span>
            </div>
            <div className="flex h-4 rounded overflow-hidden bg-surface-panel" style={{ width: `${(total / max) * 100}%` }}>
              <div className="bg-accent-green" style={{ width: `${(d.approve / total) * 100}%` }} title={`${d.approve} approved`} />
              <div className="bg-accent-amber" style={{ width: `${(d.refer / total) * 100}%` }} title={`${d.refer} referred`} />
              <div className="bg-accent-red" style={{ width: `${(d.deny / total) * 100}%` }} title={`${d.deny} denied`} />
            </div>
          </div>
        );
      })}
      <div className="flex items-center gap-3 text-[10px] text-mono-tech text-ink-muted pt-2">
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-accent-green" />approved</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-accent-amber" />referred</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-accent-red" />denied</span>
      </div>
    </div>
  );
}
