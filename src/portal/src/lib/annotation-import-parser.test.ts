import { describe, it, expect } from "vitest";
import {
  parseConll,
  parseJsonl,
  parseFile,
  computeEntityTypeCounts,
  detectFormat,
} from "./annotation-import-parser";

describe("parseConll", () => {
  it("parses valid CoNLL content", () => {
    const content = "John\tB-PER\nlives\tO\nin\tO\nNYC\tB-LOC\n\nGoogle\tB-ORG\nhires\tO\n";
    const result = parseConll(content);
    expect(result).toHaveLength(2);
    expect(result[0].tokens).toEqual(["John", "lives", "in", "NYC"]);
    expect(result[0].tags).toEqual(["B-PER", "O", "O", "B-LOC"]);
    expect(result[1].tokens).toEqual(["Google", "hires"]);
    expect(result[1].tags).toEqual(["B-ORG", "O"]);
  });

  it("throws on malformed CoNLL (missing tab)", () => {
    const content = "John B-PER\n";
    expect(() => parseConll(content)).toThrow("expected token and tag separated by tab");
  });

  it("throws on empty content", () => {
    expect(() => parseConll("")).toThrow("no valid annotation rows");
  });

  it("handles unicode tokens", () => {
    const content = "José\tB-PER\nvive\tO\nen\tO\nMéxico\tB-LOC\n";
    const result = parseConll(content);
    expect(result).toHaveLength(1);
    expect(result[0].tokens).toEqual(["José", "vive", "en", "México"]);
  });

  it("handles trailing newlines", () => {
    const content = "John\tB-PER\n\n\n";
    const result = parseConll(content);
    expect(result).toHaveLength(1);
  });
});

describe("parseJsonl", () => {
  it("parses valid JSONL content", () => {
    const content = [
      '{"tokens": ["John", "lives", "in", "NYC"], "tags": ["B-PER", "O", "O", "B-LOC"]}',
      '{"tokens": ["Google", "is", "hiring"], "tags": ["B-ORG", "O", "O"]}',
    ].join("\n");
    const result = parseJsonl(content);
    expect(result).toHaveLength(2);
    expect(result[0].tokens).toEqual(["John", "lives", "in", "NYC"]);
    expect(result[0].tags).toEqual(["B-PER", "O", "O", "B-LOC"]);
    expect(result[1].tokens).toEqual(["Google", "is", "hiring"]);
  });

  it("throws on malformed JSON", () => {
    const content = "{invalid json here}\n";
    expect(() => parseJsonl(content)).toThrow("invalid JSON");
  });

  it("throws on empty content", () => {
    expect(() => parseJsonl("")).toThrow("no valid annotation rows");
  });

  it("skips blank lines", () => {
    const content = "\n" + '{"tokens": ["x"], "tags": ["O"]}\n' + "\n";
    const result = parseJsonl(content);
    expect(result).toHaveLength(1);
  });

  it("throws when tokens and tags have different lengths", () => {
    const content = '{"tokens": ["a", "b"], "tags": ["O"]}\n';
    expect(() => parseJsonl(content)).toThrow("must have equal length");
  });
});

describe("computeEntityTypeCounts", () => {
  it("counts entity types per row", () => {
    const rows = [
      { tokens: ["John", "lives"], tags: ["B-PER", "O"] },
      { tokens: ["Google", "hires"], tags: ["B-ORG", "O"] },
      { tokens: ["NYC", "is", "big"], tags: ["B-LOC", "O", "O"] },
    ];
    expect(computeEntityTypeCounts(rows)).toEqual({ PER: 1, ORG: 1, LOC: 1 });
  });

  it("counts multiple occurrences of same type in different rows", () => {
    const rows = [
      { tokens: ["John"], tags: ["B-PER"] },
      { tokens: ["Jane"], tags: ["B-PER"] },
    ];
    expect(computeEntityTypeCounts(rows)).toEqual({ PER: 2 });
  });

  it("ignores O tags", () => {
    const rows = [
      { tokens: ["hello", "world"], tags: ["O", "O"] },
    ];
    expect(computeEntityTypeCounts(rows)).toEqual({});
  });
});

describe("detectFormat", () => {
  it("detects CoNLL for .txt", () => {
    expect(detectFormat("file.txt")).toBe("conll");
  });

  it("detects JSONL for .json", () => {
    expect(detectFormat("file.json")).toBe("jsonl");
  });

  it("detects JSONL for .jsonl", () => {
    expect(detectFormat("file.jsonl")).toBe("jsonl");
  });

  it("defaults to CoNLL for unknown extensions", () => {
    expect(detectFormat("file.conll")).toBe("conll");
  });
});

describe("parseFile", () => {
  const knownTypes = ["PER", "ORG", "LOC"];

  it("parses a valid CoNLL file", async () => {
    const file = new File(
      ["John\tB-PER\nlives\tO\n\nGoogle\tB-ORG\n"],
      "test.txt",
      { type: "text/plain" },
    );
    const result = await parseFile(file, knownTypes);
    expect(result.format).toBe("conll");
    expect(result.rowCount).toBe(2);
    expect(result.entityTypeCounts).toEqual({ PER: 1, ORG: 1 });
    expect(result.unknownTypeWarnings).toHaveLength(0);
    expect(result.error).toBeUndefined();
  });

  it("parses a valid JSONL file", async () => {
    const file = new File(
      ['{"tokens":["John"],"tags":["B-PER"]}\n{"tokens":["NYC"],"tags":["B-LOC"]}\n'],
      "test.jsonl",
      { type: "application/jsonl" },
    );
    const result = await parseFile(file, knownTypes);
    expect(result.format).toBe("jsonl");
    expect(result.rowCount).toBe(2);
    expect(result.entityTypeCounts).toEqual({ PER: 1, LOC: 1 });
  });

  it("returns error for empty file", async () => {
    const file = new File([""], "empty.txt", { type: "text/plain" });
    const result = await parseFile(file, knownTypes);
    expect(result.error).toBeDefined();
    expect(result.error).toContain("no valid annotation rows");
  });

  it("reports unknown entity type warnings", async () => {
    const file = new File(
      ["John\tB-PER\n\nbad\tB-PRODUCT\n"],
      "test.txt",
      { type: "text/plain" },
    );
    const result = await parseFile(file, knownTypes);
    expect(result.rowCount).toBe(2);
    expect(result.unknownTypeWarnings).toHaveLength(1);
    expect(result.unknownTypeWarnings[0].rowIndex).toBe(1);
    expect(result.unknownTypeWarnings[0].unknownTypes).toEqual(["PRODUCT"]);
  });

  it("returns error for file exceeding 50MB", async () => {
    const largeContent = "x".repeat(51 * 1024 * 1024);
    const file = new File([largeContent], "large.txt", { type: "text/plain" });
    const result = await parseFile(file, knownTypes);
    expect(result.error).toBe("File exceeds the 50MB maximum");
    expect(result.rowCount).toBe(0);
  });
});
