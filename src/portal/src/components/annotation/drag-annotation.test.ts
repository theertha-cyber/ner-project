/**
 * Unit tests for drag-to-annotate range computation (task 7.7).
 *
 * The drag handler in AnnotationPage uses:
 *   minIdx = Math.min(dragStartIndex, dragEndIndex)
 *   maxIdx = Math.max(dragStartIndex, dragEndIndex)
 *   charStart = tokenMap[minIdx].charStart
 *   charEnd   = tokenMap[maxIdx].charEnd
 *
 * These tests verify the token map structure and the resulting char offsets
 * match the scenarios in the drag-annotation spec.
 */

import { buildTokenMap } from "@/lib/token-map";

describe("drag-to-annotate range computation", () => {
  const text = "John Smith works here";
  // token indices: John=0, Smith=1, works=2, here=3
  const tokenMap = buildTokenMap(text);

  it("builds token map with correct char offsets", () => {
    expect(tokenMap[0]).toEqual({ token: "John", charStart: 0, charEnd: 4 });
    expect(tokenMap[1]).toEqual({ token: "Smith", charStart: 5, charEnd: 10 });
    expect(tokenMap[2]).toEqual({ token: "works", charStart: 11, charEnd: 16 });
    expect(tokenMap[3]).toEqual({ token: "here", charStart: 17, charEnd: 21 });
  });

  it("right-to-left drag (index 3 → 1) produces min=1, max=3 with correct char offsets", () => {
    const dragStart = 3;
    const dragEnd = 1;
    const minIdx = Math.min(dragStart, dragEnd);
    const maxIdx = Math.max(dragStart, dragEnd);
    expect(minIdx).toBe(1);
    expect(maxIdx).toBe(3);
    expect(tokenMap[minIdx].charStart).toBe(5);   // "Smith" starts at 5
    expect(tokenMap[maxIdx].charEnd).toBe(21);     // "here" ends at 21
  });

  it("single-click (start === end) has minIdx === maxIdx", () => {
    const dragStart = 2;
    const dragEnd = 2;
    expect(Math.min(dragStart, dragEnd)).toBe(Math.max(dragStart, dragEnd));
  });

  it("multi-token left-to-right drag (0 → 1) gives John Smith char range", () => {
    const minIdx = Math.min(0, 1);
    const maxIdx = Math.max(0, 1);
    expect(tokenMap[minIdx].charStart).toBe(0);
    expect(tokenMap[maxIdx].charEnd).toBe(10);
  });

  it("drag guard: range containing a confirmed token is blocked", () => {
    const confirmed = [{ id: "s1", entityType: "PER", charStart: 0, charEnd: 4, text: "John", confidence: 1.0, optimistic: false }];
    const minIdx = 0;
    const maxIdx = 1;
    const rangeEntries = tokenMap.slice(minIdx, maxIdx + 1);
    const blocked = rangeEntries.some((entry) =>
      confirmed.some((s) => !s.optimistic && s.charStart <= entry.charStart && s.charEnd >= entry.charEnd),
    );
    expect(blocked).toBe(true);
  });

  it("drag guard: range with no confirmed tokens is not blocked", () => {
    const confirmed = [{ id: "s1", entityType: "PER", charStart: 0, charEnd: 4, text: "John", confidence: 1.0, optimistic: false }];
    const minIdx = 1;
    const maxIdx = 2;
    const rangeEntries = tokenMap.slice(minIdx, maxIdx + 1);
    const blocked = rangeEntries.some((entry) =>
      confirmed.some((s) => !s.optimistic && s.charStart <= entry.charStart && s.charEnd >= entry.charEnd),
    );
    expect(blocked).toBe(false);
  });
});
