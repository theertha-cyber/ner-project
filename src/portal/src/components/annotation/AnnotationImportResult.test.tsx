import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { AnnotationImportResult } from "./AnnotationImportResult";

vi.mock("@/components/ui", () => ({
  SlideOver: ({ open, children }: { open: boolean; children: React.ReactNode }) =>
    open ? <div data-testid="slide-over">{children}</div> : null,
  Spinner: () => <div data-testid="spinner" />,
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

  it("shows success with skips and warnings", () => {
    render(
      <AnnotationImportResult
        open={true}
        state={{
          status: "success",
          result: {
            imported_count: 195,
            skipped_count: 5,
            warnings: [
              { row_index: 10, message: "Unknown entity type(s): PRODUCT" },
            ],
            entity_type_counts: { PER: 195 },
          },
        }}
        onDone={vi.fn()}
      />,
    );
    expect(screen.getByText(/195 rows imported, 5 rows skipped/)).toBeInTheDocument();
    expect(screen.getByText(/Row 10/)).toBeInTheDocument();
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
});
