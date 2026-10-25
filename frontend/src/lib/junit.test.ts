import { describe, expect, it } from "vitest";

import { JunitParseError, SAMPLE_JUNIT, messageSignature, parseJunit, summarise } from "./junit";

describe("parseJunit", () => {
  it("reads cases, statuses and durations from a <testsuites> report", () => {
    const report = parseJunit(SAMPLE_JUNIT);

    expect(report.totals).toMatchObject({ total: 6, passed: 2, failed: 2, broken: 1, skipped: 1 });
    expect(report.totals.durationMs).toBe(3810);
    const cancel = report.cases.find((c) => c.name === "test_cancel_order");
    expect(cancel).toMatchObject({
      classname: "tests.api.test_orders",
      suite: "api",
      status: "failed",
      durationMs: 910
    });
    expect(cancel?.message).toMatch(/^ConnectionRefusedError/);
  });

  it("groups failures that differ only in numbers and addresses", () => {
    const { groups } = parseJunit(SAMPLE_JUNIT);

    expect(groups).toHaveLength(1);
    expect(groups[0].names).toEqual(["test_cancel_order", "test_get_user"]);
  });

  it("accepts a bare <testsuite> and takes the message from the element text", () => {
    const report = parseJunit(
      `<testsuite name="s"><testcase name="t" time="1,234.5"><failure>boom\nstack</failure></testcase></testsuite>`
    );

    expect(report.cases[0]).toMatchObject({ status: "failed", message: "boom", durationMs: 1234500 });
  });

  it("rejects XML that isn't JUnit, and text that isn't XML", () => {
    expect(() => parseJunit("<html><body/></html>")).toThrow(JunitParseError);
    expect(() => parseJunit("not xml at all <")).toThrow("This file isn't valid XML.");
  });
});

describe("summarise", () => {
  it("merges cases from several files", () => {
    const a = parseJunit(SAMPLE_JUNIT).cases;
    expect(summarise([...a, ...a]).totals.total).toBe(12);
  });
});

it("messageSignature blanks numbers, hex ids and quoted values", () => {
  expect(messageSignature("Timeout 30000ms at 0xDEAD for 'x'")).toBe("timeout …ms at … for …");
});
