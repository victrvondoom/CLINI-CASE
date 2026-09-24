/**
 * /onco — Oncology Stack page surfacing all 10 strategic USPs.
 *
 * Each tab maps to one USP's API endpoints. Demo-friendly inputs preloaded
 * so evaluators can click through without typing.
 */
import clsx from "clsx";
import {
  Activity,
  AlertCircle,
  BookOpen,
  CheckCircle2,
  Dna,
  DollarSign,
  Download,
  FileText,
  Hash,
  Layers,
  Loader2,
  MessageSquare,
  Network,
  PlayCircle,
  Shield,
  Stethoscope,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { authHeader } from "../lib/auth";

type USPKey =
  | "guidelines" | "genomic" | "denial" | "davinci" | "p2p"
  | "offlabel" | "regimen" | "siteofcare" | "policydiff" | "audit";

interface USPDef {
  key: USPKey;
  num: number;
  title: string;
  short: string;
  Icon: typeof BookOpen;
}

const USPS: USPDef[] = [
  { key: "guidelines",  num: 1,  title: "OncoGuideline Engine",            short: "NCCN/ASCO real-time RAG",                          Icon: BookOpen },
  { key: "genomic",     num: 2,  title: "Genomic Authorization Agent",     short: "FoundationOne / Tempus / Caris ingestion",         Icon: Dna },
  { key: "denial",      num: 3,  title: "Denial Predict + Auto-Appeal",    short: "XGBoost-style risk + evidence-graph appeal",       Icon: Shield },
  { key: "davinci",     num: 4,  title: "CMS-0057-F Da Vinci PAS Native",  short: "FHIR PAS / CRD / DTR · X12 278 bridge",            Icon: Network },
  { key: "p2p",         num: 5,  title: "Peer-to-Peer Briefing Kit",       short: "1-page PDF · physician's 5-min war chest",         Icon: FileText },
  { key: "offlabel",    num: 6,  title: "Off-Label Justification (OLJA)",  short: "Multi-agent proposer/opponent/judge debate",       Icon: MessageSquare },
  { key: "regimen",     num: 7,  title: "Bundled Regimen PA",              short: "1 PA covers an entire NCCN regimen",               Icon: Layers },
  { key: "siteofcare",  num: 8,  title: "Site-of-Care Optimizer",          short: "Hospital vs office vs home cost transparency",     Icon: DollarSign },
  { key: "policydiff",  num: 9,  title: "Multi-Payer Policy Reconciler",   short: "Diff-tracked payer policy graph",                  Icon: Activity },
  { key: "audit",       num: 10, title: "Cryptographic Audit Trail",       short: "SHA-256 chained · QLDB-equivalent",                Icon: Hash },
];

export default function OncologyStack() {
  const [active, setActive] = useState<USPKey>("guidelines");

  return (
    <div className="px-6 py-6">
      <header className="mb-5">
        <h1 className="text-2xl font-semibold text-ink-primary leading-tight flex items-center gap-2">
          <Stethoscope size={22} className="text-accent-brand" />
          Oncology Stack
        </h1>
        <p className="text-sm text-ink-muted mt-1">
          Ten USPs from <a href="/PROPOSAL.md#§43" className="text-accent-cyan underline" target="_blank" rel="noreferrer">§43</a> · live FastAPI · real audit chain · curated NCCN-style sample data where licenses gate production
        </p>
      </header>

      {/* USP rail */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2 mb-5">
        {USPS.map((u) => (
          <button
            key={u.key}
            type="button"
            onClick={() => setActive(u.key)}
            className={clsx(
              "text-left rounded-xl border p-3 transition-all hover:border-accent-brand/60",
              active === u.key
                ? "border-accent-brand bg-accent-brand/10"
                : "border-surface-border bg-surface-raised",
            )}
          >
            <div className="flex items-center gap-2 mb-1">
              <span className="text-[10px] text-mono-tech text-ink-faint">USP #{u.num}</span>
              <u.Icon size={12} className="text-accent-brand" />
            </div>
            <div className="text-[12.5px] font-semibold text-ink-primary leading-tight">{u.title}</div>
            <div className="text-[10.5px] text-ink-muted mt-0.5 leading-snug">{u.short}</div>
          </button>
        ))}
      </div>

      <div className="bg-surface-raised border border-surface-border rounded-2xl p-5">
        {active === "guidelines"  && <GuidelinesTab />}
        {active === "genomic"     && <GenomicTab />}
        {active === "denial"      && <DenialTab />}
        {active === "davinci"     && <DaVinciTab />}
        {active === "p2p"         && <P2PTab />}
        {active === "offlabel"    && <OffLabelTab />}
        {active === "regimen"     && <RegimenTab />}
        {active === "siteofcare"  && <SiteOfCareTab />}
        {active === "policydiff"  && <PolicyDiffTab />}
        {active === "audit"       && <AuditTab />}
      </div>
    </div>
  );
}

// =============================================================================
// Shared helpers
// =============================================================================

function H({ num, title, sub }: { num: number; title: string; sub: string }) {
  return (
    <div className="mb-4">
      <div className="text-[10px] text-compact text-accent-brand">USP #{num}</div>
      <h2 className="text-lg font-semibold text-ink-primary leading-tight">{title}</h2>
      <p className="text-xs text-ink-muted mt-1">{sub}</p>
    </div>
  );
}

function StatusPill({ ok, text }: { ok: boolean; text: string }) {
  return (
    <span className={clsx(
      "inline-flex items-center gap-1 text-[11px] text-mono-tech px-2 py-0.5 rounded-full border",
      ok
        ? "border-accent-green/40 bg-accent-green/10 text-accent-green"
        : "border-accent-red/40 bg-accent-red/10 text-accent-red",
    )}>
      {ok ? <CheckCircle2 size={10} /> : <AlertCircle size={10} />}
      {text}
    </span>
  );
}

async function api<T>(method: "GET" | "POST" | "DELETE", path: string, body?: unknown): Promise<T> {
  const init: RequestInit = { method, headers: { ...authHeader() } };
  if (body !== undefined && !(body instanceof FormData)) {
    (init.headers as Record<string, string>)["Content-Type"] = "application/json";
    init.body = JSON.stringify(body);
  } else if (body instanceof FormData) {
    init.body = body;
  }
  const res = await fetch(`/api/v1${path}`, init);
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${(await res.text()).slice(0, 200)}`);
  return res.json();
}

// =============================================================================
// USP #1 — Guidelines
// =============================================================================

interface GuidelineHit {
  id: string;
  guideline: string;
  tumor_type: string;
  biomarker: string;
  line_of_therapy: string;
  regimen: string;
  evidence_category: string;
  section_heading: string;
  excerpt: string;
  reference_pmid?: string;
  relevance_score: number;
}

function GuidelinesTab() {
  const [tumor, setTumor] = useState("NSCLC");
  const [biomarker, setBiomarker] = useState("EGFR L858R");
  const [line, setLine] = useState("first");
  const [hits, setHits] = useState<GuidelineHit[]>([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [latency, setLatency] = useState<number | null>(null);

  const search = useCallback(async () => {
    setLoading(true); setErr(null);
    try {
      const params = new URLSearchParams({ tumor, biomarker, line, top_k: "5" });
      const j = await api<{ hits: GuidelineHit[]; latency_ms: number }>("GET", `/onco/guidelines/search?${params}`);
      setHits(j.hits);
      setLatency(j.latency_ms);
    } catch (e) { setErr(String(e)); }
    finally { setLoading(false); }
  }, [tumor, biomarker, line]);

  useEffect(() => { void search(); }, []);  // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div>
      <H num={1} title="OncoGuideline Engine" sub="Real-time NCCN/ASCO retrieval. TF-IDF over a curated 8-guideline corpus; production swaps in a licensed NCCN feed indexed via Bedrock Knowledge Bases." />
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 mb-3">
        <Input label="Tumor type"   value={tumor} onChange={setTumor} placeholder="NSCLC, Breast, Ovarian, any" />
        <Input label="Biomarker"    value={biomarker} onChange={setBiomarker} placeholder="EGFR L858R, BRCA1, TMB-H" />
        <Input label="Line of therapy" value={line} onChange={setLine} placeholder="first, second, maintenance" />
      </div>
      <div className="flex items-center gap-3 mb-3">
        <RunButton onClick={search} loading={loading} label="Search guidelines" />
        {latency != null && <span className="text-[11px] text-mono-tech text-ink-muted">{hits.length} hits · {latency}ms</span>}
      </div>
      {err && <ErrBox text={err} />}
      <div className="space-y-2">
        {hits.map((h) => (
          <div key={h.id} className="border border-surface-border rounded-xl p-3 bg-surface-bg">
            <div className="flex items-baseline gap-2 flex-wrap mb-1">
              <code className="text-[11px] text-mono-tech text-accent-cyan">{h.id}</code>
              <span className="text-[12.5px] font-medium text-ink-primary">{h.guideline}</span>
              <span className="text-[10px] text-mono-tech px-1.5 py-0.5 rounded bg-accent-brand/15 text-accent-brand">Cat. {h.evidence_category}</span>
              <span className="text-[10px] text-mono-tech text-ink-faint ml-auto">score {h.relevance_score}</span>
            </div>
            <div className="text-[11px] text-mono-tech text-ink-muted mb-1">{h.section_heading}</div>
            <p className="text-[12px] text-ink-body leading-relaxed">{h.excerpt}</p>
            <div className="text-[10px] text-mono-tech text-ink-faint mt-1">
              {h.tumor_type} · {h.biomarker} · {h.line_of_therapy} · regimen: <span className="text-accent-brand">{h.regimen}</span>
              {h.reference_pmid && <> · PMID {h.reference_pmid}</>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// =============================================================================
// USP #2 — Genomic
// =============================================================================

interface ExtractedVariant {
  canonical_id: string;
  text_match: string;
  variant_class: string;
  fda_approved: string[];
  nccn_preferred: string;
  evidence: string;
  tumor_types: string[];
  guideline_ref?: string;
}

function GenomicTab() {
  const [file, setFile] = useState<File | null>(null);
  const [variants, setVariants] = useState<ExtractedVariant[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [meta, setMeta] = useState<{ bytes: number; chars: number; preview: string } | null>(null);

  const handleSyntheticDemo = useCallback(async () => {
    const synth = `%PDF-1.4
FoundationOne CDx Report
Patient: J.D.
Tumor type: Triple-negative breast cancer

GENOMIC FINDINGS
- BRCA1 germline c.5266dupC (pathogenic)
- TP53 R273H
- PIK3CA E545K
- TMB 18.4 mut/Mb (TMB-H)
- MSI-H

Therapy implications: olaparib, pembrolizumab.`.repeat(2);
    const f = new File([synth], "synth_foundationone.pdf", { type: "application/pdf" });
    setFile(f);
  }, []);

  const submit = useCallback(async () => {
    if (!file) return;
    setLoading(true); setErr(null); setVariants(null);
    try {
      const fd = new FormData(); fd.append("file", file);
      const j = await api<{ variants: ExtractedVariant[]; bytes_read: number; extracted_text_chars: number; text_preview: string }>("POST", "/onco/genomic/parse", fd);
      setVariants(j.variants);
      setMeta({ bytes: j.bytes_read, chars: j.extracted_text_chars, preview: j.text_preview });
    } catch (e) { setErr(String(e)); }
    finally { setLoading(false); }
  }, [file]);

  return (
    <div>
      <H num={2} title="Genomic Authorization Agent" sub="Parse FoundationOne / Tempus / Caris NGS reports; map variants to FDA-approved + NCCN-preferred regimens. Production wires in vendor-specific PDF schemas." />
      <div className="flex flex-wrap gap-2 mb-3">
        <input type="file" accept=".pdf,application/pdf" onChange={(e) => setFile(e.target.files?.[0] ?? null)}
               className="text-xs file:px-3 file:py-1.5 file:rounded-lg file:border-0 file:bg-accent-brand file:text-white file:cursor-pointer" />
        <button type="button" onClick={handleSyntheticDemo}
                className="text-[11px] font-medium px-2.5 py-1.5 rounded-md border border-surface-border text-ink-body hover:bg-surface-raised-hi transition-colors">
          Use synthetic FoundationOne demo file
        </button>
        <RunButton onClick={submit} loading={loading} label="Parse" disabled={!file} />
      </div>
      {file && <div className="text-[11px] text-mono-tech text-ink-muted mb-2">{file.name} · {(file.size / 1024).toFixed(1)} KB</div>}
      {err && <ErrBox text={err} />}
      {meta && <div className="text-[11px] text-mono-tech text-ink-muted mb-2">read {meta.bytes} B · extracted {meta.chars} chars of text</div>}
      {variants && (
        <div className="space-y-2">
          {variants.map((v) => (
            <div key={v.canonical_id} className="border border-surface-border rounded-xl p-3 bg-surface-bg">
              <div className="flex items-center gap-2 flex-wrap mb-1">
                <code className="text-[12px] text-mono-tech text-accent-cyan">{v.canonical_id}</code>
                <span className="text-[11px] text-mono-tech text-ink-faint">matched: "{v.text_match}"</span>
                <span className="text-[10px] text-mono-tech px-1.5 py-0.5 rounded bg-accent-brand/15 text-accent-brand uppercase">{v.variant_class}</span>
                <span className="text-[10px] text-mono-tech px-1.5 py-0.5 rounded bg-accent-amber/15 text-accent-amber">Cat. {v.evidence}</span>
              </div>
              <div className="text-[12px] text-ink-body">
                <span className="text-ink-muted">FDA approved:</span> {v.fda_approved.join(", ")}
              </div>
              <div className="text-[12px] text-ink-body">
                <span className="text-ink-muted">NCCN preferred:</span> <span className="text-accent-brand font-medium">{v.nccn_preferred}</span>
              </div>
              <div className="text-[10px] text-mono-tech text-ink-faint">
                Tumor types: {v.tumor_types.join(", ")}{v.guideline_ref && ` · NCCN ${v.guideline_ref}`}
              </div>
            </div>
          ))}
          {variants.length === 0 && <div className="text-sm text-ink-muted">No actionable variants matched. Production NGS parsers handle vendor-specific layouts (Tempus xT, Caris MI Tumor Seek).</div>}
        </div>
      )}
    </div>
  );
}

// =============================================================================
// USP #3 — Denial + Appeal
// =============================================================================

function DenialTab() {
  const [predict, setPredict] = useState<any | null>(null);
  const [appeal, setAppeal] = useState<any | null>(null);
  const [loadingP, setLoadingP] = useState(false);
  const [loadingA, setLoadingA] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const runPredict = useCallback(async () => {
    setLoadingP(true); setErr(null);
    try {
      const j = await api("POST", "/onco/denial/predict", {
        treatment: "trastuzumab + pertuzumab", payer_id: "Aetna", diagnosis: "C50.911 Stage IIIA HER2+ breast",
        biomarkers: ["HER2 amplified"],
        line_of_therapy: "neoadjuvant", prior_lines: 0,
        has_pathology_report: true, has_imaging_report: true,
        has_biomarker_test: false, has_nccn_citation: false,
      });
      setPredict(j);
    } catch (e) { setErr(String(e)); }
    finally { setLoadingP(false); }
  }, []);

  const runAppeal = useCallback(async () => {
    setLoadingA(true); setErr(null);
    try {
      const j = await api("POST", "/onco/appeal/draft", {
        patient_initials: "S.D.", payer_id: "Aetna", treatment: "trastuzumab + pertuzumab",
        diagnosis: "Stage IIIA HER2+ breast cancer", denial_reason: "NCCN regimen variation cited; documentation incomplete",
        nccn_section: "BINV-K", biomarker: "HER2-positive", cited_pmids: ["23704196"],
      });
      setAppeal(j);
    } catch (e) { setErr(String(e)); }
    finally { setLoadingA(false); }
  }, []);

  return (
    <div>
      <H num={3} title="Denial Predict + Auto-Appeal" sub="Score denial risk pre-submission · auto-draft NCCN-cited appeals on denial. AMA: 80.7% of appealed denials overturned, but only 11.7% appealed." />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <div className="border border-surface-border rounded-xl p-4 bg-surface-bg">
          <div className="text-[10px] text-compact text-ink-muted mb-2">3a. Denial predictor</div>
          <RunButton onClick={runPredict} loading={loadingP} label="Predict for sample case" />
          {predict && (
            <div className="mt-3 space-y-2">
              <div className="flex items-center gap-2">
                <span className="text-[11px] text-mono-tech text-ink-muted">P(denial) =</span>
                <span className={clsx("text-2xl font-semibold tabular-nums",
                  predict.denial_probability >= 0.5 ? "text-accent-red" : predict.denial_probability >= 0.25 ? "text-accent-amber" : "text-accent-green")}>
                  {(predict.denial_probability * 100).toFixed(0)}%
                </span>
                <span className="text-[10px] text-mono-tech text-ink-faint">conf {(predict.confidence * 100).toFixed(0)}%</span>
              </div>
              <div>
                <div className="text-[11px] text-mono-tech text-ink-muted mb-1">Top risk factors</div>
                <ul className="text-[12px] text-ink-body space-y-0.5">
                  {predict.top_risk_factors.map((r: string, i: number) => <li key={i}>• {r}</li>)}
                </ul>
              </div>
              <div>
                <div className="text-[11px] text-mono-tech text-ink-muted mb-1">Recommended actions</div>
                <ul className="text-[12px] text-ink-body space-y-0.5">
                  {predict.recommended_actions.map((r: string, i: number) => <li key={i}>→ {r}</li>)}
                </ul>
              </div>
              <div className="text-[10px] text-mono-tech text-ink-faint pt-1 border-t border-surface-border">
                benchmark · {predict.benchmark.source}
              </div>
            </div>
          )}
        </div>
        <div className="border border-surface-border rounded-xl p-4 bg-surface-bg">
          <div className="text-[10px] text-compact text-ink-muted mb-2">3b. Auto-appeal generator</div>
          <RunButton onClick={runAppeal} loading={loadingA} label="Draft appeal letter" />
          {appeal && (
            <div className="mt-3">
              <div className="text-[11px] text-mono-tech text-ink-muted mb-1">{appeal.word_count} words · {appeal.citations.length} citations</div>
              <pre className="text-[11px] text-mono-tech text-ink-body whitespace-pre-wrap leading-relaxed bg-surface-panel rounded p-3 max-h-72 overflow-auto">
                {appeal.letter}
              </pre>
            </div>
          )}
        </div>
      </div>
      {err && <ErrBox text={err} />}
    </div>
  );
}

// =============================================================================
// USP #4 — Da Vinci PAS / CRD / DTR
// =============================================================================

function DaVinciTab() {
  const [pas, setPas] = useState<any | null>(null);
  const [dtr, setDtr] = useState<any | null>(null);
  const [crd, setCrd] = useState<any | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const runAll = useCallback(async () => {
    setLoading(true); setErr(null);
    try {
      const [p, d, c] = await Promise.all([
        api("POST", "/onco/davinci/pas/submit", {
          payer_id: "UnitedHealthcare", patient_initials: "M.C.",
          diagnosis_icd10: "C34.91", treatment_hcpcs: "J9305", treatment_name: "pemetrexed",
          requested_units: 6, biomarker: "EGFR L858R",
        }),
        api("GET", "/onco/davinci/dtr/questionnaire"),
        api("POST", "/onco/davinci/crd", { context: { medications: [{ medicationCodeableConcept: { text: "trastuzumab" } }] } }),
      ]);
      setPas(p); setDtr(d); setCrd(c);
    } catch (e) { setErr(String(e)); }
    finally { setLoading(false); }
  }, []);

  return (
    <div>
      <H num={4} title="CMS-0057-F Native Compliance" sub="Da Vinci PAS 2.0.1 + CRD + DTR Bundle generation. Operational by 2026; APIs by Jan 1, 2027. Production deploy must pass ONC Inferno Test Kit." />
      <RunButton onClick={runAll} loading={loading} label="Submit PAS + invoke CRD/DTR" />
      {err && <ErrBox text={err} />}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 mt-4">
        {pas && (
          <div className="border border-surface-border rounded-xl p-3 bg-surface-bg lg:col-span-2">
            <div className="flex items-center justify-between mb-2">
              <div className="text-[10px] text-compact text-ink-muted">4a · PAS Bundle (FHIR R4)</div>
              <StatusPill ok={pas.decision === "approved"} text={`auth ${pas.auth_number} · ${pas.decision}`} />
            </div>
            <pre className="text-[10px] text-mono-tech text-ink-body bg-surface-panel rounded p-2 max-h-56 overflow-auto leading-relaxed">{JSON.stringify(pas.bundle, null, 2)}</pre>
            <div className="text-[10px] text-mono-tech text-ink-faint mt-1">{pas.conformance_note}</div>
          </div>
        )}
        {crd && (
          <div className="border border-surface-border rounded-xl p-3 bg-surface-bg">
            <div className="text-[10px] text-compact text-ink-muted mb-2">4b · CRD card response</div>
            <div className="text-[12.5px] font-medium text-ink-primary">{crd.cards[0].summary}</div>
            <div className="text-[11.5px] text-ink-body mt-1">{crd.cards[0].detail}</div>
          </div>
        )}
        {dtr && (
          <div className="border border-surface-border rounded-xl p-3 bg-surface-bg">
            <div className="text-[10px] text-compact text-ink-muted mb-2">4c · DTR Questionnaire ({dtr.item.length} items)</div>
            <ul className="text-[11.5px] text-ink-body space-y-1">
              {dtr.item.map((it: any, i: number) => (
                <li key={i}>• <span className="text-mono-tech text-[10.5px] text-ink-faint">[{it.linkId}]</span> {it.text} <span className="text-ink-faint">({it.type})</span></li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}

// =============================================================================
// USP #5 — P2P Briefing Kit
// =============================================================================

function P2PTab() {
  const [loading, setLoading] = useState(false);
  const [downloaded, setDownloaded] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const generate = useCallback(async () => {
    setLoading(true); setErr(null); setDownloaded(null);
    try {
      const res = await fetch("/api/v1/onco/p2p/briefing-kit", {
        method: "POST",
        headers: { ...authHeader(), "Content-Type": "application/json" },
        body: JSON.stringify({
          patient_initials: "P.N.", diagnosis: "Stage IV NSCLC",
          treatment: "osimertinib", payer_id: "BCBS",
          denial_reason: "Step therapy: erlotinib trial required first per BCBS-RX policy",
          biomarker: "EGFR L858R", nccn_section: "NSCL-26",
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a"); a.href = url; a.download = "p2p_briefing.pdf";
      document.body.appendChild(a); a.click(); document.body.removeChild(a);
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      setDownloaded(`p2p_briefing.pdf · ${(blob.size / 1024).toFixed(1)} KB`);
    } catch (e) { setErr(String(e)); }
    finally { setLoading(false); }
  }, []);

  return (
    <div>
      <H num={5} title="Peer-to-Peer Briefing Kit" sub="Generated 1-page PDF physicians review in 5 min before P2P call. Saves 8–15 P2Ps × 30–60 min/each per oncologist per month." />
      <RunButton onClick={generate} loading={loading} label={<><Download size={11} className="inline mr-1" />Generate + download P2P briefing PDF</>} />
      {downloaded && <div className="mt-3 text-sm text-accent-green">✓ Downloaded {downloaded}</div>}
      {err && <ErrBox text={err} />}
      <div className="mt-4 text-[11.5px] text-ink-muted leading-relaxed">
        Sample case used: <code className="text-mono-tech text-accent-cyan">P.N.</code> · Stage IV NSCLC · EGFR L858R · BCBS denial cites step-therapy requirement for erlotinib.
        Generated PDF includes counter-arguments, anticipated reviewer questions, NCCN section ID, and a patient summary.
      </div>
    </div>
  );
}

// =============================================================================
// USP #6 — Off-Label Justification
// =============================================================================

function OffLabelTab() {
  const [drug, setDrug] = useState("pembrolizumab");
  const [indication, setIndication] = useState("MSI-H endometrial cancer (off-label maintenance)");
  const [biomarker, setBiomarker] = useState("MSI-H");
  const [resp, setResp] = useState<any | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const run = useCallback(async () => {
    setLoading(true); setErr(null); setResp(null);
    try {
      const j = await api("POST", "/onco/off-label/justify", { drug, indication, biomarker });
      setResp(j);
    } catch (e) { setErr(String(e)); }
    finally { setLoading(false); }
  }, [drug, indication, biomarker]);

  return (
    <div>
      <H num={6} title="Off-Label Justification (multi-agent debate)" sub="Proposer states the case → Opponent (skeptical reviewer) challenges → Proposer counters with compendium evidence → Judge issues verdict." />
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 mb-3">
        <Input label="Drug" value={drug} onChange={setDrug} />
        <Input label="Off-label indication" value={indication} onChange={setIndication} />
        <Input label="Biomarker" value={biomarker} onChange={setBiomarker} />
      </div>
      <RunButton onClick={run} loading={loading} label="Run debate" />
      {err && <ErrBox text={err} />}
      {resp && (
        <div className="mt-4">
          <div className="flex items-center gap-2 mb-3">
            <StatusPill ok={resp.verdict === "APPROVE"} text={`Verdict: ${resp.verdict}`} />
            <span className="text-[11px] text-mono-tech text-ink-muted">conf {(resp.confidence * 100).toFixed(0)}%</span>
          </div>
          <div className="space-y-2">
            {resp.rounds.map((r: any, i: number) => (
              <div key={i} className={clsx(
                "border rounded-xl p-3",
                r.role === "proposer" ? "border-accent-brand/40 bg-accent-brand/5"
                  : r.role === "opponent" ? "border-accent-red/40 bg-accent-red/5"
                  : "border-accent-amber/40 bg-accent-amber/5",
              )}>
                <div className="text-[10px] text-compact mb-1">
                  Round {r.round} · {r.role}
                </div>
                <p className="text-[12px] text-ink-body leading-relaxed">{r.text}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// =============================================================================
// USP #7 — Bundled Regimen
// =============================================================================

function RegimenTab() {
  const [regimenKey, setRegimenKey] = useState("TCHP");
  const [resp, setResp] = useState<any | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [templates, setTemplates] = useState<any | null>(null);

  useEffect(() => {
    api("GET", "/onco/regimen/templates").then(setTemplates).catch(() => {});
  }, []);

  const run = useCallback(async () => {
    setLoading(true); setErr(null);
    try {
      const j = await api("POST", "/onco/regimen/bundle", {
        regimen_key: regimenKey, patient_initials: "S.D.",
        diagnosis_icd10: "C50.911", payer_id: "Aetna", cycles_requested: 6,
      });
      setResp(j);
    } catch (e) { setErr(String(e)); }
    finally { setLoading(false); }
  }, [regimenKey]);

  const keys = useMemo(() => templates ? Object.keys(templates.regimens) : [], [templates]);

  return (
    <div>
      <H num={7} title="Bundled Regimen Authorization" sub="One PA covers an entire NCCN regimen (drugs + supportive care). Replaces N separate PAs with 1 bundled FHIR Bundle." />
      <div className="flex gap-2 mb-3 flex-wrap items-end">
        <div>
          <div className="text-[10px] text-compact text-ink-muted mb-1">Regimen</div>
          <select value={regimenKey} onChange={(e) => setRegimenKey(e.target.value)}
                  className="bg-surface-bg border border-surface-border rounded px-2 py-1 text-sm text-ink-primary">
            {keys.map((k) => <option key={k}>{k}</option>)}
          </select>
        </div>
        <RunButton onClick={run} loading={loading} label="Build bundled PA" />
      </div>
      {err && <ErrBox text={err} />}
      {resp && (
        <div className="space-y-3">
          <div className="text-sm text-ink-body">
            <span className="font-semibold">{resp.regimen.name}</span> · {resp.regimen.indication}
            {" · "}<span className="text-accent-brand">{resp.n_items} line items in 1 bundle</span> ·
            <span className="text-accent-green ml-1">{resp.vs_unbundled.reduction_pct}% PA-volume reduction</span>
          </div>
          <pre className="text-[10px] text-mono-tech text-ink-body bg-surface-panel rounded p-2 max-h-72 overflow-auto leading-relaxed">{JSON.stringify(resp.bundle, null, 2)}</pre>
        </div>
      )}
    </div>
  );
}

// =============================================================================
// USP #8 — Site-of-Care
// =============================================================================

function SiteOfCareTab() {
  const [drugKey, setDrugKey] = useState("pembrolizumab_200mg_q3w");
  const [oop, setOop] = useState<number>(500);
  const [resp, setResp] = useState<any | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const run = useCallback(async () => {
    setLoading(true); setErr(null);
    try {
      const j = await api("POST", "/onco/site-of-care/compare", {
        drug_key: drugKey, payer_id: "Aetna",
        deductible_remaining_usd: oop, coinsurance_pct: 0.20,
      });
      setResp(j);
    } catch (e) { setErr(String(e)); }
    finally { setLoading(false); }
  }, [drugKey, oop]);

  useEffect(() => { void run(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div>
      <H num={8} title="Site-of-Care Optimizer" sub="Hospital-outpatient infusions are 2–4× more expensive than office or home. Surfaces patient OOP + payer savings before authorization decision." />
      <div className="flex gap-2 mb-3 flex-wrap items-end">
        <div>
          <div className="text-[10px] text-compact text-ink-muted mb-1">Drug</div>
          <select value={drugKey} onChange={(e) => setDrugKey(e.target.value)}
                  className="bg-surface-bg border border-surface-border rounded px-2 py-1 text-sm">
            <option>pembrolizumab_200mg_q3w</option>
            <option>trastuzumab_6mgkg_q3w</option>
            <option>rituximab_375mgm2_q3w</option>
            <option>olaparib_300mg_bid</option>
          </select>
        </div>
        <Input label="Deductible remaining ($)" value={String(oop)} onChange={(v) => setOop(parseFloat(v) || 0)} />
        <RunButton onClick={run} loading={loading} label="Compare sites" />
      </div>
      {err && <ErrBox text={err} />}
      {resp && (
        <div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-2 mb-3">
            {resp.sites.map((s: any) => (
              <div key={s.site_key} className={clsx(
                "border rounded-xl p-3",
                s.site_key === resp.recommendation.preferred_site_key
                  ? "border-accent-green bg-accent-green/10"
                  : "border-surface-border bg-surface-bg",
              )}>
                <div className="text-[12.5px] font-medium text-ink-primary mb-1">{s.label}</div>
                <div className="text-[11px] text-mono-tech text-ink-muted">total cost</div>
                <div className="text-lg font-semibold text-ink-primary tabular-nums">${s.total_cost.toLocaleString()}</div>
                <div className="text-[11px] text-mono-tech text-ink-muted mt-1">est. patient OOP</div>
                <div className="text-base font-medium text-accent-cyan tabular-nums">${s.patient_oop_estimate.toLocaleString()}</div>
                {s.eligibility_notes && <div className="text-[10px] text-ink-faint mt-1.5 italic">{s.eligibility_notes}</div>}
              </div>
            ))}
          </div>
          <div className="text-sm text-ink-body">
            <span className="text-accent-green font-semibold">Preferred:</span> {resp.recommendation.preferred_label}
            {" · "}<span className="text-ink-muted">payer save:</span> <span className="text-accent-green">${resp.recommendation.payer_savings_per_session_usd.toLocaleString()}/session</span>
            {" · "}<span className="text-ink-muted">annualized:</span> <span className="text-accent-green">${resp.recommendation.annualized_savings_estimate_usd.toLocaleString()}/yr</span>
          </div>
        </div>
      )}
    </div>
  );
}

// =============================================================================
// USP #9 — Policy Diff
// =============================================================================

function PolicyDiffTab() {
  const [diffs, setDiffs] = useState<any[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    api<{ diffs: any[] }>("GET", "/onco/policies/diffs")
      .then((j) => setDiffs(j.diffs))
      .catch((e) => setErr(String(e)))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <H num={9} title="Multi-Payer Policy Reconciliation" sub="Diff-tracked snapshots of payer policies. Snapshot crawler runs hourly; in-flight PAs auto-flagged when criteria change." />
      {loading && <div className="text-sm text-ink-muted">Loading diffs…</div>}
      {err && <ErrBox text={err} />}
      <div className="space-y-3">
        {diffs?.map((d, i) => (
          <div key={i} className="border border-surface-border rounded-xl p-3 bg-surface-bg">
            <div className="flex items-baseline gap-2 flex-wrap mb-1">
              <span className="text-[12.5px] font-semibold text-ink-primary">{d.payer}</span>
              <span className="text-[11px] text-mono-tech text-accent-cyan">{d.policy_id}</span>
              <span className="text-[10px] text-mono-tech text-ink-faint">{d.version_old} → {d.version_new}</span>
              <span className="text-[10px] text-mono-tech text-ink-faint ml-auto">{new Date(d.changed_at).toLocaleString()}</span>
            </div>
            <div className="text-[12px] text-ink-body mb-1.5">
              <span className="text-ink-muted">treatment:</span> <span className="text-accent-brand">{d.treatment}</span>
              {" · "}<span className="text-ink-muted">in-flight PAs affected:</span> <span className="text-accent-amber font-medium">{d.in_flight_pas_affected}</span>
            </div>
            <div className="text-[12px] text-ink-body mb-1">{d.summary}</div>
            <ul className="text-[11.5px] text-ink-muted space-y-0.5 ml-3">
              {d.diff.map((c: any, j: number) => (
                <li key={j}>
                  <span className={clsx(
                    "text-mono-tech text-[10px] px-1 py-0.5 rounded mr-1",
                    c.action === "added" ? "bg-accent-green/15 text-accent-green"
                      : c.action === "removed" ? "bg-accent-red/15 text-accent-red"
                      : "bg-accent-amber/15 text-accent-amber",
                  )}>{c.action}</span>
                  <span className="text-ink-faint">[{c.section}]</span> {c.text}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </div>
  );
}

// =============================================================================
// USP #10 — Audit Trail
// =============================================================================

function AuditTab() {
  const [chain, setChain] = useState<any | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true); setErr(null);
    try {
      const j = await api("GET", "/onco/audit/trail?limit=20");
      setChain(j);
    } catch (e) { setErr(String(e)); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  return (
    <div>
      <H num={10} title="Cryptographic Audit Trail" sub="Every USP call appends a SHA-256-chained record. Tamper-evident structure (each record's prev_hash links to the previous). Production anchors to QLDB or S3 Object Lock." />
      <div className="flex items-center gap-3 mb-3">
        <RunButton onClick={refresh} loading={loading} label="Refresh chain" />
        {chain && (
          <StatusPill ok={chain.integrity.chain_valid}
                      text={`chain ${chain.integrity.chain_valid ? "VALID" : "BROKEN"} · ${chain.integrity.n_total_records} total records`} />
        )}
      </div>
      {err && <ErrBox text={err} />}
      {chain && (
        <div className="space-y-1">
          {chain.records.map((r: any) => (
            <div key={r.id} className="text-mono-tech text-[10.5px] text-ink-body bg-surface-bg border border-surface-border rounded-lg px-3 py-2">
              <div className="flex flex-wrap gap-x-3 gap-y-0.5 items-baseline">
                <span className="text-ink-faint">[{new Date(r.timestamp).toLocaleTimeString()}]</span>
                <span className="text-accent-cyan">{r.kind}</span>
                <span className="text-accent-brand">{r.agent}</span>
                <span className="text-ink-muted">conf {r.confidence != null ? (r.confidence * 100).toFixed(0) + "%" : "—"}</span>
              </div>
              <div className="text-ink-faint truncate">
                hash: {r.hash.slice(0, 24)}…  ←  prev: {r.prev_hash.slice(0, 24)}…
              </div>
              <div className="text-ink-faint truncate">
                inputs: {r.inputs_sha256.slice(0, 16)}…  ·  output: {r.output_sha256.slice(0, 16)}…
              </div>
            </div>
          ))}
          <div className="text-[10px] text-mono-tech text-ink-faint mt-2">{chain.anchor_note}</div>
        </div>
      )}
    </div>
  );
}

// =============================================================================
// Tiny helpers
// =============================================================================

function Input({ label, value, onChange, placeholder }: { label: string; value: string; onChange: (v: string) => void; placeholder?: string }) {
  return (
    <div>
      <div className="text-[10px] text-compact text-ink-muted mb-1">{label}</div>
      <input value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder}
             className="w-full bg-surface-bg border border-surface-border rounded px-2 py-1 text-sm text-ink-primary placeholder:text-ink-faint focus:outline-none focus:border-accent-brand" />
    </div>
  );
}

function RunButton({ onClick, loading, label, disabled }: { onClick: () => void; loading: boolean; label: React.ReactNode; disabled?: boolean }) {
  return (
    <button type="button" onClick={onClick} disabled={loading || disabled}
            className="text-[12px] font-medium px-3 py-1.5 rounded-md border border-accent-brand text-white bg-accent-brand hover:opacity-90 transition-opacity flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed">
      {loading ? <Loader2 size={12} className="animate-spin" /> : <PlayCircle size={12} />}
      {label}
    </button>
  );
}

function ErrBox({ text }: { text: string }) {
  return (
    <div className="border border-accent-red/40 bg-accent-red/10 text-accent-red text-[12px] px-3 py-2 rounded-md mb-3 flex items-start gap-2">
      <AlertCircle size={13} className="mt-0.5 shrink-0" />
      <span>{text}</span>
    </div>
  );
}
