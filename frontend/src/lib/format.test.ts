import { describe, expect, it } from "vitest";

import { countLabel, formatRunLabel, shortRunId } from "./format";

describe("run labels", () => {
  it("names a run by cycle and start time", () => {
    const label = formatRunLabel({ run_id: "3f9c2a7e-1b4d", cycle: "fake-api", created_at: 1_760_000_000 });
    expect(label).toMatch(/^fake-api · .+\d{2}:\d{2}$/);
  });

  it("falls back to 'run' when the cycle is unknown", () => {
    expect(formatRunLabel({ run_id: "x", cycle: null, created_at: 0 })).toMatch(/^run · /);
  });

  it("shortens run ids to eight characters", () => {
    expect(shortRunId("3f9c2a7e1b4d4e0f")).toBe("3f9c2a7e");
  });
});

describe("countLabel", () => {
  it("uses the singular only for exactly one", () => {
    expect(countLabel(1, "improvement")).toBe("1 improvement");
    expect(countLabel(0, "improvement")).toBe("0 improvements");
    expect(countLabel(3, "regression")).toBe("3 regressions");
  });
});
