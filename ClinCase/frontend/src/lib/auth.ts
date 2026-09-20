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

export async function login(
  email: string,
  password: string,
): Promise<{ token: string; user: AuthUser }> {
  const res = await fetch(`${BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const { detail } = await res.json().catch(() => ({ detail: "Login failed" }));
    throw new Error(detail || "Login failed");
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
  const res = await fetch(`${BASE}/auth/me`, {
    headers: { Authorization: `Bearer ${t}` },
  });
  if (!res.ok) {
    clearAuth();
    return null;
  }
  const user = await res.json();
  setStoredUser(user);
  return user;
}

export function logout(): void {
  clearAuth();
  // Hard reload to /login so all React state is cleared
  window.location.href = "/login";
}
