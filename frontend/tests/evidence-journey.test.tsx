import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { EvidenceJourney } from "../src/onehealth/Journey";
import { onehealth, type ExposureRecord } from "../src/onehealth/api";
import { interop } from "../src/interop/api";
import Login from "../src/routes/Login";
import Track7Overview from "../src/routes/Track7Overview";
import { useAuth } from "../src/components/AuthContext";

vi.mock("../src/onehealth/api", () => ({
  onehealth: { journey: vi.fn(), passport: vi.fn(), action: vi.fn() },
}));
vi.mock("../src/interop/api", () => ({ interop: vi.fn() }));
vi.mock("../src/components/AuthContext", () => ({ useAuth: vi.fn() }));
vi.mock("../src/lib/theme", () => ({
  useTheme: () => ({ theme: "dark", toggle: vi.fn() }),
}));

const record = {
  id: "oh-journey",
  version: 3,
  observation_id: "obs-journey",
  synthetic: true,
  waterbody_name: "SYNTHETIC Brook",
  consent_withdrawn: false,
  persistence: "postgresql",
  trust_states: ["RAW", "VERIFIED"],
  passport_integrity: { status: "CHAIN_VALID", valid: true, revision_count: 3 },
  epistemic_ceiling: {
    level: "verified_sample_context",
    allowed: "Describe this verified sample at its documented site and time.",
    missing_gates: ["Consent"],
    not_allowed: ["Infer disease or certify water safety."],
  },
} as ExposureRecord;

beforeEach(() => {
  vi.mocked(useAuth).mockReturnValue({
    login: vi.fn(),
  } as unknown as ReturnType<typeof useAuth>);
});
afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});
function page(r = record) {
  return render(
    <MemoryRouter>
      <EvidenceJourney record={r} busy={false} mutate={vi.fn()} />
    </MemoryRouter>,
  );
}

describe("One continuous evidence journey", () => {
  it("shows the backend-computed ceiling and passport state", () => {
    page();
    expect(screen.getByText(record.epistemic_ceiling!.allowed)).toBeTruthy();
    expect(
      screen.getByText("Infer disease or certify water safety."),
    ).toBeTruthy();
    expect(screen.getByRole("status").textContent).toContain("CHAIN_VALID");
  });
  it("loads real connections and measured retest change on request", async () => {
    vi.mocked(onehealth.journey).mockResolvedValue({
      record,
      consent_status: "ACTIVE",
      connections: [
        {
          capability: "OncoTwin patient context",
          href: "/twin/ot-005/evidence",
          binding: "ot-005",
        },
      ],
      retest_comparison: {
        previous_record_id: "oh-original",
        comparable: true,
        change_ug_l: -17,
        meaning: "Verification remains independent",
      },
    });
    page();
    expect(onehealth.journey).not.toHaveBeenCalled();
    fireEvent.click(
      screen.getByRole("button", { name: "Open continuous journey" }),
    );
    expect(
      (
        await screen.findByRole("link", { name: "OncoTwin patient context" })
      ).getAttribute("href"),
    ).toBe("/twin/ot-005/evidence");
    expect(screen.getByText("Measured change: -17 ug/L")).toBeTruthy();
  });
  it("blocks passport export and exchange after consent withdrawal", () => {
    page({ ...record, consent_withdrawn: true });
    expect(
      screen
        .getByRole("button", { name: "Export Evidence Passport" })
        .hasAttribute("disabled"),
    ).toBe(true);
    expect(
      screen
        .getByRole("button", { name: "Exchange this evidence update" })
        .hasAttribute("disabled"),
    ).toBe(true);
    expect(
      screen.queryByText("Close the loop with a new laboratory retest"),
    ).toBeNull();
  });
  it("exchanges the selected record version through the gateway", async () => {
    vi.mocked(interop).mockResolvedValue({ id: "ig-current" });
    page();
    fireEvent.click(
      screen.getByRole("button", { name: "Exchange this evidence update" }),
    );
    await waitFor(() =>
      expect(interop).toHaveBeenCalledWith("/from-evidence", {
        exposure_id: "oh-journey",
        expected_version: 3,
      }),
    );
  });
  it("leads with the One Health journey and preserves platform access", () => {
    render(
      <MemoryRouter>
        <Track7Overview />
      </MemoryRouter>,
    );
    expect(
      screen
        .getByRole("link", { name: "Open the One Health journey" })
        .getAttribute("href"),
    ).toBe("/onehealth");
    expect(
      screen
        .getByRole("link", {
          name: "Explore all existing platform capabilities",
        })
        .getAttribute("href"),
    ).toBe("/platform");
  });
  it("has no public default password or automatic demo credential", () => {
    render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>,
    );
    const password = screen.getByLabelText("Password") as HTMLInputElement;
    expect(password.value).toBe("");
    fireEvent.click(screen.getByRole("button", { name: /Reviewer/ }));
    expect(useAuth().login).not.toHaveBeenCalled();
  });
});
