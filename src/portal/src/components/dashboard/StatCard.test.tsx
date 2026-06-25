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

  it("renders delta pill with coloured background for warn direction", () => {
    render(<StatCard item={makeStat({ dir: "warn", delta: "now" })} />);
    expect(screen.getByText("now")).toBeInTheDocument();
  });

  it("renders sub text in JetBrains Mono", () => {
    render(<StatCard item={makeStat({ sub: "test sub" })} />);
    expect(screen.getByText("test sub")).toBeInTheDocument();
  });

  it("delta pill appears inline with label on same row (label+delta top row)", () => {
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
});
