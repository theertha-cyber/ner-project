"use client";

import { useEffect, useRef, useState } from "react";

import { loadPdfjs } from "@/lib/pdf";

/**
 * One rendered PDF page.
 *
 * pdf.js rather than the browser's built-in viewer so the page renders inside the panel's
 * own layout — the built-in viewer brings its own chrome, which cannot be styled and
 * fights the surrounding UI.
 *
 * Deliberately no passage highlighting. An earlier version marked the cited passage from
 * the text layer, but a citation's snippet is often most of the document, and matching a
 * line against it lit up nearly every page. A highlight that is usually wrong is worse
 * than none: it tells the reader to look in the wrong place while looking authoritative.
 * The panel opens at the cited page, which is the part that reliably helps.
 */

export interface PdfPageProps {
  /** Object URL for the document's bytes. */
  url: string;
  pageNumber: number;
  onPageCount?: (count: number) => void;
  /** Reader-controlled zoom multiplier, independent of the sharpness scale below. */
  scale?: number;
}

// Rendered above CSS size so the page stays sharp on high-density displays.
const RENDER_SCALE = 2;

export function PdfPage({ url, pageNumber, onPageCount, scale = 1 }: PdfPageProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    let doc: { destroy: () => void; numPages: number } | null = null;

    setReady(false);

    (async () => {
      try {
        const pdfjs = await loadPdfjs();
        const loaded = await pdfjs.getDocument({ url }).promise;
        if (cancelled) {
          loaded.destroy();
          return;
        }
        doc = loaded;
        onPageCount?.(loaded.numPages);

        const target = Math.min(Math.max(pageNumber, 1), loaded.numPages);
        const page = await loaded.getPage(target);
        if (cancelled) return;

        const viewport = page.getViewport({ scale: RENDER_SCALE * scale });
        const canvas = canvasRef.current;
        if (!canvas) return;
        canvas.width = viewport.width;
        canvas.height = viewport.height;
        // Laid out at half the render size, so the extra pixels become sharpness rather
        // than a page twice as wide as the panel. The reader's zoom multiplies both sides
        // of that ratio equally, so it grows the displayed page without losing sharpness.
        canvas.style.width = `${viewport.width / RENDER_SCALE}px`;
        canvas.style.height = "auto";

        const context = canvas.getContext("2d");
        if (!context) return;
        await page.render({ canvasContext: context, viewport }).promise;
        if (!cancelled) setReady(true);
      } catch {
        if (!cancelled) setError("This document could not be rendered.");
      }
    })();

    return () => {
      cancelled = true;
      doc?.destroy();
    };
  }, [url, pageNumber, onPageCount, scale]);

  if (error) {
    return (
      <p role="status" className="p-8 text-center text-sm text-ink-3">
        {error}
      </p>
    );
  }

  return (
    <canvas
      ref={canvasRef}
      data-testid="pdf-canvas"
      className={[
        "mx-auto block max-w-full rounded-md bg-white shadow-sm ring-1 ring-black/5",
        "transition-opacity duration-150",
        ready ? "opacity-100" : "opacity-0",
      ].join(" ")}
    />
  );
}
