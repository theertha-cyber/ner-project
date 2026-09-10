/**
 * Wire types for the seed-bootstrap surfaces: schema proposal, batch pre-labeling, the
 * acceptance gate, and the pre-submission readiness report.
 *
 * These mirror the backend responses rather than the UI's convenience. Where the API says
 * `agreement_rate` may be null because nothing has been reviewed yet, so does this — a type that
 * defaulted it to 0 would let a screen render "0% agreement" for a review nobody has started.
 */

export type CandidateDisposition = "pending" | "approved" | "edited" | "rejected";

export interface SchemaProposalCandidate {
  id: string;
  name: string;
  description: string | null;
  /** Quotes verified verbatim against a seed document before they were stored. */
  examples: string[];
  disposition: CandidateDisposition;
  created_entity_type: string | null;
}

export interface SchemaProposal {
  proposal_id: string;
  status: "queued" | "running" | "completed" | "failed";
  seed_document_ids: string[];
  /** The optional Q&A-pair document that guided which entity types were proposed. */
  qa_pair_document_id: string | null;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
  candidates: SchemaProposalCandidate[];
}

/** Whether a batch is the 1–5 validation batch a Tenant Admin reviews, or the main batch
 * an Annotator Admin reviews as the final annotation gate. */
export type BatchKind = "initial" | "large";

/** The named lifecycle the UI renders, derived from per-document outcomes. */
export type BatchState =
  | "queued"
  | "processing"
  | "completed"
  | "partially_completed"
  | "failed";

export interface PrelabelBatchDocument {
  document_id: string;
  position: number;
  status: "pending" | "succeeded" | "failed";
  counts: {
    returned?: number;
    grounded?: number;
    ungrounded?: number;
    unconfigured_type?: number;
  };
  error_message: string | null;
  completed_at: string | null;
}

export interface PrelabelBatch {
  batch_id: string;
  status: "queued" | "running" | "completed" | "failed";
  state: BatchState;
  batch_kind: BatchKind;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
  document_count: number;
  progress?: { settled: number; total: number };
  succeeded: number;
  failed: number;
  pending: number;
  ungrounded: number;
  /** Set to "approved" once an Annotator Admin accepts a `large` batch. */
  annotator_review_status?: string | null;
  training_eligible_at?: string | null;
  documents: PrelabelBatchDocument[];
}

export const BATCH_STATE_LABEL: Record<BatchState, string> = {
  queued: "QUEUED",
  processing: "PROCESSING",
  completed: "COMPLETED",
  partially_completed: "PARTIALLY COMPLETED",
  failed: "FAILED",
};

/**
 * What a reviewer can say about one suggested span. Only `agree` — same entity type, same
 * offsets — counts toward the rate; the other three are all disagreement for gating purposes
 * but are recorded separately, because a boundary nudged by a token and a hallucinated entity
 * are different facts about the model.
 */
export type SuggestionDisposition = "agree" | "boundary" | "retype" | "reject";

export interface AcceptanceSuggestion {
  id: string;
  document_id: string;
  entity_type: string;
  char_start: number;
  char_end: number;
  text: string;
  confidence: number;
  source: string;
}

export interface BatchAcceptance {
  acceptance_id: string;
  sampled_document_ids: string[];
  sample_size: number;
  /** True when the sample is a strict subset; false when the whole batch was reviewed. */
  sampled: boolean;
  agreement_threshold: number;
  agreement_rate: number | null;
  reviewed_count: number | null;
  agreed_count: number | null;
  dispositions: { suggestion_id: string; disposition: SuggestionDisposition }[];
  decision: "in_review" | "accepted" | "rejected";
  reviewer: string | null;
  created_at: string;
  decided_at: string | null;
  suggestions?: AcceptanceSuggestion[];
}

export interface AcceptanceReviewResult {
  acceptance_id: string;
  reviewed_count: number;
  agreed_count: number;
  agreement_rate: number | null;
  agreement_threshold: number;
  sample_review_complete: boolean;
  expected_count: number;
  meets_threshold: boolean;
}

export interface ReadinessEntityType {
  entity_type: string;
  count: number;
  threshold: number;
  meets_threshold: boolean;
  shortfall: number;
}

export interface TrainingReadiness {
  threshold_per_entity_type: number;
  entity_types: ReadinessEntityType[];
  shortfalling_entity_types: { entity_type: string; count: number }[];
  ready: boolean;
  /** Always true. The report informs; the System Admin approval step decides (ADR-009). */
  advisory: boolean;
  blocks_submission: boolean;
}
