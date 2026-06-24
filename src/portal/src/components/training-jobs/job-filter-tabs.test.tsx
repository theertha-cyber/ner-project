import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { JobFilterTabs } from "./job-filter-tabs";

describe("JobFilterTabs", () => {
  it("renders all filter tabs", () => {
    render(<JobFilterTabs selected="all" onChange={vi.fn()} />);
    expect(screen.getByText("All")).toBeDefined();
    expect(screen.getByText("Running")).toBeDefined();
    expect(screen.getByText("Completed")).toBeDefined();
    expect(screen.getByText("Failed")).toBeDefined();
  });

  it("calls onChange when a tab is clicked", () => {
    const onChange = vi.fn();
    render(<JobFilterTabs selected="all" onChange={onChange} />);
    fireEvent.click(screen.getByText("Running"));
    expect(onChange).toHaveBeenCalledWith("running");
  });

  it("highlights the selected tab", () => {
    render(<JobFilterTabs selected="running" onChange={vi.fn()} />);
    const tab = screen.getByText("Running");
    expect(tab.className).toContain("bg-brand-primary");
  });
});
