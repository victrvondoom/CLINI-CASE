/**
 * /settings — Admin-only org + user management.
 * Lists users in the org, allows admin to create new users with roles.
 */
import clsx from "clsx";
import {
  CheckCircle2,
  Loader2,
  Mail,
  Settings as SettingsIcon,
  Shield,
  UserPlus,
} from "lucide-react";
import { useEffect, useState } from "react";

import { useAuth } from "../components/AuthContext";
import { api } from "../lib/api";

interface OrgUser {
  id: string;
  email: string;
  full_name: string | null;
  role: string;
  created_at: string | null;
  last_login_at: string | null;
}

const ROLE_TINT: Record<string, string> = {
  admin:       "bg-accent-violet/15 text-accent-violet",
  reviewer:    "bg-accent-amber/15  text-accent-amber",
  coordinator: "bg-accent-cyan/15   text-accent-cyan",
};

export default function Settings() {
  const { user } = useAuth();
  const [users, setUsers] = useState<OrgUser[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Create form state
  const [newEmail, setNewEmail] = useState("");
  const [newPwd, setNewPwd] = useState("");
  const [newName, setNewName] = useState("");
  const [newRole, setNewRole] = useState<"coordinator" | "reviewer" | "admin">("coordinator");

  useEffect(() => {
    void loadUsers();
  }, []);

  async function loadUsers() {
    setLoading(true);
    try {
      const d = await api.listOrgUsers();
      setUsers(d.users as OrgUser[]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load users");
    } finally {
      setLoading(false);
    }
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setCreating(true);
    setError(null);
    setSuccess(null);
    try {
      await api.createOrgUser({
        email: newEmail,
        password: newPwd,
        full_name: newName,
        role: newRole,
      });
      setSuccess(`Created ${newEmail} as ${newRole}`);
      setNewEmail("");
      setNewPwd("");
      setNewName("");
      setNewRole("coordinator");
      setShowCreate(false);
      await loadUsers();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Create failed");
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="px-6 py-6 max-w-5xl mx-auto">
      <header className="mb-6">
        <h1 className="text-2xl font-semibold text-ink-primary leading-tight flex items-center gap-2">
          <SettingsIcon size={22} className="text-accent-brand" />
          Settings
        </h1>
        <p className="text-sm text-ink-muted mt-1">
          Organization: <span className="font-medium text-ink-body">{user?.organization_name ?? "—"}</span>
          <span className="mx-2 text-ink-faint">·</span>
          Signed in as <span className="text-mono-tech text-ink-body">{user?.email}</span>
          <span className={clsx("ml-2 text-[10px] text-compact px-1.5 py-0.5 rounded", ROLE_TINT[user?.role ?? ""])}>
            {user?.role}
          </span>
        </p>
      </header>

      {/* User management section */}
      <section className="bg-surface-raised border border-surface-border rounded-2xl overflow-hidden mb-5">
        <div className="px-5 py-3 border-b border-surface-border flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Shield size={16} className="text-accent-brand" />
            <h2 className="text-sm font-semibold text-ink-primary">Users in your organization</h2>
            {users && (
              <span className="text-[11px] text-mono-tech text-ink-muted">
                {users.length} member{users.length === 1 ? "" : "s"}
              </span>
            )}
          </div>
          <button
            type="button"
            onClick={() => setShowCreate(!showCreate)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-accent-brand text-ink-invert text-xs font-medium hover:opacity-90 transition-opacity"
          >
            <UserPlus size={12} />
            {showCreate ? "Cancel" : "Invite user"}
          </button>
        </div>

        {showCreate && (
          <form onSubmit={handleCreate} className="px-5 py-4 border-b border-surface-border bg-surface-panel/40 grid grid-cols-1 md:grid-cols-4 gap-3 items-end">
            <Field label="Full name" value={newName} setValue={setNewName} required />
            <Field label="Email" value={newEmail} setValue={setNewEmail} type="email" required />
            <Field label="Temp password" value={newPwd} setValue={setNewPwd} type="password" minLength={6} required />
            <div>
              <label className="text-[10px] text-compact text-ink-muted block mb-1">Role</label>
              <div className="flex items-center gap-1.5">
                <select
                  value={newRole}
                  onChange={(e) => setNewRole(e.target.value as typeof newRole)}
                  className="flex-1 px-2 py-2 rounded-md border border-surface-border bg-surface-bg text-sm text-ink-primary"
                >
                  <option value="coordinator">Coordinator</option>
                  <option value="reviewer">Reviewer</option>
                  <option value="admin">Admin</option>
                </select>
                <button
                  type="submit"
                  disabled={creating}
                  className="flex items-center gap-1 px-3 py-2 rounded-md bg-accent-brand text-ink-invert text-sm hover:opacity-90 disabled:opacity-50"
                >
                  {creating ? <Loader2 size={12} className="animate-spin" /> : <CheckCircle2 size={12} />}
                  Create
                </button>
              </div>
            </div>
          </form>
        )}

        {error && (
          <div className="mx-5 my-3 p-2 rounded bg-accent-red/10 text-accent-red text-xs">{error}</div>
        )}
        {success && (
          <div className="mx-5 my-3 p-2 rounded bg-accent-green/10 text-accent-green text-xs">{success}</div>
        )}

        {loading && (
          <div className="p-8 text-center text-ink-muted text-sm">
            <Loader2 size={16} className="animate-spin inline-block mr-2" />
            Loading users...
          </div>
        )}

        {users && users.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-surface-panel text-[10px] text-compact text-ink-muted">
                <tr>
                  <th className="text-left px-5 py-2.5">Name</th>
                  <th className="text-left px-5 py-2.5">Email</th>
                  <th className="text-left px-5 py-2.5">Role</th>
                  <th className="text-left px-5 py-2.5">Last login</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-border">
                {users.map((u) => (
                  <tr key={u.id} className="hover:bg-surface-raised-hi">
                    <td className="px-5 py-2.5 text-ink-primary flex items-center gap-2">
                      <div className="w-7 h-7 rounded-full bg-accent-brand/15 text-accent-brand flex items-center justify-center text-mono-tech font-semibold text-[11px]">
                        {(u.full_name ?? u.email)[0].toUpperCase()}
                      </div>
                      {u.full_name || <span className="text-ink-muted italic">no name</span>}
                    </td>
                    <td className="px-5 py-2.5 text-mono-tech text-xs text-ink-body flex items-center gap-1.5">
                      <Mail size={11} className="text-ink-faint" />
                      {u.email}
                    </td>
                    <td className="px-5 py-2.5">
                      <span className={clsx("text-[10px] text-compact px-2 py-0.5 rounded", ROLE_TINT[u.role])}>
                        {u.role}
                      </span>
                    </td>
                    <td className="px-5 py-2.5 text-mono-tech text-[11px] text-ink-muted">
                      {u.last_login_at ? new Date(u.last_login_at).toLocaleString() : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Org info */}
      <section className="bg-surface-raised border border-surface-border rounded-2xl p-5">
        <h2 className="text-sm font-semibold text-ink-primary mb-3">Organization details</h2>
        <dl className="grid grid-cols-2 gap-3 text-sm">
          <div>
            <dt className="text-[10px] text-compact text-ink-muted">Org ID</dt>
            <dd className="text-mono-tech text-ink-body">{user?.organization_id}</dd>
          </div>
          <div>
            <dt className="text-[10px] text-compact text-ink-muted">Organization name</dt>
            <dd className="text-ink-primary">{user?.organization_name}</dd>
          </div>
          <div>
            <dt className="text-[10px] text-compact text-ink-muted">Plan</dt>
            <dd className="text-ink-primary">Enterprise (demo)</dd>
          </div>
          <div>
            <dt className="text-[10px] text-compact text-ink-muted">Region</dt>
            <dd className="text-mono-tech text-ink-body">ap-south-1 (Mumbai)</dd>
          </div>
        </dl>
      </section>
    </div>
  );
}

function Field({
  label, value, setValue, type = "text", required, minLength,
}: {
  label: string;
  value: string;
  setValue: (s: string) => void;
  type?: string;
  required?: boolean;
  minLength?: number;
}) {
  return (
    <div>
      <label className="text-[10px] text-compact text-ink-muted block mb-1">{label}</label>
      <input
        type={type}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        required={required}
        minLength={minLength}
        className="w-full px-2 py-2 rounded-md border border-surface-border bg-surface-bg text-sm text-ink-primary"
      />
    </div>
  );
}
