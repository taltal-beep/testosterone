import { describe, expect, it } from "vitest";

import {
  countLabel,
  formatPercent,
  formatProvenance,
  formatRelativeTime,
  formatRunLabel,
  shortRunId
} from "./format";

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

describe("formatPercent", () => {
  it("shows whole numbers, but never rounds a failure up to 100% or a pass down to 0%", () => {
    expect(formatPercent(20)).toBe("20%");
    expect(formatPercent(66.666)).toBe("67%");
    expect(formatPercent(99.96)).toBe("99.9%");
    expect(formatPercent(0.2)).toBe("0.2%");
    expect(formatPercent(100)).toBe("100%");
    expect(formatPercent(null)).toBe("n/a");
  });
});

describe("formatRelativeTime", () => {
  const now = 1_760_000_000_000;

  it("rounds to the unit a reader would say", () => {
    expect(formatRelativeTime(now / 1000 - 10, now)).toBe("just now");
    expect(formatRelativeTime(now / 1000 - 3 * 60, now)).toBe("3 min ago");
    expect(formatRelativeTime(now / 1000 - 5 * 3600, now)).toBe("5 h ago");
    expect(formatRelativeTime(now / 1000 - 86_400, now)).toBe("1 day ago");
    expect(formatRelativeTime(now / 1000 - 3 * 86_400, now)).toBe("3 days ago");
  });

  it("falls back to the date after a month", () => {
    expect(formatRelativeTime(now / 1000 - 40 * 86_400, now)).toMatch(/\d{2}:\d{2}$/);
  });
});

describe("formatProvenance", () => {
  it("joins branch and a short commit, or shows whichever is known", () => {
    expect(formatProvenance({ branch: "main", commit: "9c23517abcdef0123" })).toBe("main @ 9c23517");
    expect(formatProvenance({ branch: "feature/x", commit: null })).toBe("feature/x");
    expect(formatProvenance({ branch: null, commit: "9c23517abcdef0123" })).toBe("9c23517");
    expect(formatProvenance({ branch: " ", commit: null })).toBeNull();
  });
});
