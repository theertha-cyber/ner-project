/**
 * Wire types for the confidence-routed review surfaces: the low-confidence queue, its
 * resolution, and the accumulation figure.
 *
 * These mirror the backend responses rather than the UI's convenience. Two places where that
 * matters:
 *
 * `AccumulationReport.model_version` is `string | null`, and null means the base model is
 * serving — there is no tenant-trained version for the figure to be a delta against. Typing it
 * as `string` and defaulting to `"0"` would let a screen render "0 spans since version 0",
 * which reads as a real version and is not one.
 *
 * `ReviewOutcome.span_id` is `string | null` because a rejection creates no span. A type that
 * promised an id would push the screen into claiming one exists.
 */

export type ReviewOutcomeKind = "confirmed" | "corrected" | "rejected";
export type ReviewRoute = "human" | "llm";

export interface QueuedPrediction {
  id: string;
  document_id: string;
  filename: string;
  entity_type: string;
  /** What the model extracted. May differ from `text_at_offsets` if the document changed. */
  value: string;
  confidence: number;
  char_start: number;
  char_end: number;
  model_version: string;
  served_by_base_model: boolean;
  /** Below the business threshold, so this prediction is not in any business-facing result. */
  below_business_threshold: boolean;
  created_at: string | null;
  /** Document text around the span, so a reviewer can judge it in context. */
  context: string;
  /** Where `context` starts in the document, for mapping a highlight back to real offsets. */
  context_char_start: number;
  /** What the document actually says at the prediction's offsets. */
  text_at_offsets: string;
}

export interface ReviewQueuePage {
  items: QueuedPrediction[];
  total: number;
  limit: number;
  offset: number;
}

export interface ResolveQueuedPredictionPayload {
  predictionId: string;
  outcome: ReviewOutcomeKind;
  /** Correction only. Omitted fields keep the prediction's own value. */
  entity_type?: string;
  char_start?: number;
  char_end?: number;
}

export interface ReviewOutcome {
  outcome_id: string;
  outcome: ReviewOutcomeKind;
  route: ReviewRoute;
  origin: "queue" | "audit";
  entity_type: string;
  char_start: number;
  char_end: number;
  /** Null for a rejection, which creates no span. */
  span_id: string | null;
  rejected: boolean;
}

export interface AccumulationReport {
  kind: "accumulation_since_training";
  /** Null when the base model is serving: no tenant-trained version to be a delta against. */
  model_version: string | null;
  spans_accumulated: number;
  /** Recorded distinctly and never added into the figure above (ADR-008). */
  spans_from_base_model: number;
  note: string;
}
