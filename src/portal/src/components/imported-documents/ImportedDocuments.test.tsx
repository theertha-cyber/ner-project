import { describe, it, expect, vi, beforeEach } from "vitest";
import { render } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

let mockSearchParams = new URLSearchParams();
vi.mock("next/navigation", () => ({
  useSearchParams: vi.fn(() => mockSearchParams),
}));

let mockRole = "tenant_admin";
vi.mock("@/lib/auth", () => ({
  useAuth: vi.fn(() => ({ user: { role: mockRole } })),
}));

vi.mock("@/hooks/use-import-files", () => ({
  useImportFiles: vi.fn(() => ({ data: { files: [] } })),
}));

vi.mock("@/hooks/use-retraining", () => ({
  useRequestRetrain: vi.fn(() => ({ mutate: vi.fn(), isPending: false, isSuccess: false })),
}));

vi.mock("@/hooks/use-annotation-import", () => ({
  useAnnotationImport: vi.fn(() => ({
    state: { status: "idle" },
    importAnnotations: vi.fn(),
    reset: vi.fn(),
  })),
}));

vi.mock("@/hooks/use-entity-types", () => ({
  useEntityTypes: vi.fn(() => ({ data: { entity_types: [] } })),
}));

const mockFetch = vi.fn();
globalThis.fetch = mockFetch;

import { ImportedDocumentsList } from "./ImportedDocuments";

function renderList() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <ImportedDocumentsList onSelectRow={vi.fn()} />
    </QueryClientProvider>,
  );
}

describe("ImportedDocumentsList — ?import=1 deep link", () => {
  beforeEach(() => {
    mockSearchParams = new URLSearchParams();
    mockRole = "tenant_admin";
    mockFetch.mockReset();
    mockFetch.mockResolvedValue(
      new Response(JSON.stringify({ items: [], total: 0, page: 1, per_page: 20 }), { status: 200 }),
    );
  });

  it("opens the file picker when linked with ?import=1", () => {
    mockSearchParams = new URLSearchParams("import=1");
    const clickSpy = vi.spyOn(HTMLInputElement.prototype, "click").mockImplementation(() => {});

    renderList();

    expect(clickSpy).toHaveBeenCalled();
    clickSpy.mockRestore();
  });

  it("does not open the file picker with no import parameter", () => {
    const clickSpy = vi.spyOn(HTMLInputElement.prototype, "click").mockImplementation(() => {});

    renderList();

    expect(clickSpy).not.toHaveBeenCalled();
    clickSpy.mockRestore();
  });

  it("does not open the file picker for a role that cannot import", () => {
    mockSearchParams = new URLSearchParams("import=1");
    mockRole = "annotator";
    const clickSpy = vi.spyOn(HTMLInputElement.prototype, "click").mockImplementation(() => {});

    renderList();

    expect(clickSpy).not.toHaveBeenCalled();
    clickSpy.mockRestore();
  });
});
