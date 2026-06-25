import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useUpload } from "./use-upload";

let mockGetAccessToken = vi.fn(() => "mock-token");
let originalXHR: typeof globalThis.XMLHttpRequest;

vi.mock("@/lib/auth", () => ({
  useAuth: vi.fn(() => ({
    getAccessToken: () => mockGetAccessToken(),
  })),
}));

vi.mock("@/lib/api", () => ({
  DOCUMENT_URL: "",
}));

function createWrapper() {
  const qc = new QueryClient();
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  };
}

describe("useUpload", () => {
  beforeEach(() => {
    mockGetAccessToken = vi.fn(() => "mock-token");
    originalXHR = globalThis.XMLHttpRequest;
  });

  afterEach(() => {
    globalThis.XMLHttpRequest = originalXHR;
  });

  function mockXhrFactory(status: number, responseText: string) {
    const instance: any = {
      upload: { onprogress: null },
      onload: null,
      onerror: null,
      open: vi.fn(),
      setRequestHeader: vi.fn(),
      send: vi.fn(),
      status,
      responseText,
    };
    globalThis.XMLHttpRequest = vi.fn(() => instance) as any;
    return instance;
  }

  it("exposes expected interface", () => {
    void mockXhrFactory(200, "");
    const { result } = renderHook(() => useUpload(), { wrapper: createWrapper() });
    expect(result.current.upload).toBeInstanceOf(Function);
    expect(result.current.reset).toBeInstanceOf(Function);
    expect(typeof result.current.progress).toBe("number");
    expect(typeof result.current.isUploading).toBe("boolean");
  });

  it("calls XMLHttpRequest with auth header", async () => {
    const xhrInstance = mockXhrFactory(201, JSON.stringify({ id: "doc-1" }));
    const { result } = renderHook(() => useUpload(), { wrapper: createWrapper() });
    const file = new File(["content"], "test.pdf", { type: "application/pdf" });

    await act(async () => {
      const p = result.current.upload(file);
      xhrInstance.onload();
      await p;
    });

    expect(xhrInstance.open).toHaveBeenCalledWith("POST", "/api/v1/documents");
    expect(xhrInstance.setRequestHeader).toHaveBeenCalledWith("Authorization", "Bearer mock-token");
  });

  it("sets progress via onprogress event", async () => {
    const xhrInstance = mockXhrFactory(201, JSON.stringify({ id: "doc-1" }));
    const { result } = renderHook(() => useUpload(), { wrapper: createWrapper() });
    const file = new File(["content"], "test.pdf", { type: "application/pdf" });
    const uploadPromise = result.current.upload(file);

    act(() => {
      xhrInstance.upload.onprogress({
        lengthComputable: true,
        loaded: 50,
        total: 100,
      });
    });

    expect(result.current.progress).toBe(50);

    await act(async () => {
      xhrInstance.onload();
      await uploadPromise;
    });

    expect(result.current.progress).toBe(100);
    expect(result.current.isUploading).toBe(false);
  });

  it("reports error on non-201 response", async () => {
    const xhrInstance = mockXhrFactory(413, JSON.stringify({ detail: "File too large" }));
    const { result } = renderHook(() => useUpload(), { wrapper: createWrapper() });
    const file = new File(["content"], "big.pdf", { type: "application/pdf" });

    await act(async () => {
      const p = result.current.upload(file);
      xhrInstance.onload();
      try {
        await p;
      } catch {}
    });

    expect(result.current.error).toContain("File too large");
    expect(result.current.isUploading).toBe(false);
  });

  it("reset clears state", () => {
    const xhrInstance = mockXhrFactory(200, "");
    const { result } = renderHook(() => useUpload(), { wrapper: createWrapper() });
    act(() => {
      result.current.reset();
    });
    expect(result.current.progress).toBe(0);
    expect(result.current.isUploading).toBe(false);
    expect(result.current.error).toBeNull();
  });
});
