export interface ParsedRow {
  tokens: string[];
  tags: string[];
}

export interface ParseResult {
  format: "conll" | "jsonl";
  rows: ParsedRow[];
  rowCount: number;
  entityTypeCounts: Record<string, number>;
  unknownTypeWarnings: { rowIndex: number; unknownTypes: string[] }[];
  error?: string;
}

const MAX_FILE_SIZE = 50 * 1024 * 1024;

function stripBioPrefix(tag: string): string {
  if (tag.startsWith("B-") || tag.startsWith("I-")) return tag.slice(2);
  return tag;
}

export function parseConll(content: string): ParsedRow[] {
  const rows: ParsedRow[] = [];
  const sentences = content.trim().split("\n\n");
  for (const sentence of sentences) {
    const stripped = sentence.trim();
    if (!stripped) continue;
    const tokens: string[] = [];
    const tags: string[] = [];
    for (const line of stripped.split("\n")) {
      const trimmed = line.trim();
      if (!trimmed) continue;
      const parts = trimmed.split("\t");
      if (parts.length !== 2) {
        throw new Error(
          `CoNLL parse error: expected token and tag separated by tab, got: "${trimmed}"`,
        );
      }
      tokens.push(parts[0].trim());
      tags.push(parts[1].trim());
    }
    if (tokens.length > 0) {
      rows.push({ tokens, tags });
    }
  }
  if (rows.length === 0) {
    throw new Error("CoNLL parse error: file contains no valid annotation rows");
  }
  return rows;
}

export function parseJsonl(content: string): ParsedRow[] {
  const rows: ParsedRow[] = [];
  const lines = content.split("\n");
  for (let i = 0; i < lines.length; i++) {
    const stripped = lines[i].trim();
    if (!stripped) continue;
    let obj: unknown;
    try {
      obj = JSON.parse(stripped);
    } catch {
      throw new Error(`JSONL parse error at line ${i + 1}: invalid JSON`);
    }
    if (typeof obj !== "object" || obj === null || Array.isArray(obj)) {
      throw new Error(`JSONL parse error at line ${i + 1}: expected a JSON object`);
    }
    const record = obj as Record<string, unknown>;
    const tokens = record.tokens;
    const tags = record.tags;
    if (!Array.isArray(tokens) || !Array.isArray(tags)) {
      throw new Error(
        `JSONL parse error at line ${i + 1}: 'tokens' and 'tags' must be arrays`,
      );
    }
    if (tokens.length !== tags.length) {
      throw new Error(
        `JSONL parse error at line ${i + 1}: 'tokens' and 'tags' must have equal length`,
      );
    }
    rows.push({ tokens: tokens as string[], tags: tags as string[] });
  }
  if (rows.length === 0) {
    throw new Error("JSONL parse error: file contains no valid annotation rows");
  }
  return rows;
}

export function computeEntityTypeCounts(rows: ParsedRow[]): Record<string, number> {
  const counts: Record<string, number> = {};
  for (const row of rows) {
    const seenInRow = new Set<string>();
    for (const tag of row.tags) {
      if (tag === "O") continue;
      const base = stripBioPrefix(tag);
      if (!seenInRow.has(base)) {
        seenInRow.add(base);
        counts[base] = (counts[base] ?? 0) + 1;
      }
    }
  }
  return counts;
}

export function detectFormat(filename: string): "conll" | "jsonl" {
  const lower = filename.toLowerCase();
  if (lower.endsWith(".json") || lower.endsWith(".jsonl")) return "jsonl";
  return "conll";
}

function readFileAsText(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = () => reject(new Error("Failed to read file"));
    reader.readAsText(file);
  });
}

export async function parseFile(
  file: File,
  knownEntityTypeNames: string[],
): Promise<ParseResult> {
  if (file.size > MAX_FILE_SIZE) {
    return {
      format: detectFormat(file.name),
      rows: [],
      rowCount: 0,
      entityTypeCounts: {},
      unknownTypeWarnings: [],
      error: "File exceeds the 50MB maximum",
    };
  }

  const format = detectFormat(file.name);
  let text: string;
  try {
    text = await readFileAsText(file);
  } catch {
    return {
      format,
      rows: [],
      rowCount: 0,
      entityTypeCounts: {},
      unknownTypeWarnings: [],
      error: "Failed to read file",
    };
  }
  let rows: ParsedRow[];

  try {
    rows = format === "conll" ? parseConll(text) : parseJsonl(text);
  } catch (e) {
    return {
      format,
      rows: [],
      rowCount: 0,
      entityTypeCounts: {},
      unknownTypeWarnings: [],
      error: (e as Error).message,
    };
  }

  const knownLower = knownEntityTypeNames.map((n) => n.toLowerCase());
  const unknownTypeWarnings: { rowIndex: number; unknownTypes: string[] }[] = [];

  for (let idx = 0; idx < rows.length; idx++) {
    const row = rows[idx];
    const invalidTypes = new Set<string>();
    for (const tag of row.tags) {
      if (tag === "O") continue;
      const base = stripBioPrefix(tag);
      if (!knownLower.includes(base.toLowerCase())) {
        invalidTypes.add(base);
      }
    }
    if (invalidTypes.size > 0) {
      unknownTypeWarnings.push({
        rowIndex: idx,
        unknownTypes: Array.from(invalidTypes).sort(),
      });
    }
  }

  const entityTypeCounts = computeEntityTypeCounts(rows);

  return {
    format,
    rows,
    rowCount: rows.length,
    entityTypeCounts,
    unknownTypeWarnings,
  };
}
