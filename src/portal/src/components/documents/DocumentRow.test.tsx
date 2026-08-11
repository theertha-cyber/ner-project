import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { DocumentRow } from "./DocumentRow";

vi.mock("@/components/ui", () => ({
  Badge: ({ variant, label }: { variant: string; label?: string }) => (
    <span data-variant={variant}>{label ?? variant}</span>
  ),
}));

const baseDoc = {
  id: "doc-1",
  filename: "test.pdf",
  content_type: "application/pdf",
  file_size: 102400,
  created_at: "2026-06-25T10:00:00Z",
};

describe("DocumentRow", () => {
  it("renders document filename", () => {
    render(<DocumentRow doc={{ ...baseDoc, status: "processed" }} onDelete={vi.fn()} />);
    expect(screen.getByText("test.pdf")).toBeDefined();
  });

  it("renders processing badge with pulse indicator", () => {
    const { container } = render(
      <DocumentRow doc={{ ...baseDoc, status: "processing" }} onDelete={vi.fn()} />,
    );
    const pulseDot = container.querySelector(".animate-pulse");
    expect(pulseDot).not.toBeNull();
  });

  it("renders deleted badge with muted variant", () => {
    render(<DocumentRow doc={{ ...baseDoc, status: "deleted" }} onDelete={vi.fn()} />);
    const badge = screen.getByText("deleted");
    expect(badge.getAttribute("data-variant")).toBe("cancelled");
  });

  it("does not show pulse dot for processed status", () => {
    const { container } = render(
      <DocumentRow doc={{ ...baseDoc, status: "processed" }} onDelete={vi.fn()} />,
    );
    expect(container.querySelector(".animate-pulse")).toBeNull();
  });

  it("shows uploader email and purpose instead of type and size", () => {
    render(
      <DocumentRow
        doc={{
          ...baseDoc,
          status: "processed",
          purpose: "training",
          uploaded_by: "user-1",
          uploaded_by_email: "admin@acme.test",
        }}
        onDelete={vi.fn()}
      />,
    );
    expect(screen.getByText("admin@acme.test")).toBeDefined();
    expect(screen.getByText("Annotation")).toBeDefined();
    expect(screen.queryByText("PDF")).toBeNull();
    expect(screen.queryByText("100.0 KB")).toBeNull();
  });

  it("labels query-purpose documents Query", () => {
    render(
      <DocumentRow
        doc={{ ...baseDoc, status: "processed", purpose: "query", uploaded_by_email: "bu@acme.test" }}
        onDelete={vi.fn()}
      />,
    );
    expect(screen.getByText("Query")).toBeDefined();
  });

  it("falls back to a dash when uploader or purpose is unknown", () => {
    render(<DocumentRow doc={{ ...baseDoc, status: "processed" }} onDelete={vi.fn()} />);
    expect(screen.getAllByText("—").length).toBe(2);
  });
});
