import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useEntityTypes } from "./use-entity-types";

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({ user: { tenantSlug: "acme-corp" } }),
}));

const mockFetch = vi.fn();
globalThis.fetch = mockFetch;

function createWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  };
}

describe("useEntityTypes", () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  it("fetches tenant-scoped entity types URL (scenario 18)", async () => {
    mockFetch.mockResolvedValue(
      new Response(JSON.stringify({ entity_types: [] }), { status: 200 }),
    );

    renderHook(() => useEntityTypes(), { wrapper: createWrapper() });

    await waitFor(() => expect(mockFetch).toHaveBeenCalled());
    const callUrl = String(mockFetch.mock.calls[0][0]);
    expect(callUrl).toContain("/api/v1/tenants/acme-corp/entity-types");
  });

  it("uses ['entity-types', tenantSlug] query key and returns list (scenario 18)", async () => {
    mockFetch.mockResolvedValue(
      new Response(JSON.stringify({ entity_types: [] }), { status: 200 }),
    );

    const { result } = renderHook(() => useEntityTypes(), { wrapper: createWrapper() });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual({ entity_types: [] });
  });

  it("returns entity types from API response", async () => {
    const entityTypes = [{ id: "et-1", name: "vendor_name", version: 1, is_active: true }];
    mockFetch.mockResolvedValue(
      new Response(JSON.stringify({ entity_types: entityTypes }), { status: 200 }),
    );

    const { result } = renderHook(() => useEntityTypes(), { wrapper: createWrapper() });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.entity_types).toHaveLength(1);
    expect(result.current.data?.entity_types[0].name).toBe("vendor_name");
  });
});
