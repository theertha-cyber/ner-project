import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { DashboardHero } from "./DashboardHero";

describe("DashboardHero", () => {
  // ── Variant A (default) ───────────────────────────────────────────────────

  it("variant A: renders kicker, title, line", () => {
    render(<DashboardHero kicker="Test kicker" title="Test title" line="Test line" variant="a" />);
    expect(screen.getByText("Test kicker")).toBeInTheDocument();
    expect(screen.getByText("Test title")).toBeInTheDocument();
    expect(screen.getByText("Test line")).toBeInTheDocument();
  });

  it("variant A: does not use dark background", () => {
    const { container } = render(<DashboardHero kicker="k" title="t" line="l" variant="a" />);
    const outer = container.firstChild as HTMLElement;
    expect(outer.style.background).not.toContain("rgb(15, 23, 42)");
    expect(outer.style.background).not.toContain("#0f172a");
  });

  it("default variant behaves as variant A (no dark background)", () => {
    const { container } = render(<DashboardHero kicker="k" title="t" line="l" />);
    const outer = container.firstChild as HTMLElement;
    expect(outer.style.background).not.toContain("rgb(15, 23, 42)");
  });

  it("variant A: title has 38px font size and weight 800", () => {
    render(<DashboardHero kicker="k" title="Title 38" line="l" variant="a" />);
    const title = screen.getByRole("heading", { name: "Title 38" });
    expect(title.style.fontSize).toBe("38px");
    expect(title.style.fontWeight).toBe("800");
  });

  // ── Variant B (system_admin dark mesh) ────────────────────────────────────

  it("variant B: renders kicker, title, line", () => {
    render(<DashboardHero kicker="SA kicker" title="SA title" line="SA line" variant="b" />);
    expect(screen.getByText("SA kicker")).toBeInTheDocument();
    expect(screen.getByText("SA title")).toBeInTheDocument();
    expect(screen.getByText("SA line")).toBeInTheDocument();
  });

  it("variant B: outer container has dark background (row 16)", () => {
    const { container } = render(<DashboardHero kicker="k" title="t" line="l" variant="b" />);
    const outer = container.firstChild as HTMLElement;
    expect(outer.style.background).toBe("rgb(15, 23, 42)");
    expect(outer.style.position).toBe("relative");
  });

  it("variant B: title text is white (row 16)", () => {
    render(<DashboardHero kicker="k" title="My Title" line="l" variant="b" />);
    const title = screen.getByRole("heading", { name: "My Title" });
    expect(title.style.color).toBe("rgb(255, 255, 255)");
  });

  it("variant B: title has 38px font size and weight 800", () => {
    render(<DashboardHero kicker="k" title="Title B" line="l" variant="b" />);
    const title = screen.getByRole("heading", { name: "Title B" });
    expect(title.style.fontSize).toBe("38px");
    expect(title.style.fontWeight).toBe("800");
  });

  it("variant B: border-radius is 24px", () => {
    const { container } = render(<DashboardHero kicker="k" title="t" line="l" variant="b" />);
    const outer = container.firstChild as HTMLElement;
    expect(outer.style.borderRadius).toBe("24px");
  });

  it("variant B: always renders full line text (no command layout)", () => {
    render(<DashboardHero kicker="k" title="t" line="Full line visible" variant="b" />);
    expect(screen.getByText("Full line visible")).toBeInTheDocument();
  });
});
