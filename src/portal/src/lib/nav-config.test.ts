import { describe, it, expect } from "vitest";
import { navFor, flattenNav, crumbsFor, SCREEN_TITLES, resolveScreenTitle } from "./nav-config";

describe("SCREEN_TITLES", () => {
  it("known screen lookup", () => {
    expect(SCREEN_TITLES["tenants"]).toEqual(["Tenants", "/admin/tenants"]);
    for (const key of ["annotate-manual", "annotate-automated", "annotate-import"]) {
      expect(SCREEN_TITLES[key]).toBeDefined();
    }
  });

  it("unknown screen falls back to Dashboard", () => {
    expect(resolveScreenTitle("/nope/not/a/route")).toEqual(["Dashboard", "/dashboard"]);
  });
});

describe("navFor", () => {
  it("system_admin stays a flat 4-item list", () => {
    const items = navFor("system_admin");
    expect(items).toHaveLength(4);
    expect(items.every((i) => i.kind === "link")).toBe(true);
    expect(flattenNav(items).map((l) => l.id)).toContain("audit");
  });

  it("tenant_admin is grouped into Annotate / Setup / Admin sections", () => {
    const items = navFor("tenant_admin");
    const sections = items.filter((i) => i.kind === "section").map((s) => (s as { label: string }).label);
    expect(sections).toEqual(["Annotate", "Setup", "Admin"]);
  });

  it("tenant_admin Annotate section has the three methods", () => {
    const items = navFor("tenant_admin");
    const annotate = items.find((i) => i.kind === "section" && i.label === "Annotate");
    expect(annotate && annotate.kind === "section" && annotate.items.map((l) => l.href)).toEqual([
      "/annotate/manual",
      "/annotate/automated",
      "/annotate/import",
    ]);
  });

  it("annotator sees Manual and Import but not Automated", () => {
    const leaves = flattenNav(navFor("annotator")).map((l) => l.href);
    expect(leaves).toContain("/annotate/manual");
    expect(leaves).toContain("/annotate/import");
    expect(leaves).not.toContain("/annotate/automated");
  });

  it("only tenant_admin reaches the automated (retrain) workflow", () => {
    expect(flattenNav(navFor("tenant_admin"))).toEqual(
      expect.arrayContaining([expect.objectContaining({ href: "/annotate/automated/retrain" })]),
    );
    for (const role of ["system_admin", "annotator", "business_user"] as const) {
      expect(flattenNav(navFor(role)).map((l) => l.href)).not.toContain("/annotate/automated/retrain");
    }
  });

  it("business_user keeps its flat 4-item list", () => {
    const items = navFor("business_user");
    expect(items).toHaveLength(4);
    expect(flattenNav(items).map((l) => l.href)).not.toContain("/annotate/manual");
  });
});

describe("crumbsFor", () => {
  it("derives section › landing › screen for a nested route", () => {
    const trail = crumbsFor(navFor("tenant_admin"), "/annotation");
    expect(trail.map((c) => c.label)).toEqual(["Annotate", "Manual", "Workspace"]);
  });

  it("derives section › landing for a landing route", () => {
    const trail = crumbsFor(navFor("tenant_admin"), "/annotate/import");
    expect(trail.map((c) => c.label)).toEqual(["Annotate", "Import"]);
  });

  it("maps the automated step routes under Automated", () => {
    const trail = crumbsFor(navFor("tenant_admin"), "/annotate/automated/schema");
    expect(trail.map((c) => c.label)).toEqual(["Annotate", "Automated", "1 · Suggest Entity Types"]);
  });

  it("falls back to the flat title map for unknown routes", () => {
    const trail = crumbsFor(navFor("tenant_admin"), "/settings");
    expect(trail.map((c) => c.label)).toEqual(["Settings"]);
  });
});
