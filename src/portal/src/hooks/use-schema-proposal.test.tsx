import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useRequestSchemaProposal } from "./use-schema-proposal";

const mockFetch = vi.fn();
globalThis.fetch = mockFetch;

function createWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  };
}

describe("useRequestSchemaProposal", () => {
  beforeEach(() => mockFetch.mockReset());

  it("omits qa_pair_document_id when none is chosen", async () => {
    mockFetch.mockResolvedValue(new Response(JSON.stringify({ proposal_id: "p1" }), { status: 202 }));
    const { result } = renderHook(() => useRequestSchemaProposal(), { wrapper: createWrapper() });

    result.current.mutate({ documentIds: ["d1"] });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(JSON.parse(mockFetch.mock.calls[0][1].body)).toEqual({ document_ids: ["d1"] });
  });

  it("includes qa_pair_document_id when chosen", async () => {
    mockFetch.mockResolvedValue(new Response(JSON.stringify({ proposal_id: "p1" }), { status: 202 }));
    const { result } = renderHook(() => useRequestSchemaProposal(), { wrapper: createWrapper() });

    result.current.mutate({ documentIds: ["d1"], qaPairDocumentId: "qa1" });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(JSON.parse(mockFetch.mock.calls[0][1].body)).toEqual({
      document_ids: ["d1"],
      qa_pair_document_id: "qa1",
    });
  });
});
