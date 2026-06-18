import { describe, it, expect } from "vitest";
import { spanReducer, initialSpanState, SpanState, ConfirmedSpan, SuggestedSpan } from "./span-reducer";

const makeSpan = (overrides: Partial<ConfirmedSpan> = {}): ConfirmedSpan => ({
  id: "span-1",
  entityType: "PER",
  charStart: 0,
  charEnd: 10,
  text: "John Doe",
  confidence: 1.0,
  ...overrides,
});

const makeSuggestion = (overrides: Partial<SuggestedSpan> = {}): SuggestedSpan => ({
  id: "suggest-1",
  entityType: "ORG",
  charStart: 5,
  charEnd: 14,
  text: "Acme Corp",
  confidence: 0.85,
  ...overrides,
});

describe("spanReducer", () => {
  it("SPANS_LOAD replaces confirmed spans and clears selection", () => {
    const state: SpanState = { ...initialSpanState, confirmed: [makeSpan()], selectedSpanId: "span-1" };
    const next = spanReducer(state, { type: "SPANS_LOAD", spans: [makeSpan({ id: "span-2" })] });
    expect(next.confirmed).toHaveLength(1);
    expect(next.confirmed[0].id).toBe("span-2");
    expect(next.selectedSpanId).toBeNull();
  });

  it("SUGGESTIONS_LOAD replaces suggested spans", () => {
    const state: SpanState = { ...initialSpanState, suggested: [makeSuggestion()] };
    const newSuggestion = makeSuggestion({ id: "suggest-2" });
    const next = spanReducer(state, { type: "SUGGESTIONS_LOAD", spans: [newSuggestion] });
    expect(next.suggested).toHaveLength(1);
    expect(next.suggested[0].id).toBe("suggest-2");
  });

  it("SPAN_ADD_OPTIMISTIC adds span to confirmed list", () => {
    const optimisticSpan = makeSpan({ id: "optimistic-abc", optimistic: true });
    const next = spanReducer(initialSpanState, { type: "SPAN_ADD_OPTIMISTIC", span: optimisticSpan });
    expect(next.confirmed).toHaveLength(1);
    expect(next.confirmed[0].id).toBe("optimistic-abc");
    expect(next.confirmed[0].optimistic).toBe(true);
  });

  it("SPAN_CONFIRM replaces optimistic entry with real span", () => {
    const optSpan = makeSpan({ id: "optimistic-abc", optimistic: true });
    const state: SpanState = { ...initialSpanState, confirmed: [optSpan] };
    const realSpan = makeSpan({ id: "real-id-123" });
    const next = spanReducer(state, { type: "SPAN_CONFIRM", optimisticId: "optimistic-abc", realSpan });
    expect(next.confirmed).toHaveLength(1);
    expect(next.confirmed[0].id).toBe("real-id-123");
    expect(next.confirmed[0].optimistic).toBe(false);
  });

  it("SPAN_REVERT removes optimistic span", () => {
    const optSpan = makeSpan({ id: "optimistic-abc", optimistic: true });
    const state: SpanState = { ...initialSpanState, confirmed: [optSpan] };
    const next = spanReducer(state, { type: "SPAN_REVERT", optimisticId: "optimistic-abc" });
    expect(next.confirmed).toHaveLength(0);
  });

  it("SPAN_DELETE removes span by id and clears selection if it was selected", () => {
    const state: SpanState = {
      ...initialSpanState,
      confirmed: [makeSpan({ id: "span-1" }), makeSpan({ id: "span-2" })],
      selectedSpanId: "span-1",
    };
    const next = spanReducer(state, { type: "SPAN_DELETE", spanId: "span-1" });
    expect(next.confirmed).toHaveLength(1);
    expect(next.confirmed[0].id).toBe("span-2");
    expect(next.selectedSpanId).toBeNull();
  });

  it("SPAN_DELETE does not clear selection if a different span is selected", () => {
    const state: SpanState = {
      ...initialSpanState,
      confirmed: [makeSpan({ id: "span-1" }), makeSpan({ id: "span-2" })],
      selectedSpanId: "span-2",
    };
    const next = spanReducer(state, { type: "SPAN_DELETE", spanId: "span-1" });
    expect(next.selectedSpanId).toBe("span-2");
  });

  it("SPAN_RETYPE updates entity type and clears selection", () => {
    const state: SpanState = {
      ...initialSpanState,
      confirmed: [makeSpan({ id: "span-1", entityType: "PER" })],
      selectedSpanId: "span-1",
    };
    const next = spanReducer(state, { type: "SPAN_RETYPE", spanId: "span-1", entityType: "ORG" });
    expect(next.confirmed[0].entityType).toBe("ORG");
    expect(next.selectedSpanId).toBeNull();
  });

  it("SPAN_SET_SELECTED sets selectedSpanId", () => {
    const next = spanReducer(initialSpanState, { type: "SPAN_SET_SELECTED", spanId: "span-1" });
    expect(next.selectedSpanId).toBe("span-1");
  });

  it("SUGGESTION_PROMOTE adds to confirmed and removes from suggested", () => {
    const suggestion = makeSuggestion({ id: "suggest-1" });
    const state: SpanState = { ...initialSpanState, suggested: [suggestion] };
    const confirmedSpan = makeSpan({ id: "new-span-1", entityType: "ORG" });
    const next = spanReducer(state, { type: "SUGGESTION_PROMOTE", suggestId: "suggest-1", confirmedSpan });
    expect(next.confirmed).toHaveLength(1);
    expect(next.confirmed[0].id).toBe("new-span-1");
    expect(next.suggested).toHaveLength(0);
  });

  it("SUGGESTION_DISMISS removes suggestion without touching confirmed", () => {
    const suggestion = makeSuggestion({ id: "suggest-1" });
    const confirmed = makeSpan();
    const state: SpanState = { ...initialSpanState, confirmed: [confirmed], suggested: [suggestion] };
    const next = spanReducer(state, { type: "SUGGESTION_DISMISS", suggestId: "suggest-1" });
    expect(next.suggested).toHaveLength(0);
    expect(next.confirmed).toHaveLength(1);
  });

  it("ARM sets armedType and clears selection", () => {
    const state: SpanState = { ...initialSpanState, selectedSpanId: "span-1" };
    const next = spanReducer(state, { type: "ARM", entityType: "ORG" });
    expect(next.armedType).toBe("ORG");
    expect(next.selectedSpanId).toBeNull();
  });

  it("DISARM clears armedType", () => {
    const state: SpanState = { ...initialSpanState, armedType: "PER" };
    const next = spanReducer(state, { type: "DISARM" });
    expect(next.armedType).toBeNull();
  });
});
