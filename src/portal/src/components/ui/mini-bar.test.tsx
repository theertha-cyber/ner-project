import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MiniBar } from "./mini-bar";

describe("MiniBar", () => {
  it("fill width is proportional to used/max (30%)", () => {
    render(<MiniBar used={3} max={10} />);
    expect(screen.getByTestId("mini-bar-fill").style.width).toBe("30%");
  });

  it("fill uses warning colour when ratio >= 0.9", () => {
    render(<MiniBar used={9} max={10} />);
    expect(screen.getByTestId("mini-bar-fill")).toHaveClass("bg-warning");
  });

  it("fill does NOT use warning colour below 0.9", () => {
    render(<MiniBar used={8} max={10} />);
    const fill = screen.getByTestId("mini-bar-fill");
    expect(fill).not.toHaveClass("bg-warning");
    expect(fill).toHaveClass("bg-brand-primary");
  });

  it("fill is clamped to 100% when used exceeds max", () => {
    render(<MiniBar used={15} max={10} />);
    expect(screen.getByTestId("mini-bar-fill").style.width).toBe("100%");
  });
});
