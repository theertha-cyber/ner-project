import { describe, it, expect, vi, beforeEach } from "vitest";
import { render } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

const mockRouterPush = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: vi.fn(() => ({ push: mockRouterPush })),
}));

let mockRole = "tenant_admin";
vi.mock("@/lib/auth", () => ({
  useAuth: vi.fn(() => ({ user: { role: mockRole } })),
}));

vi.mock("@/hooks/use-import-files", () => ({
  useImportFiles: vi.fn(() => ({ data: { files: [] } })),
}));

const mockTypeMapMutate = vi.fn();
vi.mock("@/hooks/use-import-type-map", () => ({
  useImportTypeMap: vi.fn(() => ({
    mutate: mockTypeMapMutate,
    isPending: false,
    isError: false,
    error: null,
  })),
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

import { useImportFiles } from "@/hooks/use-import-files";
import { ImportedDocumentsList } from "./ImportedDocuments";

function renderList() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <ImportedDocumentsList onSelectRow={vi.fn()} />
    </QueryClientProvider>,
  );
}

describe("ImportedDocumentsList — file picker only opens on an explicit click", () => {
  beforeEach(() => {
    mockRole = "tenant_admin";
    mockRouterPush.mockReset();
    mockFetch.mockReset();
    mockFetch.mockResolvedValue(
      new Response(JSON.stringify({ items: [], total: 0, page: 1, per_page: 20 }), { status: 200 }),
    );
  });

  it("never auto-opens the file picker on mount, regardless of how the page was reached", () => {
    const clickSpy = vi.spyOn(HTMLInputElement.prototype, "click").mockImplementation(() => {});

    renderList();

    expect(clickSpy).not.toHaveBeenCalled();
    clickSpy.mockRestore();
  });

  it("opens the file picker when the tenant admin clicks Import file", () => {
    const clickSpy = vi.spyOn(HTMLInputElement.prototype, "click").mockImplementation(() => {});

    const { getByText } = renderList();
    getByText("Import file").click();

    expect(clickSpy).toHaveBeenCalled();
    clickSpy.mockRestore();
  });
});

describe("ImportedDocumentsList — accept all as new types", () => {
  beforeEach(() => {
    mockRole = "tenant_admin";
    mockTypeMapMutate.mockReset();
    mockFetch.mockReset();
    mockFetch.mockResolvedValue(
      new Response(JSON.stringify({ items: [], total: 0, page: 1, per_page: 20 }), { status: 200 }),
    );
    vi.mocked(useImportFiles).mockReturnValue({
      data: {
        files: [
          {
            source_file: "legacy.jsonl",
            row_count: 3,
            type_map: {},
            training_eligible: false,
            training_eligible_at: null,
            pending_count: 3,
            reviewed_count: 0,
            unmapped_types: [
              { type: "NAME", row_count: 3 },
              { type: "EMAIL", row_count: 2 },
            ],
          },
        ],
      },
    } as ReturnType<typeof useImportFiles>);
  });

  it("submits every unmapped type as a create-new mapping in one call", () => {
    const { getByRole } = renderList();

    getByRole("button", { name: "Accept all as new types" }).click();

    expect(mockTypeMapMutate).toHaveBeenCalledWith({
      sourceFile: "legacy.jsonl",
      mapping: { NAME: { create: true }, EMAIL: { create: true } },
    });
  });
});

describe("ImportedDocumentsList — training-eligible files hand off to Models & Training", () => {
  beforeEach(() => {
    mockRole = "tenant_admin";
    mockRouterPush.mockReset();
    mockFetch.mockReset();
    mockFetch.mockResolvedValue(
      new Response(JSON.stringify({ items: [], total: 0, page: 1, per_page: 20 }), { status: 200 }),
    );
    vi.mocked(useImportFiles).mockReturnValue({
      data: {
        files: [
          {
            source_file: "clean.jsonl",
            row_count: 5,
            type_map: {},
            training_eligible: true,
            training_eligible_at: "2026-09-14T00:00:00Z",
            pending_count: 0,
            reviewed_count: 0,
            unmapped_types: [],
          },
        ],
      },
    } as unknown as ReturnType<typeof useImportFiles>);
  });

  it("routes straight to Models & Training scoped to the import source — no approval request", () => {
    const { getByRole } = renderList();

    getByRole("button", { name: "Train model" }).click();

    expect(mockRouterPush).toHaveBeenCalledWith("/training-jobs?source=import");
  });
});
