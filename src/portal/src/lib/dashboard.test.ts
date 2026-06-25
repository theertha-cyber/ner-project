import { describe, it, expect } from "vitest";
import { heroVariant } from "./dashboard";

describe("heroVariant", () => {
  it("returns 'b' for system_admin", () => {
    expect(heroVariant("system_admin")).toBe("b");
  });

  it("returns 'a' for annotator", () => {
    expect(heroVariant("annotator")).toBe("a");
  });

  it("returns 'a' for tenant_admin", () => {
    expect(heroVariant("tenant_admin")).toBe("a");
  });

  it("returns 'a' for business_user", () => {
    expect(heroVariant("business_user")).toBe("a");
  });

  it("returns 'a' for any unknown role", () => {
    expect(heroVariant("unknown_role")).toBe("a");
  });
});
