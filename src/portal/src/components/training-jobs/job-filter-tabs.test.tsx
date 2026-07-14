import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { JobFilterTabs } from "./job-filter-tabs";

describe("JobFilterTabs", () => {
  it("renders all filter tabs", () => {
    render(<JobFilterTabs selected="all" onChange={vi.fn()} />);
    expect(screen.getByText("all")).toBeDefined();
    expect(screen.getByText("running")).toBeDefined();
    expect(screen.getByText("pending approval")).toBeDefined();
    expect(screen.getByText("completed")).toBeDefined();
    expect(screen.getByText("failed")).toBeDefined();
  });

  it("calls onChange when a tab is clicked", () => {
    const onChange = vi.fn();
    render(<JobFilterTabs selected="all" onChange={onChange} />);
    fireEvent.click(screen.getByText("running"));
    expect(onChange).toHaveBeenCalledWith("running");
  });

  it("highlights the selected tab with the dark/ink background and leaves others on surface-2", () => {
    render(<JobFilterTabs selected="running" onChange={vi.fn()} />);
    const activeTab = screen.getByText("running");
    expect(activeTab.style.background).toBe("var(--ink)");
    expect(activeTab.style.color).toBe("var(--surface-2)");

    const inactiveTab = screen.getByText("completed");
    expect(inactiveTab.style.background).toBe("var(--surface-2)");
    expect(inactiveTab.style.color).toBe("var(--ink-2)");
  });

  it("re-styles a tab correctly when it becomes the selected one, with no residual state from a prior render", () => {
    const onChange = vi.fn();
    const { rerender } = render(<JobFilterTabs selected="all" onChange={onChange} />);

    fireEvent.mouseEnter(screen.getByText("pending approval"));
    rerender(<JobFilterTabs selected="pending_approval" onChange={onChange} />);

    const activeTab = screen.getByText("pending approval");
    expect(activeTab.style.background).toBe("var(--ink)");
  });

  it("wraps tabs instead of letting them overflow their container", () => {
    render(<JobFilterTabs selected="all" onChange={vi.fn()} />);
    const container = screen.getByText("all").parentElement!;
    expect(container.className).toContain("flex-wrap");
  });
});
