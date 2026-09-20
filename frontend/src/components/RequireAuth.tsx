/**
 * RequireAuth — wraps protected routes. If no user, redirects to /login.
 * If `roles` is set, also enforces RBAC (sends 403-equivalent UI).
 */
import { Loader2, ShieldAlert } from "lucide-react";
import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { useAuth } from "./AuthContext";

interface Props {
  children: ReactNode;
  /** If set, only these roles can access. */
  roles?: ("coordinator" | "reviewer" | "admin")[];
}

export function RequireAuth({ children, roles }: Props) {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen text-ink-muted">
        <Loader2 size={20} className="animate-spin mr-2" />
        Verifying session...
      </div>
    );
  }

  if (!user) {
    // Send to login with `from` so we can return after auth
    return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  }

  if (roles && !roles.includes(user.role)) {
    return (
      <div className="px-6 py-12 max-w-md mx-auto text-center">
        <div className="bg-surface-raised border-2 border-accent-amber/30 rounded-2xl p-8">
          <div className="inline-flex w-12 h-12 rounded-lg bg-accent-amber/10 text-accent-amber items-center justify-center mb-3">
            <ShieldAlert size={20} />
          </div>
          <h1 className="text-xl font-semibold text-ink-primary mb-2">
            Access restricted
          </h1>
          <p className="text-sm text-ink-muted leading-relaxed">
            This page requires the <strong className="text-ink-body">
              {roles.join(" or ")}
            </strong>{" "}
            role. You're signed in as{" "}
            <span className="text-mono-tech text-ink-body">{user.role}</span>.
          </p>
          <p className="text-xs text-ink-faint mt-3 text-mono-tech">
            Ask your administrator to update your role in Settings.
          </p>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
