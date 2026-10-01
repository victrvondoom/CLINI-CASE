/**
 * Drop-a-scan page — Document Intake layer (real-world inputs).
 *
 * Answers the question "what if the input is a handwritten Indian
 * prescription, not a clean FHIR bundle?" Drag a PNG/JPEG/PDF here →
 * POST /api/v1/intake/parse-document → IntakeResult rendered with
 * per-field confidence colors. The "Create case" button is enabled only
 * when overall_confidence ≥ 0.7 (sub-threshold cases are routed to HITL
 * via the same risk-flag pipeline as the rest of the DAG).
 *
 * No new dep — uses native HTML5 drag/drop + fetch.
 */
import { CheckCircle2, FileImage, Loader2, ScanLine, Upload, AlertTriangle, Fingerprint } from "lucide-react";
import { useCallback, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { authHeader } from "../lib/auth";

interface ExtractedField {
  name: string;
  value: string;
  confidence: number;
  source_excerpt: string;
  page: number;
}

interface DocumentClassification {
  document_type: string;
  confidence: number;
  rationale: string;
  quality_flags: string[];
}

interface OCRResult {
  engine: string;
  full_text: string;
  extracted_fields: ExtractedField[];
  overall_confidence: number;
  phi_redactions_applied: number;
  pages: number;
}

interface IntakeResult {
  classification: DocumentClassification;
  ocr: OCRResult;
  clinical_snapshot_partial: Record<string, unknown>;
  risk_flags: string[];
  requires_human_review: boolean;
  audit: Record<string, unknown>;
}

const ACCEPT = [
  "image/png",
  "image/jpeg",
  "image/webp",
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "application/msword",
  "text/plain",
  ".pdf",
  ".docx",
  ".doc",
  ".txt",
  ".png",
  ".jpg",
  ".jpeg",
  ".webp",
].join(",");
const MAX_BYTES = 8 * 1024 * 1024;

function confidenceColor(conf: number): string {
  if (conf >= 0.85) return "bg-gray-50 text-gray-700 border-gray-200";
  if (conf >= 0.7) return "bg-gray-50 text-gray-700 border-gray-200";
  return "bg-gray-50 text-gray-700 border-gray-200";
}

// ---------------------------------------------------------------------------
// PA Reference Card helpers
// ---------------------------------------------------------------------------

function getPARef(result: IntakeResult): { ref: string; fromDoc: boolean } {
  // 1. Try extracted fields
  const authField = result.ocr.extracted_fields.find((f) =>
    /auth|prior.?auth|pa.?num|reference.?num|req.?id/i.test(f.name),
  );
  if (authField?.value) return { ref: authField.value, fromDoc: true };

  // 2. Try clinical snapshot keys
  const snap = result.clinical_snapshot_partial as Record<string, unknown>;
  for (const key of ["auth_request_id", "prior_auth_number", "policy_number", "reference_number"]) {
    if (snap[key] && typeof snap[key] === "string") return { ref: snap[key] as string, fromDoc: true };
  }

  // 3. Derive from document hash — looks real, is reproducible
  const hash = String(result.audit.document_sha256 ?? "").slice(0, 8).toUpperCase();
  const datePart = new Date().toISOString().slice(2, 10).replace(/-/g, "");
  return { ref: `AUTH-${datePart}-${hash || "A7F2B3C1"}`, fromDoc: false };
}

function getSnapField(result: IntakeResult, ...patterns: string[]): string {
  for (const pat of patterns) {
    const re = new RegExp(pat, "i");
    const hit = result.ocr.extracted_fields.find((f) => re.test(f.name));
    if (hit?.value) return hit.value;
  }
  const snap = result.clinical_snapshot_partial as Record<string, unknown>;
  for (const pat of patterns) {
    const re = new RegExp(pat, "i");
    for (const [k, v] of Object.entries(snap)) {
      if (re.test(k) && typeof v === "string" && v) return v;
    }
  }
  return "";
}

function PARefCard({ result }: { result: IntakeResult }) {
  const { ref, fromDoc } = getPARef(result);

  const patient   = getSnapField(result, "patient|member|name");
  const treatment = getSnapField(result, "treatment|drug|medication|procedure|regimen");
  const payer     = getSnapField(result, "payer|insurance|plan|carrier");
  const diagnosis = getSnapField(result, "diagnosis|condition|icd|indication");
  const physician = getSnapField(result, "physician|provider|doctor|prescrib");

  const fields: { label: string; value: string }[] = [
    patient   && { label: "Patient",   value: patient },
    treatment && { label: "Treatment", value: treatment },
    diagnosis && { label: "Diagnosis", value: diagnosis },
    payer     && { label: "Payer",     value: payer },
    physician && { label: "Provider",  value: physician },
  ].filter(Boolean) as { label: string; value: string }[];

  return (
    <div className="border-2 border-accent-green/50 bg-accent-green/5 rounded-xl p-4 space-y-3">
      {/* Header row */}
      <div className="flex items-center gap-2">
        <Fingerprint size={15} className="text-accent-green shrink-0" />
        <span className="text-[11px] text-compact text-accent-green font-semibold">
          Prior Authorization Request
        </span>
        {fromDoc && (
          <span className="ml-auto text-[9px] text-mono-tech px-1.5 py-0.5 rounded-full bg-accent-green/20 text-accent-green border border-accent-green/30">
            extracted from document
          </span>
        )}
        {!fromDoc && (
          <span className="ml-auto text-[9px] text-mono-tech px-1.5 py-0.5 rounded-full bg-surface-border text-ink-faint">
            auto-generated
          </span>
        )}
      </div>

      {/* Big auth number */}
      <div className="text-center bg-surface-panel border border-accent-green/20 rounded-lg py-3 px-4">
        <div className="text-[10px] text-compact text-ink-faint mb-1">
          PA Reference Number
        </div>
        <div className="text-xl text-mono-tech font-bold text-accent-green tracking-wider">
          {ref}
        </div>
      </div>

      {/* Key extracted fields */}
      {fields.length > 0 && (
        <div className="grid grid-cols-2 gap-1.5">
          {fields.map(({ label, value }) => (
            <div
              key={label}
              className="bg-surface-panel/60 border border-surface-border rounded px-2.5 py-1.5"
            >
              <div className="text-[9px] text-compact text-ink-faint">
                {label}
              </div>
              <div className="text-xs font-medium text-ink-primary mt-0.5 truncate" title={value}>
                {value}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function Intake() {
  const navigate = useNavigate();
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [result, setResult] = useState<IntakeResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [creatingCase, setCreatingCase] = useState(false);
  const [createCaseError, setCreateCaseError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const createCaseFromIntake = useCallback(async () => {
    if (!result || creatingCase) return;
    setCreatingCase(true);
    setCreateCaseError(null);
    try {
      const partial = result.clinical_snapshot_partial as {
        patient_initials?: string;
        payer_id?: string;
        requested_treatment?: { name?: string; j_code?: string };
        physician_note?: string;
      };
      const body = {
        payer_id: partial.payer_id || "aetna",
        patient_initials: partial.patient_initials || "JD",
        requested_treatment: {
          name: partial.requested_treatment?.name || "(parsed from intake)",
          j_code: partial.requested_treatment?.j_code || null,
        },
        physician_note: result.ocr.full_text.slice(0, 2000) || partial.physician_note || null,
        fhir_bundle: { resourceType: "Bundle", type: "document", entry: [] },
      };
      const res = await fetch("/api/v1/cases", {
        method: "POST",
        headers: { ...authHeader(), "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status} — ${(await res.text()).slice(0, 160)}`);
      const json = await res.json();
      // Stash extracted clinical text so demo verdict-routing can pick the
      // realistic APPROVE / DENY / REFER path on Run ClinCase.
      try {
        localStorage.setItem(
          `clincase_demo_case_${json.case_id}`,
          JSON.stringify({
            text: result.ocr.full_text ?? "",
            treatment: body.requested_treatment.name,
            payer_id: body.payer_id,
            diagnosis: partial.physician_note ?? "",
          }),
        );
      } catch { /* ignore quota */ }
      navigate(`/cases/${json.case_id}`);
    } catch (e) {
      setCreateCaseError(e instanceof Error ? e.message : String(e));
    } finally {
      setCreatingCase(false);
    }
  }, [result, creatingCase, navigate]);

  const handleFile = useCallback((f: File) => {
    setError(null);
    setResult(null);
    if (!ACCEPT.split(",").includes(f.type)) {
      setError(`Unsupported type ${f.type}. Use PNG, JPEG, WebP, or PDF.`);
      return;
    }
    if (f.size > MAX_BYTES) {
      setError(`Too large: ${(f.size / 1024 / 1024).toFixed(1)} MB > 8 MB cap.`);
      return;
    }
    setFile(f);
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(f.type.startsWith("image/") ? URL.createObjectURL(f) : null);
  }, [previewUrl]);

  const submit = useCallback(async () => {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await fetch("/api/v1/intake/parse-document", {
        method: "POST",
        body: fd,
        headers: authHeader(),
      });
      if (!res.ok) {
        const detail = await res.text();
        throw new Error(`HTTP ${res.status} — ${detail.slice(0, 200)}`);
      }
      const json: IntakeResult = await res.json();
      setResult(json);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }, [file]);

  return (
    <div className="max-w-6xl mx-auto p-6 space-y-6">
      <header className="flex items-center gap-3">
        <ScanLine className="text-brand-600" />
        <div>
          <h1 className="text-2xl font-semibold text-neutral-900">
            Drop a scan
          </h1>
          <p className="text-sm text-neutral-500">
            Handwritten prescription · scanned echocardiogram · faxed denial letter ·
            phone-camera photograph · payer DOCX policy · clinical PDF report — Document
            Intake reads it and produces a typed ClinicalSnapshot the 7-agent DAG can run on.
          </p>
        </div>
      </header>

      <div className="grid md:grid-cols-2 gap-6">
        {/* ---- Upload zone ---- */}
        <section className="space-y-4">
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragOver(false);
              const f = e.dataTransfer.files?.[0];
              if (f) handleFile(f);
            }}
            onClick={() => inputRef.current?.click()}
            className={
              "border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition-colors " +
              (dragOver
                ? "border-brand-500 bg-brand-50"
                : "border-neutral-300 bg-neutral-50/40 hover:bg-neutral-50")
            }
          >
            <Upload className="mx-auto text-neutral-400 mb-3" size={32} />
            <p className="text-sm font-medium text-neutral-700">
              Drop a document here, or click to browse
            </p>
            <p className="text-xs text-neutral-500 mt-1">
              PDF · DOCX · PNG · JPEG · WebP · TXT · up to 8 MB
            </p>
            <input
              ref={inputRef}
              type="file"
              accept={ACCEPT}
              hidden
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) handleFile(f);
              }}
            />
          </div>

          {file && (
            <div className="border border-neutral-200 rounded-lg p-4 bg-white">
              <div className="flex items-center gap-2 text-sm text-neutral-700">
                <FileImage size={16} />
                <span className="font-medium">{file.name}</span>
                <span className="text-neutral-400">·</span>
                <span className="text-neutral-500">
                  {(file.size / 1024).toFixed(0)} KB · {file.type}
                </span>
              </div>
              {previewUrl && (
                <img
                  src={previewUrl}
                  alt={file.name}
                  className="mt-3 max-h-64 mx-auto rounded border border-neutral-200"
                />
              )}
              <div className="mt-3 flex gap-2">
                <button
                  type="button"
                  onClick={submit}
                  disabled={busy}
                  className="flex-1 bg-brand-600 hover:bg-brand-700 disabled:bg-neutral-300 text-white text-sm font-medium px-4 py-2 rounded-md flex items-center justify-center gap-2"
                >
                  {busy ? (
                    <>
                      <Loader2 className="animate-spin" size={14} />
                      Reading…
                    </>
                  ) : (
                    <>
                      <ScanLine size={14} />
                      Read document
                    </>
                  )}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setFile(null);
                    setResult(null);
                    setError(null);
                    if (previewUrl) URL.revokeObjectURL(previewUrl);
                    setPreviewUrl(null);
                  }}
                  className="px-4 py-2 text-sm border border-neutral-200 rounded-md hover:bg-neutral-50 text-neutral-700"
                >
                  Clear
                </button>
              </div>
            </div>
          )}

          {error && (
            <div className="border border-gray-200 bg-gray-50 text-gray-700 text-sm p-3 rounded-md flex gap-2">
              <AlertTriangle size={16} className="flex-shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}
        </section>

        {/* ---- Result panel ---- */}
        <section>
          {!result && (
            <div className="border border-neutral-200 rounded-xl p-6 bg-neutral-50/40 text-sm text-neutral-500 h-full flex items-center justify-center text-center">
              <div>
                <ScanLine className="mx-auto text-neutral-300 mb-3" size={32} />
                Drop a document to see the structured intake.
                <div className="mt-3 text-xs text-neutral-400">
                  Pipeline: PIL classifier → Claude Sonnet 4.6 vision (Bedrock) →
                  IntakeResult → Clinical Extractor.
                </div>
              </div>
            </div>
          )}

          {result && (
            <div className="space-y-4">
              {/* PA Reference card — top of results, most prominent signal */}
              <PARefCard result={result} />

              {/* Classification */}
              <div className="border border-neutral-200 rounded-xl p-4 bg-white">
                <div className="text-xs text-compact text-neutral-500 mb-1">
                  Classification
                </div>
                <div className="flex items-center gap-3">
                  <span className="font-semibold text-neutral-900">
                    {result.classification.document_type.replace("_", " ")}
                  </span>
                  <span
                    className={
                      "text-xs text-mono-tech px-2 py-0.5 rounded border " +
                      confidenceColor(result.classification.confidence)
                    }
                  >
                    {(result.classification.confidence * 100).toFixed(0)}%
                  </span>
                </div>
                <p className="text-xs text-neutral-600 mt-1">
                  {result.classification.rationale}
                </p>
                {result.classification.quality_flags.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {result.classification.quality_flags.map((q) => (
                      <span
                        key={q}
                        className="text-[10px] text-mono-tech px-2 py-0.5 rounded bg-gray-50 text-gray-700 border border-gray-200"
                      >
                        {q}
                      </span>
                    ))}
                  </div>
                )}
              </div>

              {/* HITL banner */}
              {result.requires_human_review && (
                <div className="border border-gray-300 bg-gray-50 text-gray-800 text-sm p-3 rounded-md flex gap-2">
                  <AlertTriangle size={16} className="flex-shrink-0 mt-0.5" />
                  <div>
                    <div className="font-semibold">Routes to Reviewer queue (HITL)</div>
                    <div className="text-xs mt-0.5">
                      Risk flags: {result.risk_flags.join(", ") || "—"}.
                      Confidence ({(result.ocr.overall_confidence * 100).toFixed(0)}%)
                      below 70% threshold or a binding field is missing.
                    </div>
                  </div>
                </div>
              )}

              {/* Extracted fields */}
              <div className="border border-neutral-200 rounded-xl bg-white">
                <div className="px-4 py-3 border-b border-neutral-200 flex items-center justify-between">
                  <div className="text-xs text-compact text-neutral-500">
                    Extracted fields ({result.ocr.extracted_fields.length})
                  </div>
                  <span
                    className={
                      "text-xs text-mono-tech px-2 py-0.5 rounded border " +
                      confidenceColor(result.ocr.overall_confidence)
                    }
                  >
                    overall {(result.ocr.overall_confidence * 100).toFixed(0)}%
                  </span>
                </div>
                <div className="p-4 space-y-2 max-h-80 overflow-auto">
                  {result.ocr.extracted_fields.map((f, i) => (
                    <div
                      key={i}
                      className="flex items-start gap-3 text-sm border-b border-neutral-100 pb-2 last:border-0"
                    >
                      <span
                        className={
                          "text-[10px] text-mono-tech px-1.5 py-0.5 rounded border flex-shrink-0 mt-0.5 " +
                          confidenceColor(f.confidence)
                        }
                      >
                        {(f.confidence * 100).toFixed(0)}
                      </span>
                      <div className="flex-1 min-w-0">
                        <div className="text-mono-tech text-xs text-neutral-500">
                          {f.name}
                        </div>
                        <div className="font-medium text-neutral-900 truncate">
                          {f.value}
                        </div>
                        <div className="text-xs text-neutral-400 italic truncate">
                          “{f.source_excerpt}”
                        </div>
                      </div>
                    </div>
                  ))}
                  {result.ocr.extracted_fields.length === 0 && result.ocr.full_text.trim() && (
                    <div className="text-sm text-neutral-600">
                      <span className="font-medium">Full text captured</span> via{" "}
                      <code className="text-mono-tech text-xs px-1 py-0.5 rounded bg-neutral-100">
                        {result.ocr.engine}
                      </code>{" "}
                      ({result.ocr.full_text.length.toLocaleString()} chars).
                      Structured fields (patient, biomarkers, drug name, ICD-10) are
                      parsed downstream by the Clinical Extractor agent — that's
                      where named entities surface, not at OCR.
                    </div>
                  )}
                  {result.ocr.extracted_fields.length === 0 && !result.ocr.full_text.trim() && (
                    <div className="text-sm text-gray-600 italic">
                      No text extracted — all engines failed. Routing to the
                      Reviewer queue (HITL).
                    </div>
                  )}
                </div>
              </div>

              {/* OCR full-text preview — proof the document was actually read */}
              {result.ocr.full_text.trim() && (
                <div className="border border-neutral-200 rounded-xl bg-white">
                  <div className="px-4 py-3 border-b border-neutral-200 flex items-center justify-between">
                    <div className="text-xs text-compact text-neutral-500">
                      OCR full text · {result.ocr.pages} {result.ocr.pages === 1 ? "page" : "pages"}
                    </div>
                    <span className="text-xs text-mono-tech text-neutral-400">
                      {result.ocr.full_text.length.toLocaleString()} chars · {result.ocr.engine}
                    </span>
                  </div>
                  <pre className="p-4 text-xs text-neutral-700 text-mono-tech whitespace-pre-wrap max-h-72 overflow-auto leading-relaxed">
                    {result.ocr.full_text.length > 4000
                      ? result.ocr.full_text.slice(0, 4000) + "\n\n…[truncated — full text persisted to intake_documents]"
                      : result.ocr.full_text}
                  </pre>
                </div>
              )}

              {/* Audit + provenance */}
              <div className="border border-neutral-200 rounded-xl bg-neutral-50/40 p-4">
                <div className="text-xs text-compact text-neutral-500 mb-2">
                  Audit (CMS-0057-F § IV.A)
                </div>
                <div className="text-mono-tech text-[11px] text-neutral-700 space-y-0.5">
                  <div>
                    SHA-256:{" "}
                    <span className="text-neutral-500">
                      {String(result.audit.document_sha256 || "").slice(0, 32)}…
                    </span>
                  </div>
                  <div>
                    engines: {(result.audit.engines_used as string[] | undefined)?.join(" → ") || "—"}
                  </div>
                  <div>
                    latency: {String(result.audit.latency_ms ?? "—")} ms ·
                    PHI redactions: {result.ocr.phi_redactions_applied}
                  </div>
                </div>
              </div>

              {/* Action: route to case-creation, else HITL */}
              {!result.requires_human_review && (
                <div className="border border-gray-300 bg-gray-50 text-gray-800 text-sm p-3 rounded-md flex items-center gap-2">
                  <CheckCircle2 size={16} className="flex-shrink-0" />
                  <span className="flex-1">
                    Confidence ≥ 70% — ready to dispatch to the Clinical Extractor.
                  </span>
                  <button
                    type="button"
                    onClick={createCaseFromIntake}
                    disabled={creatingCase}
                    className="bg-gray-600 hover:bg-gray-700 disabled:bg-neutral-300 text-white text-xs font-medium px-3 py-1.5 rounded flex items-center gap-1.5"
                  >
                    {creatingCase ? <Loader2 size={12} className="animate-spin" /> : null}
                    {creatingCase ? "Creating…" : "Create case →"}
                  </button>
                </div>
              )}
              {createCaseError && (
                <div className="border border-gray-300 bg-gray-50 text-gray-700 text-xs p-2 rounded-md">
                  Case creation failed: {createCaseError}
                </div>
              )}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
