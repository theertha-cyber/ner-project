import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useSubmitTrainingJob } from "./use-submit-training-job";

const mockFetch = vi.fn();
globalThis.fetch = mockFetch;

function createWrapper() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  };
}

describe("useSubmitTrainingJob", () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  it("posts payload and returns created job", async () => {
    const created = { id: "job-new", status: "pending_approval" };
    mockFetch.mockResolvedValue(new Response(JSON.stringify(created), { status: 201 }));

    const { result } = renderHook(() => useSubmitTrainingJob(), { wrapper: createWrapper() });

    result.current.mutate({ learning_rate: 2e-5, num_epochs: 3, batch_size: 8, max_seq_length: 128 });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(created);
  });

  it("throws on error response", async () => {
    mockFetch.mockResolvedValue(new Response(JSON.stringify({ detail: "Bad request" }), { status: 422 }));

    const { result } = renderHook(() => useSubmitTrainingJob(), { wrapper: createWrapper() });

    result.current.mutate({ learning_rate: 2e-5, num_epochs: -1, batch_size: 8, max_seq_length: 128 });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error?.message).toBe("Bad request");
  });
});
