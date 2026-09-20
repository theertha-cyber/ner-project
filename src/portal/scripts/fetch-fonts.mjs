/**
 * Downloads the portal's webfonts into `src/fonts/` so the build never reaches the
 * network for them.
 *
 * `next/font/google` fetches from fonts.gstatic.com at build time. The build container
 * cannot resolve it — the same DNS gap that breaks `db-init` — so every font request
 * failed, retried three times, and Next silently fell back. The shipped image was
 * rendering in fallback fonts, which is a correctness problem before it is a speed one.
 *
 * Run on a machine with network access; the files are committed. All three families are
 * SIL Open Font License, which permits redistribution — `OFL.txt` alongside them records
 * that.
 *
 * Usage: node scripts/fetch-fonts.mjs
 */

import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";

// A modern browser UA, or Google serves legacy `ttf` instead of the variable `woff2`.
const UA =
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) " +
  "Chrome/120.0.0.0 Safari/537.36";

// Matches the families and axes `layout.tsx` asks for: latin subset, full weight axis.
const FAMILIES = [
  { name: "Hanken Grotesk", query: "Hanken+Grotesk:wght@100..900", file: "hanken-grotesk" },
  { name: "Inter", query: "Inter:wght@100..900", file: "inter" },
  { name: "JetBrains Mono", query: "JetBrains+Mono:wght@100..800", file: "jetbrains-mono" },
];

const outDir = join(process.cwd(), "src", "fonts");
mkdirSync(outDir, { recursive: true });

for (const family of FAMILIES) {
  const cssUrl = `https://fonts.googleapis.com/css2?family=${family.query}&display=swap`;
  const css = await fetch(cssUrl, { headers: { "User-Agent": UA } }).then((r) => {
    if (!r.ok) throw new Error(`${family.name}: css ${r.status}`);
    return r.text();
  });

  // The latin block is the last `@font-face` Google emits for the family; taking the
  // final `latin` range avoids picking up latin-ext or cyrillic.
  const blocks = css.split("@font-face").filter((b) => b.includes("U+0000-00FF"));
  if (blocks.length === 0) throw new Error(`${family.name}: no latin block in css`);

  const match = blocks[blocks.length - 1].match(/url\((https:[^)]+\.woff2)\)/);
  if (!match) throw new Error(`${family.name}: no woff2 url in latin block`);

  const bytes = Buffer.from(
    await fetch(match[1], { headers: { "User-Agent": UA } }).then((r) => {
      if (!r.ok) throw new Error(`${family.name}: font ${r.status}`);
      return r.arrayBuffer();
    }),
  );

  const target = join(outDir, `${family.file}.woff2`);
  writeFileSync(target, bytes);
  console.log(`${family.name}: ${bytes.length} bytes -> src/fonts/${family.file}.woff2`);
}

writeFileSync(
  join(outDir, "OFL.txt"),
  [
    "Hanken Grotesk, Inter and JetBrains Mono are licensed under the",
    "SIL Open Font License, Version 1.1, which permits redistribution.",
    "",
    "https://openfontlicense.org/",
    "",
    "Downloaded from Google Fonts by scripts/fetch-fonts.mjs.",
    "",
  ].join("\n"),
  "utf-8",
);
console.log("wrote src/fonts/OFL.txt");
