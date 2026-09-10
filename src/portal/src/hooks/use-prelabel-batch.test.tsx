import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useCreatePrelabelBatch, useRecordBatchGuidance } from "./use-prelabel-batch";

const mockFetch = vi.fn();
globalThis.fetch = mockFetch;

function createWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  };
}

describe("useCreatePrelabelBatch", () => {
  beforeEach(() => mockFetch.mockReset());

  it("sends document_ids and batch_kind", async () => {
    mockFetch.mockResolvedValue(
      new Response(JSON.stringify({ batch_id: "b1", batch_kind: "initial" }), { status: 202 }),
    );
    const { result } = renderHook(() => useCreatePrelabelBatch(), { wrapper: createWrapper() });

    result.current.mutate({ documentIds: ["d1", "d2"], batchKind: "initial" });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    const body = JSON.parse(mockFetch.mock.calls[0][1].body);
    expect(body).toEqual({ document_ids: ["d1", "d2"], batch_kind: "initial" });
  });
});

describe("useRecordBatchGuidance", () => {
  beforeEach(() => mockFetch.mockReset());

  it("posts corrected spans and a note to the batch's guidance endpoint", async () => {
    mockFetch.mockResolvedValue(new Response(JSON.stringify({ recorded: true }), { status: 201 }));
    const { result } = renderHook(() => useRecordBatchGuidance(), { wrapper: createWrapper() });

    result.current.mutate({
      batchId: "b1",
      documentId: "d1",
      correctedSpans: [{ text: "Acme", entity_type: "org" }],
      note: "codenames are PROJECT",
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    const [url, opts] = mockFetch.mock.calls[0];
    expect(String(url)).toContain("/api/v1/prelabel-batches/b1/guidance");
    const body = JSON.parse(opts.body);
    expect(body.corrected_spans).toEqual([{ text: "Acme", entity_type: "org" }]);
    expect(body.note).toBe("codenames are PROJECT");
  });
});
