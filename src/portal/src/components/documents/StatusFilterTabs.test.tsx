import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { StatusFilterTabs } from "./StatusFilterTabs";

describe("StatusFilterTabs", () => {
  it("renders all filter tabs", () => {
    render(<StatusFilterTabs selected="all" onChange={vi.fn()} />);
    expect(screen.getByText("All")).toBeDefined();
    expect(screen.getByText("Pending")).toBeDefined();
    expect(screen.getByText("Processing")).toBeDefined();
    expect(screen.getByText("Processed")).toBeDefined();
    expect(screen.getByText("Failed")).toBeDefined();
  });

  it("calls onChange when a tab is clicked", () => {
    const onChange = vi.fn();
    render(<StatusFilterTabs selected="all" onChange={onChange} />);
    fireEvent.click(screen.getByText("Processed"));
    expect(onChange).toHaveBeenCalledWith("processed");
  });

  it("highlights the selected tab", () => {
    render(<StatusFilterTabs selected="processed" onChange={vi.fn()} />);
    const tab = screen.getByText("Processed");
    expect(tab.className).toContain("bg-brand-primary");
  });

  it("displays counts when provided", () => {
    render(
      <StatusFilterTabs
        selected="all"
        onChange={vi.fn()}
        counts={{ all: 10, pending: 3, processing: 2, processed: 4, failed: 1 }}
      />,
    );
    expect(screen.getByText("10")).toBeDefined();
    expect(screen.getByText("3")).toBeDefined();
    expect(screen.getByText("2")).toBeDefined();
    expect(screen.getByText("4")).toBeDefined();
    expect(screen.getByText("1")).toBeDefined();
  });
});
