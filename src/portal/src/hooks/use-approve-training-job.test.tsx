import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useApproveTrainingJob } from "./use-approve-training-job";

const mockFetch = vi.fn();
globalThis.fetch = mockFetch;

function createWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  };
}

describe("useApproveTrainingJob", () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  it("posts approve with tenant_id and returns updated job", async () => {
    const updated = { id: "job-1", status: "queued" };
    mockFetch.mockResolvedValue(new Response(JSON.stringify(updated), { status: 200 }));

    const { result } = renderHook(() => useApproveTrainingJob(), { wrapper: createWrapper() });

    result.current.mutate({ jobId: "job-1", tenantId: "tenant-1" });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    const callUrl = String(mockFetch.mock.calls[0][0]);
    expect(callUrl).toContain("tenant_id=tenant-1");
    expect(result.current.data).toEqual(updated);
  });
});
