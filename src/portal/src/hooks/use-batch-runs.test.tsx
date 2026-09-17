/**
 * Covers verification.md rows 105-107.
 *
 * The processing mode must travel with the request rather than living in client state,
 * and a mode the server refuses must surface as a refusal — a client that quietly
 * downgraded would leave the user believing a run produced data it did not.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import type { ReactNode } from "react";
import { renderHook, act, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useBatchRuns } from "./use-batch-runs";

const mockAuthFetch = vi.fn();
vi.mock("@/lib/auth-fetch", () => ({
  authFetch: (...args: unknown[]) => mockAuthFetch(...args),
}));

function renderBatchRuns(client = new QueryClient({ defaultOptions: { queries: { retry: false } } })) {
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  return renderHook(() => useBatchRuns(), { wrapper });
}

function listResponse() {
  return new Response(JSON.stringify({ runs: [] }), { status: 200 });
}

function acceptedResponse(runId = "run-new-1") {
  return new Response(JSON.stringify({ run_id: runId, status: "queued" }), { status: 202 });
}

function postCall() {
  return mockAuthFetch.mock.calls.find(
    ([, init]) => (init as RequestInit | undefined)?.method === "POST"
  );
}

/**
 * Routes by method rather than by call order. The hook fetches the run list on mount, so
 * an order-based mock would hand that GET the response meant for the POST.
 */
function respondToPostWith(response: Response) {
  mockAuthFetch.mockImplementation((_url: string, init?: RequestInit) =>
    Promise.resolve(init?.method === "POST" ? response : listResponse())
  );
}

describe("useBatchRuns.triggerBatch", () => {
  beforeEach(() => {
    mockAuthFetch.mockReset();
    mockAuthFetch.mockImplementation(() => Promise.resolve(listResponse()));
  });

  it("sends the default processing mode when the caller specifies none", async () => {
    const { result } = renderBatchRuns();
    respondToPostWith(acceptedResponse());

    await act(async () => {
      await result.current.triggerBatch(["doc-1", "doc-2"]);
    });

    const call = postCall();
    expect(call).toBeDefined();
    expect(call![0]).toBe("/api/v1/extract-batch");
    expect(JSON.parse((call![1] as RequestInit).body as string)).toEqual({
      documentIds: ["doc-1", "doc-2"],
      processing_mode: "bert_only",
    });
  });

  it("sends the selected mode alongside the document ids in one request", async () => {
    const { result } = renderBatchRuns();
    respondToPostWith(acceptedResponse());

    await act(async () => {
      await result.current.triggerBatch(["doc-1"], "bert_llm_postprocess");
    });

    const body = JSON.parse((postCall()![1] as RequestInit).body as string);
    expect(body.processing_mode).toBe("bert_llm_postprocess");
    expect(body.documentIds).toEqual(["doc-1"]);
  });

  it("sends the mode in the body, never as a query parameter", async () => {
    const { result } = renderBatchRuns();
    respondToPostWith(acceptedResponse());

    await act(async () => {
      await result.current.triggerBatch(["doc-1"], "bert_llm_postprocess");
    });

    expect(postCall()![0]).not.toContain("processing_mode");
    expect(postCall()![0]).not.toContain("?");
  });

  it("records the mode on the run it adds to the list", async () => {
    const { result } = renderBatchRuns();
    // The mount effect replaces the whole list when its fetch resolves, so it has to
    // settle before a triggered run is added or it would be overwritten.
    await waitFor(() => expect(mockAuthFetch).toHaveBeenCalled());
    await act(async () => {});

    respondToPostWith(acceptedResponse("run-mode-1"));

    await act(async () => {
      await result.current.triggerBatch(["doc-1"], "bert_llm_postprocess");
    });

    await waitFor(() => {
      expect(result.current.runs[0]).toMatchObject({
        run_id: "run-mode-1",
        processing_mode: "bert_llm_postprocess",
      });
    });
  });

  it("surfaces a 422 rejection and adds no run", async () => {
    const { result } = renderBatchRuns();
    respondToPostWith(
      new Response(
        JSON.stringify({ detail: "LLM post-processing is not configured for this deployment" }),
        { status: 422 }
      )
    );

    await expect(
      act(async () => {
        await result.current.triggerBatch(["doc-1"], "bert_llm_postprocess");
      })
    ).rejects.toThrow(/not configured/i);

    expect(result.current.runs).toHaveLength(0);
  });

  it("falls back to the status code when the server sends no detail", async () => {
    const { result } = renderBatchRuns();
    respondToPostWith(new Response("nope", { status: 500 }));

    await expect(
      act(async () => {
        await result.current.triggerBatch(["doc-1"]);
      })
    ).rejects.toThrow(/500/);
  });
});

describe("useBatchRuns list", () => {
  beforeEach(() => mockAuthFetch.mockReset());

  it("reports loading, not an empty list, while the first fetch is in flight", async () => {
    let resolve!: (r: Response) => void;
    mockAuthFetch.mockImplementation(() => new Promise<Response>((r) => { resolve = r; }));

    const { result } = renderBatchRuns();

    expect(result.current.isLoading).toBe(true);
    expect(result.current.runs).toEqual([]);

    await act(async () => {
      resolve(new Response(JSON.stringify({ runs: [{ run_id: "r1", status: "completed" }] }), { status: 200 }));
    });
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.runs).toHaveLength(1);
  });

  it("serves a remount from cache instead of starting empty", async () => {
    mockAuthFetch.mockImplementation(() =>
      Promise.resolve(new Response(JSON.stringify({ runs: [{ run_id: "r1", status: "completed" }] }), { status: 200 }))
    );
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });

    const first = renderBatchRuns(client);
    await waitFor(() => expect(first.result.current.runs).toHaveLength(1));
    first.unmount();

    const second = renderBatchRuns(client);
    expect(second.result.current.isLoading).toBe(false);
    expect(second.result.current.runs).toHaveLength(1);
  });

  it("surfaces a failed load as an error rather than an empty list", async () => {
    mockAuthFetch.mockImplementation(() => Promise.resolve(new Response("{}", { status: 503 })));

    const { result } = renderBatchRuns();

    await waitFor(() => expect(result.current.error).toBeTruthy());
    expect(result.current.isLoading).toBe(false);
  });
});
