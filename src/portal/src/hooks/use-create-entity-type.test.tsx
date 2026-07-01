import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useCreateEntityType } from "./use-create-entity-type";

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({ user: { tenantSlug: "acme-corp" } }),
}));

const mockFetch = vi.fn();
globalThis.fetch = mockFetch;

function createWrapper() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  };
}

const payload = {
  name: "vendor_name",
  description: "Name of a vendor",
  examples: ["Acme Corp"],
  base_label_mapping: { ORG: ["vendor_name"] },
  required_flag: false,
};

describe("useCreateEntityType", () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  it("POSTs to the tenant-scoped entity types URL", async () => {
    const created = { id: "et-new", name: "vendor_name", version: 1 };
    mockFetch.mockResolvedValue(new Response(JSON.stringify(created), { status: 201 }));

    const { result } = renderHook(() => useCreateEntityType(), { wrapper: createWrapper() });

    act(() => {
      result.current.mutate(payload);
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    const callUrl = String(mockFetch.mock.calls[0][0]);
    expect(callUrl).toContain("/api/v1/tenants/acme-corp/entity-types");
    expect(mockFetch.mock.calls[0][1]?.method).toBe("POST");
  });

  it("throws on error response", async () => {
    mockFetch.mockResolvedValue(
      new Response(JSON.stringify({ detail: "Already exists" }), { status: 409 }),
    );

    const { result } = renderHook(() => useCreateEntityType(), { wrapper: createWrapper() });

    act(() => {
      result.current.mutate(payload);
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error?.message).toBe("Already exists");
  });

  it("returns the created entity type on success (scenario 19)", async () => {
    const created = { id: "et-new", name: "vendor_name", version: 1 };
    mockFetch.mockResolvedValue(new Response(JSON.stringify(created), { status: 201 }));

    const { result } = renderHook(() => useCreateEntityType(), { wrapper: createWrapper() });

    act(() => {
      result.current.mutate(payload);
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(created);
  });
});
