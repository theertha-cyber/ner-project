/**
 * Copies the pdf.js worker into `public/` before a build.
 *
 * The worker cannot go through the bundler. Referencing it with
 * `new URL('pdfjs-dist/build/pdf.worker.min.mjs', import.meta.url)` makes webpack emit it
 * as an asset, and Terser then minifies it as a classic script and fails on its ESM
 * syntax: "'import', and 'export' cannot be used outside of module code". Serving it as a
 * static file sidesteps the asset pipeline altogether.
 *
 * Copied at build time from the installed package rather than committed, so the worker
 * and the library parsing the document can never be different versions — the failure that
 * produces is an opaque runtime error in the browser, not a build error.
 */

import { copyFileSync, existsSync, mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";

const require = createRequire(import.meta.url);

// Resolved through the package rather than a hard-coded path: npm may hoist `pdfjs-dist`
// to the workspace root instead of `src/portal/node_modules`.
const entry = require.resolve("pdfjs-dist/package.json");
const source = join(dirname(entry), "build", "pdf.worker.min.mjs");

if (!existsSync(source)) {
  console.error(`pdf.js worker not found at ${source} — is pdfjs-dist installed?`);
  process.exit(1);
}

const targetDir = join(process.cwd(), "public");
mkdirSync(targetDir, { recursive: true });
copyFileSync(source, join(targetDir, "pdf.worker.min.mjs"));

console.log("copied pdf.js worker to public/pdf.worker.min.mjs");
