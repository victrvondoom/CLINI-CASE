/* global window, React */
/* ============================================================
   INTAKE PAGE — Drop a scan (handwritten Rx · echo report · faxed letter)

   Standalone has no backend, so this page renders a *deterministic mock*
   IntakeResult that matches what the live Bedrock vision pipeline would
   actually return for the synthetic Indian oncology Rx fixture. The shape
   matches the real Pydantic IntakeResult model exactly — same data the
   React frontend renders against the live /api/v1/intake/parse-document
   endpoint.
   ============================================================ */
const { useState: useStateI, useRef: useRefI } = React;

function IntakeFlowPage({ navigate }) {
  const { FIXTURE, RESULT } = window.CLINCASE_INTAKE;
  const [stage, setStage] = useStateI("ready");        // ready | scanning | done
  const [progress, setProgress] = useStateI(0);
  const inputRef = useRefI(null);

  const startScan = () => {
    setStage("scanning");
    setProgress(0);
    let p = 0;
    const t = setInterval(() => {
      p += 6 + Math.random() * 12;
      if (p >= 100) {
        clearInterval(t);
        setProgress(100);
        setStage("done");
      } else {
        setProgress(Math.round(p));
      }
    }, 220);
  };

  return (
    <div data-screen-label="intake" className="space-y-5">
      <header>
        <Eyebrow>Workspace · Document Intake · Pre-DAG layer</Eyebrow>
        <h1 className="mt-1 text-[26px] font-semibold tracking-tight text-ink-primary display-tight">
          Drop a scan
        </h1>
        <p className="mt-1.5 text-[13px] text-ink-body max-w-[78ch]">
          Handwritten oncology prescription · scanned echocardiogram · faxed denial letter ·
          phone-camera photograph — the Document Intake layer reads it and produces a typed
          ClinicalSnapshot the 7-agent DAG can run on. India-ready. CMS-0057-F § IV.A audited.
        </p>
      </header>

      {/* Pipeline strip — always visible so judges can see the architecture */}
      <PipelineStrip />

      <div className="grid grid-cols-1 lg:grid-cols-[1.15fr_1fr] gap-5">
        {/* ---- LEFT — Upload zone + fixture preview ---- */}
        <section className="space-y-3">
          {stage === "ready" && (
            <IntakeDropZone
              onDrop={startScan}
              onPick={() => inputRef.current?.click()}
              onUseFixture={startScan}
              fixture={FIXTURE}
            />
          )}
          {stage === "scanning" && <ScanningPanel progress={progress} />}
          {stage === "done" && (
            <FixturePreview
              fixture={FIXTURE}
              classification={RESULT.classification}
              onReset={() => setStage("ready")}
            />
          )}
          <input
            ref={inputRef}
            type="file"
            accept="image/png,image/jpeg,image/webp,application/pdf"
            hidden
            onChange={(e) => {
              if (e.target.files?.[0]) startScan();
            }}
          />
        </section>

        {/* ---- RIGHT — IntakeResult panel ---- */}
        <section>
          {stage === "done" ? (
            <IntakeResultPanel result={RESULT} navigate={navigate} />
          ) : (
            <ResultPlaceholder stage={stage} progress={progress} />
          )}
        </section>
      </div>
    </div>
  );
}

/* ---------- Pipeline strip ---------- */
function PipelineStrip() {
  const stages = [
    { num: "1", label: "Classifier",       sub: "PIL stats · 0 LLM tokens",            tone: "cyan" },
    { num: "2", label: "Vision Extractor", sub: "Sonnet 4.6 vision · Bedrock",         tone: "violet" },
    { num: "3", label: "FHIR Shaper",      sub: "partial ClinicalSnapshot + audit",    tone: "indigo" },
    { num: "→", label: "Clinical Extractor", sub: "feeds the 7-agent DAG",             tone: "slate" },
  ];
  const toneClass = {
    cyan:   "bg-cyan-500/15 text-cyan-300 border-cyan-500/40",
    violet: "bg-violet-500/15 text-violet-300 border-violet-500/40",
    indigo: "bg-indigo-500/15 text-indigo-300 border-indigo-500/40",
    slate:  "bg-surface-bg text-ink-muted border-surface-border",
  };
  return (
    <div className="border border-surface-border rounded-xl p-3 bg-surface-bg/40 flex items-stretch gap-2 overflow-x-auto">
      {stages.map((st, i) => (
        <React.Fragment key={i}>
          <div className="flex-1 min-w-[170px] flex items-center gap-2 px-3 py-2">
            <span className={`text-[11px] font-mono font-semibold w-6 h-6 rounded inline-flex items-center justify-center border ${toneClass[st.tone]}`}>
              {st.num}
            </span>
            <div>
              <div className="text-[12.5px] font-semibold text-ink-primary">{st.label}</div>
              <div className="text-[10.5px] text-ink-muted font-mono">{st.sub}</div>
            </div>
          </div>
          {i < stages.length - 1 && (
            <div className="flex items-center text-ink-muted text-sm">›</div>
          )}
        </React.Fragment>
      ))}
    </div>
  );
}

/* ---------- Drop zone ---------- */
function IntakeDropZone({ onDrop, onPick, onUseFixture, fixture }) {
  const [hover, setHover] = useStateI(false);
  return (
    <div
      onDragOver={(e) => { e.preventDefault(); setHover(true); }}
      onDragLeave={() => setHover(false)}
      onDrop={(e) => { e.preventDefault(); setHover(false); onDrop(); }}
      onClick={onPick}
      className={`border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition-colors ${
        hover
          ? "border-accent-brand bg-accent-brand/10"
          : "border-surface-border bg-surface-bg/40 hover:bg-surface-bg/60"
      }`}
    >
      <I.Upload className="mx-auto text-ink-muted mb-3" size={32} />
      <p className="text-[14px] font-medium text-ink-primary">
        Drop a document here, or click to browse
      </p>
      <p className="text-[12px] text-ink-muted mt-1">
        PNG · JPEG · WebP · PDF · up to 8 MB
      </p>
      <div className="mt-4 inline-flex items-center gap-2 text-[12px]">
        <span className="text-ink-muted">No file? </span>
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); onUseFixture(); }}
          className="px-3 py-1.5 rounded-md text-[12px] font-medium border border-accent-brand/40 bg-accent-brand/10 text-accent-brand-glow hover:bg-accent-brand/20"
        >
          Use the demo Rx → {fixture.filename}
        </button>
      </div>
    </div>
  );
}

/* ---------- Scanning state ---------- */
function ScanningPanel({ progress }) {
  return (
    <div className="border border-accent-brand/40 rounded-xl p-8 bg-accent-brand/5">
      <div className="flex items-center gap-3 mb-4">
        <div className="w-10 h-10 rounded-full border-2 border-accent-brand border-t-transparent animate-spin" />
        <div>
          <div className="text-[14px] font-semibold text-ink-primary">Reading document…</div>
          <div className="text-[12px] text-ink-muted font-mono">
            classifier → claude_vision_bedrock → fhir_shaper
          </div>
        </div>
      </div>
      <div className="h-2 rounded-full bg-surface-bg overflow-hidden">
        <div
          className="h-full bg-gradient-to-r from-accent-brand to-accent-cyan transition-all duration-200"
          style={{ width: `${progress}%` }}
        />
      </div>
      <div className="mt-2 text-[11px] font-mono text-ink-muted">
        {progress}% · streaming via SSE
      </div>
    </div>
  );
}

/* ---------- Fixture preview (after scan) ---------- */
function FixturePreview({ fixture, classification, onReset }) {
  return (
    <div className="border border-surface-border rounded-xl bg-surface-raised overflow-hidden">
      <div className="px-4 py-2.5 border-b border-surface-border bg-surface-bg/40 flex items-center gap-2 flex-wrap">
        <I.FileText size={14} className="text-ink-body" />
        <span className="text-[13px] font-semibold text-ink-primary">{fixture.filename}</span>
        <span className="text-[11px] font-mono text-ink-muted">{fixture.sizeKB} KB · image/png</span>
        <Pill tone="cyan" className="ml-1">
          {classification.document_type.replace("_", " ")}
        </Pill>
        <button
          type="button"
          onClick={onReset}
          className="ml-auto text-[11px] text-ink-muted hover:text-ink-body underline"
        >
          drop another
        </button>
      </div>
      <div className="p-4 bg-paper text-ink-body text-[12px] font-mono leading-[1.55] max-h-[420px] overflow-auto">
        {/* Rendered approximation of the Rx — same content the vision pipeline reads */}
        <div className="border border-surface-border rounded-md p-3 bg-white">
          <div className="bg-[#0F1E50] -m-3 mb-2 px-3 py-2 text-[11px] text-cyan-200 font-bold tracking-wide">
            ABC ONCOLOGY CENTRE · Dr. Priya Menon, MD (Med Onc) · Pune
          </div>
          <div className="text-[12.5px] mt-2">Date: 06/05/26   Patient: <span className="text-ink-muted">[redacted-name]</span>   Age: 57   Sex: M   Wt: 68 kg</div>
          <div className="mt-3"><strong>Dx:</strong> Ca Breast Lt — Stage IIIA</div>
          <div>HER2 + (IHC 3+, FISH amp.) · ER 88% pos · PR 62% pos</div>
          <div>Post-op RT done 03/2026</div>
          <div className="mt-3 text-rose-700 font-bold">
            Rx: Inj. Herceptin 6 mg/kg IV q3w × 17 cycles
          </div>
          <div className="text-rose-700/80 text-[11px]">(maintenance HER2-targeted therapy)</div>
          <div className="mt-3"><strong>Baseline cardiac:</strong> LVEF 62% (echo 15/04/2026) · ECOG = 1</div>
          <div className="mt-3 text-ink-muted text-[11px]">
            Signed — Dr. Priya Menon, MD · Med Reg KMC-48201
          </div>
        </div>
      </div>
    </div>
  );
}

/* ---------- IntakeResult panel ---------- */
function IntakeResultPanel({ result, navigate }) {
  const overall = result.ocr.overall_confidence;
  const tone =
    overall >= 0.85 ? "green" :
    overall >= 0.70 ? "amber" : "red";
  return (
    <div className="space-y-3">
      {/* Classification card */}
      <div className="border border-surface-border rounded-xl bg-surface-raised p-4">
        <Eyebrow>Classification</Eyebrow>
        <div className="mt-1 flex items-center gap-3">
          <span className="text-[16px] font-semibold text-ink-primary capitalize">
            {result.classification.document_type.replace("_", " ")}
          </span>
          <ConfidenceChip value={result.classification.confidence} />
        </div>
        <p className="mt-1 text-[12px] text-ink-body">
          {result.classification.rationale}
        </p>
        {result.classification.quality_flags?.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {result.classification.quality_flags.map((q) => (
              <Pill key={q} tone="amber">{q}</Pill>
            ))}
          </div>
        )}
      </div>

      {/* HITL banner — only when routing requires it */}
      {result.requires_human_review && (
        <div className="border border-amber-500/40 bg-amber-500/10 rounded-xl p-3">
          <div className="text-[12px] font-mono uppercase tracking-widest text-amber-400 mb-1">
            ▲ Routes to Reviewer queue (HITL)
          </div>
          <p className="text-[12.5px] text-ink-body">
            Confidence {(result.ocr.overall_confidence * 100).toFixed(0)}% below 70%
            threshold OR a binding field is missing. Risk flags: {result.risk_flags.join(", ") || "—"}.
          </p>
        </div>
      )}

      {/* Extracted fields */}
      <div className="border border-surface-border rounded-xl bg-surface-raised">
        <div className="px-4 py-2.5 border-b border-surface-border bg-surface-bg/40 flex items-center justify-between">
          <Eyebrow>Extracted fields ({result.ocr.extracted_fields.length})</Eyebrow>
          <ConfidenceChip value={overall} />
        </div>
        <div className="p-2 max-h-[340px] overflow-auto divide-y divide-surface-border">
          {result.ocr.extracted_fields.map((f, i) => (
            <FieldRow key={i} field={f} />
          ))}
        </div>
      </div>

      {/* Audit panel */}
      <div className="border border-surface-border rounded-xl bg-surface-bg/40 p-3">
        <Eyebrow>Audit · CMS-0057-F § IV.A</Eyebrow>
        <div className="mt-1 grid grid-cols-2 gap-x-4 gap-y-1 font-mono text-[11px] text-ink-body">
          <div>SHA-256:</div><div className="text-ink-muted truncate">{result.audit.document_sha256.slice(0, 32)}…</div>
          <div>Engines:</div><div className="text-ink-muted">{result.audit.engines_used.join(" → ")}</div>
          <div>Latency:</div><div className="text-ink-muted">{result.audit.latency_ms} ms</div>
          <div>Tokens:</div><div className="text-ink-muted">in {result.audit.input_tokens.toLocaleString()} · out {result.audit.output_tokens.toLocaleString()}</div>
          <div>Model:</div><div className="text-ink-muted truncate">{result.audit.model_id}</div>
          <div>PHI redactions:</div><div className="text-ink-muted">{result.ocr.phi_redactions_applied}</div>
        </div>
      </div>

      {/* Action — Create case */}
      {!result.requires_human_review && (
        <button
          type="button"
          onClick={() => navigate?.("#/cases/case_8f4ad9c2")}
          className="w-full border border-emerald-500/40 bg-emerald-500/10 hover:bg-emerald-500/15 rounded-xl p-3 text-left flex items-center gap-3 transition-colors"
        >
          <I.Check size={20} className="text-emerald-400 flex-shrink-0" />
          <div className="flex-1">
            <div className="text-[13px] font-semibold text-ink-primary">
              Confidence {(overall * 100).toFixed(0)}% — ready to dispatch.
            </div>
            <div className="text-[11.5px] text-ink-muted">
              Create case → Clinical Extractor uses this snapshot as the seed.
            </div>
          </div>
          <span className="text-[11px] font-mono text-emerald-300">→ run DAG</span>
        </button>
      )}
    </div>
  );
}

/* ---------- one-row field card ---------- */
function FieldRow({ field }) {
  return (
    <div className="px-3 py-2 flex items-start gap-2.5">
      <ConfidenceChip value={field.confidence} compact />
      <div className="flex-1 min-w-0">
        <div className="text-[10.5px] font-mono text-ink-muted truncate">
          {field.name}
        </div>
        <div className="text-[13px] font-medium text-ink-primary truncate">
          {field.value}
        </div>
        <div className="text-[10.5px] text-ink-muted italic truncate">
          “{field.source_excerpt}”
        </div>
      </div>
    </div>
  );
}

/* ---------- confidence chip ---------- */
function ConfidenceChip({ value, compact = false }) {
  const tone =
    value >= 0.85 ? "bg-emerald-500/15 text-emerald-300 border-emerald-500/40" :
    value >= 0.70 ? "bg-amber-500/15 text-amber-300 border-amber-500/40" :
                    "bg-rose-500/15 text-rose-300 border-rose-500/40";
  return (
    <span className={`inline-flex items-center justify-center rounded border font-mono ${
      compact ? "text-[10px] px-1.5 py-0.5 min-w-[34px]" : "text-[11px] px-2 py-0.5 min-w-[44px]"
    } ${tone}`}>
      {(value * 100).toFixed(0)}%
    </span>
  );
}

/* ---------- empty result placeholder ---------- */
function ResultPlaceholder({ stage, progress }) {
  return (
    <div className="border border-surface-border rounded-xl bg-surface-bg/40 p-8 h-full flex items-center justify-center text-center">
      <div>
        <I.FileText className="mx-auto text-ink-muted/60 mb-3" size={32} />
        <div className="text-[13px] text-ink-body font-semibold">
          {stage === "scanning" ? `Reading… (${progress}%)` : "Drop a document to see the structured intake."}
        </div>
        <div className="text-[11px] text-ink-muted mt-2 font-mono leading-[1.6]">
          PIL classifier → Claude Sonnet 4.6 vision (Bedrock) → IntakeResult → Clinical Extractor.
        </div>
      </div>
    </div>
  );
}

window.IntakeFlowPage = IntakeFlowPage;
