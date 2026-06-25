import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { FocusPalette } from "./FocusPalette";
import type { EntityTypeItem } from "./EntityPalette";

const entityTypes: EntityTypeItem[] = [
  { id: "et-1", name: "vendor_name", target_table: "ORG", is_active: true },
  { id: "et-2", name: "customer_name", target_table: "PER", is_active: true },
];

const entityColors = {
  vendor_name: "#6366f1",
  customer_name: "#f59e0b",
};

const confirmedSpans = [
  { id: "s1", entityType: "vendor_name", charStart: 0, charEnd: 9, text: "Acme Corp", confidence: 1.0 },
];

// ── Scenario 25 (task 6.4): Bottom palette visible in focus mode ──────────────

describe("Scenario 25 — Bottom palette renders in focus mode", () => {
  it("renders a horizontal pill at fixed bottom-center position with entity chips and Pre-label", () => {
    render(
      <FocusPalette
        entityTypes={entityTypes}
        entityColors={entityColors}
        confirmedSpans={confirmedSpans}
        armedType={null}
        isPrelabeling={false}
        onArm={vi.fn()}
        onDisarm={vi.fn()}
        onPrelabel={vi.fn()}
      />,
    );

    const palette = screen.getByTestId("focus-palette");
    expect(palette).toBeInTheDocument();
    expect(palette).toHaveStyle({ position: "fixed" });
    expect(palette).toHaveStyle({ bottom: "28px" });

    // Entity chips
    expect(screen.getByTestId("focus-entity-chip-vendor_name")).toBeInTheDocument();
    expect(screen.getByTestId("focus-entity-chip-customer_name")).toBeInTheDocument();

    // LABEL AS text
    expect(screen.getByText("LABEL AS")).toBeInTheDocument();

    // Pre-label button
    expect(screen.getByTestId("focus-prelabel-btn")).toBeInTheDocument();
  });
});

// ── Scenario 26 (task 6.4): Bottom palette absent in 3-pane (AnnotationPage) ─
// NOTE: FocusPalette itself is always in DOM when rendered; it is conditionally
// mounted by AnnotationPage only in focus mode. This is tested in AnnotationPage.test.tsx.

// ── Scenario 27 (task 6.4): Arming from bottom palette shows armed banner ─────

describe("Scenario 27 — Arming from bottom palette calls onArm", () => {
  it("clicking an entity chip calls onArm with entity type name", () => {
    const onArm = vi.fn();
    render(
      <FocusPalette
        entityTypes={entityTypes}
        entityColors={entityColors}
        confirmedSpans={[]}
        armedType={null}
        isPrelabeling={false}
        onArm={onArm}
        onDisarm={vi.fn()}
        onPrelabel={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByTestId("focus-entity-chip-vendor_name"));
    expect(onArm).toHaveBeenCalledWith("vendor_name");
  });

  it("clicking an armed chip calls onDisarm (toggle-off)", () => {
    const onDisarm = vi.fn();
    const onArm = vi.fn();
    render(
      <FocusPalette
        entityTypes={entityTypes}
        entityColors={entityColors}
        confirmedSpans={[]}
        armedType="vendor_name"
        isPrelabeling={false}
        onArm={onArm}
        onDisarm={onDisarm}
        onPrelabel={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByTestId("focus-entity-chip-vendor_name"));
    expect(onDisarm).toHaveBeenCalledOnce();
    expect(onArm).not.toHaveBeenCalled();
  });
});
