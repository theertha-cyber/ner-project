import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ToastProvider } from "@/hooks/use-toast";
import { EntityTypesPage } from "./EntityTypesPage";
import type { EntityTypeListResponse } from "@/types/entity-types";

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({ user: { tenantSlug: "acme-corp" } }),
}));

const mockFetch = vi.fn();
globalThis.fetch = mockFetch;

const mockEntityTypes: EntityTypeListResponse = {
  entity_types: [
    {
      id: "et-1",
      name: "vendor_name",
      description: "Name of a vendor",
      examples: ["Northwind Logistics", "Globex Supplies"],
      base_label_mapping: { ORG: ["vendor_name"] },
      target_table: null,
      required_flag: true,
      is_active: true,
      version: 2,
    },
    {
      id: "et-2",
      name: "ship_to_location",
      description: "Shipping destination",
      examples: ["123 Main St"],
      base_label_mapping: { LOC: ["ship_to_location"] },
      target_table: null,
      required_flag: false,
      is_active: false,
      version: 1,
    },
  ],
};

function createWrapper() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return (
      <QueryClientProvider client={qc}>
        <ToastProvider>{children}</ToastProvider>
      </QueryClientProvider>
    );
  };
}

describe("EntityTypesPage", () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  it("renders page header with Entity Types heading", async () => {
    mockFetch.mockResolvedValue(
      new Response(JSON.stringify(mockEntityTypes), { status: 200 }),
    );
    render(<EntityTypesPage />, { wrapper: createWrapper() });
    expect(screen.getByText("Entity Types")).toBeDefined();
    expect(screen.getByText("/api/v1/entity-types")).toBeDefined();
  });

  it("shows '+ Define entity type' button", async () => {
    mockFetch.mockResolvedValue(
      new Response(JSON.stringify(mockEntityTypes), { status: 200 }),
    );
    render(<EntityTypesPage />, { wrapper: createWrapper() });
    expect(screen.getByRole("button", { name: "+ Define entity type" })).toBeDefined();
  });

  it("shows 6 skeleton cards while loading", () => {
    mockFetch.mockReturnValue(new Promise(() => {}));
    const { container } = render(<EntityTypesPage />, { wrapper: createWrapper() });
    const skeletons = container.querySelectorAll(".animate-pulse");
    expect(skeletons.length).toBe(6);
  });

  it("renders empty-state message when no entity types", async () => {
    mockFetch.mockResolvedValue(
      new Response(JSON.stringify({ entity_types: [] }), { status: 200 }),
    );
    render(<EntityTypesPage />, { wrapper: createWrapper() });
    await waitFor(() =>
      expect(screen.getByText("Define your first entity type to get started")).toBeDefined(),
    );
    expect(screen.getByRole("button", { name: "+ Define entity type" })).toBeDefined();
  });

  it("renders card grid with data", async () => {
    mockFetch.mockResolvedValue(
      new Response(JSON.stringify(mockEntityTypes), { status: 200 }),
    );
    render(<EntityTypesPage />, { wrapper: createWrapper() });
    await waitFor(() => expect(screen.getByText("vendor_name")).toBeDefined());
    expect(screen.getByText("ship_to_location")).toBeDefined();
  });

  it("shows active count in header after data loads", async () => {
    mockFetch.mockResolvedValue(
      new Response(JSON.stringify(mockEntityTypes), { status: 200 }),
    );
    render(<EntityTypesPage />, { wrapper: createWrapper() });
    await waitFor(() => expect(screen.getByText("1 active / 2")).toBeDefined());
  });

  it("calls toggle mutation when Deactivate is clicked", async () => {
    mockFetch
      .mockResolvedValueOnce(new Response(JSON.stringify(mockEntityTypes), { status: 200 }))
      .mockResolvedValueOnce(new Response(null, { status: 200 }));

    render(<EntityTypesPage />, { wrapper: createWrapper() });
    await waitFor(() => expect(screen.getByText("vendor_name")).toBeDefined());

    fireEvent.click(screen.getByRole("button", { name: "Deactivate" }));

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/tenants/acme-corp/entity-types/vendor_name"),
        expect.objectContaining({ method: "PATCH" }),
      );
    });
  });

  it("opens slide-over when '+ Define entity type' is clicked", async () => {
    mockFetch.mockResolvedValue(
      new Response(JSON.stringify(mockEntityTypes), { status: 200 }),
    );
    render(<EntityTypesPage />, { wrapper: createWrapper() });
    await waitFor(() => expect(screen.getByText("vendor_name")).toBeDefined());

    fireEvent.click(screen.getByRole("button", { name: "+ Define entity type" }));
    expect(screen.getByRole("heading", { name: "Create entity type" })).toBeDefined();
  });
});
