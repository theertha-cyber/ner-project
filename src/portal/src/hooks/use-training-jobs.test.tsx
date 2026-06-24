import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useTrainingJobs } from "./use-training-jobs";

const mockFetch = vi.fn();
globalThis.fetch = mockFetch;

function createWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  };
}

describe("useTrainingJobs", () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  it("fetches training jobs without status filter", async () => {
    mockFetch.mockResolvedValue(
      new Response(JSON.stringify({ items: [], total: 0, page: 1, per_page: 50 }), {
        status: 200,
      }),
    );

    const { result } = renderHook(() => useTrainingJobs(), { wrapper: createWrapper() });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual({ items: [], total: 0, page: 1, per_page: 50 });
  });

  it("appends status filter to query string", async () => {
    mockFetch.mockResolvedValue(
      new Response(JSON.stringify({ items: [], total: 0, page: 1, per_page: 50 }), {
        status: 200,
      }),
    );

    renderHook(() => useTrainingJobs("running"), { wrapper: createWrapper() });

    await waitFor(() => expect(mockFetch).toHaveBeenCalled());
    const callUrl = String(mockFetch.mock.calls[0][0]);
    expect(callUrl).toContain("status=running");
  });
});
