import { describe, it, expect } from "vitest";
import { navFor } from "./nav-config";

describe("navFor", () => {
  it("system_admin returns 4 items including no Settings", () => {
    const items = navFor("system_admin");
    expect(items).toHaveLength(4);
    expect(items.find((i) => i.id === "settings")).toBeUndefined();
  });

  it("tenant_admin returns 13 items including no Settings", () => {
    const items = navFor("tenant_admin");
    expect(items).toHaveLength(13);
    expect(items.find((i) => i.id === "settings")).toBeUndefined();
  });

  it("only tenant_admin reaches the retraining decision surface", () => {
    // Requesting a retrain is Tenant Admin work, and approving it is System Admin work. A
    // System Admin who could do both would make the approval a formality rather than a gate,
    // so the request surface is not on their sidebar.
    expect(navFor("tenant_admin").find((i) => i.id === "retraining")?.href).toBe("/retraining");
    for (const role of ["system_admin", "annotator", "business_user"] as const) {
      expect(navFor(role).map((i) => i.id)).not.toContain("retraining");
    }
  });

  it("tenant_admin can reach the seed-bootstrap screens", () => {
    const items = navFor("tenant_admin");
    expect(items.find((i) => i.id === "schema-proposals")?.href).toBe("/schema-proposals");
    expect(items.find((i) => i.id === "prelabel-batches")?.href).toBe("/prelabel-batches");
  });

  it("only tenant_admin gets the seed-bootstrap screens", () => {
    for (const role of ["system_admin", "annotator", "business_user"] as const) {
      const ids = navFor(role).map((i) => i.id);
      expect(ids).not.toContain("schema-proposals");
      expect(ids).not.toContain("prelabel-batches");
    }
  });

  it("annotator returns 4 items including no Settings", () => {
    const items = navFor("annotator");
    expect(items).toHaveLength(4);
    expect(items.find((i) => i.id === "settings")).toBeUndefined();
  });

  it("the review queue reaches the roles that work annotations", () => {
    // Both roles that produce training data get it. A business user does not: the queue is
    // annotation work that feeds retraining, not an extraction surface.
    for (const role of ["tenant_admin", "annotator"] as const) {
      expect(navFor(role).find((i) => i.id === "review-queue")?.href).toBe("/review-queue");
    }
    for (const role of ["system_admin", "business_user"] as const) {
      expect(navFor(role).map((i) => i.id)).not.toContain("review-queue");
    }
  });

  it("business_user returns 5 items including no Settings", () => {
    const items = navFor("business_user");
    expect(items).toHaveLength(5);
    expect(items.find((i) => i.id === "settings")).toBeUndefined();
  });
});
