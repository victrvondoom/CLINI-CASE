import { cleanup, render, screen } from "@testing-library/react";
import { lazy } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { RouteBoundary } from "../src/components/RouteBoundary";

afterEach(cleanup);
it("shows a recoverable error instead of a blank page when a downloaded route fails", async () => {
  vi.spyOn(console, "error").mockImplementation(() => {});
  const preventExpectedJsdomError = (event: ErrorEvent) => event.preventDefault();
  window.addEventListener("error", preventExpectedJsdomError);
  const FailedPage = lazy(() => Promise.reject(new Error("chunk unavailable")));
  render(<MemoryRouter><RouteBoundary><FailedPage /></RouteBoundary></MemoryRouter>);
  expect((await screen.findByRole("alert")).textContent).toContain("could not be opened");
  expect(screen.getByRole("button", { name: "Reload page" })).toBeTruthy();
  expect(screen.getByRole("link", { name: "Go to dashboard" }).getAttribute("href")).toBe("/dashboard");
  window.removeEventListener("error", preventExpectedJsdomError);
});
