import { describe, it, expect } from "vitest";
import { tagsToSpans, spansToTags } from "./token-range-reducer";

describe("tagsToSpans", () => {
  it("returns empty for all O tags", () => {
    const tags = ["O", "O", "O"];
    expect(tagsToSpans(tags)).toEqual([]);
  });

  it("converts a single B/I run into one span", () => {
    const tags = ["B-PER", "I-PER", "O"];
    const spans = tagsToSpans(tags);
    expect(spans).toHaveLength(1);
    expect(spans[0].entityType).toBe("PER");
    expect(spans[0].startToken).toBe(0);
    expect(spans[0].endToken).toBe(1);
  });

  it("handles multiple spans", () => {
    const tags = ["B-PER", "O", "B-ORG", "I-ORG", "O"];
    const spans = tagsToSpans(tags);
    expect(spans).toHaveLength(2);
    expect(spans[0].entityType).toBe("PER");
    expect(spans[0].startToken).toBe(0);
    expect(spans[0].endToken).toBe(0);
    expect(spans[1].entityType).toBe("ORG");
    expect(spans[1].startToken).toBe(2);
    expect(spans[1].endToken).toBe(3);
  });
});

describe("spansToTags", () => {
  it("generates correct tags from spans", () => {
    const spans = [
      { id: "1", entityType: "PER", startToken: 0, endToken: 1 },
      { id: "2", entityType: "ORG", startToken: 3, endToken: 4 },
    ];
    const tags = spansToTags(spans, 6);
    expect(tags).toEqual(["B-PER", "I-PER", "O", "B-ORG", "I-ORG", "O"]);
  });

  it("fills rest with O", () => {
    const tags = spansToTags([], 3);
    expect(tags).toEqual(["O", "O", "O"]);
  });
});
