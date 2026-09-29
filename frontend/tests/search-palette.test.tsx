import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { SearchPalette } from "../src/components/SearchPalette";
import { api } from "../src/lib/api";

vi.mock("../src/lib/api", () => ({ api: { listFixtures: vi.fn(), createFromFixture: vi.fn() } }));
afterEach(() => { cleanup(); vi.resetAllMocks(); });
const fixture = { name: "test", label: "Test demo", requested_treatment: { name: "Therapy" }, payer_id: "demo", expected_verdict: "REFER" };

describe("search palette", () => {
  it("keeps the dialog open with actionable feedback when case creation fails", async () => {
    vi.mocked(api.listFixtures).mockResolvedValue([fixture] as never);
    vi.mocked(api.createFromFixture).mockRejectedValue(new Error("private internal detail"));
    const close = vi.fn();
    render(<MemoryRouter><SearchPalette open onClose={close} /></MemoryRouter>);
    fireEvent.click(await screen.findByRole("button", { name: /Test demo/ }));
    expect((await screen.findByRole("alert")).textContent).toContain("could not be created");
    expect(screen.getByRole("dialog")).toBeTruthy();
    expect(close).not.toHaveBeenCalled();
    expect(screen.queryByText(/private internal/)).toBeNull();
  });

  it("prevents duplicate in-flight case creation", async () => {
    vi.mocked(api.listFixtures).mockResolvedValue([fixture] as never);
    vi.mocked(api.createFromFixture).mockImplementation(() => new Promise(() => {}));
    render(<MemoryRouter><SearchPalette open onClose={vi.fn()} /></MemoryRouter>);
    const button = await screen.findByRole("button", { name: /Test demo/ });
    fireEvent.click(button);
    fireEvent.click(button);
    expect(api.createFromFixture).toHaveBeenCalledTimes(1);
    expect((button as HTMLButtonElement).disabled).toBe(true);
  });

  it("traps tab focus and restores the invoking control", async () => {
    vi.mocked(api.listFixtures).mockResolvedValue([]);
    const trigger = document.createElement("button");
    document.body.appendChild(trigger); trigger.focus();
    const { rerender } = render(<MemoryRouter><SearchPalette open onClose={vi.fn()} /></MemoryRouter>);
    const input = screen.getByRole("textbox");
    await waitFor(() => expect(document.activeElement).toBe(input));
    await userEvent.tab({ shift: true });
    expect(document.activeElement).toBe(screen.getByRole("button", { name: "Compliance" }));
    await userEvent.tab();
    expect(document.activeElement).toBe(input);
    rerender(<MemoryRouter><SearchPalette open={false} onClose={vi.fn()} /></MemoryRouter>);
    expect(document.activeElement).toBe(trigger);
    trigger.remove();
  });
});
