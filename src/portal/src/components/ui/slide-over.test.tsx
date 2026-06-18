import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SlideOver } from "./slide-over";

function noop() {}

describe("SlideOver", () => {
  it("panel is not visible when closed", () => {
    render(
      <SlideOver open={false} onClose={noop}>
        <p>content</p>
      </SlideOver>,
    );
    const panel = screen.getByRole("dialog");
    expect(panel).toHaveClass("translate-x-full");
  });

  it("panel is visible when open", () => {
    render(
      <SlideOver open={true} onClose={noop}>
        <p>content</p>
      </SlideOver>,
    );
    const panel = screen.getByRole("dialog");
    expect(panel).toHaveClass("translate-x-0");
  });

  it("calls onClose when backdrop is clicked", async () => {
    const mockClose = vi.fn();
    render(
      <SlideOver open={true} onClose={mockClose}>
        <p>content</p>
      </SlideOver>,
    );
    const backdrop = document.querySelector('[aria-hidden="true"]') as Element;
    await userEvent.click(backdrop);
    expect(mockClose).toHaveBeenCalledOnce();
  });

  it("calls onClose when Escape key is pressed", async () => {
    const mockClose = vi.fn();
    render(
      <SlideOver open={true} onClose={mockClose}>
        <p>content</p>
      </SlideOver>,
    );
    await userEvent.keyboard("{Escape}");
    expect(mockClose).toHaveBeenCalledOnce();
  });
});
