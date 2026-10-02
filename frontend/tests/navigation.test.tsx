/**
 * Unification must not delete anything: every pre-existing route stays registered and every
 * pre-existing nav destination stays reachable, alongside the new journey and runtime entries.
 */
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { Link, MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Sidenav } from "../src/components/Sidenav";
import { RouteBoundary } from "../src/components/RouteBoundary";
import { areas } from "../src/workflow/areas";
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

afterEach(() => { cleanup(); localStorage.clear(); sessionStorage.clear(); });

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
    expect(hrefs.slice(0, 3)).toEqual(["/dashboard", "/cases", "/journey"]);
    const contextual = areas.flatMap(a => a.links.map(([,href]) => href));
    for (const href of LEGACY_NAV) expect([...hrefs, ...contextual], href).toContain(href);
    expect(hrefs.length).toBeLessThanOrEqual(13);
    expect(new Set(hrefs).size).toBe(hrefs.length);
  });
});

it("keeps sidebar DOM, scroll and expanded state across navigation and remembers collapse", () => {
  render(<MemoryRouter><RouteBoundary><Sidenav /><Link to="/architecture">Open architecture</Link></RouteBoundary></MemoryRouter>);
  const nav = screen.getByRole("navigation", { name: "Sections" });
  nav.scrollTop = 125;
  fireEvent.scroll(nav);
  fireEvent.click(screen.getByRole("button", { name: "Workflow" }));
  fireEvent.click(screen.getByRole("link", { name: "Open architecture" }));
  expect(screen.getByRole("navigation", { name: "Sections" })).toBe(nav);
  expect(nav.scrollTop).toBe(125);
  expect(screen.getByRole("button", { name: "Workflow" }).getAttribute("aria-expanded")).toBe("false");
  fireEvent.click(screen.getByRole("button", { name: "Collapse navigation" }));
  expect(localStorage.getItem("clini-nav-collapsed")).toBe("true");
  expect(screen.getByRole("link", { name: "Architecture" }).getAttribute("title")).toBe("Architecture");
});
