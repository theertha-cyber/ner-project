import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useRejectTrainingJob } from "./use-reject-training-job";

const mockFetch = vi.fn();
globalThis.fetch = mockFetch;

function createWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  };
}

describe("useRejectTrainingJob", () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  it("posts reject with tenant_id and reason", async () => {
    const updated = { id: "job-1", status: "rejected", error_message: "GPU at capacity" };
    mockFetch.mockResolvedValue(new Response(JSON.stringify(updated), { status: 200 }));

    const { result } = renderHook(() => useRejectTrainingJob(), { wrapper: createWrapper() });

    result.current.mutate({ jobId: "job-1", tenantId: "tenant-1", reason: "GPU at capacity" });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    const callUrl = String(mockFetch.mock.calls[0][0]);
    expect(callUrl).toContain("tenant_id=tenant-1");
    expect(result.current.data).toEqual(updated);
  });

  it("posts reject without reason body when reason is undefined", async () => {
    mockFetch.mockResolvedValue(new Response(JSON.stringify({ id: "job-1", status: "rejected", error_message: null }), { status: 200 }));

    const { result } = renderHook(() => useRejectTrainingJob(), { wrapper: createWrapper() });

    result.current.mutate({ jobId: "job-1", tenantId: "tenant-1" });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    const callBody = mockFetch.mock.calls[0][1]?.body;
    expect(callBody).toBeUndefined();
  });
});
