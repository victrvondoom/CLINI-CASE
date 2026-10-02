import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import Runtime from "../src/routes/Runtime";
import { fetchRuntime, type RuntimeTopology } from "../src/runtime/api";

vi.mock("../src/runtime/api", () => ({ fetchRuntime: vi.fn() }));

function topology(kind: RuntimeTopology["platform"]["kind"]): RuntimeTopology {
  const k8s = kind === "kubernetes";
  return {
    label: k8s ? "Live cluster topology" : "Deployment topology",
    live: k8s,
    platform: {
      kind,
      provider: k8s ? "kind" : null,
      namespace: k8s ? "clinicase" : null,
      pod: k8s ? "api-7c9d" : null,
      node: k8s ? "clinicase-control-plane" : null,
      pod_ip: null,
      hostname: "host-1",
      python: "3.11.9",
      detected_from: k8s ? ["KUBERNETES_SERVICE_HOST"] : [],
    },
    services: [
      { id: "frontend", name: "Web frontend", role: "UI", image: null, endpoint: null, health_path: "/healthz", workload: null, status: "not_probed", detail: "not configured", probe_ms: null, checked_at: "2026-10-01T18:00:00+00:00" },
      { id: "api", name: "API", role: "API role", image: "clinicase-api:local", endpoint: "10.0.0.5:8000", health_path: "/api/v1/healthz", workload: k8s ? "Deployment" : null, status: "up", detail: "Answered this request", probe_ms: null, checked_at: "2026-10-01T18:00:00+00:00" },
      { id: "receiver", name: "System B receiver", role: "Receiver role", image: "clinicase-api:local", endpoint: "receiver:8091", health_path: "/healthz", workload: "Deployment", status: k8s ? "up" : "down", detail: k8s ? "GET /healthz returned 200" : "Unreachable", probe_ms: 4.2, checked_at: "2026-10-01T18:00:00+00:00" },
      { id: "database", name: "Evidence store", role: "Store role", image: null, endpoint: "postgres:5432", health_path: null, workload: "StatefulSet", engine: "postgresql", status: "up", detail: "SELECT 1 succeeded", probe_ms: 1.1, checked_at: "2026-10-01T18:00:00+00:00" },
    ],
    edges: [
      { from: "frontend", to: "api", protocol: "HTTP · /api, /fhir" },
      { from: "api", to: "receiver", protocol: "HTTP FHIR · service token" },
      { from: "api", to: "database", protocol: "PostgreSQL" },
    ],
    routes: [
      { prefix: "/api/v1/journey", routes: 2, methods: ["GET"] },
      { prefix: "/fhir", routes: 5, methods: ["GET", "POST"] },
    ],
    route_count: 7,
    generated_at: "2026-10-01T18:00:00+00:00",
    notice: "Statuses are live probes.",
  };
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("runtime topology", () => {
  it("labels a local process honestly and reports real probe results", async () => {
    vi.mocked(fetchRuntime).mockResolvedValue(topology("process"));
    render(<Runtime />);
    expect(await screen.findByRole("heading", { name: "Deployment topology" })).toBeTruthy();
    expect(screen.getByText(/Local process on host-1; not containerised/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Web frontend: Serving this page. Open details" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "System B receiver: Unreachable. Open details" })).toBeTruthy();
  });

  it("shows live Kubernetes identity only when the API runs in a cluster", async () => {
    vi.mocked(fetchRuntime).mockResolvedValue(topology("kubernetes"));
    render(<Runtime />);
    expect(await screen.findByRole("heading", { name: "Live cluster topology" })).toBeTruthy();
    expect(screen.getByText(/Namespace clinicase · pod api-7c9d · node clinicase-control-plane/)).toBeTruthy();
    const orchestration = screen.getByRole("region", { name: "Orchestration" });
    expect(within(orchestration).getAllByText("(active)")).toHaveLength(3);
  });

  it("opens service details and switches tabs with the keyboard", async () => {
    vi.mocked(fetchRuntime).mockResolvedValue(topology("kubernetes"));
    render(<Runtime />);
    fireEvent.click(await screen.findByRole("button", { name: /System B receiver: Healthy/ }));
    const dialog = screen.getByRole("dialog", { name: "System B receiver" });
    expect(within(dialog).getByText("receiver:8091")).toBeTruthy();
    expect(within(dialog).getByText("api → receiver (HTTP FHIR · service token)")).toBeTruthy();
    fireEvent.keyDown(document, { key: "Escape" });

    const services = screen.getByRole("tab", { name: "Services" });
    fireEvent.keyDown(services, { key: "ArrowRight" });
    await waitFor(() => expect(screen.getByRole("tab", { name: "Routes" }).getAttribute("aria-selected")).toBe("true"));
    expect(screen.getByText("/api/v1/journey")).toBeTruthy();
    expect(screen.getByText(/7 API routes served by this process/)).toBeTruthy();
  });

  it("keeps the last good topology visible when a refresh fails", async () => {
    vi.mocked(fetchRuntime)
      .mockResolvedValueOnce(topology("process"))
      .mockRejectedValueOnce(new Error("Runtime topology unavailable (HTTP 502)"));
    render(<Runtime />);
    fireEvent.click(await screen.findByRole("button", { name: /Re-check now/ }));
    expect((await screen.findByRole("alert")).textContent).toContain("Showing the last successful check");
    expect(screen.getByRole("heading", { name: "Deployment topology" })).toBeTruthy();
  });
});
