import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { isRetryable, useOriginalDocument } from "./use-original-document";

/**
 * The object-URL lifetime is what these tests exist for.
 *
 * A leaked URL holds the whole document in memory for the session; a URL revoked from a
 * stale closure kills the document the user is currently looking at. Neither shows up in
 * a rendering test, so they are asserted here directly.
 */

const mockFetch = vi.fn();
vi.mock("@/lib/auth-fetch", () => ({
  authFetch: (url: string, init?: RequestInit) => mockFetch(url, init),
}));

const PROBE = {
  document_id: "doc-1",
  filename: "resume.pdf",
  media_type: "application/pdf",
  render_mode: "pdf",
  file_size: 1024,
  retention_mode: "platform_blob",
  available: true,
  reason: null,
  message: null,
};

function probeResponse(body: unknown, ok = true, status = 200) {
  return { ok, status, json: () => Promise.resolve(body) };
}

function bytesResponse(blob: Blob, ok = true, status = 200) {
  return { ok, status, blob: () => Promise.resolve(blob), json: () => Promise.resolve({}) };
}

let created: string[] = [];
let revoked: string[] = [];

beforeEach(() => {
  mockFetch.mockReset();
  created = [];
  revoked = [];
  let counter = 0;
  globalThis.URL.createObjectURL = vi.fn(() => {
    const url = `blob:mock/${++counter}`;
    created.push(url);
    return url;
  });
  globalThis.URL.revokeObjectURL = vi.fn((url: string) => {
    revoked.push(url);
  });
});

describe("fetching as authenticated data", () => {
  it("probes, then fetches the bytes, both through authFetch", async () => {
    mockFetch
      .mockResolvedValueOnce(probeResponse(PROBE))
      .mockResolvedValueOnce(bytesResponse(new Blob(["%PDF"], { type: "application/pdf" })));

    const { result } = renderHook(() => useOriginalDocument("doc-1"));

    await waitFor(() => expect(result.current.state.status).toBe("ready"));
    expect(mockFetch.mock.calls[0][0]).toBe("/api/v1/documents/doc-1/content/status");
    expect(mockFetch.mock.calls[1][0]).toBe("/api/v1/documents/doc-1/content");
  });

  it("renders from an object URL that carries no credential", async () => {
    mockFetch
      .mockResolvedValueOnce(probeResponse(PROBE))
      .mockResolvedValueOnce(bytesResponse(new Blob(["%PDF"])));

    const { result } = renderHook(() => useOriginalDocument("doc-1"));

    await waitFor(() => expect(result.current.state.status).toBe("ready"));
    const state = result.current.state as { url: string };
    expect(state.url).toMatch(/^blob:/);
    expect(state.url).not.toMatch(/token|bearer|eyJ/i);
  });

  it("types the blob from the probe, not from the response", async () => {
    // The response claims something else; the server's decision must win, because the
    // object URL runs in this origin.
    mockFetch
      .mockResolvedValueOnce(probeResponse({ ...PROBE, media_type: "application/pdf" }))
      .mockResolvedValueOnce(bytesResponse(new Blob(["<script>"], { type: "text/html" })));

    const { result } = renderHook(() => useOriginalDocument("doc-1"));

    await waitFor(() => expect(result.current.state.status).toBe("ready"));
    const blob = (globalThis.URL.createObjectURL as ReturnType<typeof vi.fn>).mock.calls[0][0] as Blob;
    expect(blob.type).toBe("application/pdf");
  });
});

describe("releasing what it holds", () => {
  it("revokes the object URL when the viewer closes", async () => {
    mockFetch
      .mockResolvedValueOnce(probeResponse(PROBE))
      .mockResolvedValueOnce(bytesResponse(new Blob(["%PDF"])));

    const { result, unmount } = renderHook(() => useOriginalDocument("doc-1"));
    await waitFor(() => expect(result.current.state.status).toBe("ready"));

    unmount();

    expect(revoked).toEqual(created);
  });

  it("releases the previous document when another is opened", async () => {
    mockFetch
      .mockResolvedValueOnce(probeResponse(PROBE))
      .mockResolvedValueOnce(bytesResponse(new Blob(["one"])))
      .mockResolvedValueOnce(probeResponse({ ...PROBE, document_id: "doc-2" }))
      .mockResolvedValueOnce(bytesResponse(new Blob(["two"])));

    const { result, rerender } = renderHook(({ id }) => useOriginalDocument(id), {
      initialProps: { id: "doc-1" as string | null },
    });
    await waitFor(() => expect(result.current.state.status).toBe("ready"));
    const first = (result.current.state as { url: string }).url;

    rerender({ id: "doc-2" });
    await waitFor(() => expect(result.current.state.status).toBe("ready"));
    const second = (result.current.state as { url: string }).url;

    expect(revoked).toContain(first);
    expect(second).not.toBe(first);
    // The regression this guards: revoking through a stale closure would kill the URL
    // the user is currently looking at.
    expect(revoked).not.toContain(second);
  });

  it("abandons a superseded request so it cannot replace the newer document", async () => {
    let releaseFirst: (value: unknown) => void = () => {};
    const blocked = new Promise((resolve) => {
      releaseFirst = resolve;
    });

    mockFetch
      .mockImplementationOnce(async () => {
        await blocked;
        return probeResponse(PROBE);
      })
      .mockResolvedValueOnce(probeResponse({ ...PROBE, document_id: "doc-2", filename: "second.pdf" }))
      .mockResolvedValueOnce(bytesResponse(new Blob(["two"])));

    const { result, rerender } = renderHook(({ id }) => useOriginalDocument(id), {
      initialProps: { id: "doc-1" as string | null },
    });

    rerender({ id: "doc-2" });
    await waitFor(() => expect(result.current.state.status).toBe("ready"));

    releaseFirst(null);
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect((result.current.state as { filename: string }).filename).toBe("second.pdf");
  });

  it("goes idle without fetching when no document is selected", async () => {
    const { result } = renderHook(() => useOriginalDocument(null));
    expect(result.current.state.status).toBe("idle");
    expect(mockFetch).not.toHaveBeenCalled();
  });
});

describe("unavailable outcomes", () => {
  it("surfaces the server's reason from the probe without fetching bytes", async () => {
    mockFetch.mockResolvedValueOnce(
      probeResponse({
        ...PROBE,
        available: false,
        reason: "ORIGINAL_RELEASED",
        message: "The original was not retained after processing.",
      }),
    );

    const { result } = renderHook(() => useOriginalDocument("doc-1"));

    await waitFor(() => expect(result.current.state.status).toBe("unavailable"));
    expect((result.current.state as { code: string }).code).toBe("ORIGINAL_RELEASED");
    expect(mockFetch).toHaveBeenCalledTimes(1);
  });

  it("surfaces a refusal from the probe", async () => {
    mockFetch.mockResolvedValueOnce(
      probeResponse({ detail: { code: "DOCUMENT_NOT_PERMITTED", message: "No access." } }, false, 403),
    );

    const { result } = renderHook(() => useOriginalDocument("doc-1"));

    await waitFor(() => expect(result.current.state.status).toBe("unavailable"));
    expect((result.current.state as { code: string }).code).toBe("DOCUMENT_NOT_PERMITTED");
  });

  it("separates permanent outcomes from retryable ones", () => {
    expect(isRetryable("SOURCE_UNAVAILABLE")).toBe(true);
    expect(isRetryable("CONVERSION_FAILED")).toBe(true);
    // A released original will not come back; offering a retry would be a lie.
    expect(isRetryable("ORIGINAL_RELEASED")).toBe(false);
    expect(isRetryable("DOCUMENT_NOT_PERMITTED")).toBe(false);
    expect(isRetryable("SOURCE_NOT_REOPENABLE")).toBe(false);
  });
});
