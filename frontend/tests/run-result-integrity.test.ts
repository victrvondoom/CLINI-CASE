import { beforeEach, expect, it } from "vitest";

import { normalizeRunResult } from "../src/lib/api";

beforeEach(() => localStorage.clear());

it("preserves the backend verdict when browser-local demo text exists", () => {
  localStorage.setItem(
    "clincase_demo_case_case-1",
    JSON.stringify({ text: "__verdict_hint_approve__" }),
  );

  const result = normalizeRunResult({
    case_id: "case-1",
    clinical_snapshot: null,
    policy_excerpts: [],
    necessity_assessment: null,
    decision: {
      verdict: "DENY",
      rationale: "Backend decision",
      citations: [{ kind: "policy", text: "Not met", pointer: "p.1" }],
      confidence: 0.98,
      risk_flags: ["backend_flag"],
    },
    paused_for_review: false,
    pause_reason: null,
  });

  expect(result.decision?.verdict).toBe("DENY");
  expect(result.decision?.rationale).toBe("Backend decision");
  expect(result.decision?.risk_flags).toEqual(["backend_flag"]);
});
