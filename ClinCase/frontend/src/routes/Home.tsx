import { ArrowRight, Loader2, Sparkles } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { api } from "../lib/api";
import type { DemoFixture } from "../lib/types";

const VERDICT_TINT: Record<string, string> = {
  APPROVE: "text-gray-700 bg-gray-50 border-gray-200",
  DENY: "text-gray-700 bg-gray-50 border-gray-200",
  REFER: "text-gray-700 bg-gray-50 border-gray-200",
};

export default function Home() {
  const [fixtures, setFixtures] = useState<DemoFixture[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [creatingFixture, setCreatingFixture] = useState<string | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    api
      .listFixtures()
      .then(setFixtures)
      .catch((e) => setError(String(e)));
  }, []);

  async function handleStart(fixtureName: string) {
    setCreatingFixture(fixtureName);
    setError(null);
    try {
      const { case_id } = await api.createFromFixture(fixtureName);
      navigate(`/cases/${case_id}`);
    } catch (e) {
      setError(String(e));
      setCreatingFixture(null);
    }
  }

  return (
    <div className="mx-auto max-w-7xl px-6 py-10">
      <div className="grid md:grid-cols-2 gap-10 items-start">
        {/* Hero */}
        <div>
          <div className="text-xs text-compact text-brand-600 mb-3">
            Healthcare · Prior Authorisation Automation
          </div>
          <h1 className="text-4xl font-bold leading-tight mb-4 text-neutral-900">
            Approve cancer treatment in minutes, <br />
            not weeks.
          </h1>
          <p className="text-neutral-600 leading-relaxed mb-4">
            ClinCase is a provider-side, agentic prior-authorisation copilot for
            oncology. It ingests FHIR clinical data, retrieves the relevant
            payer medical policy, reasons criterion-by-criterion, and produces
            an explainable APPROVE / DENY / REFER decision with a full citation
            chain. When a payer denies, ClinCase auto-drafts an evidence-grounded
            appeal letter.
          </p>
          <div className="grid grid-cols-3 gap-2 text-sm">
            <Stat value="94%" label="of physicians say PA delays care" />
            <Stat value="80.7%" label="of appealed MA denials are overturned" />
            <Stat value="$30B+" label="annual US PA admin waste" />
          </div>

          <div className="mt-6 p-4 rounded-xl bg-brand-50 border border-brand-200">
            <div className="text-xs uppercase tracking-wider text-mono-tech text-brand-700 mb-1">
              7-agent LangGraph DAG
            </div>
            <div className="text-mono-tech text-sm text-brand-900">
              Clinical Extractor → Policy Retriever → Necessity Reasoner →
              Decision Composer → Appeals Drafter
            </div>
          </div>
        </div>

        {/* Demo fixtures */}
        <div>
          <div className="flex items-center gap-2 mb-4">
            <Sparkles size={16} className="text-brand-600" />
            <h2 className="font-semibold text-neutral-900">Live demo cases</h2>
          </div>

          {error && (
            <div className="mb-4 p-3 rounded bg-gray-50 border border-gray-200 text-gray-700 text-sm">
              {error}
            </div>
          )}

          {!fixtures && !error && (
            <div className="flex items-center gap-2 text-neutral-500 text-sm">
              <Loader2 size={14} className="animate-spin" />
              Loading fixtures...
            </div>
          )}

          <div className="space-y-3">
            {fixtures?.map((f) => (
              <button
                key={f.name}
                type="button"
                onClick={() => handleStart(f.name)}
                disabled={creatingFixture !== null}
                className="w-full text-left bg-white border border-neutral-200 rounded-xl p-5 hover:border-brand-300 hover:shadow-md transition-all group disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1.5">
                      <div className="font-semibold text-neutral-900">
                        {f.label}
                      </div>
                      <span
                        className={`text-[10px] text-compact rounded px-2 py-0.5 border ${
                          VERDICT_TINT[f.expected_verdict] ??
                          "text-neutral-700 bg-neutral-100 border-neutral-200"
                        }`}
                      >
                        Expected: {f.expected_verdict}
                      </span>
                    </div>
                    <p className="text-sm text-neutral-600 leading-relaxed">
                      {f.description}
                    </p>
                    <div className="mt-2 flex items-center gap-2 text-xs text-neutral-500 text-mono-tech">
                      <span>{f.payer_id.toUpperCase()}</span>
                      <span>·</span>
                      <span>
                        {f.requested_treatment.name} ({f.requested_treatment.j_code})
                      </span>
                      <span>·</span>
                      <span>Patient {f.patient_initials}</span>
                    </div>
                  </div>
                  <div className="flex-shrink-0 self-center">
                    {creatingFixture === f.name ? (
                      <Loader2
                        size={20}
                        className="text-brand-500 animate-spin"
                      />
                    ) : (
                      <ArrowRight
                        size={20}
                        className="text-neutral-400 group-hover:text-brand-600 transition-colors"
                      />
                    )}
                  </div>
                </div>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function Stat({ value, label }: { value: string; label: string }) {
  return (
    <div className="rounded-lg bg-neutral-50 border border-neutral-200 p-3">
      <div className="font-bold text-neutral-900 text-lg">{value}</div>
      <div className="text-xs text-neutral-500 leading-tight">{label}</div>
    </div>
  );
}
