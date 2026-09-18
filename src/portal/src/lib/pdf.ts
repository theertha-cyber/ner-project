/**
 * pdf.js setup for the portal.
 *
 * The worker is configured explicitly rather than left to a CDN default. A misconfigured
 * worker is the classic pdf.js failure under a bundler: nothing breaks at build time, and
 * the viewer fails at runtime in the browser with an opaque error. Pointing it at the
 * copy in `node_modules` means the version serving the worker and the version parsing the
 * document cannot drift.
 *
 * Imported lazily by the viewer so the ~1MB library is not in the initial bundle for
 * every page of the portal — only the chat thread ever opens a document.
 */

export const PDF_WORKER_PATH = "pdfjs-dist/build/pdf.worker.min.mjs";

let configured = false;

export async function loadPdfjs() {
  const pdfjs = await import("pdfjs-dist");
  if (!configured) {
    // `new URL(..., import.meta.url)` is what lets the bundler emit the worker as an
    // asset and rewrite this to its real path. A bare string would resolve at runtime
    // against the page's origin and 404.
    pdfjs.GlobalWorkerOptions.workerSrc = new URL(
      "pdfjs-dist/build/pdf.worker.min.mjs",
      import.meta.url,
    ).toString();
    configured = true;
  }
  return pdfjs;
}

export function isWorkerConfigured() {
  return configured;
}

/** Test seam: lets a suite assert configuration happens exactly once. */
export function __resetPdfjsForTests() {
  configured = false;
}
