import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useAnnotationImport } from "./use-annotation-import";

const mockAuthFetch = vi.fn();
vi.mock("@/lib/auth-fetch", () => ({ authFetch: (...args: unknown[]) => mockAuthFetch(...args) }));

function makeFile(content = "John\tB-PER\n", name = "test.txt", type = "text/plain") {
  return new File([content], name, { type });
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("useAnnotationImport", () => {
  it("starts in idle state", () => {
    const { result } = renderHook(() => useAnnotationImport());
    expect(result.current.state).toEqual({ status: "idle" });
  });

  it("transitions to uploading then success on 201", async () => {
    const mockResult = {
      imported_count: 2,
      skipped_count: 0,
      warnings: [],
      entity_type_counts: { PER: 1, ORG: 1 },
    };

    mockAuthFetch.mockResolvedValueOnce({
      ok: true,
      status: 201,
      json: () => Promise.resolve(mockResult),
    });

    const { result } = renderHook(() => useAnnotationImport());

    await act(async () => {
      await result.current.importAnnotations(makeFile());
    });

    expect(result.current.state).toEqual({ status: "success", result: mockResult });
  });

  it("handles partial import response", async () => {
    const mockResult = {
      imported_count: 95,
      skipped_count: 5,
      warnings: [
        { row_index: 10, message: "Unknown entity type(s): PRODUCT" },
        { row_index: 20, message: "Unknown entity type(s): FOO" },
      ],
      entity_type_counts: { PER: 50, ORG: 45 },
    };

    mockAuthFetch.mockResolvedValueOnce({
      ok: true,
      status: 201,
      json: () => Promise.resolve(mockResult),
    });

    const { result } = renderHook(() => useAnnotationImport());

    await act(async () => {
      await result.current.importAnnotations(makeFile());
    });

    const state = result.current.state;
    expect(state.status).toBe("success");
    if (state.status === "success") {
      expect(state.result.imported_count).toBe(95);
      expect(state.result.skipped_count).toBe(5);
      expect(state.result.warnings).toHaveLength(2);
    }
  });

  it("handles 413 file too large error", async () => {
    mockAuthFetch.mockResolvedValueOnce({
      ok: false,
      status: 413,
      json: () => Promise.resolve({ detail: { message: "File exceeds maximum size of 50MB" } }),
    });

    const { result } = renderHook(() => useAnnotationImport());

    await act(async () => {
      await result.current.importAnnotations(makeFile());
    });

    expect(result.current.state).toEqual({
      status: "error",
      error: "File exceeds maximum size of 50MB",
    });
  });

  it("handles 415 unsupported media type error", async () => {
    mockAuthFetch.mockResolvedValueOnce({
      ok: false,
      status: 415,
      json: () => Promise.resolve({ detail: { message: "Unsupported MIME type: application/pdf" } }),
    });

    const { result } = renderHook(() => useAnnotationImport());

    await act(async () => {
      await result.current.importAnnotations(makeFile());
    });

    expect(result.current.state).toEqual({
      status: "error",
      error: "Unsupported MIME type: application/pdf",
    });
  });

  it("handles network failure", async () => {
    mockAuthFetch.mockRejectedValueOnce(new Error("Network failure"));

    const { result } = renderHook(() => useAnnotationImport());

    await act(async () => {
      await result.current.importAnnotations(makeFile());
    });

    expect(result.current.state).toEqual({
      status: "error",
      error: "Network error. Please try again.",
    });
  });

  it("reset returns to idle state", async () => {
    const { result } = renderHook(() => useAnnotationImport());

    await act(async () => {
      result.current.reset();
    });

    expect(result.current.state).toEqual({ status: "idle" });
  });
});
