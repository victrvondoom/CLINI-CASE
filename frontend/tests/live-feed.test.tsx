import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ActivityTicker } from "../src/components/ActivityTicker";
import { EMPTY_SNAPSHOT, buildNavChips, buildTickerItems, fetchSnapshot, resetSnapshotCache, type FeedSnapshot } from "../src/lib/liveFeed";

const snap = (over: Partial<FeedSnapshot> = {}): FeedSnapshot => ({ ...EMPTY_SNAPSHOT, ...over });
beforeEach(() => resetSnapshotCache());
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe("ticker wording comes from data", () => {
  it("emits nothing when nothing is known — no filler claims", () => {
    expect(buildTickerItems(EMPTY_SNAPSHOT)).toEqual([]);
  });

  it("reports real counts and flags problems", () => {
    const items = buildTickerItems(snap({
      health: { status: "ok", db: "not_checked" }, cases: { total: 12, awaiting: 3 }, agents: { invocations: 40, errors: 2, hours: 24 },
      onco: { open_alerts: 5, patients: 8, ledger_valid: false }, cardio: { integrity: true, version: "1.0.0", cad_auc: 0.9127 }, policies: { n: 22, with_change: 2 } }));
    const text = items.map((i) => i.text);
    expect(text).toContain("API healthy · database not checked");
    expect(text).toContain("12 cases in your organisation · 3 awaiting human review");
    expect(text).toContain("40 agent runs in the last 24 h · 2 errors");
    expect(text.find((t) => t.startsWith("OncoTwin"))).toMatch(/8 twin patients · 5 open alerts · audit ledger FAILED verification/);
    expect(text.find((t) => t.startsWith("CardioTwin"))).toMatch(/v1\.0\.0 integrity verified · held-out CAD AUC 0\.91/);
    expect(items.find((i) => i.text.startsWith("OncoTwin"))?.tone).toBe("red");
    expect(items.find((i) => i.text.includes("awaiting"))?.tone).toBe("amber");
  });

  it("singular / plural and quiet agents", () => {
    const t = buildTickerItems(snap({ cases: { total: 1, awaiting: 0 }, agents: { invocations: 0, errors: 0, hours: 24 } })).map((i) => i.text);
    expect(t).toEqual(["1 case in your organisation · 0 awaiting human review"]); // zero agent runs → no agent line
  });

  it("marks an unhealthy API in red", () => {
    expect(buildTickerItems(snap({ health: { status: "degraded", db: "down" } }))[0].tone).toBe("red");
  });
});

describe("sidebar chips are metrics or nothing", () => {
  it("formats live values and hides unknown ones", () => {
    expect(buildNavChips(snap({ evalF1: 0.9034, roiAnnualUsd: 1_260_000_000, archLayers: 5 }))).toEqual({ "/eval": "F1 .90", "/roi": "$1.26B", "/architecture": "5-LAYER" });
    expect(buildNavChips(EMPTY_SNAPSHOT)).toEqual({ "/eval": null, "/roi": null, "/architecture": null });
    expect(buildNavChips(snap({ roiAnnualUsd: 0, evalF1: 0 }))["/roi"]).toBeNull(); // zero savings is not a "$0" badge
    expect(buildNavChips(snap({ roiAnnualUsd: 42_500 }))["/roi"]).toBe("$42.5K");
  });
});

function stubBackend(handlers: Record<string, unknown>) {
  const fn = vi.fn(async (url: string) => {
    const key = Object.keys(handlers).find((k) => url.includes(k));
    if (!key || handlers[key] === null) return new Response("nope", { status: 503 });
    return new Response(JSON.stringify(handlers[key]), { status: 200 });
  });
  vi.stubGlobal("fetch", fn);
  return fn;
}

describe("snapshot fetching", () => {
  it("fails soft per source and de-duplicates concurrent callers", async () => {
    const f = stubBackend({
      "/healthz": { status: "ok", db: "connected" }, "status=awaiting_review": { total: 2 }, "/cases?limit=1": { total: 9 },
      "/oncotwin/overview": null, "/cardiotwin/overview": null, "/agents/metrics": null, "/policy-catalog": { n: 22, n_with_recent_change: 2 },
      "/eval/cohort": { macro_f1: 0.91 }, "/business-value/org": { direct_savings_annual_projection_usd: 5000, db_unavailable: true }, "/architecture/layers": { layers: [1, 2, 3] } });
    const [a, b] = await Promise.all([fetchSnapshot(), fetchSnapshot()]);
    expect(a).toBe(b);
    expect(f.mock.calls.length).toBe(10); // one round for both callers
    expect(a.cases).toEqual({ total: 9, awaiting: 2 });
    expect(a.onco).toBeNull();
    expect(a.policies).toEqual({ n: 22, with_change: 2 });
    expect(a.roiAnnualUsd).toBeNull(); // db_unavailable is never shown as a number
    expect(a.archLayers).toBe(3);
  });
});

describe("ActivityTicker", () => {
  it("renders live items from the backend", async () => {
    stubBackend({ "/healthz": { status: "ok", db: "connected" }, "status=awaiting_review": { total: 1 }, "/cases?limit=1": { total: 4 } });
    render(<ActivityTicker />);
    await waitFor(() => expect(screen.getAllByTestId("ticker-item").length).toBeGreaterThan(0));
    expect(screen.getAllByText("4 cases in your organisation · 1 awaiting human review").length).toBeGreaterThan(0);
    expect(screen.queryByText(/Deterministic demo fixtures/)).toBeNull(); // the old static marketing lines are gone
  });

  it("says so when live status is unavailable instead of showing filler", async () => {
    stubBackend({});
    render(<ActivityTicker />);
    expect((await screen.findByTestId("ticker")).textContent).toMatch(/No live status reported|Live status unavailable/);
  });
});
