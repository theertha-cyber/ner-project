import { describe, it, expect } from "vitest";
import { navFor } from "./nav-config";

describe("navFor", () => {
  it("system_admin returns 5 items including no Settings", () => {
    const items = navFor("system_admin");
    expect(items).toHaveLength(5);
    expect(items.find((i) => i.id === "settings")).toBeUndefined();
  });

  it("tenant_admin returns 7 items including no Settings", () => {
    const items = navFor("tenant_admin");
    expect(items).toHaveLength(7);
    expect(items.find((i) => i.id === "settings")).toBeUndefined();
  });

  it("annotator returns 3 items including no Settings", () => {
    const items = navFor("annotator");
    expect(items).toHaveLength(3);
    expect(items.find((i) => i.id === "settings")).toBeUndefined();
  });

  it("business_user returns 4 items including no Settings", () => {
    const items = navFor("business_user");
    expect(items).toHaveLength(4);
    expect(items.find((i) => i.id === "settings")).toBeUndefined();
  });
});
