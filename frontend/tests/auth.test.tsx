import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AuthProvider } from "../src/components/AuthContext";
import { RequireAuth } from "../src/components/RequireAuth";
import { fetchMe, setStoredUser, setToken } from "../src/lib/auth";

const user = { id: "1", email: "test@example.com", full_name: "Test", organization_id: "org", organization_name: "Test", role: "admin" as const };
afterEach(() => { cleanup(); localStorage.clear(); vi.unstubAllGlobals(); });

describe("session verification", () => {
  it("never authorizes a cached profile when the verification request fails, and allows retry", async () => {
    setToken("expired-or-unverified");
    setStoredUser(user);
    const fetch = vi.fn().mockRejectedValueOnce(new TypeError("offline")).mockResolvedValueOnce(new Response(JSON.stringify(user), { status: 200 }));
    vi.stubGlobal("fetch", fetch);
    render(<MemoryRouter><AuthProvider><RequireAuth><div>Protected records</div></RequireAuth></AuthProvider></MemoryRouter>);
    await screen.findByRole("button", { name: "Retry verification" });
    expect(screen.queryByText("Protected records")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Retry verification" }));
    await screen.findByText("Protected records");
  });

  it("preserves credentials during a service outage but revokes them on rejection", async () => {
    setToken("token");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 503 })));
    await expect(fetchMe()).rejects.toThrow("temporarily unavailable");
    expect(localStorage.getItem("clincase-jwt")).toBe("token");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 401 })));
    expect(await fetchMe()).toBeNull();
    expect(localStorage.getItem("clincase-jwt")).toBeNull();
  });

  it("does not authorize cached data when no token exists", async () => {
    setStoredUser(user);
    render(
      <MemoryRouter initialEntries={["/protected"]}>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<div>Sign in</div>} />
            <Route path="/protected" element={<RequireAuth><div>Protected records</div></RequireAuth>} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>,
    );
    await screen.findByText("Sign in");
    expect(screen.queryByText("Protected records")).toBeNull();
  });
});
