/**
 * /policies — Policy Library card grid.
 *
 * 5 real payer policies from backend/app/data/policies.json (mirrored in
 * lib/syntheticPolicies.ts for synchronous client render). Each card shows
 * payer + policy ID + title + version + last-updated time + section count.
 *
 * Click a card → /policies/:policy_id/diff (Phase 6 second route).
 */
import clsx from "clsx";
import {
  AlertTriangle,
  ArrowRight,
  BookOpen,
  CheckCircle2,
  ChevronDown,
  FileText,
  Loader2,
  Plus,
  RotateCcw,
  Search,
  Sparkles,
  Trash2,
  Upload,
  X,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { authHeader } from "../lib/auth";
import { POLICIES } from "../lib/syntheticPolicies";

const PAYER_TINT: Record<string, string> = {
  aetna:  "bg-gray-500/15    text-gray-700    dark:text-gray-300",
  uhc:    "bg-gray-500/15    text-gray-700    dark:text-gray-300",
  bcbs:   "bg-gray-500/15    text-gray-700    dark:text-gray-300",
  anthem: "bg-gray-500/15  text-gray-700  dark:text-gray-300",
};

function timeAgo(iso: string): string {
  const ms = Date.now() - new Date(iso).getTime();
  const d = Math.floor(ms / (1000 * 60 * 60 * 24));
  if (d < 1) return "today";
  if (d < 30) return `${d} days ago`;
  if (d < 365) return `${Math.floor(d / 30)} months ago`;
  return `${Math.floor(d / 365)} years ago`;
}

interface UploadResult {
  name: string;
  policy_key: string;
  s3_uri: string | null;
  ingestion_job_id: string | null;
  status: string;
  kb_id: string | null;
  backend: string;
  message: string;
  demo_mode: boolean;
}

interface PolicySummary {
  policy_key: string;
  title: string;
  payer_id: string;
  policy_id: string | null;
  uploaded_by: string | null;
  uploaded_at: string | null;
  trashed_at: string | null;
  size_bytes: number;
  content_type: string | null;
  s3_uri: string | null;
}

interface PolicyListResponse {
  n: number;
  backend: string;
  bucket: string | null;
  policies: PolicySummary[];
}

export default function Policies() {
  const [search, setSearch] = useState("");
  const [payerFilter, setPayerFilter] = useState<string>("all");

  // Policy upload panel state
  const [uploadOpen, setUploadOpen] = useState(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadBusy, setUploadBusy] = useState(false);
  const [uploadResult, setUploadResult] = useState<UploadResult | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const uploadInputRef = useRef<HTMLInputElement>(null);

  // My policies + trash state
  const [myPolicies, setMyPolicies] = useState<PolicySummary[]>([]);
  const [trashed, setTrashed] = useState<PolicySummary[]>([]);
  const [view, setView] = useState<"active" | "trash">("active");
  const [policiesLoading, setPoliciesLoading] = useState(false);
  const [policiesError, setPoliciesError] = useState<string | null>(null);
  const [policyBackend, setPolicyBackend] = useState<string>("local");
  const [policyBucket, setPolicyBucket] = useState<string | null>(null);
  const [busyKey, setBusyKey] = useState<string | null>(null);

  const refreshPolicies = useCallback(async () => {
    setPoliciesLoading(true);
    setPoliciesError(null);
    try {
      const [actRes, trashRes] = await Promise.all([
        fetch("/api/v1/policies/list", { headers: authHeader() }),
        fetch("/api/v1/policies/trash", { headers: authHeader() }),
      ]);
      if (!actRes.ok) throw new Error(`active list HTTP ${actRes.status}`);
      if (!trashRes.ok) throw new Error(`trash list HTTP ${trashRes.status}`);
      const act: PolicyListResponse = await actRes.json();
      const tr: PolicyListResponse = await trashRes.json();
      setMyPolicies(act.policies);
      setTrashed(tr.policies);
      setPolicyBackend(act.backend);
      setPolicyBucket(act.bucket);
    } catch (e) {
      setPoliciesError(e instanceof Error ? e.message : String(e));
    } finally {
      setPoliciesLoading(false);
    }
  }, []);

  useEffect(() => { void refreshPolicies(); }, [refreshPolicies]);

  const handleDelete = useCallback(async (key: string) => {
    setBusyKey(key);
    try {
      const res = await fetch(`/api/v1/policies/${encodeURIComponent(key)}`, {
        method: "DELETE",
        headers: authHeader(),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      await refreshPolicies();
    } catch (e) {
      setPoliciesError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusyKey(null);
    }
  }, [refreshPolicies]);

  const handleRestore = useCallback(async (key: string) => {
    setBusyKey(key);
    try {
      const res = await fetch(`/api/v1/policies/trash/${encodeURIComponent(key)}/restore`, {
        method: "POST",
        headers: authHeader(),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      await refreshPolicies();
    } catch (e) {
      setPoliciesError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusyKey(null);
    }
  }, [refreshPolicies]);

  const handlePurge = useCallback(async (key: string) => {
    if (!confirm(`Permanently delete ${key}? This cannot be undone.`)) return;
    setBusyKey(key);
    try {
      const res = await fetch(`/api/v1/policies/trash/${encodeURIComponent(key)}/purge`, {
        method: "DELETE",
        headers: authHeader(),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      await refreshPolicies();
    } catch (e) {
      setPoliciesError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusyKey(null);
    }
  }, [refreshPolicies]);

  const handleUploadFile = useCallback((f: File) => {
    setUploadError(null);
    setUploadResult(null);
    if (!["application/pdf", "image/png", "image/jpeg"].includes(f.type)) {
      setUploadError("Supported formats: PDF, PNG, JPEG");
      return;
    }
    if (f.size > 8 * 1024 * 1024) {
      setUploadError(`File too large (${(f.size / 1024 / 1024).toFixed(1)} MB > 8 MB)`);
      return;
    }
    setUploadFile(f);
  }, []);

  const submitUpload = useCallback(async () => {
    if (!uploadFile) return;
    setUploadBusy(true);
    setUploadError(null);
    try {
      const fd = new FormData();
      fd.append("file", uploadFile);
      fd.append("policy_title", uploadFile.name.replace(/\.[^.]+$/, "").replace(/[_-]/g, " "));
      const res = await fetch("/api/v1/policies/upload", {
        method: "POST",
        body: fd,
        headers: authHeader(),
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(`HTTP ${res.status} — ${text.slice(0, 200)}`);
      }
      const json = await res.json();
      setUploadResult({
        name: uploadFile.name,
        policy_key: json.policy_key ?? "",
        s3_uri: json.s3_uri ?? null,
        ingestion_job_id: json.ingestion_job_id ?? null,
        status: json.status ?? "unknown",
        kb_id: json.kb_id ?? null,
        backend: json.backend ?? "local",
        message: json.message ?? "",
        demo_mode: json.demo_mode ?? false,
      });
      setUploadFile(null);
      void refreshPolicies();
    } catch (e) {
      setUploadError(String(e));
    } finally {
      setUploadBusy(false);
    }
  }, [uploadFile, refreshPolicies]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return POLICIES.filter((p) => {
      if (payerFilter !== "all" && p.payer_id !== payerFilter) return false;
      if (q) {
        const blob = `${p.policy_id} ${p.title} ${p.treatment_keywords.join(" ")}`.toLowerCase();
        if (!blob.includes(q)) return false;
      }
      return true;
    });
  }, [search, payerFilter]);

  const recentlyUpdated = POLICIES.filter((p) => p.status === "updated_recently");

  return (
    <div className="px-6 py-6">
      <header className="mb-5 flex items-end justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-semibold text-ink-primary leading-tight flex items-center gap-2">
            <BookOpen size={22} className="text-accent-brand" />
            Policy Library
          </h1>
          <p className="text-sm text-ink-muted mt-1">
            <span className="text-mono-tech text-ink-body">{POLICIES.length}</span> policies indexed
            <span className="mx-2 text-ink-faint">·</span>
            <span className="text-mono-tech text-ink-body">4</span> payers
            <span className="mx-2 text-ink-faint">·</span>
            <span className="text-accent-cyan font-medium">RAG-ready</span>
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="text-[10px] text-mono-tech text-ink-muted hidden lg:block">
            BACKED BY · pgvector + Bedrock KB-ready
          </div>
          <button
            type="button"
            onClick={() => {
              setUploadOpen((o) => !o);
              setUploadResult(null);
              setUploadError(null);
              setUploadFile(null);
            }}
            className={clsx(
              "inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium border transition-all",
              uploadOpen
                ? "bg-accent-brand text-white border-accent-brand"
                : "bg-surface-raised text-ink-body border-surface-border hover:border-accent-brand/50 hover:text-accent-brand",
            )}
          >
            <Plus size={13} />
            Upload policy
          </button>
        </div>
      </header>

      {/* Policy upload panel */}
      {uploadOpen && (
        <div className="mb-5 bg-surface-raised border border-accent-brand/30 rounded-2xl p-4">
          <div className="flex items-center justify-between mb-3">
            <div>
              <div className="text-sm font-semibold text-ink-primary flex items-center gap-2">
                <Upload size={14} className="text-accent-brand" />
                Upload Policy Document
              </div>
              <div className="text-xs text-ink-muted mt-0.5">
                PDF · PNG · JPEG — parsed by Claude Vision and indexed to Bedrock Knowledge Base
              </div>
            </div>
            <button
              type="button"
              onClick={() => setUploadOpen(false)}
              className="p-1 rounded text-ink-faint hover:text-ink-body"
            >
              <X size={14} />
            </button>
          </div>

          {/* Success state */}
          {uploadResult && (
            <div className={`border rounded-xl p-4 flex items-start gap-3 ${uploadResult.demo_mode ? "border-accent-amber/40 bg-accent-amber/5" : "border-accent-green/40 bg-accent-green/5"}`}>
              <CheckCircle2 size={16} className={`shrink-0 mt-0.5 ${uploadResult.demo_mode ? "text-accent-amber" : "text-accent-green"}`} />
              <div className="flex-1 min-w-0">
                <div className="text-sm font-semibold text-ink-primary">
                  {uploadResult.demo_mode
                    ? "Demo mode — set POLICIES_S3_BUCKET to enable real upload"
                    : uploadResult.ingestion_job_id
                      ? "Policy uploaded · Bedrock KB sync initiated"
                      : "Policy uploaded to S3"}
                </div>
                <div className="text-xs text-ink-muted mt-1.5 text-mono-tech space-y-1">
                  <div>file: <span className="text-ink-body">{uploadResult.name}</span></div>
                  {uploadResult.s3_uri && (
                    <div className="truncate">s3: <span className="text-accent-cyan">{uploadResult.s3_uri}</span></div>
                  )}
                  {uploadResult.ingestion_job_id && (
                    <div>job_id: <span className="text-accent-green">{uploadResult.ingestion_job_id}</span></div>
                  )}
                  {uploadResult.kb_id && (
                    <div>kb_id: <span className="text-ink-body">{uploadResult.kb_id}</span></div>
                  )}
                  <div className={`font-medium ${uploadResult.demo_mode ? "text-accent-amber" : "text-accent-green"}`}>
                    status: {uploadResult.status}
                  </div>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setUploadResult(null)}
                className="text-xs font-medium text-accent-brand hover:underline shrink-0"
              >
                Upload another
              </button>
            </div>
          )}

          {/* Upload dropzone */}
          {!uploadResult && (
            <div className="space-y-3">
              <div
                onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                onDragLeave={() => setDragOver(false)}
                onDrop={(e) => {
                  e.preventDefault();
                  setDragOver(false);
                  const f = e.dataTransfer.files?.[0];
                  if (f) handleUploadFile(f);
                }}
                onClick={() => uploadInputRef.current?.click()}
                className={clsx(
                  "border-2 border-dashed rounded-xl px-6 py-8 text-center cursor-pointer transition-colors",
                  dragOver
                    ? "border-accent-brand bg-accent-brand/5"
                    : "border-surface-border hover:border-accent-brand/40 hover:bg-surface-raised-hi",
                )}
              >
                <Upload size={24} className="mx-auto text-ink-faint mb-2" />
                {uploadFile ? (
                  <div className="text-sm font-medium text-ink-primary">{uploadFile.name}</div>
                ) : (
                  <>
                    <div className="text-sm font-medium text-ink-body">
                      Drop a policy PDF here, or click to browse
                    </div>
                    <div className="text-xs text-ink-faint mt-1">
                      Payer policy · clinical criteria · denial letter — up to 8 MB
                    </div>
                  </>
                )}
                <input
                  ref={uploadInputRef}
                  type="file"
                  accept="application/pdf,image/png,image/jpeg"
                  hidden
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) handleUploadFile(f);
                  }}
                />
              </div>

              {uploadError && (
                <div className="flex items-center gap-2 text-xs text-accent-red border border-accent-red/30 bg-accent-red/5 rounded-lg px-3 py-2">
                  <AlertTriangle size={13} className="shrink-0" />
                  {uploadError}
                </div>
              )}

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={submitUpload}
                  disabled={!uploadFile || uploadBusy}
                  className="flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-medium bg-accent-brand text-white hover:bg-accent-brand/90 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
                >
                  {uploadBusy ? (
                    <><Loader2 size={13} className="animate-spin" /> Indexing…</>
                  ) : (
                    <><Upload size={13} /> Index to Knowledge Base</>
                  )}
                </button>
                {uploadFile && !uploadBusy && (
                  <button
                    type="button"
                    onClick={() => { setUploadFile(null); setUploadError(null); }}
                    className="text-xs text-ink-muted hover:text-ink-body"
                  >
                    Clear
                  </button>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Recently updated callout */}
      {recentlyUpdated.length > 0 && (
        <div className="bg-accent-amber/5 border border-accent-amber/30 rounded-xl px-4 py-3 mb-5 flex items-start gap-3">
          <Sparkles size={16} className="text-accent-amber shrink-0 mt-0.5" />
          <div className="flex-1">
            <div className="text-sm font-medium text-ink-primary">
              {recentlyUpdated.length} polic{recentlyUpdated.length === 1 ? "y" : "ies"} updated recently
            </div>
            <div className="text-xs text-ink-muted mt-0.5">
              ClinCase automatically re-evaluates in-flight cases against new policy versions. View the diff to see what criteria changed.
            </div>
          </div>
          {recentlyUpdated[0] && (
            <Link
              to={`/policies/${recentlyUpdated[0].policy_id}/diff`}
              className="text-xs font-medium text-accent-amber hover:underline shrink-0"
            >
              View diff →
            </Link>
          )}
        </div>
      )}

      {/* Your policies — uploaded by you, real S3 / local-disk backed */}
      <div className="bg-surface-raised border border-surface-border rounded-2xl mb-5 overflow-hidden">
          <div className="px-4 py-3 border-b border-surface-border flex items-center justify-between gap-3 flex-wrap">
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-semibold text-ink-primary">Your policies</h3>
              <span className="text-[10px] text-compact text-ink-muted">
                {policyBackend === "s3" ? `S3 · ${policyBucket}` : "local disk"}
              </span>
              {policiesLoading && <Loader2 size={11} className="text-ink-muted animate-spin" />}
            </div>
            <div className="inline-flex items-center rounded-lg border border-surface-border bg-surface-bg p-0.5 text-[11px] text-mono-tech">
              <button
                type="button"
                onClick={() => setView("active")}
                className={clsx(
                  "px-2.5 py-1 rounded-md transition-colors",
                  view === "active"
                    ? "bg-accent-brand text-white"
                    : "text-ink-muted hover:text-ink-body",
                )}
              >
                Active ({myPolicies.length})
              </button>
              <button
                type="button"
                onClick={() => setView("trash")}
                className={clsx(
                  "px-2.5 py-1 rounded-md transition-colors flex items-center gap-1",
                  view === "trash"
                    ? "bg-accent-brand text-white"
                    : "text-ink-muted hover:text-ink-body",
                )}
              >
                <Trash2 size={10} />
                Trash ({trashed.length})
              </button>
            </div>
          </div>

          {policiesError && (
            <div className="px-4 py-2 bg-accent-red/10 border-b border-accent-red/30 text-xs text-accent-red flex items-center gap-2">
              <AlertTriangle size={12} />
              {policiesError}
            </div>
          )}

          <div className="divide-y divide-surface-border">
            {(view === "active" ? myPolicies : trashed).map((p) => (
              <div
                key={p.policy_key}
                className="px-4 py-3 flex items-center gap-3 hover:bg-surface-raised-hi/30 transition-colors"
              >
                <FileText size={14} className="text-ink-faint shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-ink-primary truncate">{p.title}</div>
                  <div className="text-[11px] text-mono-tech text-ink-muted flex items-center gap-2 flex-wrap mt-0.5">
                    <span className="truncate max-w-[180px]" title={p.policy_key}>{p.policy_key}</span>
                    <span className="text-ink-faint">·</span>
                    <span>{(p.size_bytes / 1024).toFixed(1)} KB</span>
                    {p.payer_id && p.payer_id !== "unknown" && (
                      <>
                        <span className="text-ink-faint">·</span>
                        <span className="uppercase">{p.payer_id}</span>
                      </>
                    )}
                    {p.policy_id && (
                      <>
                        <span className="text-ink-faint">·</span>
                        <span className="text-accent-cyan">{p.policy_id}</span>
                      </>
                    )}
                    {view === "active" && p.uploaded_at && (
                      <>
                        <span className="text-ink-faint">·</span>
                        <span>uploaded {timeAgo(p.uploaded_at)}</span>
                      </>
                    )}
                    {view === "trash" && p.trashed_at && (
                      <>
                        <span className="text-ink-faint">·</span>
                        <span className="text-accent-amber">trashed {timeAgo(p.trashed_at)}</span>
                      </>
                    )}
                    {p.s3_uri && (
                      <>
                        <span className="text-ink-faint">·</span>
                        <span className="text-accent-cyan truncate max-w-[200px]" title={p.s3_uri}>{p.s3_uri}</span>
                      </>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-1 shrink-0">
                  {view === "active" ? (
                    <button
                      type="button"
                      disabled={busyKey === p.policy_key}
                      onClick={() => void handleDelete(p.policy_key)}
                      className="text-[11px] font-medium px-2 py-1 rounded-md border border-surface-border text-ink-muted hover:text-accent-red hover:border-accent-red/40 transition-colors flex items-center gap-1 disabled:opacity-50"
                      title="Move to trash (re-syncs Bedrock KB)"
                    >
                      {busyKey === p.policy_key ? <Loader2 size={11} className="animate-spin" /> : <Trash2 size={11} />}
                      Delete
                    </button>
                  ) : (
                    <>
                      <button
                        type="button"
                        disabled={busyKey === p.policy_key}
                        onClick={() => void handleRestore(p.policy_key)}
                        className="text-[11px] font-medium px-2 py-1 rounded-md border border-surface-border text-ink-muted hover:text-accent-green hover:border-accent-green/40 transition-colors flex items-center gap-1 disabled:opacity-50"
                        title="Restore to active policies"
                      >
                        {busyKey === p.policy_key ? <Loader2 size={11} className="animate-spin" /> : <RotateCcw size={11} />}
                        Restore
                      </button>
                      <button
                        type="button"
                        disabled={busyKey === p.policy_key}
                        onClick={() => void handlePurge(p.policy_key)}
                        className="text-[11px] font-medium px-2 py-1 rounded-md border border-accent-red/30 text-accent-red hover:bg-accent-red/10 transition-colors flex items-center gap-1 disabled:opacity-50"
                        title="Permanently delete — cannot be undone"
                      >
                        <X size={11} />
                        Purge
                      </button>
                    </>
                  )}
                </div>
              </div>
            ))}
            {(view === "active" ? myPolicies : trashed).length === 0 && !policiesLoading && (
              <div className="px-4 py-8 text-center text-sm text-ink-muted">
                {view === "active"
                  ? "No uploaded policies yet. Click \"Upload policy\" above to add one."
                  : "Trash is empty."}
              </div>
            )}
          </div>
        </div>

      {/* Filter bar */}
      <div className="bg-surface-raised border border-surface-border rounded-2xl p-3 mb-4 flex items-center gap-3">
        <div className="flex-1 flex items-center gap-2 px-3 py-1.5 rounded-lg border border-surface-border bg-surface-bg">
          <Search size={14} className="text-ink-faint" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by treatment, policy ID, or title..."
            className="flex-1 bg-transparent outline-none text-sm text-ink-primary placeholder:text-ink-faint"
          />
        </div>
        <div className="relative">
          <select
            value={payerFilter}
            onChange={(e) => setPayerFilter(e.target.value)}
            className="appearance-none pl-3 pr-8 py-1.5 rounded-lg border border-surface-border bg-surface-bg text-sm text-ink-body cursor-pointer hover:bg-surface-raised-hi"
          >
            <option value="all">All payers</option>
            <option value="aetna">Aetna</option>
            <option value="uhc">UnitedHealthcare</option>
            <option value="bcbs">BlueCross BlueShield</option>
            <option value="anthem">Anthem</option>
          </select>
          <ChevronDown
            size={14}
            className="absolute right-2.5 top-1/2 -translate-y-1/2 text-ink-faint pointer-events-none"
          />
        </div>
      </div>

      {/* Card grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {filtered.map((p) => {
          const isUpdated = p.status === "updated_recently";
          return (
            <Link
              key={`${p.payer_id}-${p.policy_id}`}
              to={`/policies/${p.policy_id}/diff`}
              className="group bg-surface-raised border border-surface-border rounded-2xl p-5 hover:border-accent-brand/50 hover:shadow-md transition-all flex flex-col gap-3 relative"
            >
              {isUpdated && (
                <span className="absolute top-3 right-3 text-[9px] text-compact px-1.5 py-0.5 rounded bg-accent-amber/15 text-accent-amber animate-pulse-soft">
                  updated
                </span>
              )}

              <div className="flex items-start gap-3">
                <span
                  className={clsx(
                    "w-10 h-10 rounded-lg font-bold text-mono-tech text-base flex items-center justify-center shrink-0",
                    PAYER_TINT[p.payer_id],
                  )}
                >
                  {p.initial}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="text-[10px] text-compact text-ink-muted">
                    {p.payer_id.toUpperCase()} · POLICY {p.policy_id}
                  </div>
                  <h3 className="text-sm font-semibold text-ink-primary mt-0.5 line-clamp-2 leading-tight">
                    {p.title}
                  </h3>
                </div>
              </div>

              <div className="flex flex-wrap gap-1">
                {p.treatment_keywords.slice(0, 3).map((kw) => (
                  <span
                    key={kw}
                    className="text-[10px] text-mono-tech px-1.5 py-0.5 rounded bg-surface-panel text-ink-body"
                  >
                    {kw}
                  </span>
                ))}
              </div>

              <div className="flex items-center justify-between text-[11px] text-ink-muted text-mono-tech mt-auto pt-2 border-t border-surface-border">
                <span className="flex items-center gap-1">
                  <FileText size={11} />
                  {p.section_count} {p.section_count === 1 ? "section" : "sections"} · {p.word_count.toLocaleString()} words
                </span>
                <span>{p.version}</span>
              </div>
              <div className="flex items-center justify-between text-[11px] text-ink-muted">
                <span>updated {timeAgo(p.last_updated_iso)}</span>
                <span className="flex items-center gap-1 text-accent-brand opacity-0 group-hover:opacity-100 transition-opacity">
                  View policy <ArrowRight size={11} />
                </span>
              </div>
            </Link>
          );
        })}

        {filtered.length === 0 && (
          <div className="col-span-full p-10 text-center text-ink-muted text-sm">
            No policies match your filters.
          </div>
        )}
      </div>
    </div>
  );
}
