import { existsSync, readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { PDF_WORKER_PATH, __resetPdfjsForTests, isWorkerConfigured, loadPdfjs } from "./pdf";

/**
 * jsdom has no canvas and cannot render a PDF, so what is testable here is the
 * build-time contract — and that contract is where pdf.js actually breaks under a
 * bundler.
 *
 * This suite exists because the first version of this module configured the worker with
 * `new URL('pdfjs-dist/build/pdf.worker.min.mjs', import.meta.url)`. That made webpack
 * emit the worker as an asset, Terser minified it as a classic script, and the portal
 * build failed on the worker's own ESM syntax. The tests below pin the shape that does
 * not do that.
 */

const require = createRequire(import.meta.url);

beforeEach(() => {
  __resetPdfjsForTests();
});

describe("worker configuration", () => {
  it("points at a static path, not a bundled asset", () => {
    // A bundler-resolved specifier would start with a bare package name; a static file
    // served from `public/` is an absolute URL path.
    expect(PDF_WORKER_PATH.startsWith("/")).toBe(true);
    expect(PDF_WORKER_PATH).not.toContain("node_modules");
    expect(PDF_WORKER_PATH).not.toContain("pdfjs-dist/");
  });

  it("configures the worker exactly once", async () => {
    expect(isWorkerConfigured()).toBe(false);

    const first = await loadPdfjs();
    expect(isWorkerConfigured()).toBe(true);
    expect(first.GlobalWorkerOptions.workerSrc).toBe(PDF_WORKER_PATH);

    // A second load must not reassign — pdf.js ignores a change once a worker exists, so
    // a reassignment here would be silently meaningless rather than an error.
    first.GlobalWorkerOptions.workerSrc = "sentinel";
    await loadPdfjs();
    expect(first.GlobalWorkerOptions.workerSrc).toBe("sentinel");
  });
});

describe("the worker file the copy step provides", () => {
  it("exists in the installed package", () => {
    const entry = require.resolve("pdfjs-dist/package.json");
    const worker = join(dirname(entry), "build", "pdf.worker.min.mjs");
    expect(existsSync(worker)).toBe(true);
  });

  it("is an ES module, which is why it cannot go through the bundler", () => {
    const entry = require.resolve("pdfjs-dist/package.json");
    const worker = join(dirname(entry), "build", "pdf.worker.min.mjs");
    // Scanned whole, not sampled: the first `import` in this minified bundle sits about
    // a megabyte in, well past any head slice — which is exactly how a sampling version
    // of this test would have passed while asserting nothing.
    const source = readFileSync(worker, "utf-8");
    // The property that broke the build: Terser cannot minify this as a classic script.
    expect(/\b(import|export)\b/.test(source)).toBe(true);
  });

  it("is copied to the path the module points at", () => {
    // `prebuild`/`predev` run the copy; if the copy step is removed, the worker 404s at
    // runtime and the viewer fails with an opaque pdf.js error rather than a build error.
    const copied = join(process.cwd(), "public", PDF_WORKER_PATH.replace(/^\//, ""));
    expect(existsSync(copied)).toBe(true);
  });
});
