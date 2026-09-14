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

  it("posts the chosen source scope and returns the created job", async () => {
    const created = { id: "job-new", status: "pending_approval", source_scope: "automated" };
    mockFetch.mockResolvedValue(new Response(JSON.stringify(created), { status: 201 }));

    const { result } = renderHook(() => useSubmitTrainingJob(), { wrapper: createWrapper() });

    result.current.mutate({ sourceScope: "automated" });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(created);

    const [, init] = mockFetch.mock.calls[0];
    expect(JSON.parse(init.body)).toEqual({ source_scope: "automated" });
  });

  it("omits source_scope from the body when none is given", async () => {
    mockFetch.mockResolvedValue(new Response(JSON.stringify({ id: "job-new" }), { status: 201 }));

    const { result } = renderHook(() => useSubmitTrainingJob(), { wrapper: createWrapper() });

    result.current.mutate({});

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    const [, init] = mockFetch.mock.calls[0];
    expect(JSON.parse(init.body)).toEqual({});
  });

  it("throws on error response", async () => {
    mockFetch.mockResolvedValue(new Response(JSON.stringify({ detail: "Bad request" }), { status: 422 }));

    const { result } = renderHook(() => useSubmitTrainingJob(), { wrapper: createWrapper() });

    result.current.mutate({ sourceScope: "manual" });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error?.message).toBe("Bad request");
  });
});
