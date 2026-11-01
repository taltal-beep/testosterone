import { describe, expect, it } from "vitest";

import type { QuarantineItem } from "../../lib/api-client";
import { globMatches, matchingEntry } from "./QuarantineControl";

const entry = (test: string, is_glob = false): QuarantineItem => ({
  cycle: "web",
  test,
  is_glob,
  reason: "",
  owner: "",
  added_by: null,
  added_at: 1
});

describe("globMatches", () => {
  it("follows fnmatch", () => {
    expect(globMatches("test_checkout*", "test_checkout[card]")).toBe(true);
    expect(globMatches("tests.api#*", "tests.api#test_x")).toBe(true);
    expect(globMatches("test_?", "test_a")).toBe(true);
    expect(globMatches("test_[ab]", "test_b")).toBe(true);
    expect(globMatches("test_[!ab]", "test_b")).toBe(false);
    expect(globMatches("Test_*", "test_x")).toBe(false);
    expect(globMatches("a.b", "axb")).toBe(false);
  });
});

describe("matchingEntry", () => {
  it("prefers an exact name, then the full name, then a glob", () => {
    const items = [entry("pay#*", true), entry("pay#test_refund")];
    expect(matchingEntry(items, "test_refund", "pay#test_refund")?.test).toBe("pay#test_refund");
    expect(matchingEntry(items, "test_other", "pay#test_other")?.test).toBe("pay#*");
    expect(matchingEntry(items, "test_other", "cart#test_other")).toBeNull();
  });
});
