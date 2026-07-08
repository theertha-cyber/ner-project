"use client";

export interface TokenRangeSpan {
  id: string;
  entityType: string;
  startToken: number;
  endToken: number;
}

export interface TokenRangeState {
  spans: TokenRangeSpan[];
  selectedSpanId: string | null;
  armedType: string | null;
  dragRange: { start: number; end: number } | null;
}

export const initialTokenRangeState: TokenRangeState = {
  spans: [],
  selectedSpanId: null,
  armedType: null,
  dragRange: null,
};

export type TokenRangeAction =
  | { type: "SPANS_LOAD"; spans: TokenRangeSpan[] }
  | { type: "SPAN_RETYPE"; spanId: string; entityType: string }
  | { type: "SPAN_DELETE"; spanId: string }
  | { type: "SPAN_CREATE"; span: TokenRangeSpan }
  | { type: "SPAN_SET_SELECTED"; spanId: string | null }
  | { type: "ARM"; entityType: string }
  | { type: "DISARM" }
  | { type: "DRAG_START"; tokenIndex: number }
  | { type: "DRAG_EXTEND"; tokenIndex: number }
  | { type: "DRAG_END" };

let _nextId = 1;
export function nextSpanId(): string {
  return `tr-${_nextId++}-${Date.now()}`;
}

export function tokenRangeReducer(state: TokenRangeState, action: TokenRangeAction): TokenRangeState {
  switch (action.type) {
    case "SPANS_LOAD":
      return { ...state, spans: action.spans, selectedSpanId: null };

    case "SPAN_RETYPE":
      return {
        ...state,
        spans: state.spans.map((s) =>
          s.id === action.spanId ? { ...s, entityType: action.entityType } : s,
        ),
        selectedSpanId: null,
      };

    case "SPAN_DELETE":
      return {
        ...state,
        spans: state.spans.filter((s) => s.id !== action.spanId),
        selectedSpanId: state.selectedSpanId === action.spanId ? null : state.selectedSpanId,
      };

    case "SPAN_CREATE":
      return { ...state, spans: [...state.spans, action.span], dragRange: null };

    case "SPAN_SET_SELECTED":
      return { ...state, selectedSpanId: action.spanId };

    case "ARM":
      return { ...state, armedType: action.entityType, selectedSpanId: null };

    case "DISARM":
      return { ...state, armedType: null };

    case "DRAG_START":
      return { ...state, dragRange: { start: action.tokenIndex, end: action.tokenIndex } };

    case "DRAG_EXTEND":
      if (!state.dragRange) return state;
      return { ...state, dragRange: { ...state.dragRange, end: action.tokenIndex } };

    case "DRAG_END":
      return { ...state, dragRange: null };

    default:
      return state;
  }
}

export function tagsToSpans(tags: string[]): TokenRangeSpan[] {
  const spans: TokenRangeSpan[] = [];
  let i = 0;
  while (i < tags.length) {
    if (tags[i] === "O") {
      i++;
      continue;
    }
    const prefix = tags[i][0];
    const entityType = tags[i].substring(2);
    const start = i;
    i++;
    while (i < tags.length && tags[i].startsWith("I-") && tags[i].substring(2) === entityType) {
      i++;
    }
    spans.push({
      id: nextSpanId(),
      entityType,
      startToken: start,
      endToken: i - 1,
    });
  }
  return spans;
}

export function spansToTags(spans: TokenRangeSpan[], totalTokens: number): string[] {
  const tags: string[] = new Array(totalTokens).fill("O");
  for (const span of spans) {
    for (let i = span.startToken; i <= span.endToken; i++) {
      tags[i] = i === span.startToken ? `B-${span.entityType}` : `I-${span.entityType}`;
    }
  }
  return tags;
}
