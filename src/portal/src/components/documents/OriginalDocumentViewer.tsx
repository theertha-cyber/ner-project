"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ChevronLeft, ChevronRight, FileWarning, Loader2, RefreshCw, X } from "lucide-react";

import { SlideOver } from "@/components/ui/slide-over";
import { PdfPage } from "@/components/documents/PdfPage";
import { isRetryable, useOriginalDocument } from "@/hooks/use-original-document";

/**
 * Shows the original document behind a citation or attachment chip.
 *
 * Lives under `components/documents/` rather than `components/chat/` because nothing
 * about it is chat-specific — the Documents library is the obvious second caller.
 *
 * The panel shows the document and almost nothing else. An earlier version also carried
 * the citation's snippet across the top and marked the matching passage in the page; both
 * were removed. The snippet duplicated text already visible in the answer, and the
 * highlight was usually wrong because a citation's snippet is often most of the document.
 * What remains is the page the answer came from.
 *
 * Formats a browser cannot render are converted to PDF by the server, so they arrive here
 * as PDFs and take the same path — one rendering path in the client, not a per-format
 * matrix.
 */

export interface OriginalDocumentViewerProps {
  documentId: string | null;
  /** The page the citation pointed at, 1-based. Null when the citation carried none. */
  pageNumber?: number | null;
  /** Falls back to the server-reported filename; used before the probe returns. */
  documentName?: string | null;
  onClose: () => void;
}

const PANEL_MAX_WIDTH = 940;

function useViewerWidth() {
  const [width, setWidth] = useState(PANEL_MAX_WIDTH);
  useEffect(() => {
    if (typeof window === "undefined") return;
    setWidth(Math.min(PANEL_MAX_WIDTH, Math.round(window.innerWidth * 0.94)));
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
      className="flex flex-1 flex-col items-center justify-center gap-4 px-8 text-center"
    >
      <FileWarning className="h-7 w-7 text-ink-3/70" aria-hidden="true" />
      <p className="max-w-sm text-[13.5px] leading-relaxed text-ink-2" data-testid="unavailable-message">
        {message}
      </p>
      <p className="font-mono text-[11px] uppercase tracking-wider text-ink-3/70" data-testid="unavailable-code">
        {code}
      </p>
      <div className="mt-1 flex gap-2">
        {/* Offered only when retrying could change the outcome. A released original is
            gone under the tenant's own retention policy; inviting a retry would be a lie. */}
        {retryable && (
          <button
            type="button"
            onClick={onRetry}
            className="inline-flex items-center gap-1.5 rounded-lg border border-line px-3 py-1.5 text-[13px] text-ink-1 transition-colors hover:bg-surface-2"
          >
            <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
            Try again
          </button>
        )}
        <button
          type="button"
          onClick={onShowText}
          className="rounded-lg border border-line px-3 py-1.5 text-[13px] text-ink-1 transition-colors hover:bg-surface-2"
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
    return <p className="p-8 text-center text-sm text-ink-3">No extracted text is available either.</p>;
  }
  if (text === null) {
    return <p className="p-8 text-center text-sm text-ink-3">Loading extracted text…</p>;
  }
  return (
    <div className="flex-1 overflow-auto px-8 py-6">
      {/* Labelled as extracted text, not presented as the document: it has no layout, and
          a reader checking a citation needs to know which one they are looking at. */}
      <p className="mb-4 text-[11px] uppercase tracking-wider text-ink-3">
        Extracted text — not the original document
      </p>
      <pre className="whitespace-pre-wrap break-words font-sans text-[13.5px] leading-relaxed text-ink-1">
        {text}
      </pre>
    </div>
  );
}

export function OriginalDocumentViewer({
  documentId,
  pageNumber,
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

  const citedPage = pageNumber && pageNumber > 0 ? pageNumber : 1;
  const [page, setPage] = useState(citedPage);
  const [pageCount, setPageCount] = useState<number | null>(null);

  useEffect(() => {
    setPage(citedPage);
    setPageCount(null);
  }, [documentId, citedPage]);

  // Stable identity: `PdfPage` takes this in a dependency array, and a new function each
  // render would re-open the document on every keystroke elsewhere in the tree.
  const handlePageCount = useCallback((count: number) => setPageCount(count), []);

  const multiPage = pageCount !== null && pageCount > 1;

  return (
    <SlideOver open={documentId !== null} onClose={onClose} width={width}>
      <div className="flex h-full flex-col bg-surface-2">
        <header className="flex items-center justify-between gap-4 border-b border-line/60 bg-surface-1/80 px-5 py-3 backdrop-blur">
          <div className="min-w-0">
            <h2 className="truncate text-[13.5px] font-medium tracking-tight text-ink-1" title={title}>
              {title}
            </h2>
            {pageCount !== null && (
              <p className="mt-0.5 text-[11.5px] text-ink-3">
                {pageCount === 1 ? "1 page" : `${pageCount} pages`}
              </p>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close document"
            className="-mr-1 shrink-0 rounded-lg p-1.5 text-ink-3 transition-colors hover:bg-surface-2 hover:text-ink-1"
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        </header>

        {state.status === "loading" && (
          <div className="flex flex-1 items-center justify-center gap-2 text-[13px] text-ink-3">
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
          <div className="flex-1 overflow-auto p-6">
            <img
              src={state.url}
              alt={title}
              className="mx-auto max-w-full rounded-md shadow-sm ring-1 ring-black/5"
            />
          </div>
        )}

        {state.status === "ready" && state.renderMode !== "image" && (
          <div className="relative flex-1 overflow-auto">
            <div className="px-6 py-6">
              <PdfPage url={state.url} pageNumber={page} onPageCount={handlePageCount} />
            </div>

            {/* Floating rather than a fixed bar: the page is the content, and a bordered
                strip across the bottom would take height from it on every document,
                including the single-page ones that need no navigation at all. */}
            {multiPage && (
              <nav
                aria-label="Document pages"
                className="pointer-events-none sticky bottom-4 flex justify-center"
              >
                <div className="pointer-events-auto flex items-center gap-1 rounded-full border border-line/60 bg-surface-1/95 px-1.5 py-1 shadow-lg backdrop-blur">
                  <button
                    type="button"
                    onClick={() => setPage((n) => Math.max(1, n - 1))}
                    disabled={page <= 1}
                    aria-label="Previous page"
                    className="rounded-full p-1.5 text-ink-2 transition-colors hover:bg-surface-2 hover:text-ink-1 disabled:pointer-events-none disabled:opacity-35"
                  >
                    <ChevronLeft className="h-4 w-4" aria-hidden="true" />
                  </button>
                  <span
                    data-testid="page-indicator"
                    className="min-w-[4.5rem] text-center text-[12px] tabular-nums text-ink-2"
                  >
                    {page} / {pageCount}
                  </span>
                  <button
                    type="button"
                    onClick={() => setPage((n) => Math.min(pageCount as number, n + 1))}
                    disabled={page >= (pageCount as number)}
                    aria-label="Next page"
                    className="rounded-full p-1.5 text-ink-2 transition-colors hover:bg-surface-2 hover:text-ink-1 disabled:pointer-events-none disabled:opacity-35"
                  >
                    <ChevronRight className="h-4 w-4" aria-hidden="true" />
                  </button>
                </div>
              </nav>
            )}
          </div>
        )}
      </div>
    </SlideOver>
  );
}
