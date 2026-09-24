/**
 * About modal — opened from the Sidenav user pill.
 *
 * Shows:
 *   • ClinCase version + git SHA (live from /api/v1/version)
 *   • Deployment mode (live from /api/v1/capabilities)
 *   • Active feature flags so a reviewer can verify "is this demo mode?"
 *   • Quick links to the live introspection endpoints
 */
import { Layers, X } from "lucide-react";
import { useEffect, useState } from "react";

import { authHeader } from "../lib/auth";

interface VersionInfo {
  clincase_version: string;
  git_sha: string;
  git_branch: string;
  boot_time_iso: string;
  uptime_seconds: number;
}

interface CapabilitiesInfo {
  deployment: {
    llm_provider: string;
    aws_region: string;
    bedrock_model_id: string;
  };
  feature_flags: Record<string, boolean | string>;
  demo_mode_indicators: Record<string, boolean>;
  compliance: {
    cms_0057f_clauses_tracked: number;
  };
}

interface Props {
  open: boolean;
  onClose: () => void;
}

export function AboutModal({ open, onClose }: Props) {
  const [version, setVersion] = useState<VersionInfo | null>(null);
  const [caps, setCaps] = useState<CapabilitiesInfo | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    Promise.all([
      fetch("/api/v1/version", { headers: authHeader() }).then((r) => r.json()),
      fetch("/api/v1/capabilities", { headers: authHeader() }).then((r) => r.json()),
    ])
      .then(([v, c]) => {
        setVersion(v);
        setCaps(c);
        setError(null);
      })
      .catch((e) => setError(String(e)));
  }, [open]);

  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="about-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm"
      onClick={onClose}
      onKeyDown={(e) => e.key === "Escape" && onClose()}
      tabIndex={-1}
    >
      <div
        className="bg-surface-raised border border-surface-border rounded-2xl p-6 max-w-2xl w-full m-4 max-h-[85vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between mb-4">
          <div className="flex items-center gap-2">
            <Layers size={20} className="text-accent-brand" />
            <h2 id="about-modal-title" className="text-lg font-semibold text-ink-primary">
              About ClinCase
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close About dialog"
            className="text-ink-muted hover:text-ink-primary p-1 rounded focus:outline-none focus:ring-2 focus:ring-accent-brand"
          >
            <X size={18} />
          </button>
        </div>

        {error && (
          <div className="text-sm text-accent-red bg-accent-red/10 border border-accent-red/30 rounded p-3 mb-4">
            Could not load build/version data: {error}
          </div>
        )}

        {version && (
          <section className="mb-5">
            <div className="text-[10px] text-compact text-ink-muted mb-2">
              Build
            </div>
            <table className="w-full text-sm">
              <tbody className="divide-y divide-surface-border">
                <Row label="Version">{version.clincase_version}</Row>
                <Row label="Git SHA">
                  <code className="text-mono-tech text-[12px] text-accent-cyan">{version.git_sha}</code>
                </Row>
                <Row label="Branch">
                  <code className="text-mono-tech text-[12px]">{version.git_branch}</code>
                </Row>
                <Row label="Booted">{new Date(version.boot_time_iso).toLocaleString()}</Row>
                <Row label="Uptime">{formatUptime(version.uptime_seconds)}</Row>
              </tbody>
            </table>
          </section>
        )}

        {caps && (
          <>
            <section className="mb-5">
              <div className="text-[10px] text-compact text-ink-muted mb-2">
                Deployment
              </div>
              <table className="w-full text-sm">
                <tbody className="divide-y divide-surface-border">
                  <Row label="LLM provider">
                    <code className="text-mono-tech text-[12px]">{caps.deployment.llm_provider}</code>
                  </Row>
                  <Row label="AWS region">
                    <code className="text-mono-tech text-[12px]">{caps.deployment.aws_region}</code>
                  </Row>
                  <Row label="Primary model">
                    <code className="text-mono-tech text-[11px]">{caps.deployment.bedrock_model_id}</code>
                  </Row>
                </tbody>
              </table>
            </section>

            <section className="mb-5">
              <div className="text-[10px] text-compact text-ink-muted mb-2">
                Feature flags
              </div>
              <div className="grid grid-cols-2 gap-2">
                {Object.entries(caps.feature_flags).map(([k, v]) => (
                  <FeatureFlag key={k} name={k} value={v} />
                ))}
              </div>
            </section>

            <section>
              <div className="text-[10px] text-compact text-ink-muted mb-2">
                Compliance
              </div>
              <div className="text-sm text-ink-body">
                <strong>{caps.compliance.cms_0057f_clauses_tracked}</strong>{" "}
                CMS-0057-F + state-AI-law clauses tracked. Live scorecard at{" "}
                <code className="text-[11px] text-mono-tech text-accent-brand">/compliance</code>.
              </div>
            </section>
          </>
        )}

        <div className="mt-6 pt-4 border-t border-surface-border text-[11px] text-ink-faint">
          ClinCase — Built by vsrupeshkumar · MIT License
        </div>
      </div>
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <tr>
      <td className="py-2 pr-4 text-ink-muted text-xs">{label}</td>
      <td className="py-2 text-ink-primary">{children}</td>
    </tr>
  );
}

function FeatureFlag({ name, value }: { name: string; value: boolean | string }) {
  const isBool = typeof value === "boolean";
  const ok = isBool ? value : true;
  return (
    <div
      className={`text-[11px] border rounded px-2 py-1 ${
        ok
          ? "border-accent-green/30 bg-accent-green/5"
          : "border-surface-border bg-surface-panel/40"
      }`}
    >
      <code className="text-mono-tech text-[10px] text-ink-muted">{name}</code>
      <div className="text-ink-primary font-medium">
        {isBool ? (value ? "enabled" : "disabled") : String(value)}
      </div>
    </div>
  );
}

function formatUptime(s: number): string {
  if (s < 60) return `${s}s`;
  if (s < 3600) return `${Math.floor(s / 60)}m ${s % 60}s`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m`;
  return `${Math.floor(s / 86400)}d ${Math.floor((s % 86400) / 3600)}h`;
}
