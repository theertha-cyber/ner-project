"use client";

import { useEffect, useRef, useState } from "react";
import { FileWarning, Loader2, RefreshCw, X } from "lucide-react";

import { SlideOver } from "@/components/ui/slide-over";
import { PdfPage } from "@/components/documents/PdfPage";
import { isRetryable, useOriginalDocument } from "@/hooks/use-original-document";

/**
 * Shows the original document behind a citation or attachment chip.
 *
 * Lives under `components/documents/` rather than `components/chat/` because nothing
 * about it is chat-specific — the Documents library is the obvious second caller, and
 * moving a component after it has tests is more disruptive than placing it well now.
 *
 * PDFs render through pdf.js rather than the browser's built-in viewer, because the
 * built-in one cannot be asked to mark a passage — and marking the passage is the point.
 * A citation says "this answer came from here"; opening the right page and leaving the
 * reader to hunt for the sentence is only half of that. Images render as images.
 *
 * Formats a browser cannot render are converted to PDF by the server, so they arrive here
 * as PDFs and take the same path — which is what keeps one rendering path in the client
 * instead of a per-format matrix.
 */

export interface OriginalDocumentViewerProps {
  documentId: string | null;
  /** The page the citation pointed at, 1-based. Null when the citation carried none. */
  pageNumber?: number | null;
  /** The passage the answer quoted, shown alongside so the reader knows what to look for. */
  contextSnippet?: string | null;
  /** Falls back to the server-reported filename; used before the probe returns. */
  documentName?: string | null;
  onClose: () => void;
}

const PANEL_MAX_WIDTH = 920;

function useViewerWidth() {
  // `SlideOver` takes a pixel width. Read once on open rather than tracking resize: the
  // panel is transient and a mid-read reflow is more disruptive than a stale width.
  const [width, setWidth] = useState(PANEL_MAX_WIDTH);
  useEffect(() => {
    if (typeof window === "undefined") return;
    setWidth(Math.min(PANEL_MAX_WIDTH, Math.round(window.innerWidth * 0.92)));
  }, []);
  return width;
}

function Unavailable({
  code,
  message,
  onRetry,
  onShowText,
}: {
  code: string;
  message: string;
  onRetry: () => void;
  onShowText: () => void;
}) {
  const retryable = isRetryable(code);
  return (
    <div
      role="status"
      className="flex flex-1 flex-col items-center justify-center gap-3 p-8 text-center"
    >
      <FileWarning className="h-8 w-8 text-ink-3" aria-hidden="true" />
      <p className="max-w-sm text-sm text-ink-2" data-testid="unavailable-message">
        {message}
      </p>
      <p className="text-xs text-ink-3" data-testid="unavailable-code">
        {code}
      </p>
      <div className="flex gap-2">
        {/* Offered only when trying again could actually change the outcome. A released
            original is gone under the tenant's own retention policy, and inviting a
            retry there would be a lie. */}
        {retryable && (
          <button
            type="button"
            onClick={onRetry}
            className="inline-flex items-center gap-1.5 rounded border border-line px-3 py-1.5 text-sm"
          >
            <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
            Try again
          </button>
        )}
        <button
          type="button"
          onClick={onShowText}
          className="rounded border border-line px-3 py-1.5 text-sm"
        >
          Show extracted text
        </button>
      </div>
    </div>
  );
}

function ExtractedText({ documentId }: { documentId: string }) {
  const [text, setText] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const { authFetch } = await import("@/lib/auth-fetch");
        const response = await authFetch(`/api/v1/documents/${documentId}/text`);
        if (!response.ok) throw new Error(String(response.status));
        const body = await response.json();
        if (!cancelled) setText(body.text ?? "");
      } catch {
        if (!cancelled) setFailed(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [documentId]);

  if (failed) {
    return <p className="p-6 text-sm text-ink-3">No extracted text is available either.</p>;
  }
  if (text === null) {
    return <p className="p-6 text-sm text-ink-3">Loading extracted text…</p>;
  }
  return (
    <div className="flex-1 overflow-auto p-6">
      {/* Labelled as extracted text, not presented as the document: it has no layout, and
          a reader checking a citation needs to know which one they are looking at. */}
      <p className="mb-3 text-xs uppercase tracking-wide text-ink-3">
        Extracted text — not the original document
      </p>
      <pre className="whitespace-pre-wrap break-words text-sm text-ink-1">{text}</pre>
    </div>
  );
}

export function OriginalDocumentViewer({
  documentId,
  pageNumber,
  contextSnippet,
  documentName,
  onClose,
}: OriginalDocumentViewerProps) {
  const { state, retry } = useOriginalDocument(documentId);
  const [showText, setShowText] = useState(false);
  const width = useViewerWidth();
  const previousDocument = useRef<string | null>(null);

  useEffect(() => {
    if (previousDocument.current !== documentId) {
      setShowText(false);
      previousDocument.current = documentId;
    }
  }, [documentId]);

  const title =
    (state.status !== "idle" ? state.filename : null) ?? documentName ?? "Document";

  // The page the citation pointed at, or the first. pdf.js clamps to the document's real
  // length once it knows it.
  const citedPage = pageNumber && pageNumber > 0 ? pageNumber : 1;
  const [page, setPage] = useState(citedPage);
  const [pageCount, setPageCount] = useState<number | null>(null);

  useEffect(() => {
    setPage(citedPage);
    setPageCount(null);
  }, [documentId, citedPage]);

  return (
    <SlideOver open={documentId !== null} onClose={onClose} width={width}>
      <div className="flex h-full flex-col">
        <header className="flex items-start justify-between gap-3 border-b border-line px-4 py-3">
          <div className="min-w-0">
            <h2 className="truncate text-sm font-semibold text-ink-1" title={title}>
              {title}
            </h2>
            {pageNumber ? (
              <p className="text-xs text-ink-3">Cited on page {pageNumber}</p>
            ) : null}
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close document"
            className="rounded p-1 text-ink-3 hover:text-ink-1"
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        </header>

        {contextSnippet ? (
          <p className="border-b border-line bg-surface-2 px-4 py-2 text-xs italic text-ink-2">
            “{contextSnippet}”
          </p>
        ) : null}

        {state.status === "loading" && (
          <div className="flex flex-1 items-center justify-center gap-2 text-sm text-ink-3">
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
            Loading document…
          </div>
        )}

        {state.status === "unavailable" &&
          (showText && documentId ? (
            <ExtractedText documentId={documentId} />
          ) : (
            <Unavailable
              code={state.code}
              message={state.message}
              onRetry={retry}
              onShowText={() => setShowText(true)}
            />
          ))}

        {state.status === "ready" && state.renderMode === "image" && (
          <div className="flex-1 overflow-auto bg-surface-2 p-4">
            <img src={state.url} alt={title} className="mx-auto max-w-full" />
          </div>
        )}

        {state.status === "ready" && state.renderMode !== "image" && (
          <>
            <div className="flex-1 overflow-auto bg-surface-2 p-4">
              <PdfPage
                url={state.url}
                pageNumber={page}
                highlight={contextSnippet}
                onPageCount={setPageCount}
              />
            </div>
            {pageCount !== null && pageCount > 1 && (
              <nav
                aria-label="Document pages"
                className="flex items-center justify-center gap-3 border-t border-line px-4 py-2 text-sm"
              >
                <button
                  type="button"
                  onClick={() => setPage((n) => Math.max(1, n - 1))}
                  disabled={page <= 1}
                  className="rounded border border-line px-2 py-1 disabled:opacity-40"
                >
                  Previous
                </button>
                <span data-testid="page-indicator" className="text-ink-2">
                  Page {page} of {pageCount}
                </span>
                <button
                  type="button"
                  onClick={() => setPage((n) => Math.min(pageCount, n + 1))}
                  disabled={page >= pageCount}
                  className="rounded border border-line px-2 py-1 disabled:opacity-40"
                >
                  Next
                </button>
              </nav>
            )}
          </>
        )}
      </div>
    </SlideOver>
  );
}
