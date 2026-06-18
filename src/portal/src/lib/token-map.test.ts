import { describe, it, expect } from "vitest";
import { buildTokenMap, spanToTokenRange } from "./token-map";

describe("buildTokenMap", () => {
  it("maps single token correctly", () => {
    const map = buildTokenMap("Hello");
    expect(map).toHaveLength(1);
    expect(map[0]).toEqual({ token: "Hello", charStart: 0, charEnd: 5 });
  });

  it("maps three tokens with correct offsets", () => {
    const map = buildTokenMap("Hello World Foo");
    expect(map).toHaveLength(3);
    expect(map[0]).toEqual({ token: "Hello", charStart: 0, charEnd: 5 });
    expect(map[1]).toEqual({ token: "World", charStart: 6, charEnd: 11 });
    expect(map[2]).toEqual({ token: "Foo", charStart: 12, charEnd: 15 });
  });

  it("token at start has charStart 0", () => {
    const map = buildTokenMap("First second");
    expect(map[0].charStart).toBe(0);
  });

  it("last token charEnd equals text length", () => {
    const text = "Hello World Foo";
    const map = buildTokenMap(text);
    expect(map[map.length - 1].charEnd).toBe(text.length);
  });

  it("scenario 29: token index 1 maps to char_start=6, char_end=11", () => {
    const map = buildTokenMap("Hello World Foo");
    expect(map[1].charStart).toBe(6);
    expect(map[1].charEnd).toBe(11);
  });
});

describe("spanToTokenRange", () => {
  it("maps single-token span", () => {
    const map = buildTokenMap("Hello World Foo");
    expect(spanToTokenRange(map, 0, 5)).toEqual([0]);
  });

  it("scenario 30: span char_start=0, char_end=11 covers tokens 0 and 1 only", () => {
    const map = buildTokenMap("Hello World Foo");
    expect(spanToTokenRange(map, 0, 11)).toEqual([0, 1]);
  });

  it("mid-document span", () => {
    const map = buildTokenMap("Hello World Foo");
    expect(spanToTokenRange(map, 6, 15)).toEqual([1, 2]);
  });

  it("single mid-document token", () => {
    const map = buildTokenMap("Hello World Foo");
    expect(spanToTokenRange(map, 6, 11)).toEqual([1]);
  });

  it("returns empty array when span covers no tokens", () => {
    const map = buildTokenMap("Hello World");
    expect(spanToTokenRange(map, 100, 200)).toEqual([]);
  });
});
