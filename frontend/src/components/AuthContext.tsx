/**
 * AuthContext — single source of truth for the current user across the app.
 *
 * On mount: reads JWT from localStorage, calls /auth/me to verify, sets user.
 * On login/signup: components call login()/signup() helpers; provider re-syncs.
 * Logout: clears storage and reloads to /login.
 */
import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";

import {
  type AuthUser,
  clearAuth,
  fetchMe,
  getToken,
  login as loginApi,
  signup as signupApi,
} from "../lib/auth";

interface AuthContextValue {
  user: AuthUser | null;
  loading: boolean;
  verificationError: string | null;
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
  // Cached profile data is never proof of a valid session.
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState<boolean>(() => Boolean(getToken()));
  const [verificationError, setVerificationError] = useState<string | null>(null);
  const verificationAttempt = useRef(0);

  useEffect(() => {
    const attempt = ++verificationAttempt.current;
    if (!getToken()) {
      setLoading(false);
      return;
    }
    fetchMe()
      .then((u) => {
        if (attempt !== verificationAttempt.current) return;
        setUser(u);
      })
      .catch(() => {
        if (attempt !== verificationAttempt.current) return;
        setUser(null);
        setVerificationError("We could not verify your session. Check your connection and retry.");
      })
      .finally(() => {
        if (attempt === verificationAttempt.current) setLoading(false);
      });
    return () => {
      if (attempt === verificationAttempt.current) verificationAttempt.current += 1;
    };
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const { user } = await loginApi(email, password);
    verificationAttempt.current += 1;
    setVerificationError(null);
    setUser(user);
    setLoading(false);
  }, []);

  const signup = useCallback(
    async (req: {
      email: string;
      password: string;
      full_name: string;
      organization_name: string;
    }) => {
      const { user } = await signupApi(req);
      verificationAttempt.current += 1;
      setVerificationError(null);
      setUser(user);
      setLoading(false);
    },
    [],
  );

  const logout = useCallback(() => {
    verificationAttempt.current += 1;
    clearAuth();
    setUser(null);
    setLoading(false);
    window.location.href = "/login";
  }, []);

  const refresh = useCallback(async () => {
    const attempt = ++verificationAttempt.current;
    setLoading(true);
    setVerificationError(null);
    try {
      const u = await fetchMe();
      if (attempt !== verificationAttempt.current) return;
      setUser(u);
    } catch {
      if (attempt !== verificationAttempt.current) return;
      setUser(null);
      setVerificationError("We could not verify your session. Check your connection and retry.");
    } finally {
      if (attempt === verificationAttempt.current) setLoading(false);
    }
  }, []);

  return (
    <Ctx.Provider value={{ user, loading, verificationError, login, signup, logout, refresh }}>
      {children}
    </Ctx.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const v = useContext(Ctx);
  if (!v) throw new Error("useAuth must be used inside <AuthProvider>");
  return v;
}
