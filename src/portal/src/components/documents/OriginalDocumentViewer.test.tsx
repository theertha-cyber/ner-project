import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { OriginalDocumentViewer } from "./OriginalDocumentViewer";

/**
 * jsdom has no canvas and no PDF engine, so pdf.js is mocked at the module boundary. What
 * remains testable is everything that decides *what* is rendered — which page is asked
 * for, which unavailable message is shown, and whether the panel behaves as a dialog. The
 * rendering itself is verified in a real browser.
 */

const mockFetch = vi.fn();
vi.mock("@/lib/auth-fetch", () => ({
  authFetch: (url: string, init?: RequestInit) => mockFetch(url, init),
}));

const renderPage = vi.fn();

vi.mock("@/lib/pdf", () => ({
  loadPdfjs: async () => ({
    getDocument: () => ({
      promise: Promise.resolve({
        numPages: 5,
        destroy: vi.fn(),
        getPage: async (n: number) => {
          renderPage(n);
          return {
            getViewport: () => ({ width: 600, height: 800, scale: 1.5, convertToViewportPoint: () => [10, 20] }),
            render: () => ({ promise: Promise.resolve() }),
          };
        },
      }),
    }),
  }),
  PDF_WORKER_PATH: "pdfjs-dist/build/pdf.worker.min.mjs",
}));

function probe(overrides: Record<string, unknown> = {}) {
  return {
    ok: true,
    status: 200,
    json: () =>
      Promise.resolve({
        document_id: "doc-1",
        filename: "resume.pdf",
        media_type: "application/pdf",
        render_mode: "pdf",
        file_size: 2048,
        retention_mode: "platform_blob",
        available: true,
        reason: null,
        message: null,
        ...overrides,
      }),
  };
}

function bytes(type = "application/pdf") {
  return {
    ok: true,
    status: 200,
    blob: () => Promise.resolve(new Blob(["%PDF"], { type })),
    json: () => Promise.resolve({}),
  };
}

beforeEach(() => {
  mockFetch.mockReset();
  renderPage.mockReset();
  globalThis.URL.createObjectURL = vi.fn(() => "blob:mock/1");
  globalThis.URL.revokeObjectURL = vi.fn();
  // jsdom implements neither.
  HTMLCanvasElement.prototype.getContext = vi.fn(() => ({})) as never;
});

function open(props: Partial<React.ComponentProps<typeof OriginalDocumentViewer>> = {}) {
  return render(
    <OriginalDocumentViewer documentId="doc-1" onClose={vi.fn()} {...props} />,
  );
}

describe("rendering the document at the cited page", () => {
  it("opens at the page the citation identified", async () => {
    mockFetch.mockResolvedValueOnce(probe()).mockResolvedValueOnce(bytes());

    open({ pageNumber: 4 });

    await waitFor(() => expect(renderPage).toHaveBeenCalledWith(4));
  });

  it("opens at the first page when the citation carried none", async () => {
    mockFetch.mockResolvedValueOnce(probe()).mockResolvedValueOnce(bytes());

    open({ pageNumber: null });

    await waitFor(() => expect(renderPage).toHaveBeenCalledWith(1));
  });

  it("does not mark anything on the page", async () => {
    // Removed deliberately. A citation's snippet is often most of the document, so
    // matching page text against it lit up nearly everything. A highlight that is
    // usually wrong is worse than none: it points the reader somewhere confidently and
    // incorrectly.
    mockFetch.mockResolvedValueOnce(probe()).mockResolvedValueOnce(bytes());

    open({ pageNumber: 1 });

    await waitFor(() => expect(screen.getByTestId("pdf-canvas")).toBeInTheDocument());
    expect(screen.queryAllByTestId("pdf-highlight")).toHaveLength(0);
    expect(document.querySelectorAll("[class*='yellow']")).toHaveLength(0);
  });

  it("renders an image document as an image", async () => {
    mockFetch
      .mockResolvedValueOnce(probe({ media_type: "image/png", render_mode: "image", filename: "scan.png" }))
      .mockResolvedValueOnce(bytes("image/png"));

    open();

    await waitFor(() => expect(screen.getByRole("img", { name: "scan.png" })).toBeInTheDocument());
    expect(screen.queryByTestId("pdf-canvas")).not.toBeInTheDocument();
  });

  it("renders a converted document through the same PDF path", async () => {
    mockFetch
      .mockResolvedValueOnce(probe({ render_mode: "convert", filename: "cv.docx" }))
      .mockResolvedValueOnce(bytes());

    open({ pageNumber: 2 });

    await waitFor(() => expect(renderPage).toHaveBeenCalledWith(2));
    expect(screen.getByTestId("pdf-canvas")).toBeInTheDocument();
  });

  it("offers page navigation for a multi-page document", async () => {
    mockFetch.mockResolvedValueOnce(probe()).mockResolvedValueOnce(bytes());

    open({ pageNumber: 2 });

    await waitFor(() => expect(screen.getByTestId("page-indicator")).toHaveTextContent("2 / 5"));
    await userEvent.click(screen.getByRole("button", { name: /next page/i }));
    await waitFor(() => expect(renderPage).toHaveBeenCalledWith(3));
  });
});

describe("stating why a document cannot be shown", () => {
  it("explains a released original as permanent and offers no retry", async () => {
    mockFetch.mockResolvedValueOnce(
      probe({
        available: false,
        reason: "ORIGINAL_RELEASED",
        message: "The original was not retained after processing.",
      }),
    );

    open();

    await waitFor(() =>
      expect(screen.getByTestId("unavailable-code")).toHaveTextContent("ORIGINAL_RELEASED"),
    );
    expect(screen.queryByRole("button", { name: /try again/i })).not.toBeInTheDocument();
  });

  it("invites a retry for an unreachable source", async () => {
    mockFetch.mockResolvedValueOnce(
      probe({ available: false, reason: "SOURCE_UNAVAILABLE", message: "The source could not be reached." }),
    );

    open();

    await waitFor(() => expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument());
  });

  it("distinguishes a failed conversion from a missing original", async () => {
    mockFetch.mockResolvedValueOnce(
      probe({ available: false, reason: "CONVERSION_FAILED", message: "Could not be prepared for display." }),
    );

    open();

    await waitFor(() =>
      expect(screen.getByTestId("unavailable-message")).toHaveTextContent("prepared for display"),
    );
    expect(screen.getByTestId("unavailable-code")).not.toHaveTextContent("ORIGINAL_RELEASED");
  });

  it("offers the extracted text, labelled as extracted text", async () => {
    mockFetch
      .mockResolvedValueOnce(probe({ available: false, reason: "ORIGINAL_RELEASED", message: "Gone." }))
      .mockResolvedValueOnce({ ok: true, status: 200, json: () => Promise.resolve({ text: "extracted body" }) });

    open();

    await userEvent.click(await screen.findByRole("button", { name: /show extracted text/i }));

    expect(await screen.findByText(/extracted body/)).toBeInTheDocument();
    expect(screen.getByText(/not the original document/i)).toBeInTheDocument();
  });
});

describe("dialog behaviour", () => {
  it("is exposed as a modal dialog naming the document", async () => {
    mockFetch.mockResolvedValueOnce(probe()).mockResolvedValueOnce(bytes());

    open();

    const dialog = await screen.findByRole("dialog");
    expect(dialog).toHaveAttribute("aria-modal", "true");
    await waitFor(() => expect(screen.getByRole("heading", { name: "resume.pdf" })).toBeInTheDocument());
  });

  it("closes on Escape", async () => {
    mockFetch.mockResolvedValueOnce(probe()).mockResolvedValueOnce(bytes());
    const onClose = vi.fn();

    open({ onClose });
    await screen.findByRole("dialog");

    await userEvent.keyboard("{Escape}");

    expect(onClose).toHaveBeenCalled();
  });

  it("closes from the close control", async () => {
    mockFetch.mockResolvedValueOnce(probe()).mockResolvedValueOnce(bytes());
    const onClose = vi.fn();

    open({ onClose });

    await userEvent.click(await screen.findByRole("button", { name: /close document/i }));

    expect(onClose).toHaveBeenCalled();
  });

  it("shows nothing but the document", async () => {
    // No snippet banner: it duplicated text already visible in the answer the chip sits
    // under, and took vertical space from the page itself.
    mockFetch.mockResolvedValueOnce(probe()).mockResolvedValueOnce(bytes());

    open();

    await waitFor(() => expect(screen.getByTestId("pdf-canvas")).toBeInTheDocument());
    expect(screen.queryByText(/five years of Python/)).not.toBeInTheDocument();
  });
});
