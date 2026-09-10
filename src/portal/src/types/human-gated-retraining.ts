/**
 * Wire types for the two decision surfaces: retraining and promotion.
 *
 * These mirror the backend responses rather than the UI's convenience, and two places where
 * that costs something are worth stating:
 *
 * `RetrainingDecision` is a union, not one object with optional fields. A tenant with no trained
 * model has no accumulation figure at all — not zero — and a shape with `spans_accumulated?:
 * number` would let a screen render `?? 0` and produce exactly the conflation the backend went
 * out of its way to avoid: "0 spans since version 3" and "there is no version 3" are opposite
 * situations, and the one that reads as "nothing to do" is the one where a first training run is
 * what is needed. Discriminating on `has_trained_model` makes the compiler refuse that.
 *
 * `PromotionEvidence.comparable` is `boolean | null`, and `null` means the dataset size of at
 * least one run was not recorded. Not "comparable enough" — unknown. A type that folded null
 * into false, or into true, would make an absence of evidence into a claim.
 *
 * There is no field on either type for a verdict, a score, or a recommendation, because the
 * backend produces none. The decision belongs to a person.
 */

export interface EligibleSource {
  count: number;
  latest_at: string | null;
}

export interface EligibleOverview {
  manual: EligibleSource;
  automated: EligibleSource;
  import: EligibleSource;
}

export interface RetrainingDecisionBase {
  kind: "accumulation_since_training";
  training_run_in_flight: boolean;
  /** Present only when a run is in flight: why the figure reads as it does. */
  in_flight_detail?: string;
  /** Recorded distinctly and never added into the accumulation figure (ADR-008). */
  spans_from_base_model: number;
  note: string;
  /** Training-eligible-and-unconsumed units per source. A report, never a gate. */
  eligible_overview: EligibleOverview;
}

export interface RetrainingDecisionTrained extends RetrainingDecisionBase {
  has_trained_model: true;
  serving_model_version: string;
  spans_accumulated: number;
  /** Entity type to accumulated span count, largest first. */
  by_entity_type: Record<string, number>;
  /** Span source to accumulated count; `manual + automated === spans_accumulated`. */
  by_source: { manual: number; automated: number };
}

export interface RetrainingDecisionUntrained extends RetrainingDecisionBase {
  has_trained_model: false;
  serving_model_version: null;
  state: "no_trained_model";
  state_detail: string;
}

export type RetrainingDecision = RetrainingDecisionTrained | RetrainingDecisionUntrained;

export interface EvaluationMetrics {
  eval_f1?: number;
  eval_precision?: number;
  eval_recall?: number;
  eval_loss?: number;
  dataset_rows?: number;
  [key: string]: unknown;
}

export interface PromotionEvidenceVersion {
  version_number: number;
  status: string;
  metrics: EvaluationMetrics;
  /** Confirmed spans this version's run recorded as consumed. 0 means unrecorded. */
  trained_on_span_count: number;
  training_job_id: string | null;
  created_at: string | null;
}

export interface PromotionEvidence {
  candidate: PromotionEvidenceVersion;
  /** Null when there is no other promoted version to compare against. */
  current: PromotionEvidenceVersion | null;
  /** Null when at least one dataset size was not recorded — unknown, not "close enough". */
  comparable: boolean | null;
  note: string;
}

export interface RetrainRequestResult {
  id: string;
  status: string;
  run_number: number | null;
  run_name: string | null;
  /** True when no reviewed evidence had accumulated. A warning, never a refusal. */
  warnedNoAccumulation: boolean;
}
