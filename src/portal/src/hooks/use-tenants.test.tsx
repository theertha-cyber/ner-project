import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useTenants } from "./use-tenants";

const mockFetch = vi.fn();
globalThis.fetch = mockFetch;

vi.mock("@/lib/auth-fetch", () => ({
  authFetch: vi.fn((url: string) => mockFetch(url)),
}));

function createWrapper() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  };
}

describe("useTenants", () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  it("fetches tenants with a large per_page to list all tenants", async () => {
    const mockResponse = {
      tenants: [{ id: "test-tenant", name: "Test Tenant", slug: "test-tenant", status: "active" }],
      total: 1,
      page: 1,
      per_page: 100,
    };
    mockFetch.mockResolvedValue(new Response(JSON.stringify(mockResponse), { status: 200 }));

    const { result } = renderHook(() => useTenants(), { wrapper: createWrapper() });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(mockResponse);
    const callUrl = String(mockFetch.mock.calls[0][0]);
    expect(callUrl).toContain("per_page=100");
    expect(callUrl).not.toContain("status");
  });
});
