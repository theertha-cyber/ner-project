import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CitationChips } from "./CitationChips";

/**
 * The viewer itself is covered by its own suite; here the question is only which chip
 * opens what, and that the detail card people already rely on did not disappear when the
 * chip gained a second job.
 */

const viewerProps = vi.fn();
vi.mock("@/components/documents/OriginalDocumentViewer", () => ({
  OriginalDocumentViewer: (props: Record<string, unknown>) => {
    viewerProps(props);
    return props.documentId ? (
      <div data-testid="viewer">viewing {String(props.documentId)}</div>
    ) : null;
  },
}));

const DOC_CITATION = {
  document_name: "resume.pdf",
  document_id: "doc-1",
  page_number: 3,
  context_snippet: "five years of Python",
  relevance_score: 0.9,
};

const SQL_CITATION = {
  entity_type: "ORG",
  entity_value: "Acme",
  source_type: "sql",
};

beforeEach(() => {
  viewerProps.mockReset();
});

describe("a chip that names a document", () => {
  it("opens the viewer on that document", async () => {
    render(<CitationChips citations={[DOC_CITATION]} />);

    await userEvent.click(screen.getByRole("button", { name: /open document resume.pdf/i }));

    expect(await screen.findByTestId("viewer")).toHaveTextContent("doc-1");
  });

  it("passes the cited page through", async () => {
    render(<CitationChips citations={[DOC_CITATION]} />);

    await userEvent.click(screen.getByRole("button", { name: /open document resume.pdf/i }));

    await waitFor(() =>
      expect(viewerProps).toHaveBeenCalledWith(
        expect.objectContaining({
          documentId: "doc-1",
          pageNumber: 3,
        }),
      ),
    );
  });

  it("keeps the citation detail reachable", async () => {
    render(<CitationChips citations={[DOC_CITATION]} />);

    await userEvent.click(
      screen.getByRole("button", { name: /show citation details for resume.pdf/i }),
    );

    expect(screen.getByText(/relevance/i)).toBeInTheDocument();
    expect(screen.queryByTestId("viewer")).not.toBeInTheDocument();
  });
});

describe("a chip with no document", () => {
  it("reveals its details instead of opening a viewer", async () => {
    render(<CitationChips citations={[SQL_CITATION]} />);

    await userEvent.click(screen.getByRole("button", { name: "Source" }));

    expect(screen.queryByTestId("viewer")).not.toBeInTheDocument();
    expect(screen.getByText(/Acme/)).toBeInTheDocument();
  });

  it("offers no open affordance at all", () => {
    render(<CitationChips citations={[SQL_CITATION]} />);

    expect(screen.queryByRole("button", { name: /open document/i })).not.toBeInTheDocument();
  });
});

describe("one viewer per message", () => {
  it("shows the most recently opened document, never two viewers", async () => {
    render(
      <CitationChips
        citations={[
          DOC_CITATION,
          { document_name: "other.pdf", document_id: "doc-2", page_number: 1 },
        ]}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: /open document resume.pdf/i }));
    await userEvent.click(screen.getByRole("button", { name: /open document other.pdf/i }));

    const viewers = screen.getAllByTestId("viewer");
    expect(viewers).toHaveLength(1);
    expect(viewers[0]).toHaveTextContent("doc-2");
  });

  it("renders nothing until a chip is activated", () => {
    render(<CitationChips citations={[DOC_CITATION]} />);
    expect(screen.queryByTestId("viewer")).not.toBeInTheDocument();
  });
});
