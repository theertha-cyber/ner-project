import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useAuditLog } from "./use-audit-log";

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

describe("useAuditLog", () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  it("fetches audit log with page and per_page params", async () => {
    const mockResponse = {
      events: [
        {
          id: "evt-1",
          actor: "admin@test.com",
          role: "system_admin",
          action: "tenant.deactivate",
          target: "test-tenant",
          kind: "reject",
          tenant_id: null,
          created_at: "2026-07-14T10:00:00Z",
        },
      ],
      total: 1,
      page: 1,
      per_page: 50,
    };

    mockFetch.mockResolvedValue(
      new Response(JSON.stringify(mockResponse), { status: 200 }),
    );

    const { result } = renderHook(() => useAuditLog(1, 50), { wrapper: createWrapper() });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(mockResponse);
  });

  it("uses correct query key with page and perPage", async () => {
    mockFetch.mockResolvedValue(
      new Response(JSON.stringify({ events: [], total: 0, page: 1, per_page: 25 }), {
        status: 200,
      }),
    );

    const { result } = renderHook(() => useAuditLog(2, 25), { wrapper: createWrapper() });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    const callUrl = String(mockFetch.mock.calls[0][0]);
    expect(callUrl).toContain("page=2");
    expect(callUrl).toContain("per_page=25");
  });

  it("returns paginated data with correct shape", async () => {
    const mockResponse = {
      events: [],
      total: 0,
      page: 1,
      per_page: 50,
    };

    mockFetch.mockResolvedValue(
      new Response(JSON.stringify(mockResponse), { status: 200 }),
    );

    const { result } = renderHook(() => useAuditLog(1), { wrapper: createWrapper() });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toHaveProperty("events");
    expect(result.current.data).toHaveProperty("total");
    expect(result.current.data).toHaveProperty("page");
    expect(result.current.data).toHaveProperty("per_page");
  });

  it("includes tenant_id in query string when tenantId is provided", async () => {
    mockFetch.mockResolvedValue(
      new Response(JSON.stringify({ events: [], total: 0, page: 1, per_page: 50 }), {
        status: 200,
      }),
    );

    const { result } = renderHook(() => useAuditLog(1, 50, "test-tenant"), { wrapper: createWrapper() });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    const callUrl = String(mockFetch.mock.calls[0][0]);
    expect(callUrl).toContain("tenant_id=test-tenant");
  });

  it("omits tenant_id from query string when tenantId is null", async () => {
    mockFetch.mockResolvedValue(
      new Response(JSON.stringify({ events: [], total: 0, page: 1, per_page: 50 }), {
        status: 200,
      }),
    );

    const { result } = renderHook(() => useAuditLog(1, 50, null), { wrapper: createWrapper() });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    const callUrl = String(mockFetch.mock.calls[0][0]);
    expect(callUrl).not.toContain("tenant_id");
  });

  it("throws on error response", async () => {
    mockFetch.mockResolvedValue(
      new Response(null, { status: 500 }),
    );

    const { result } = renderHook(() => useAuditLog(1), { wrapper: createWrapper() });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error?.message).toBe("Failed to fetch audit log: 500");
  });
});
