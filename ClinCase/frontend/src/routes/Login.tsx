/**
 * /login — email + password sign-in.
 *
 * Polished pre-demo: ClinCase mark (public/clincase-mark.svg), ambient glow,
 * and one-click demo accounts so judges can land in a workspace without typing.
 */
import { Loader2, LogIn, ShieldCheck, Sparkles } from "lucide-react";
import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "../components/AuthContext";

const DEMO_ACCOUNTS = [
  { email: "admin@aerofyta.health",        password: "clincase2026", role: "Admin",       desc: "Full access" },
  { email: "reviewer@aerofyta.health",     password: "clincase2026", role: "Reviewer",    desc: "REFER queue" },
  { email: "coordinator@aerofyta.health",  password: "clincase2026", role: "Coordinator", desc: "Create cases" },
];

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from ?? "/dashboard";

  const [email, setEmail] = useState("admin@aerofyta.health");
  const [password, setPassword] = useState("clincase2026");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent | null, opts?: { email: string; password: string }) {
    e?.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await login(opts?.email ?? email, opts?.password ?? password);
      navigate(from, { replace: true });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Login failed");
    } finally {
      setLoading(false);
    }
  }

  async function loginAs(account: { email: string; password: string }) {
    setEmail(account.email);
    setPassword(account.password);
    await handleSubmit(null, account);
  }

  return (
    <div className="relative min-h-screen flex items-center justify-center px-4 py-12 overflow-hidden bg-gradient-to-br from-surface-bg via-surface-bg to-accent-brand/[0.04]">
      {/* ---- Ambient backdrop blobs (turned up to obvious) ---- */}
      <div aria-hidden="true" className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute -top-40 -left-40 w-[720px] h-[720px] rounded-full bg-accent-brand/40 blur-[100px] motion-safe:animate-pulse [animation-duration:6s]" />
        <div className="absolute top-32 -right-40 w-[640px] h-[640px] rounded-full bg-accent-cyan/40 blur-[100px] motion-safe:animate-pulse [animation-duration:7s] [animation-delay:1s]" />
        <div className="absolute -bottom-40 left-1/3 w-[560px] h-[560px] rounded-full bg-accent-violet/40 blur-[100px] motion-safe:animate-pulse [animation-duration:8s] [animation-delay:2s]" />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] rounded-full bg-accent-brand/15 blur-[160px] motion-safe:animate-pulse [animation-duration:10s] [animation-delay:3s]" />
        {/* Visible dot grid */}
        <div
          className="absolute inset-0 opacity-[0.10]"
          style={{
            backgroundImage:
              "radial-gradient(circle at 1px 1px, currentColor 1px, transparent 0)",
            backgroundSize: "28px 28px",
          }}
        />
      </div>

      <div className="relative w-full max-w-md">
        {/* ---- Logo + lockup ---- */}
        <Link to="/" className="flex flex-col items-center gap-3 mb-7 group" aria-label="ClinCase home">
          <div className="relative">
            {/* Two-layer pulsing halo — unmissable */}
            <div
              className="absolute inset-0 rounded-full bg-accent-brand/70 blur-3xl scale-[1.9] motion-safe:animate-pulse [animation-duration:3s]"
              aria-hidden="true"
            />
            <div
              className="absolute inset-0 rounded-full bg-accent-cyan/50 blur-2xl scale-[1.5] group-hover:scale-[2] transition-transform duration-500"
              aria-hidden="true"
            />
            <img
              src="/clincase-mark.svg"
              alt="ClinCase"
              className="relative w-24 h-24 object-contain drop-shadow-[0_12px_40px_rgba(18,18,18,0.5)] group-hover:scale-110 transition-transform duration-300"
              width={96}
              height={96}
            />
          </div>
          <div className="text-center">
            <div className="text-display-primary text-2xl tracking-tight text-ink-primary">ClinCase</div>
            <div className="text-compact text-[11px] text-ink-muted">
              Prior Authorisation Copilot
            </div>
          </div>
        </Link>

        {/* ---- Card ---- */}
        <div className="relative bg-surface-raised/95 backdrop-blur-sm border border-surface-border rounded-2xl p-7 shadow-2xl shadow-accent-brand/5">
          <h1 className="text-display-secondary text-xl text-ink-primary mb-1">
            Sign in to your workspace
          </h1>
          <p className="text-ui-secondary text-sm text-ink-muted mb-5">
            Enter your credentials, or use a demo account below.
          </p>

          <form onSubmit={(e) => handleSubmit(e)} className="space-y-3">
            <div>
              <label className="text-compact text-[10px] text-ink-muted block mb-1">
                Email
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
                className="w-full px-3 py-2.5 rounded-lg border border-surface-border bg-surface-bg text-sm text-ink-primary placeholder:text-ink-faint focus:border-accent-brand focus:ring-2 focus:ring-accent-brand/20 focus:outline-none transition-all"
                placeholder="you@org.com"
              />
            </div>
            <div>
              <label className="text-compact text-[10px] text-ink-muted block mb-1">
                Password
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={6}
                autoComplete="current-password"
                className="w-full px-3 py-2.5 rounded-lg border border-surface-border bg-surface-bg text-sm text-ink-primary placeholder:text-ink-faint focus:border-accent-brand focus:ring-2 focus:ring-accent-brand/20 focus:outline-none transition-all"
                placeholder="••••••••"
              />
            </div>

            {error && (
              <div className="text-xs text-accent-red bg-accent-red/10 border border-accent-red/30 rounded-md px-3 py-2 flex items-center gap-2">
                <span className="text-mono-tech">●</span>
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="text-ui-primary w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-accent-brand text-ink-invert text-sm shadow-lg shadow-accent-brand/30 hover:shadow-xl hover:shadow-accent-brand/40 hover:-translate-y-px active:translate-y-0 transition-all disabled:opacity-50 disabled:translate-y-0"
            >
              {loading ? <Loader2 size={14} className="animate-spin" /> : <LogIn size={14} />}
              Sign in
            </button>
          </form>

          <div className="text-compact my-5 flex items-center gap-3 text-[10px] text-ink-faint">
            <span className="flex-1 h-px bg-surface-border" />
            Demo accounts · one-click sign-in
            <span className="flex-1 h-px bg-surface-border" />
          </div>

          <div className="space-y-1.5">
            {DEMO_ACCOUNTS.map((a) => (
              <button
                key={a.email}
                type="button"
                onClick={() => loginAs(a)}
                disabled={loading}
                className="w-full text-left px-3 py-2.5 rounded-lg border border-surface-border bg-surface-bg/60 hover:bg-surface-raised-hi hover:border-accent-brand/40 hover:shadow-sm transition-all flex items-center justify-between gap-3 disabled:opacity-50 group/account"
              >
                <div className="min-w-0 flex-1">
                  <div className="text-mono-tech text-xs text-ink-primary truncate">
                    {a.email}
                  </div>
                  <div className="text-compact text-[10px] text-ink-muted">
                    {a.role} · {a.desc}
                  </div>
                </div>
                <Sparkles size={14} className="text-accent-brand shrink-0 group-hover/account:rotate-12 transition-transform" />
              </button>
            ))}
          </div>

          <div className="text-ui-secondary mt-5 pt-4 border-t border-surface-border text-center text-xs text-ink-muted">
            Don't have an account?{" "}
            <Link to="/signup" className="text-accent-brand font-medium hover:underline">
              Create one
            </Link>
          </div>
        </div>

        {/* ---- Compliance footer ---- */}
        <div className="text-micro mt-6 flex items-center justify-center gap-1.5 text-ink-faint">
          <ShieldCheck size={11} className="text-accent-green" />
          <span>HIPAA · SOC 2 · CMS-0057-F § IV.A audited</span>
        </div>
        <div className="text-micro mt-2 text-center text-ink-faint leading-relaxed">
          7-agent LangGraph DAG · AWS Bedrock · Claude Sonnet 4.6 + Haiku 4.5 · MCP-compatible
        </div>
      </div>
    </div>
  );
}
