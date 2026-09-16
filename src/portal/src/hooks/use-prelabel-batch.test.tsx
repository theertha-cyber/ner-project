import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  useCreatePrelabelBatch,
  usePrelabelBatches,
  useRecordBatchGuidance,
} from "./use-prelabel-batch";

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

describe("usePrelabelBatches", () => {
  beforeEach(() => mockFetch.mockReset());

  it("loads the batch list", async () => {
    mockFetch.mockResolvedValue(
      new Response(
        JSON.stringify({
          batches: [
            { batch_id: "b1", status: "completed", state: "completed", batch_kind: "large", annotator_review_status: "approved", training_eligible_at: "x", created_at: "y", acceptance_decision: "accepted" },
          ],
        }),
        { status: 200 },
      ),
    );
    const { result } = renderHook(() => usePrelabelBatches(true), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(String(mockFetch.mock.calls[0][0])).toContain("/api/v1/prelabel-batches");
    expect(result.current.data?.batches[0].annotator_review_status).toBe("approved");
  });
});
