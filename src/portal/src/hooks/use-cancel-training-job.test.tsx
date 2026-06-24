import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useCancelTrainingJob } from "./use-cancel-training-job";

const mockFetch = vi.fn();
globalThis.fetch = mockFetch;

function createWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  };
}

describe("useCancelTrainingJob", () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  it("posts cancel and returns updated job", async () => {
    const updated = { id: "job-1", status: "cancelled" };
    mockFetch.mockResolvedValue(new Response(JSON.stringify(updated), { status: 200 }));

    const { result } = renderHook(() => useCancelTrainingJob(), { wrapper: createWrapper() });

    result.current.mutate("job-1");

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(updated);
  });
});
