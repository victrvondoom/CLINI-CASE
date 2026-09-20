import { Download, FileEdit, Mail, Paperclip } from "lucide-react";
import { useState } from "react";

import type { AppealDraft } from "../lib/types";

interface Props {
  appeal: AppealDraft;
  caseId?: string;
}

/**
 * Trigger a server-side PDF render via POST /api/v1/appeals/render.pdf.
 * Falls back to the browser's native print → save-as-PDF if the endpoint
 * is unreachable (e.g. running the frontend without a live backend).
 */
async function downloadAppealPdf(appeal: AppealDraft, caseId?: string): Promise<void> {
  try {
    const response = await fetch("/api/v1/appeals/render.pdf", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(appeal),
    });
    if (!response.ok) throw new Error(`PDF endpoint returned ${response.status}`);
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `appeal-${appeal.patient_initials}-${caseId ?? appeal.payer_id}.pdf`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  } catch (err) {
    console.warn("Server PDF endpoint unreachable; falling back to window.print()", err);
    window.print();
  }
}

export function AppealLetterEditor({ appeal, caseId }: Props) {
  const [showStructured, setShowStructured] = useState(false);
  const [downloading, setDownloading] = useState(false);

  const handleDownload = async () => {
    setDownloading(true);
    try {
      await downloadAppealPdf(appeal, caseId);
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div className="bg-white border border-neutral-200 rounded-xl overflow-hidden">
      <div className="px-5 py-3 border-b border-neutral-200 bg-neutral-50 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Mail size={16} className="text-brand-600" />
          <h3 className="font-semibold text-neutral-900">Drafted Appeal Letter</h3>
          <span className="text-xs text-mono-tech text-neutral-500">
            {appeal.appeal_body.split(/\s+/).length} words
          </span>
        </div>
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => setShowStructured(!showStructured)}
            className="text-xs text-brand-600 hover:text-brand-700 flex items-center gap-1"
          >
            <FileEdit size={12} />
            {showStructured ? "Letter view" : "Structured arguments"}
          </button>
          <button
            type="button"
            onClick={handleDownload}
            disabled={downloading}
            title="POST /api/v1/appeals/render.pdf · ReportLab letter with letterhead, footer page numbers, and CMS-0057-F § IV.A audit anchor"
            className="text-xs px-2.5 py-1.5 rounded-md border border-brand-200 bg-brand-50 text-brand-700 hover:bg-brand-100 disabled:opacity-60 flex items-center gap-1"
          >
            <Download size={12} />
            {downloading ? "Rendering…" : "Download PDF"}
          </button>
        </div>
      </div>

      <div className="p-6 max-h-[500px] overflow-auto">
        {!showStructured && (
          <div className="prose prose-sm max-w-none">
            <pre className="whitespace-pre-wrap font-sans text-neutral-800 leading-relaxed text-sm">
              {appeal.appeal_body}
            </pre>
          </div>
        )}

        {showStructured && (
          <div className="space-y-4">
            {appeal.structured_arguments.map((arg, i) => (
              <div
                key={i}
                className="border border-neutral-200 rounded-lg p-4 bg-neutral-50/40"
              >
                <div className="text-xs text-compact text-neutral-500 mb-1">
                  Argument #{i + 1}
                </div>
                <div className="font-semibold text-neutral-900 text-sm mb-2">
                  {arg.contested_criterion}
                </div>

                <div className="grid md:grid-cols-2 gap-3 text-sm">
                  <div>
                    <div className="text-xs text-gray-600 text-mono-tech uppercase mb-1">
                      Payer position
                    </div>
                    <p className="text-neutral-700">{arg.payer_position}</p>
                  </div>
                  <div>
                    <div className="text-xs text-gray-600 text-mono-tech uppercase mb-1">
                      Our position
                    </div>
                    <p className="text-neutral-700">{arg.counter_position}</p>
                  </div>
                </div>

                {arg.cited_evidence.length > 0 && (
                  <div className="mt-3 pt-3 border-t border-neutral-200">
                    <div className="text-xs text-neutral-500 text-mono-tech uppercase mb-1">
                      Cited clinical evidence
                    </div>
                    <ul className="text-sm text-neutral-700 space-y-0.5 list-disc list-inside">
                      {arg.cited_evidence.map((e, j) => (
                        <li key={j}>{e}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {arg.cited_guideline && (
                  <div className="mt-2">
                    <span className="text-[11px] text-mono-tech px-2 py-1 rounded bg-gray-50 text-gray-800 border border-gray-200">
                      📖 {arg.cited_guideline}
                    </span>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {appeal.attachments_referenced.length > 0 && (
        <div className="px-6 py-3 border-t border-neutral-200 bg-neutral-50">
          <div className="text-xs text-neutral-500 text-mono-tech uppercase mb-1.5 flex items-center gap-1">
            <Paperclip size={11} />
            Attachments referenced
          </div>
          <div className="flex flex-wrap gap-1.5">
            {appeal.attachments_referenced.map((a, i) => (
              <span
                key={i}
                className="text-xs px-2 py-1 rounded bg-white border border-neutral-200"
              >
                {a}
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="px-6 py-3 border-t-2 border-brand-100 bg-brand-50/50">
        <div className="text-xs text-brand-700 text-mono-tech uppercase mb-1">
          Requested action
        </div>
        <div className="text-sm text-brand-900">{appeal.requested_action}</div>
      </div>
    </div>
  );
}
