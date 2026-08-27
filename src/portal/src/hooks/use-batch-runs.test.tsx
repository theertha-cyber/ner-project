/**
 * Covers verification.md rows 105-107.
 *
 * The processing mode must travel with the request rather than living in client state,
 * and a mode the server refuses must surface as a refusal — a client that quietly
 * downgraded would leave the user believing a run produced data it did not.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { useBatchRuns } from "./use-batch-runs";

const mockAuthFetch = vi.fn();
vi.mock("@/lib/auth-fetch", () => ({
  authFetch: (...args: unknown[]) => mockAuthFetch(...args),
}));

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
    const { result } = renderHook(() => useBatchRuns());
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
    const { result } = renderHook(() => useBatchRuns());
    respondToPostWith(acceptedResponse());

    await act(async () => {
      await result.current.triggerBatch(["doc-1"], "bert_llm_postprocess");
    });

    const body = JSON.parse((postCall()![1] as RequestInit).body as string);
    expect(body.processing_mode).toBe("bert_llm_postprocess");
    expect(body.documentIds).toEqual(["doc-1"]);
  });

  it("sends the mode in the body, never as a query parameter", async () => {
    const { result } = renderHook(() => useBatchRuns());
    respondToPostWith(acceptedResponse());

    await act(async () => {
      await result.current.triggerBatch(["doc-1"], "bert_llm_postprocess");
    });

    expect(postCall()![0]).not.toContain("processing_mode");
    expect(postCall()![0]).not.toContain("?");
  });

  it("records the mode on the run it adds to the list", async () => {
    const { result } = renderHook(() => useBatchRuns());
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
    const { result } = renderHook(() => useBatchRuns());
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
    const { result } = renderHook(() => useBatchRuns());
    respondToPostWith(new Response("nope", { status: 500 }));

    await expect(
      act(async () => {
        await result.current.triggerBatch(["doc-1"]);
      })
    ).rejects.toThrow(/500/);
  });
});
