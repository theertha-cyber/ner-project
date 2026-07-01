import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { EntityTypeCard } from "./EntityTypeCard";
import type { EntityType } from "@/types/entity-types";

const baseEntityType: EntityType = {
  id: "et-1",
  name: "vendor_name",
  description: "Name of a vendor",
  examples: ["Northwind Logistics", "Globex Supplies"],
  base_label_mapping: { ORG: ["vendor_name"] },
  target_table: null,
  required_flag: true,
  is_active: true,
  version: 2,
};

describe("EntityTypeCard", () => {
  it("renders entity type name and version", () => {
    render(<EntityTypeCard entityType={baseEntityType} index={0} onEdit={vi.fn()} onToggle={vi.fn()} />);
    expect(screen.getByText("vendor_name")).toBeDefined();
    expect(screen.getByText("v2")).toBeDefined();
  });

  it("renders description", () => {
    render(<EntityTypeCard entityType={baseEntityType} index={0} onEdit={vi.fn()} onToggle={vi.fn()} />);
    expect(screen.getByText("Name of a vendor")).toBeDefined();
  });

  it("renders Required pill for required entity type", () => {
    render(<EntityTypeCard entityType={baseEntityType} index={0} onEdit={vi.fn()} onToggle={vi.fn()} />);
    expect(screen.getByText("Required")).toBeDefined();
  });

  it("does not render Required pill for non-required entity type", () => {
    render(
      <EntityTypeCard
        entityType={{ ...baseEntityType, required_flag: false }}
        index={0}
        onEdit={vi.fn()}
        onToggle={vi.fn()}
      />,
    );
    expect(screen.queryByText("Required")).toBeNull();
  });

  it("renders Active pill for active entity type", () => {
    render(<EntityTypeCard entityType={baseEntityType} index={0} onEdit={vi.fn()} onToggle={vi.fn()} />);
    expect(screen.getByText("Active")).toBeDefined();
  });

  it("renders Inactive pill for inactive entity type", () => {
    render(
      <EntityTypeCard
        entityType={{ ...baseEntityType, is_active: false }}
        index={0}
        onEdit={vi.fn()}
        onToggle={vi.fn()}
      />,
    );
    expect(screen.getByText("Inactive")).toBeDefined();
  });

  it("renders Deactivate button for active entity type", () => {
    render(<EntityTypeCard entityType={baseEntityType} index={0} onEdit={vi.fn()} onToggle={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Deactivate" })).toBeDefined();
  });

  it("renders Reactivate button for inactive entity type", () => {
    render(
      <EntityTypeCard
        entityType={{ ...baseEntityType, is_active: false }}
        index={0}
        onEdit={vi.fn()}
        onToggle={vi.fn()}
      />,
    );
    expect(screen.getByRole("button", { name: "Reactivate" })).toBeDefined();
  });

  it("renders BASE LABEL MAPPING section", () => {
    render(<EntityTypeCard entityType={baseEntityType} index={0} onEdit={vi.fn()} onToggle={vi.fn()} />);
    expect(screen.getByText("ORG → vendor_name")).toBeDefined();
  });

  it("renders EXAMPLES section with up to 2 examples", () => {
    render(<EntityTypeCard entityType={baseEntityType} index={0} onEdit={vi.fn()} onToggle={vi.fn()} />);
    expect(screen.getByText("Northwind Logistics, Globex Supplies")).toBeDefined();
  });

  it("calls onEdit when Edit button is clicked", () => {
    const onEdit = vi.fn();
    render(<EntityTypeCard entityType={baseEntityType} index={0} onEdit={onEdit} onToggle={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Edit" }));
    expect(onEdit).toHaveBeenCalledOnce();
  });

  it("calls onToggle when toggle button is clicked", () => {
    const onToggle = vi.fn();
    render(<EntityTypeCard entityType={baseEntityType} index={0} onEdit={vi.fn()} onToggle={onToggle} />);
    fireEvent.click(screen.getByRole("button", { name: "Deactivate" }));
    expect(onToggle).toHaveBeenCalledOnce();
  });
});
