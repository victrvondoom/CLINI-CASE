/**
 * AuthContext — single source of truth for the current user across the app.
 *
 * On mount: reads JWT from localStorage, calls /auth/me to verify, sets user.
 * On login/signup: components call login()/signup() helpers; provider re-syncs.
 * Logout: clears storage and reloads to /login.
 */
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";

import {
  type AuthUser,
  clearAuth,
  fetchMe,
  getStoredUser,
  getToken,
  login as loginApi,
  signup as signupApi,
} from "../lib/auth";

interface AuthContextValue {
  user: AuthUser | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (req: {
    email: string;
    password: string;
    full_name: string;
    organization_name: string;
  }) => Promise<void>;
  logout: () => void;
  refresh: () => Promise<void>;
}

const Ctx = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  // Hydrate immediately from localStorage so the first render isn't blank
  const [user, setUser] = useState<AuthUser | null>(() => getStoredUser());
  const [loading, setLoading] = useState<boolean>(() => Boolean(getToken()));

  useEffect(() => {
    let cancelled = false;
    if (!getToken()) {
      setLoading(false);
      return;
    }
    fetchMe()
      .then((u) => {
        if (cancelled) return;
        setUser(u);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const { user } = await loginApi(email, password);
    setUser(user);
  }, []);

  const signup = useCallback(
    async (req: {
      email: string;
      password: string;
      full_name: string;
      organization_name: string;
    }) => {
      const { user } = await signupApi(req);
      setUser(user);
    },
    [],
  );

  const logout = useCallback(() => {
    clearAuth();
    setUser(null);
    window.location.href = "/login";
  }, []);

  const refresh = useCallback(async () => {
    const u = await fetchMe();
    setUser(u);
  }, []);

  return (
    <Ctx.Provider value={{ user, loading, login, signup, logout, refresh }}>
      {children}
    </Ctx.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const v = useContext(Ctx);
  if (!v) throw new Error("useAuth must be used inside <AuthProvider>");
  return v;
}
