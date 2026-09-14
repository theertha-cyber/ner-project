import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

const mockPush = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: vi.fn(() => ({ push: mockPush })),
}));

let mockRole: "tenant_admin" | "annotator" = "tenant_admin";
vi.mock("@/lib/auth", () => ({
  useAuth: vi.fn(() => ({ user: { role: mockRole } })),
}));

vi.mock("@/hooks/use-entity-types", () => ({
  useEntityTypes: vi.fn(() => ({ data: { entity_types: [] } })),
}));

let mockFiles: Array<{ pending_count: number; training_eligible: boolean }> = [];
vi.mock("@/hooks/use-import-files", () => ({
  useImportFiles: vi.fn(() => ({ data: { files: mockFiles } })),
}));

import ImportAnnotationLanding from "./page";

describe("ImportAnnotationLanding", () => {
  beforeEach(() => {
    mockPush.mockClear();
    mockRole = "tenant_admin";
    mockFiles = [];
  });

  it("tenant_admin sees the two-step workflow — import, then train — in order", () => {
    render(<ImportAnnotationLanding />);

    expect(screen.getByText("Your workflow")).toBeDefined();
    expect(screen.getByText("1. Import annotations")).toBeDefined();
    expect(screen.getByText("2. Train model")).toBeDefined();
    expect(screen.queryByText(/review imported files/i)).toBeNull();
  });

  it("step 1 routes to the import file picker", () => {
    render(<ImportAnnotationLanding />);
    fireEvent.click(screen.getByText("Import annotations →"));
    expect(mockPush).toHaveBeenCalledWith("/imported-documents?import=1");
  });

  it("step 2 routes straight to Models & Training scoped to import, with no review gate", () => {
    render(<ImportAnnotationLanding />);
    fireEvent.click(screen.getByText("Train model →"));
    expect(mockPush).toHaveBeenCalledWith("/training-jobs?source=import");
  });

  it("step 2 is available even with nothing imported yet — no eligibility gate", () => {
    mockFiles = [];
    render(<ImportAnnotationLanding />);
    expect(screen.getByText("2. Train model")).toBeDefined();
  });

  it("annotator sees only a single review card, not the two-step workflow", () => {
    mockRole = "annotator";
    render(<ImportAnnotationLanding />);

    expect(screen.getByText("Where the work is")).toBeDefined();
    expect(screen.getByText("Imported files")).toBeDefined();
    expect(screen.queryByText("1. Import annotations")).toBeNull();
    expect(screen.queryByText("2. Train model")).toBeNull();
  });
});
