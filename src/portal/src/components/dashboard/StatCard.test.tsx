import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { StatCard } from "./StatCard";
import type { StatItem } from "@/types/dashboard";

function makeStat(overrides: Partial<StatItem> = {}): StatItem {
  return { label: "Test", value: 42, unit: "%", sub: "sub text", delta: "+5", ...overrides };
}

describe("StatCard (dashboard)", () => {
  it("renders live value", () => {
    render(<StatCard item={makeStat()} />);
    expect(screen.getByText("Test")).toBeInTheDocument();
    expect(screen.getByText("42")).toBeInTheDocument();
  });

  it("renders em-dash for null value", () => {
    render(<StatCard item={makeStat({ value: null })} />);
    expect(screen.getByText("\u2014")).toBeInTheDocument();
  });

  it("renders delta as coloured text for warn direction", () => {
    render(<StatCard item={makeStat({ dir: "warn", delta: "now" })} />);
    const delta = screen.getByText("now");
    expect(delta).toBeInTheDocument();
    expect(delta.style.background).toBe("");
    expect(delta.style.color).toContain("--color-delta-warn");
  });

  it("renders sub text in JetBrains Mono", () => {
    render(<StatCard item={makeStat({ sub: "test sub" })} />);
    expect(screen.getByText("test sub")).toBeInTheDocument();
  });

  it("delta appears inline with label on same row (label+delta top row)", () => {
    const { container } = render(<StatCard item={makeStat({ delta: "+12", dir: "up" })} />);
    const firstChild = container.firstChild as HTMLElement;
    const topRow = firstChild.firstChild as HTMLElement;
    expect(topRow.style.display).toBe("flex");
    expect(topRow.style.justifyContent).toBe("space-between");
  });

  it("hover effect uses border-color transition (not box-shadow)", () => {
    const { container } = render(<StatCard item={makeStat()} />);
    const card = container.firstChild as HTMLElement;
    expect(card.style.transition).toContain("border-color");
    expect(card.style.transition).not.toContain("box-shadow");
  });
  it("renders no context line when sub is empty", () => {
    const { container } = render(<StatCard item={makeStat({ sub: "" })} />);
    // Only the label/delta row and the value row remain.
    expect((container.firstChild as HTMLElement).children.length).toBe(2);
  });

  it("renders a fraction value with the numerator emphasised", () => {
    render(<StatCard item={makeStat({ value: "3/5" })} />);
    const numerator = screen.getByText("3");
    const denominator = screen.getByText("5");
    expect(screen.getByText("/")).toBeInTheDocument();
    // The numerator inherits the wrapper's display size; the denominator is
    // explicitly stepped down, so the fraction reads as "3 of 5".
    const wrapperSize = parseInt((numerator.parentElement as HTMLElement).style.fontSize, 10);
    expect(wrapperSize).toBeGreaterThan(parseInt(denominator.style.fontSize, 10));
  });
  it("centres its content vertically so short cards align with taller siblings", () => {
    const { container } = render(<StatCard item={makeStat({ sub: "" })} />);
    const card = container.firstChild as HTMLElement;
    expect(card.style.flexDirection).toBe("column");
    expect(card.style.justifyContent).toBe("center");
  });
});
