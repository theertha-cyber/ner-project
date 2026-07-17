import { describe, it, expect } from "vitest";
import { heroVariant } from "./dashboard";

describe("heroVariant", () => {
  it("returns 'b' (dark gradient hero) for every role", () => {
    expect(heroVariant("system_admin")).toBe("b");
    expect(heroVariant("annotator")).toBe("b");
    expect(heroVariant("tenant_admin")).toBe("b");
    expect(heroVariant("business_user")).toBe("b");
  });

  it("returns 'b' for any unknown role", () => {
    expect(heroVariant("unknown_role")).toBe("b");
  });
});
