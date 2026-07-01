import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ToastProvider } from "@/hooks/use-toast";
import { DefineEntityTypeSlideOver } from "./DefineEntityTypeSlideOver";
import type { EntityType } from "@/types/entity-types";

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({ user: { tenantSlug: "acme-corp" } }),
}));

const mockFetch = vi.fn();
globalThis.fetch = mockFetch;

function createWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return (
      <QueryClientProvider client={qc}>
        <ToastProvider>{children}</ToastProvider>
      </QueryClientProvider>
    );
  };
}

const editTarget: EntityType = {
  id: "et-1",
  name: "vendor_name",
  description: "Name of a vendor",
  examples: ["Northwind Logistics"],
  base_label_mapping: { ORG: ["vendor_name"] },
  target_table: null,
  required_flag: true,
  is_active: true,
  version: 1,
};

describe("DefineEntityTypeSlideOver", () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  it("shows 'Create entity type' title in create mode", () => {
    render(
      <DefineEntityTypeSlideOver open={true} onClose={vi.fn()} editTarget={null} />,
      { wrapper: createWrapper() },
    );
    expect(screen.getByRole("heading", { name: "Create entity type" })).toBeDefined();
  });

  it("shows 'Edit entity type' title in edit mode", () => {
    render(
      <DefineEntityTypeSlideOver open={true} onClose={vi.fn()} editTarget={editTarget} />,
      { wrapper: createWrapper() },
    );
    expect(screen.getByRole("heading", { name: "Edit entity type" })).toBeDefined();
  });

  it("shows empty fields in create mode", () => {
    render(
      <DefineEntityTypeSlideOver open={true} onClose={vi.fn()} editTarget={null} />,
      { wrapper: createWrapper() },
    );
    const nameInput = screen.getByPlaceholderText("vendor_name") as HTMLInputElement;
    expect(nameInput.value).toBe("");
    expect(nameInput.disabled).toBe(false);
  });

  it("pre-fills fields and disables NAME in edit mode", () => {
    render(
      <DefineEntityTypeSlideOver open={true} onClose={vi.fn()} editTarget={editTarget} />,
      { wrapper: createWrapper() },
    );
    const nameInput = screen.getByPlaceholderText("vendor_name") as HTMLInputElement;
    expect(nameInput.value).toBe("vendor_name");
    expect(nameInput.disabled).toBe(true);

    const descInput = screen.getByPlaceholderText("Name of a vendor / supplier") as HTMLInputElement;
    expect(descInput.value).toBe("Name of a vendor");
  });

  it("pre-fills examples joined with ', ' in edit mode", () => {
    render(
      <DefineEntityTypeSlideOver open={true} onClose={vi.fn()} editTarget={editTarget} />,
      { wrapper: createWrapper() },
    );
    const examplesInput = screen.getByPlaceholderText("Acme Supplies, Global Tech Ltd") as HTMLInputElement;
    expect(examplesInput.value).toBe("Northwind Logistics");
  });

  it("pre-selects the base label chip from editTarget in edit mode", () => {
    render(
      <DefineEntityTypeSlideOver open={true} onClose={vi.fn()} editTarget={editTarget} />,
      { wrapper: createWrapper() },
    );
    const orgChip = screen.getByRole("button", { name: "ORG" });
    expect(orgChip.getAttribute("aria-pressed")).toBe("true");
  });

  it("enforces single-select on chip row", () => {
    render(
      <DefineEntityTypeSlideOver open={true} onClose={vi.fn()} editTarget={null} />,
      { wrapper: createWrapper() },
    );
    const locChip = screen.getByRole("button", { name: "LOC" });
    fireEvent.click(locChip);
    expect(locChip.getAttribute("aria-pressed")).toBe("true");
    const perChip = screen.getByRole("button", { name: "PER" });
    expect(perChip.getAttribute("aria-pressed")).toBe("false");
  });

  it("calls POST and shows success toast on create", async () => {
    const created = { id: "et-new", name: "customer_name", version: 1 };
    mockFetch.mockResolvedValue(new Response(JSON.stringify(created), { status: 201 }));

    const onClose = vi.fn();
    render(
      <DefineEntityTypeSlideOver open={true} onClose={onClose} editTarget={null} />,
      { wrapper: createWrapper() },
    );

    fireEvent.change(screen.getByPlaceholderText("vendor_name"), {
      target: { value: "customer_name" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Create entity type" }));

    await waitFor(() => expect(onClose).toHaveBeenCalled());
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/tenants/acme-corp/entity-types"),
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("shows error toast and keeps slide-over open on API error", async () => {
    mockFetch.mockResolvedValue(
      new Response(JSON.stringify({ detail: "Duplicate name" }), { status: 422 }),
    );

    const onClose = vi.fn();
    render(
      <DefineEntityTypeSlideOver open={true} onClose={onClose} editTarget={null} />,
      { wrapper: createWrapper() },
    );

    fireEvent.change(screen.getByPlaceholderText("vendor_name"), {
      target: { value: "bad_name" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create entity type" }));

    await waitFor(() => expect(screen.getByRole("alert")).toBeDefined());
    expect(onClose).not.toHaveBeenCalled();
  });

  it("renders save button labeled 'Save changes' in edit mode", () => {
    render(
      <DefineEntityTypeSlideOver open={true} onClose={vi.fn()} editTarget={editTarget} />,
      { wrapper: createWrapper() },
    );
    expect(screen.getByRole("button", { name: "Save changes" })).toBeDefined();
  });
});
