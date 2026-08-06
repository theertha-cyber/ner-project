import { describe, it, expect } from "vitest";
import { goToHref } from "./use-dashboard-data";

describe("goToHref", () => {
  it("routes tenant lifecycle activity to the tenant admin console", () => {
    expect(goToHref("tenants")).toBe("/admin/tenants");
  });

  it("routes training activity to the training jobs page", () => {
    expect(goToHref("training")).toBe("/training-jobs");
  });

  it("falls back to the dashboard for an unknown go value", () => {
    expect(goToHref("unknown")).toBe("/dashboard");
  });
});
