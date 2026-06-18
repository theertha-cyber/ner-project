import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SegmentControl } from "./segment-control";

const options = [
  { label: "A", value: "a" },
  { label: "B", value: "b" },
];

describe("SegmentControl", () => {
  it("selected option has active class and unselected does not", () => {
    render(<SegmentControl options={options} value="a" onChange={vi.fn()} />);
    const aBtn = screen.getByRole("radio", { name: "A" });
    const bBtn = screen.getByRole("radio", { name: "B" });
    expect(aBtn).toHaveClass("bg-brand-primary");
    expect(bBtn).not.toHaveClass("bg-brand-primary");
  });

  it("clicking an option calls onChange with its value", async () => {
    const onChange = vi.fn();
    render(<SegmentControl options={options} value="a" onChange={onChange} />);
    await userEvent.click(screen.getByRole("radio", { name: "B" }));
    expect(onChange).toHaveBeenCalledWith("b");
  });

  it("right arrow moves focus to next button", async () => {
    render(<SegmentControl options={options} value="a" onChange={vi.fn()} />);
    const aBtn = screen.getByRole("radio", { name: "A" });
    aBtn.focus();
    await userEvent.keyboard("{ArrowRight}");
    expect(screen.getByRole("radio", { name: "B" })).toHaveFocus();
  });
});
