/**
 * pdf.js setup for the portal.
 *
 * The worker is configured explicitly rather than left to a CDN default. A misconfigured
 * worker is the classic pdf.js failure under a bundler: nothing breaks at build time, and
 * the viewer fails at runtime in the browser with an opaque error. The file is copied
 * from the installed package at build time, so the worker and the library parsing the
 * document cannot be different versions.
 *
 * Imported lazily by the viewer so the ~1MB library is not in the initial bundle for
 * every page of the portal — only the chat thread ever opens a document.
 */

export const PDF_WORKER_PATH = "/pdf.worker.min.mjs";

let configured = false;

export async function loadPdfjs() {
  const pdfjs = await import("pdfjs-dist");
  if (!configured) {
    // Served as a static file, deliberately not bundled. Referencing it with
    // `new URL(..., import.meta.url)` makes webpack emit it as an asset, and Terser then
    // minifies it as a classic script and fails the build on its ESM syntax. The file is
    // copied into `public/` from the installed package by `scripts/copy-pdf-worker.mjs`,
    // so the worker and the library parsing the document are always the same version.
    pdfjs.GlobalWorkerOptions.workerSrc = PDF_WORKER_PATH;
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
