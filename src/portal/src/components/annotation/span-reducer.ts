export interface ConfirmedSpan {
  id: string;
  entityType: string;
  charStart: number;
  charEnd: number;
  text: string;
  confidence: number;
  optimistic?: boolean;
}

export interface SuggestedSpan {
  id: string;
  entityType: string;
  charStart: number;
  charEnd: number;
  text: string;
  confidence: number;
}

export interface SpanState {
  confirmed: ConfirmedSpan[];
  suggested: SuggestedSpan[];
  armedType: string | null;
  selectedSpanId: string | null;
}

export const initialSpanState: SpanState = {
  confirmed: [],
  suggested: [],
  armedType: null,
  selectedSpanId: null,
};

export type SpanAction =
  | { type: "SPANS_LOAD"; spans: ConfirmedSpan[] }
  | { type: "SUGGESTIONS_LOAD"; spans: SuggestedSpan[] }
  | { type: "SPAN_ADD_OPTIMISTIC"; span: ConfirmedSpan }
  | { type: "SPAN_CONFIRM"; optimisticId: string; realSpan: ConfirmedSpan }
  | { type: "SPAN_REVERT"; optimisticId: string }
  | { type: "SPAN_DELETE"; spanId: string }
  | { type: "SPAN_RETYPE"; spanId: string; entityType: string }
  | { type: "SPAN_SET_SELECTED"; spanId: string | null }
  | { type: "SUGGESTION_PROMOTE"; suggestId: string; confirmedSpan: ConfirmedSpan }
  | { type: "SUGGESTION_DISMISS"; suggestId: string }
  | { type: "ARM"; entityType: string }
  | { type: "DISARM" };

export function spanReducer(state: SpanState, action: SpanAction): SpanState {
  switch (action.type) {
    case "SPANS_LOAD":
      return { ...state, confirmed: action.spans, selectedSpanId: null };

    case "SUGGESTIONS_LOAD":
      return { ...state, suggested: action.spans };

    case "SPAN_ADD_OPTIMISTIC":
      return { ...state, confirmed: [...state.confirmed, action.span] };

    case "SPAN_CONFIRM":
      return {
        ...state,
        confirmed: state.confirmed.map((s) =>
          s.id === action.optimisticId ? { ...action.realSpan, optimistic: false } : s,
        ),
      };

    case "SPAN_REVERT":
      return {
        ...state,
        confirmed: state.confirmed.filter((s) => s.id !== action.optimisticId),
      };

    case "SPAN_DELETE":
      return {
        ...state,
        confirmed: state.confirmed.filter((s) => s.id !== action.spanId),
        selectedSpanId: state.selectedSpanId === action.spanId ? null : state.selectedSpanId,
      };

    case "SPAN_RETYPE":
      return {
        ...state,
        confirmed: state.confirmed.map((s) =>
          s.id === action.spanId ? { ...s, entityType: action.entityType } : s,
        ),
        selectedSpanId: null,
      };

    case "SPAN_SET_SELECTED":
      return { ...state, selectedSpanId: action.spanId };

    case "SUGGESTION_PROMOTE":
      return {
        ...state,
        confirmed: [...state.confirmed, action.confirmedSpan],
        suggested: state.suggested.filter((s) => s.id !== action.suggestId),
      };

    case "SUGGESTION_DISMISS":
      return {
        ...state,
        suggested: state.suggested.filter((s) => s.id !== action.suggestId),
      };

    case "ARM":
      return { ...state, armedType: action.entityType, selectedSpanId: null };

    case "DISARM":
      return { ...state, armedType: null };

    default:
      return state;
  }
}
