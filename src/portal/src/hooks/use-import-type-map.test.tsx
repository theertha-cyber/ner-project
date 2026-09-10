import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useImportTypeMap } from "./use-import-type-map";

const mockFetch = vi.fn();
globalThis.fetch = mockFetch;

function createWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  };
}

describe("useImportTypeMap", () => {
  beforeEach(() => mockFetch.mockReset());

  it("posts the mapping to the file's type-map endpoint", async () => {
    mockFetch.mockResolvedValue(
      new Response(JSON.stringify({ source_file: "g.jsonl", type_map: {}, training_eligible: true }), {
        status: 201,
      }),
    );
    const { result } = renderHook(() => useImportTypeMap(), { wrapper: createWrapper() });

    result.current.mutate({
      sourceFile: "g.jsonl",
      mapping: { JOB_TITLE: { to: "job_title" }, contract_id: { create: true } },
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    const [url, opts] = mockFetch.mock.calls[0];
    expect(String(url)).toContain("/api/v1/annotation-imports/g.jsonl/type-map");
    expect(JSON.parse(opts.body)).toEqual({
      JOB_TITLE: { to: "job_title" },
      contract_id: { create: true },
    });
    expect(result.current.data?.training_eligible).toBe(true);
  });

  it("surfaces the server error message", async () => {
    mockFetch.mockResolvedValue(
      new Response(JSON.stringify({ detail: { message: "Target entity type 'x' is not defined" } }), {
        status: 422,
      }),
    );
    const { result } = renderHook(() => useImportTypeMap(), { wrapper: createWrapper() });

    result.current.mutate({ sourceFile: "g.jsonl", mapping: { X: { to: "x" } } });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error?.message).toContain("not defined");
  });
});
