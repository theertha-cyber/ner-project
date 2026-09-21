"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  ChevronLeft,
  ChevronRight,
  Download,
  FileWarning,
  Loader2,
  Minus,
  Plus,
  RefreshCw,
  X,
} from "lucide-react";

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

/** Another source cited alongside the one currently open, offered as a quick jump. */
export interface DocumentViewerSource {
  documentId: string;
  documentName?: string | null;
  pageNumber?: number | null;
}

export interface OriginalDocumentViewerProps {
  documentId: string | null;
  /** The page the citation pointed at, 1-based. Null when the citation carried none. */
  pageNumber?: number | null;
  /** Falls back to the server-reported filename; used before the probe returns. */
  documentName?: string | null;
  /** Sibling sources from the same answer, excluding the one currently open. */
  otherSources?: DocumentViewerSource[];
  onSelectSource?: (source: DocumentViewerSource) => void;
  onClose: () => void;
}

// A PDF page rendered at 100% zoom is ~600px wide (see PdfPage's RENDER_SCALE); the
// panel only needs to be wide enough to pad that, not fill most of the viewport.
const PANEL_MAX_WIDTH = 680;

const ZOOM_MIN = 0.5;
const ZOOM_MAX = 2;
const ZOOM_STEP = 0.25;

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

// Short label for the meta line, not a MIME-type dump — "PDF", not "application/pdf".
function typeLabel(mediaType: string): string {
  const subtype = mediaType.split("/")[1] ?? mediaType;
  return subtype.split("+")[0].toUpperCase();
}

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
  otherSources,
  onSelectSource,
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
  const [zoom, setZoom] = useState(1);

  useEffect(() => {
    setPage(citedPage);
    setPageCount(null);
    setZoom(1);
  }, [documentId, citedPage]);

  // Stable identity: `PdfPage` takes this in a dependency array, and a new function each
  // render would re-open the document on every keystroke elsewhere in the tree.
  const handlePageCount = useCallback((count: number) => setPageCount(count), []);

  const multiPage = pageCount !== null && pageCount > 1;
  const fileSize = state.status === "ready" ? state.fileSize : null;
  const mediaType = state.status === "ready" ? state.mediaType : null;

  const metaParts: string[] = [];
  if (mediaType) metaParts.push(typeLabel(mediaType));
  if (pageCount !== null) metaParts.push(pageCount === 1 ? "1 page" : `${pageCount} pages`);
  if (fileSize !== null) metaParts.push(formatFileSize(fileSize));

  const canDownload = state.status === "ready";
  const sources = otherSources ?? [];

  return (
    <SlideOver open={documentId !== null} onClose={onClose} width={width}>
      <div className="flex h-full flex-col bg-surface-2">
        <header className="flex items-center justify-between gap-4 border-b border-line/60 bg-surface-1/80 px-5 py-3 backdrop-blur">
          <div className="min-w-0">
            <h2 className="truncate text-[13.5px] font-medium tracking-tight text-ink-1" title={title}>
              {title}
            </h2>
            {metaParts.length > 0 && (
              <p className="mt-0.5 truncate text-[11.5px] text-ink-3">{metaParts.join(" · ")}</p>
            )}
          </div>
          <div className="flex shrink-0 items-center gap-1">
            {canDownload && (
              <a
                href={state.status === "ready" ? state.url : undefined}
                download={title}
                aria-label="Download document"
                title="Download"
                className="inline-flex items-center gap-1.5 rounded-lg border border-line px-2.5 py-1.5 text-[12.5px] text-ink-2 transition-colors hover:bg-surface-2 hover:text-ink-1"
              >
                <Download className="h-3.5 w-3.5" aria-hidden="true" />
                Download
              </a>
            )}
            <button
              type="button"
              onClick={onClose}
              aria-label="Close document"
              className="-mr-1 shrink-0 rounded-lg p-1.5 text-ink-3 transition-colors hover:bg-surface-2 hover:text-ink-1"
            >
              <X className="h-4 w-4" aria-hidden="true" />
            </button>
          </div>
        </header>

        {state.status === "ready" && state.renderMode !== "image" && (
          <div className="flex items-center justify-between gap-4 border-b border-line/60 bg-surface-1/50 px-5 py-2">
            {multiPage ? (
              <nav aria-label="Document pages" className="flex items-center gap-1">
                <button
                  type="button"
                  onClick={() => setPage((n) => Math.max(1, n - 1))}
                  disabled={page <= 1}
                  aria-label="Previous page"
                  className="rounded-lg p-1 text-ink-2 transition-colors hover:bg-surface-2 hover:text-ink-1 disabled:pointer-events-none disabled:opacity-35"
                >
                  <ChevronLeft className="h-4 w-4" aria-hidden="true" />
                </button>
                <span
                  data-testid="page-indicator"
                  className="min-w-[5.5rem] text-center text-[12px] tabular-nums text-ink-2"
                >
                  Page {page} of {pageCount}
                </span>
                <button
                  type="button"
                  onClick={() => setPage((n) => Math.min(pageCount as number, n + 1))}
                  disabled={page >= (pageCount as number)}
                  aria-label="Next page"
                  className="rounded-lg p-1 text-ink-2 transition-colors hover:bg-surface-2 hover:text-ink-1 disabled:pointer-events-none disabled:opacity-35"
                >
                  <ChevronRight className="h-4 w-4" aria-hidden="true" />
                </button>
              </nav>
            ) : (
              <span />
            )}
            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={() => setZoom((z) => Math.max(ZOOM_MIN, Math.round((z - ZOOM_STEP) * 100) / 100))}
                disabled={zoom <= ZOOM_MIN}
                aria-label="Zoom out"
                className="rounded-lg p-1 text-ink-2 transition-colors hover:bg-surface-2 hover:text-ink-1 disabled:pointer-events-none disabled:opacity-35"
              >
                <Minus className="h-3.5 w-3.5" aria-hidden="true" />
              </button>
              <span className="min-w-[3.25rem] text-center text-[12px] tabular-nums text-ink-2">
                {Math.round(zoom * 100)}%
              </span>
              <button
                type="button"
                onClick={() => setZoom((z) => Math.min(ZOOM_MAX, Math.round((z + ZOOM_STEP) * 100) / 100))}
                disabled={zoom >= ZOOM_MAX}
                aria-label="Zoom in"
                className="rounded-lg p-1 text-ink-2 transition-colors hover:bg-surface-2 hover:text-ink-1 disabled:pointer-events-none disabled:opacity-35"
              >
                <Plus className="h-3.5 w-3.5" aria-hidden="true" />
              </button>
            </div>
          </div>
        )}

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
          <div className="flex-1 overflow-auto p-4">
            <img
              src={state.url}
              alt={title}
              className="mx-auto max-w-full rounded-md shadow-sm ring-1 ring-black/5"
            />
          </div>
        )}

        {state.status === "ready" && state.renderMode !== "image" && (
          <div className="flex-1 overflow-auto">
            <div className="px-4 py-4">
              <PdfPage url={state.url} pageNumber={page} onPageCount={handlePageCount} scale={zoom} />
            </div>
          </div>
        )}

        {sources.length > 0 && onSelectSource && (
          <footer className="border-t border-line/60 bg-surface-1/80 px-5 py-3">
            <p className="mb-2 text-[11px] uppercase tracking-wider text-ink-3">Other sources</p>
            <div className="flex gap-2 overflow-x-auto">
              {sources.map((source) => {
                const label =
                  source.documentName || `${source.documentId.slice(0, 8)}...`;
                return (
                  <button
                    key={source.documentId}
                    type="button"
                    onClick={() => onSelectSource(source)}
                    title={`Open ${label}`}
                    className="shrink-0 whitespace-nowrap rounded-full border border-line bg-surface-2 px-3 py-1.5 text-[12px] text-ink-2 transition-colors hover:bg-surface-3 hover:text-ink-1"
                  >
                    {label}
                  </button>
                );
              })}
            </div>
          </footer>
        )}
      </div>
    </SlideOver>
  );
}
