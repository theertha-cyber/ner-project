import { describe, it, expect } from "vitest";
import { navFor } from "./nav-config";

describe("navFor", () => {
  it("system_admin returns 4 items including no Settings", () => {
    const items = navFor("system_admin");
    expect(items).toHaveLength(4);
    expect(items.find((i) => i.id === "settings")).toBeUndefined();
  });

  it("tenant_admin returns 10 items including Data Sources", () => {
    const items = navFor("tenant_admin");
    expect(items).toHaveLength(10);
    expect(items.find((i) => i.id === "settings")).toBeUndefined();
    const entry = items.find((i) => i.id === "data-sources");
    expect(entry).toMatchObject({ label: "Data Sources", href: "/settings/data-sources" });
    expect(entry?.roles).toEqual(["tenant_admin"]);
  });

  it("annotator returns 3 items including no Settings", () => {
    const items = navFor("annotator");
    expect(items).toHaveLength(3);
    expect(items.find((i) => i.id === "settings")).toBeUndefined();
  });

  it("business_user returns 5 items including no Settings", () => {
    const items = navFor("business_user");
    expect(items).toHaveLength(5);
    expect(items.find((i) => i.id === "settings")).toBeUndefined();
  });
});
