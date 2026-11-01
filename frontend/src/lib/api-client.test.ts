import { describe, expect, it } from "vitest";

import { ApiError, shouldRetry } from "./api-client";

describe("shouldRetry", () => {
  it("does not retry a 4xx: a missing run stays missing", () => {
    expect(shouldRetry(0, new ApiError("Run not found", 404))).toBe(false);
  });

  it("retries network errors and 5xx twice", () => {
    expect(shouldRetry(0, new TypeError("Failed to fetch"))).toBe(true);
    expect(shouldRetry(1, new ApiError("boom", 503))).toBe(true);
    expect(shouldRetry(2, new ApiError("boom", 503))).toBe(false);
  });
});
