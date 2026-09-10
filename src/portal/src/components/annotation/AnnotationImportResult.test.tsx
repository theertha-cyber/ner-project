import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { AnnotationImportResult } from "./AnnotationImportResult";

vi.mock("@/components/ui", () => ({
  SlideOver: ({ open, children }: { open: boolean; children: React.ReactNode }) =>
    open ? <div data-testid="slide-over">{children}</div> : null,
  Spinner: () => <div data-testid="spinner" />,
}));

vi.mock("@/hooks/use-entity-types", () => ({
  useEntityTypes: () => ({ data: { entity_types: [{ name: "job_title" }] } }),
}));

const typeMapMutate = vi.fn();
vi.mock("@/hooks/use-import-type-map", () => ({
  useImportTypeMap: () => ({
    mutate: typeMapMutate,
    isPending: false,
    isSuccess: false,
    isError: false,
    data: undefined,
    error: null,
  }),
}));

describe("AnnotationImportResult", () => {
  it("shows uploading spinner", () => {
    render(
      <AnnotationImportResult
        open={true}
        state={{ status: "uploading" }}
        onDone={vi.fn()}
      />,
    );
    expect(screen.getByTestId("spinner")).toBeInTheDocument();
    expect(screen.getByText("Importing...")).toBeInTheDocument();
  });

  it("shows success with no skips", () => {
    render(
      <AnnotationImportResult
        open={true}
        state={{
          status: "success",
          result: {
            imported_count: 200,
            skipped_count: 0,
            warnings: [],
            entity_type_counts: { PER: 100, ORG: 100 },
          },
        }}
        onDone={vi.fn()}
      />,
    );
    expect(screen.getByText("200 rows imported")).toBeInTheDocument();
    expect(screen.getByText("PER: 100")).toBeInTheDocument();
    expect(screen.getByText("ORG: 100")).toBeInTheDocument();
  });

  it("shows success with rows held for type mapping", () => {
    render(
      <AnnotationImportResult
        open={true}
        state={{
          status: "success",
          result: {
            source_file: "g.jsonl",
            imported_count: 195,
            pending_count: 5,
            unmapped_types: [{ type: "PRODUCT", row_count: 5 }],
            skipped_count: 5,
            warnings: [],
            entity_type_counts: { PER: 195 },
          },
        }}
        onDone={vi.fn()}
      />,
    );
    expect(screen.getByText(/195 rows imported, 5 held for type mapping/)).toBeInTheDocument();
    expect(screen.getByText("PRODUCT")).toBeInTheDocument();
  });

  it("shows error state", () => {
    render(
      <AnnotationImportResult
        open={true}
        state={{ status: "error", error: "File exceeds the 50MB maximum" }}
        onDone={vi.fn()}
      />,
    );
    expect(screen.getByText("File exceeds the 50MB maximum")).toBeInTheDocument();
  });

  it("calls onDone when Done button is clicked", () => {
    const onDone = vi.fn();
    render(
      <AnnotationImportResult
        open={true}
        state={{
          status: "success",
          result: {
            imported_count: 200,
            skipped_count: 0,
            warnings: [],
            entity_type_counts: {},
          },
        }}
        onDone={onDone}
      />,
    );
    fireEvent.click(screen.getByText("Done"));
    expect(onDone).toHaveBeenCalled();
  });

  it("does not show Done button while uploading", () => {
    render(
      <AnnotationImportResult
        open={true}
        state={{ status: "uploading" }}
        onDone={vi.fn()}
      />,
    );
    expect(screen.queryByText("Done")).not.toBeInTheDocument();
  });

  it("shows the unmapped-type mapping form and submits a mapping", () => {
    typeMapMutate.mockClear();
    render(
      <AnnotationImportResult
        open={true}
        state={{
          status: "success",
          result: {
            source_file: "gold.jsonl",
            imported_count: 8,
            pending_count: 2,
            unmapped_types: [{ type: "JOB_TITLE", row_count: 2 }],
            skipped_count: 2,
            warnings: [],
            entity_type_counts: {},
          },
        }}
        onDone={vi.fn()}
      />,
    );
    expect(screen.getByText("1 entity type not defined yet")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Map JOB_TITLE"), { target: { value: "job_title" } });
    fireEvent.click(screen.getByText("Map types"));
    expect(typeMapMutate).toHaveBeenCalledWith({
      sourceFile: "gold.jsonl",
      mapping: { JOB_TITLE: { to: "job_title" } },
    });
  });
});
