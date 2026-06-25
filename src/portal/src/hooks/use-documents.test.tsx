import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useDocuments } from "./use-documents";

const mockFetch = vi.fn();
globalThis.fetch = mockFetch;

vi.mock("@/lib/auth-fetch", () => ({
  authFetch: vi.fn((url: string) => mockFetch(url)),
}));

function createWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  };
}

describe("useDocuments", () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  it("fetches documents with page and per_page params", async () => {
    mockFetch.mockResolvedValue(
      new Response(JSON.stringify({ documents: [], total: 0, page: 1, per_page: 25 }), {
        status: 200,
      }),
    );

    const { result } = renderHook(() => useDocuments(1, 25), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual({ documents: [], total: 0, page: 1, per_page: 25 });
  });

  it("appends status filter when provided", async () => {
    mockFetch.mockResolvedValue(
      new Response(JSON.stringify({ documents: [], total: 0, page: 1, per_page: 25 }), {
        status: 200,
      }),
    );

    renderHook(() => useDocuments(1, 25, "pending"), { wrapper: createWrapper() });
    await waitFor(() => expect(mockFetch).toHaveBeenCalled());
    const callUrl = String(mockFetch.mock.calls[0][0]);
    expect(callUrl).toContain("status=pending");
  });

  it("does not append status filter when status is all", async () => {
    mockFetch.mockResolvedValue(
      new Response(JSON.stringify({ documents: [], total: 0, page: 1, per_page: 25 }), {
        status: 200,
      }),
    );

    renderHook(() => useDocuments(1, 25, "all"), { wrapper: createWrapper() });
    await waitFor(() => expect(mockFetch).toHaveBeenCalled());
    const callUrl = String(mockFetch.mock.calls[0][0]);
    expect(callUrl).not.toContain("status=");
  });
});
