import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useTrainingJob } from "./use-training-job";

const mockFetch = vi.fn();
globalThis.fetch = mockFetch;

const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });

function createWrapper() {
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  };
}

describe("useTrainingJob", () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  it("fetches a single training job by id", async () => {
    mockFetch.mockResolvedValue(
      new Response(
        JSON.stringify({ id: "job-1", status: "running", current_epoch: 2, current_loss: 0.05 }),
        { status: 200 },
      ),
    );

    const { result } = renderHook(() => useTrainingJob("job-1"), { wrapper: createWrapper() });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.id).toBe("job-1");
  });

  it("does not fetch when id is null", async () => {
    const { result } = renderHook(() => useTrainingJob(null), { wrapper: createWrapper() });

    expect(result.current.isPending).toBe(true);
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("polls at 5s interval when job status is running", async () => {
    mockFetch.mockResolvedValue(
      new Response(JSON.stringify({ id: "job-1", status: "running" }), { status: 200 }),
    );

    const { result } = renderHook(() => useTrainingJob("job-1"), { wrapper: createWrapper() });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    const query = qc.getQueryCache().find({ queryKey: ["training-job", "job-1", undefined] });
    const interval = query?.options.refetchInterval;
    expect(typeof interval).toBe("function");
    expect(interval({ state: { data: { status: "running" } } } as any)).toBe(5000);
  });

  it("appends tenant_id query param when role is system_admin", async () => {
    mockFetch.mockResolvedValue(
      new Response(JSON.stringify({ id: "job-1", status: "queued", tenant_id: "tenant-b" }), {
        status: 200,
      }),
    );

    renderHook(() => useTrainingJob("job-1", "system_admin", "tenant-b"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(mockFetch).toHaveBeenCalled());
    const callUrl = String(mockFetch.mock.calls[0][0]);
    expect(callUrl).toBe("/api/v1/training-jobs/job-1?tenant_id=tenant-b");
  });

  it("does not append tenant_id query param for tenant_admin, even if a tenantId is passed", async () => {
    mockFetch.mockResolvedValue(
      new Response(JSON.stringify({ id: "job-1", status: "queued", tenant_id: "t1" }), {
        status: 200,
      }),
    );

    renderHook(() => useTrainingJob("job-1", "tenant_admin", "t1"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(mockFetch).toHaveBeenCalled());
    const callUrl = String(mockFetch.mock.calls[0][0]);
    expect(callUrl).toBe("/api/v1/training-jobs/job-1");
  });
});
