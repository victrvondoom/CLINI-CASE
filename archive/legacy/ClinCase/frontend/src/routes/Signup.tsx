/**
 * /signup — Create a new organization + admin user.
 */
import { Activity, Loader2, UserPlus } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useAuth } from "../components/AuthContext";

export default function Signup() {
  const { signup } = useAuth();
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [orgName, setOrgName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await signup({
        email,
        password,
        full_name: fullName,
        organization_name: orgName,
      });
      navigate("/dashboard", { replace: true });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Signup failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-12 bg-surface-bg">
      <div className="w-full max-w-md">
        <Link to="/" className="flex items-center justify-center gap-3 mb-8">
          <div className="w-12 h-12 rounded-xl bg-accent-brand text-ink-invert flex items-center justify-center shadow-md">
            <Activity size={22} strokeWidth={2.5} />
          </div>
          <div>
            <div className="font-semibold text-xl text-ink-primary">ClinCase</div>
            <div className="text-[11px] text-ink-muted text-mono-tech">
              Prior Authorisation Copilot
            </div>
          </div>
        </Link>

        <div className="bg-surface-raised border border-surface-border rounded-2xl p-6 shadow-sm">
          <h1 className="text-xl font-semibold text-ink-primary mb-1">
            Create your organization
          </h1>
          <p className="text-sm text-ink-muted mb-5">
            You'll be the admin. You can invite reviewers + coordinators after.
          </p>

          <form onSubmit={handleSubmit} className="space-y-3">
            <Field label="Organization name" value={orgName} setValue={setOrgName} placeholder="Memorial Hospital · Oncology" required minLength={2} />
            <Field label="Your full name" value={fullName} setValue={setFullName} placeholder="Jane Smith, MD" required minLength={1} />
            <Field label="Email" value={email} setValue={setEmail} type="email" placeholder="you@org.com" required />
            <Field label="Password" value={password} setValue={setPassword} type="password" placeholder="At least 6 characters" required minLength={6} />

            {error && (
              <div className="text-xs text-accent-red bg-accent-red/10 border border-accent-red/30 rounded px-3 py-2">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-accent-brand text-ink-invert text-sm font-semibold hover:opacity-90 transition-opacity disabled:opacity-50"
            >
              {loading ? <Loader2 size={14} className="animate-spin" /> : <UserPlus size={14} />}
              Create account + organization
            </button>
          </form>

          <div className="mt-4 pt-4 border-t border-surface-border text-center text-xs text-ink-muted">
            Already have an account?{" "}
            <Link to="/login" className="text-accent-brand hover:underline">
              Sign in
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}

function Field({
  label, value, setValue, type = "text", placeholder, required, minLength,
}: {
  label: string;
  value: string;
  setValue: (s: string) => void;
  type?: string;
  placeholder?: string;
  required?: boolean;
  minLength?: number;
}) {
  return (
    <div>
      <label className="text-[10px] text-compact text-ink-muted block mb-1">
        {label}
      </label>
      <input
        type={type}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        required={required}
        minLength={minLength}
        className="w-full px-3 py-2 rounded-lg border border-surface-border bg-surface-bg text-sm text-ink-primary placeholder:text-ink-faint focus:border-accent-brand focus:outline-none"
        placeholder={placeholder}
      />
    </div>
  );
}
