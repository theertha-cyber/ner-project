import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { ArmedBanner } from "./ArmedBanner";

// ── Scenarios 18, 19, 33: Banner shows instructional text ────────────────────

describe("Scenarios 18/19/33 — ArmedBanner renders instructional text", () => {
  it("renders instructional text with entity type name", () => {
    render(<ArmedBanner entityType="vendor_name" onDisarm={vi.fn()} />);

    expect(screen.getByTestId("armed-banner")).toBeInTheDocument();

    // Instructional text format
    expect(
      screen.getByText(/Labeling mode · click words to tag as/),
    ).toBeInTheDocument();
    expect(screen.getByText("vendor_name")).toBeInTheDocument();

    // Description string must NOT appear as banner text
    expect(screen.queryByText(/—/)).not.toBeInTheDocument();
  });

  it("renders pulsing dot", () => {
    render(<ArmedBanner entityType="vendor_name" onDisarm={vi.fn()} />);
    const dot = screen.getByTestId("armed-banner").querySelector(".armed-dot");
    expect(dot).not.toBeNull();
    expect((dot as HTMLElement).style.animation).toContain("pulse");
  });

  it("shows 'esc · done' button", () => {
    render(<ArmedBanner entityType="vendor_name" onDisarm={vi.fn()} />);
    expect(screen.getByText("esc · done")).toBeInTheDocument();
  });

  it("does not render description text even when description prop is passed", () => {
    render(
      <ArmedBanner
        entityType="vendor_name"
        description="Supplier or vendor company name"
        onDisarm={vi.fn()}
      />,
    );
    expect(screen.queryByText(/Supplier or vendor company name/)).not.toBeInTheDocument();
    expect(
      screen.getByText(/Labeling mode · click words to tag as/),
    ).toBeInTheDocument();
  });
});

// ── Disarm controls ───────────────────────────────────────────────────────────

describe("ArmedBanner — disarm controls", () => {
  it("clicking 'esc · done' calls onDisarm", () => {
    const onDisarm = vi.fn();
    render(<ArmedBanner entityType="vendor_name" onDisarm={onDisarm} />);
    fireEvent.click(screen.getByText("esc · done"));
    expect(onDisarm).toHaveBeenCalledOnce();
  });
});
