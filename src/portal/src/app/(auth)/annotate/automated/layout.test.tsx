import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("next/navigation", () => ({
  useRouter: vi.fn(() => ({ push: vi.fn(), replace: vi.fn() })),
  usePathname: vi.fn(() => "/annotate/automated/schema"),
}));

vi.mock("@/lib/auth", () => ({
  useAuth: vi.fn(() => ({
    user: { role: "tenant_admin", tenantId: "t1", userId: "u1", email: "a@b.com", tenantSlug: "acme" },
  })),
}));

vi.mock("@/hooks/use-entity-types", () => ({
  useEntityTypes: vi.fn(() => ({ data: { entity_types: [] } })),
}));

vi.mock("@/hooks/use-prelabel-batch", () => ({
  usePrelabelBatches: vi.fn(() => ({ data: { batches: [] } })),
}));

import AutomatedLayout from "./layout";
import { usePathname } from "next/navigation";

describe("AutomatedLayout", () => {
  beforeEach(() => {
    vi.mocked(usePathname).mockReturnValue("/annotate/automated/schema");
  });

  it("shows exactly three numbered steps — Retraining is no longer one of them", () => {
    render(
      <AutomatedLayout>
        <div>child content</div>
      </AutomatedLayout>,
    );

    expect(screen.getByText("Suggest Entity Types")).toBeDefined();
    expect(screen.getByText("Batch Pre-labeling")).toBeDefined();
    expect(screen.getByText("Review Sample")).toBeDefined();
    expect(screen.queryByText("Retraining")).toBeNull();

    // Every visible step's "N / 4"-style counter now reads against a 3-step total.
    expect(screen.getByText("1 / 3")).toBeDefined();
    expect(screen.getByText("2 / 3")).toBeDefined();
    expect(screen.getByText("3 / 3")).toBeDefined();
    expect(screen.queryByText(/\/ 4/)).toBeNull();
  });

  it("still renders its children", () => {
    render(
      <AutomatedLayout>
        <div>child content</div>
      </AutomatedLayout>,
    );
    expect(screen.getByText("child content")).toBeDefined();
  });

  it("hides the stepper on the retraining route — it isn't step 4 of this pipeline", () => {
    vi.mocked(usePathname).mockReturnValue("/annotate/automated/retrain");

    render(
      <AutomatedLayout>
        <div>retraining page content</div>
      </AutomatedLayout>,
    );

    expect(screen.queryByText("Suggest Entity Types")).toBeNull();
    expect(screen.queryByText(/\d \/ 3/)).toBeNull();
    expect(screen.getByText("retraining page content")).toBeDefined();
  });
});
