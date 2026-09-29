/**
 * Auth helpers — JWT in localStorage, login/signup/logout.
 * The token is auto-attached to every API call via api.ts's `authHeader()`.
 */
const TOKEN_KEY = "clincase-jwt";
const USER_KEY = "clincase-user";

export interface AuthUser {
  id: string;
  email: string;
  full_name: string | null;
  organization_id: string;
  organization_name: string;
  role: "coordinator" | "reviewer" | "admin";
}

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string): void {
  try {
    localStorage.setItem(TOKEN_KEY, token);
  } catch {}
}

export function clearAuth(): void {
  try {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  } catch {}
}

export function getStoredUser(): AuthUser | null {
  try {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? (JSON.parse(raw) as AuthUser) : null;
  } catch {
    return null;
  }
}

export function setStoredUser(user: AuthUser): void {
  try {
    localStorage.setItem(USER_KEY, JSON.stringify(user));
  } catch {}
}

export function authHeader(): Record<string, string> {
  const t = getToken();
  return t ? { Authorization: `Bearer ${t}` } : {};
}

const BASE = "/api/v1";
const SESSION_VERIFICATION_TIMEOUT_MS = 15_000;

function isAuthUser(value: unknown): value is AuthUser {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Partial<AuthUser>;
  return (
    typeof candidate.id === "string" &&
    typeof candidate.email === "string" &&
    (candidate.full_name === null || typeof candidate.full_name === "string") &&
    typeof candidate.organization_id === "string" &&
    typeof candidate.organization_name === "string" &&
    (candidate.role === "coordinator" || candidate.role === "reviewer" || candidate.role === "admin")
  );
}

export async function login(
  email: string,
  password: string,
): Promise<{ token: string; user: AuthUser }> {
  let res: Response;
  try {
    res = await fetch(`${BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
  } catch {
    throw new Error("Cannot reach the ClinCase API. Check that the backend is running on port 8000.");
  }
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const detail = typeof body?.detail === "string" ? body.detail : null;
    throw new Error(
      detail ?? `Login failed: the API returned HTTP ${res.status}. Check that the backend is running on port 8000.`,
    );
  }
  const data = await res.json();
  setToken(data.access_token);
  setStoredUser(data.user);
  return { token: data.access_token, user: data.user };
}

export async function signup(req: {
  email: string;
  password: string;
  full_name: string;
  organization_name: string;
}): Promise<{ token: string; user: AuthUser }> {
  const res = await fetch(`${BASE}/auth/signup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!res.ok) {
    const { detail } = await res.json().catch(() => ({ detail: "Signup failed" }));
    throw new Error(detail || "Signup failed");
  }
  const data = await res.json();
  setToken(data.access_token);
  setStoredUser(data.user);
  return { token: data.access_token, user: data.user };
}

export async function fetchMe(): Promise<AuthUser | null> {
  const t = getToken();
  if (!t) return null;
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), SESSION_VERIFICATION_TIMEOUT_MS);
  let res: Response;
  try {
    res = await fetch(`${BASE}/auth/me`, {
      headers: { Authorization: `Bearer ${t}` },
      signal: controller.signal,
    });
  } finally {
    window.clearTimeout(timeout);
  }
  if (res.status === 401 || res.status === 403) {
    clearAuth();
    return null;
  }
  if (!res.ok) throw new Error("Session verification is temporarily unavailable. Please retry.");
  const user: unknown = await res.json();
  if (!isAuthUser(user)) {
    throw new Error("Session verification returned an invalid response. Please retry.");
  }
  setStoredUser(user);
  return user;
}

export function logout(): void {
  clearAuth();
  // Hard reload to /login so all React state is cleared
  window.location.href = "/login";
}

export interface ActivityEvent {
  id: string;
  kind: "case_opened" | "reviewer_action" | "login" | string;
  at: string | null;
  summary: string;
}

export async function fetchMyActivity(limit = 25): Promise<{ events: ActivityEvent[]; db_unavailable?: boolean }> {
  const res = await fetch(`${BASE}/auth/me/activity?limit=${limit}`, {
    headers: authHeader(),
  });
  if (!res.ok) throw new Error(`Failed to load activity (HTTP ${res.status})`);
  return res.json();
}
