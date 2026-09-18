"use client";

import { useEffect, useRef, useState } from "react";

import { loadPdfjs } from "@/lib/pdf";

/**
 * One rendered PDF page, with the cited passage highlighted.
 *
 * pdf.js rather than the browser's built-in viewer, because the built-in one cannot be
 * asked to mark a passage — and marking the passage is the point. A citation says "this
 * answer came from here"; opening the right page and leaving the reader to find the
 * sentence is only half of that.
 *
 * The highlight is drawn from pdf.js's text layer: every text item carries a transform,
 * so the items whose concatenated text contains the snippet can be boxed directly. When
 * the snippet spans a line break or the extraction differs from the rendered glyphs, no
 * match is found and the page simply renders unmarked — a missing highlight is a much
 * better failure than a wrong one.
 */

export interface PdfPageProps {
  /** Object URL for the document's bytes. */
  url: string;
  pageNumber: number;
  /** The passage to mark, if the citation carried one. */
  highlight?: string | null;
  onPageCount?: (count: number) => void;
}

interface Box {
  left: number;
  top: number;
  width: number;
  height: number;
}

/** Comparable form: extraction whitespace rarely matches the answer's quoting. */
function normalise(value: string) {
  return value.replace(/\s+/g, " ").trim().toLowerCase();
}

export function PdfPage({ url, pageNumber, highlight, onPageCount }: PdfPageProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [boxes, setBoxes] = useState<Box[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [size, setSize] = useState<{ width: number; height: number } | null>(null);

  useEffect(() => {
    let cancelled = false;
    let doc: { destroy: () => void; numPages: number } | null = null;

    (async () => {
      try {
        const pdfjs = await loadPdfjs();
        const task = pdfjs.getDocument({ url });
        const loaded = await task.promise;
        if (cancelled) {
          loaded.destroy();
          return;
        }
        doc = loaded;
        onPageCount?.(loaded.numPages);

        const target = Math.min(Math.max(pageNumber, 1), loaded.numPages);
        const page = await loaded.getPage(target);
        if (cancelled) return;

        const viewport = page.getViewport({ scale: 1.5 });
        const canvas = canvasRef.current;
        if (!canvas) return;
        canvas.width = viewport.width;
        canvas.height = viewport.height;
        setSize({ width: viewport.width, height: viewport.height });

        const context = canvas.getContext("2d");
        if (!context) return;
        await page.render({ canvasContext: context, viewport }).promise;
        if (cancelled) return;

        if (highlight) {
          const wanted = normalise(highlight);
          const content = await page.getTextContent();
          if (cancelled) return;
          const found: Box[] = [];
          for (const item of content.items as Array<{
            str: string;
            transform: number[];
            width: number;
            height: number;
          }>) {
            const text = normalise(item.str);
            if (!text) continue;
            // Either direction: the snippet may be a fragment of a long line, or a line
            // may be a fragment of a multi-line snippet.
            if (wanted.includes(text) || text.includes(wanted)) {
              const [, , , , x, y] = item.transform;
              const [left, top] = viewport.convertToViewportPoint(x, y);
              found.push({
                left,
                top: top - item.height * viewport.scale,
                width: item.width * viewport.scale,
                height: item.height * viewport.scale,
              });
            }
          }
          setBoxes(found);
        } else {
          setBoxes([]);
        }
      } catch {
        if (!cancelled) setError("This document could not be rendered.");
      }
    })();

    return () => {
      cancelled = true;
      doc?.destroy();
    };
  }, [url, pageNumber, highlight, onPageCount]);

  if (error) {
    return (
      <p role="status" className="p-6 text-sm text-ink-3">
        {error}
      </p>
    );
  }

  return (
    <div className="relative mx-auto" style={size ? { width: size.width } : undefined}>
      <canvas ref={canvasRef} data-testid="pdf-canvas" className="mx-auto block shadow" />
      {boxes.map((box, index) => (
        <span
          key={index}
          data-testid="pdf-highlight"
          aria-hidden="true"
          className="pointer-events-none absolute bg-yellow-300/40"
          style={{ left: box.left, top: box.top, width: box.width, height: box.height }}
        />
      ))}
    </div>
  );
}
