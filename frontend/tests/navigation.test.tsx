/**
 * Unification must not delete anything: every pre-existing route stays registered and every
 * pre-existing nav destination stays reachable, alongside the new journey and runtime entries.
 */
import { cleanup, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Sidenav } from "../src/components/Sidenav";
import mainSource from "../src/main.tsx?raw";

vi.mock("../src/components/AuthContext", () => ({
  useAuth: () => ({
    user: { id: "u", email: "a@b.c", full_name: "Ann Lee", role: "admin", organization_id: "o", organization_name: "Org" },
    logout: vi.fn(),
  }),
}));
vi.mock("../src/lib/api", async (orig) => ({
  ...(await orig<typeof import("../src/lib/api")>()),
  api: { listCases: vi.fn().mockRejectedValue(new Error("offline")) },
}));
vi.mock("../src/lib/liveFeed", async (orig) => ({
  ...(await orig<typeof import("../src/lib/liveFeed")>()),
  fetchSnapshot: vi.fn().mockRejectedValue(new Error("offline")),
}));

const LEGACY_ROUTES = [
  "/", "/platform", "/login", "/signup", "/dashboard", "/cases", "/cases/bulk-import", "/cases/:caseId",
  "/cases/:caseId/compare", "/intake", "/sandbox", "/twin", "/twin/overview", "/twin/lab", "/twin/ops",
  "/twin/demo", "/twin/demo/classic", "/twin/demo/:tab", "/twin/:patientId/classic", "/twin/:patientId/:tab?",
  "/cardiotwin", "/cardiotwin/evaluation", "/policies", "/onco", "/policies/:policyId/diff", "/agents",
  "/cohorts", "/reviewer", "/compliance", "/roi", "/industrialize", "/architecture", "/eval", "/settings",
  "/aquahealth", "/onehealth", "/interop", "/aquahealth/observations", "/aquahealth/observations/new",
  "/aquahealth/observations/:observationId", "/aquahealth/map", "/aquahealth/trends", "/aquahealth/one-health",
  "/aquahealth/community", "/aquahealth/evaluation", "/aquahealth/review",
];
const NEW_ROUTES = ["/journey", "/journey/:jobId", "/journey/:jobId/:stageId", "/runtime"];
const LEGACY_NAV = [
  "/interop", "/onehealth", "/aquahealth", "/aquahealth/observations/new", "/aquahealth/observations",
  "/aquahealth/map", "/aquahealth/trends", "/aquahealth/one-health", "/aquahealth/evaluation",
  "/aquahealth/review", "/aquahealth/community", "/dashboard", "/cases", "/intake", "/cases/bulk-import",
  "/sandbox", "/twin", "/twin/demo", "/twin/lab", "/twin/ops", "/cardiotwin", "/cardiotwin/evaluation",
  "/policies", "/agents", "/onco", "/cohorts", "/reviewer", "/eval", "/roi", "/compliance",
  "/industrialize", "/architecture", "/settings",
];

afterEach(cleanup);

describe("one platform, nothing removed", () => {
  it("keeps every pre-existing route registered and adds the journey and runtime routes", () => {
    for (const path of [...LEGACY_ROUTES, ...NEW_ROUTES]) {
      expect(mainSource, path).toContain(`path="${path}"`);
    }
  });

  it("leads navigation with the evidence journey and keeps every capability reachable", () => {
    render(
      <MemoryRouter>
        <Sidenav />
      </MemoryRouter>,
    );
    const nav = screen.getByRole("navigation", { name: "Sections" });
    const hrefs = within(nav)
      .getAllByRole("link")
      .map((link) => link.getAttribute("href"));
    expect(hrefs.slice(0, 2)).toEqual(["/journey", "/runtime"]);
    for (const href of LEGACY_NAV) expect(hrefs, href).toContain(href);
    expect(new Set(hrefs).size).toBe(hrefs.length);
  });
});
