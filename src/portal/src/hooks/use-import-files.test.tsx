import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useImportFiles } from "./use-import-files";

const mockFetch = vi.fn();
globalThis.fetch = mockFetch;

function createWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  };
}

describe("useImportFiles", () => {
  beforeEach(() => mockFetch.mockReset());

  it("loads the imported-files list", async () => {
    mockFetch.mockResolvedValue(
      new Response(
        JSON.stringify({
          files: [
            { source_file: "g.jsonl", row_count: 40, type_map: {}, training_eligible: true, training_eligible_at: "x", pending_count: 0, reviewed_count: 5 },
          ],
        }),
        { status: 200 },
      ),
    );
    const { result } = renderHook(() => useImportFiles(true), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(String(mockFetch.mock.calls[0][0])).toContain("/api/v1/annotation-imports");
    expect(result.current.data?.files[0].training_eligible).toBe(true);
  });

  it("does not fetch when disabled", () => {
    renderHook(() => useImportFiles(false), { wrapper: createWrapper() });
    expect(mockFetch).not.toHaveBeenCalled();
  });
});
