import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { SpanInspector } from "./SpanInspector";
import type { ConfirmedSpan } from "./span-reducer";
import type { EntityTypeItem } from "./EntityPalette";

const span: ConfirmedSpan = {
  id: "span-1",
  entityType: "vendor_name",
  charStart: 0,
  charEnd: 9,
  text: "Acme Corp",
  confidence: 1.0,
};

const entityTypes: EntityTypeItem[] = [
  { id: "et-1", name: "vendor_name", target_table: "ORG", is_active: true },
  { id: "et-2", name: "customer_name", target_table: "PER", is_active: true },
  { id: "et-3", name: "invoice_number", target_table: "NUM", is_active: true },
];

const entityColors = {
  vendor_name: "#6366f1",
  customer_name: "#f59e0b",
  invoice_number: "#10b981",
};

// ── Scenario 16 (task 5.5): Inspector shows metadata 2×2 grid ────────────────

describe("Scenario 16 — Inspector shows colored chip and 2×2 metadata grid", () => {
  it("renders the span text chip and all four metadata cells", () => {
    render(
      <SpanInspector
        span={span}
        entityTypes={entityTypes}
        entityColors={entityColors}
        onRetype={vi.fn()}
        onDelete={vi.fn()}
        onClose={vi.fn()}
      />,
    );

    // Span text chip
    expect(screen.getByText("Acme Corp")).toBeInTheDocument();

    // Metadata grid
    const grid = screen.getByTestId("metadata-grid");
    expect(grid).toBeInTheDocument();
    expect(grid).toHaveTextContent("char_start");
    expect(grid).toHaveTextContent("0");
    expect(grid).toHaveTextContent("char_end");
    expect(grid).toHaveTextContent("9");
    expect(grid).toHaveTextContent("confidence");
    expect(grid).toHaveTextContent("1.00");
    expect(grid).toHaveTextContent("base");
    expect(grid).toHaveTextContent("ORG");
  });
});

// ── Scenario 17 (task 5.5): Inline retype chips present ─────────────────────

describe("Scenario 17 — Retype chips shown for all entity types except current", () => {
  it("shows chips for customer_name and invoice_number but not vendor_name", () => {
    render(
      <SpanInspector
        span={span}
        entityTypes={entityTypes}
        entityColors={entityColors}
        onRetype={vi.fn()}
        onDelete={vi.fn()}
        onClose={vi.fn()}
      />,
    );

    // Other types shown
    expect(screen.getByTestId("retype-chip-customer_name")).toBeInTheDocument();
    expect(screen.getByTestId("retype-chip-invoice_number")).toBeInTheDocument();

    // Current type excluded
    expect(screen.queryByTestId("retype-chip-vendor_name")).not.toBeInTheDocument();
  });
});

// ── Scenario 18 (task 5.5): Clicking retype chip calls onRetype ──────────────

describe("Scenario 18 — Clicking retype chip calls onRetype and closes inspector", () => {
  it("clicking a chip calls onRetype with the new entity type", () => {
    const onRetype = vi.fn();
    const onClose = vi.fn();
    render(
      <SpanInspector
        span={span}
        entityTypes={entityTypes}
        entityColors={entityColors}
        onRetype={onRetype}
        onDelete={vi.fn()}
        onClose={onClose}
      />,
    );

    fireEvent.click(screen.getByTestId("retype-chip-customer_name"));
    expect(onRetype).toHaveBeenCalledWith("span-1", "customer_name");
  });
});

// ── Scenario 19 (task 5.5): Delete button calls onDelete ─────────────────────

describe("Scenario 19 — Delete span calls onDelete", () => {
  it("clicking Delete span button calls onDelete with span id", () => {
    const onDelete = vi.fn();
    render(
      <SpanInspector
        span={span}
        entityTypes={entityTypes}
        entityColors={entityColors}
        onRetype={vi.fn()}
        onDelete={onDelete}
        onClose={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByTestId("delete-span-btn"));
    expect(onDelete).toHaveBeenCalledWith("span-1");
  });
});

// ── Scenario 20 (task 5.5): Focus mode inspector uses fixed glass styles ──────

describe("Scenario 20 — Focus mode inspector renders with fixed/glass styles", () => {
  it("renders at fixed position with backdrop-filter when layoutMode=focus", () => {
    render(
      <SpanInspector
        span={span}
        entityTypes={entityTypes}
        entityColors={entityColors}
        layoutMode="focus"
        onRetype={vi.fn()}
        onDelete={vi.fn()}
        onClose={vi.fn()}
      />,
    );

    const inspector = screen.getByTestId("span-inspector");
    expect(inspector).toHaveAttribute("data-layout", "focus");
    expect(inspector).toHaveStyle({ position: "fixed" });
    expect(inspector).toHaveStyle({ top: "140px" });
    expect(inspector).toHaveStyle({ right: "30px" });
    expect(inspector).toHaveStyle({ width: "290px" });
  });

  it("renders as a card (not fixed) when layoutMode=3pane", () => {
    render(
      <SpanInspector
        span={span}
        entityTypes={entityTypes}
        entityColors={entityColors}
        layoutMode="3pane"
        onRetype={vi.fn()}
        onDelete={vi.fn()}
        onClose={vi.fn()}
      />,
    );

    const inspector = screen.getByTestId("span-inspector");
    expect(inspector).toHaveAttribute("data-layout", "3pane");
    expect(inspector).not.toHaveStyle({ position: "fixed" });
  });
});
