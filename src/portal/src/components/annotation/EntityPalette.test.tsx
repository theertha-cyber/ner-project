import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { EntityPalette } from "./EntityPalette";
import type { EntityTypeItem } from "./EntityPalette";

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

const confirmedSpans = [
  { id: "s1", entityType: "vendor_name", charStart: 0, charEnd: 9, text: "Acme Corp", confidence: 1.0 },
  { id: "s2", entityType: "vendor_name", charStart: 10, charEnd: 20, text: "BigCo Ltd", confidence: 0.9 },
  { id: "s3", entityType: "vendor_name", charStart: 21, charEnd: 30, text: "Corp LLC", confidence: 0.8 },
];

// ── Scenario 12 (task 4.3): Palette shows base label and span count ──────────

describe("Scenario 12 — Entity palette shows base sub-label and span count", () => {
  it("renders the entity name as primary label", () => {
    render(
      <EntityPalette
        entityTypes={entityTypes}
        entityColors={entityColors}
        confirmedSpans={confirmedSpans}
        armedType={null}
        onArm={vi.fn()}
        onDisarm={vi.fn()}
      />,
    );
    expect(screen.getByText("vendor_name")).toBeInTheDocument();
  });

  it("renders 'base: ORG' as secondary sub-label for vendor_name", () => {
    render(
      <EntityPalette
        entityTypes={entityTypes}
        entityColors={entityColors}
        confirmedSpans={confirmedSpans}
        armedType={null}
        onArm={vi.fn()}
        onDisarm={vi.fn()}
      />,
    );
    expect(screen.getByTestId("entity-base-vendor_name")).toHaveTextContent("base: ORG");
  });

  it("renders right-aligned confirmed span count of 3 for vendor_name", () => {
    render(
      <EntityPalette
        entityTypes={entityTypes}
        entityColors={entityColors}
        confirmedSpans={confirmedSpans}
        armedType={null}
        onArm={vi.fn()}
        onDisarm={vi.fn()}
      />,
    );
    // vendor_name has 3 confirmed spans
    const btn = screen.getByTestId("entity-btn-vendor_name");
    expect(btn).toHaveTextContent("3");
  });
});

// ── Scenario 15 (task 4.3): Clicking armed chip disarms (toggle-off) ─────────

describe("Scenario 15 — Clicking armed chip calls onDisarm", () => {
  it("clicking the armed entity type button calls onDisarm", () => {
    const onDisarm = vi.fn();
    const onArm = vi.fn();
    render(
      <EntityPalette
        entityTypes={entityTypes}
        entityColors={entityColors}
        confirmedSpans={[]}
        armedType="vendor_name"
        onArm={onArm}
        onDisarm={onDisarm}
      />,
    );
    fireEvent.click(screen.getByTestId("entity-btn-vendor_name"));
    expect(onDisarm).toHaveBeenCalledOnce();
    expect(onArm).not.toHaveBeenCalled();
  });

  it("clicking an unarmed entity type button calls onArm", () => {
    const onDisarm = vi.fn();
    const onArm = vi.fn();
    render(
      <EntityPalette
        entityTypes={entityTypes}
        entityColors={entityColors}
        confirmedSpans={[]}
        armedType={null}
        onArm={onArm}
        onDisarm={onDisarm}
      />,
    );
    fireEvent.click(screen.getByTestId("entity-btn-vendor_name"));
    expect(onArm).toHaveBeenCalledWith("vendor_name");
    expect(onDisarm).not.toHaveBeenCalled();
  });
});
