export interface ExtractedEntity {
  entity_type: string;
  value: string;
  confidence: number;
  start_offset: number;
  end_offset: number;
}

export interface ExtractResponse {
  entities: ExtractedEntity[];
  model_version?: string | null;
}

export type BatchRunStatus = "queued" | "running" | "completed" | "failed";

/**
 * How a batch extraction run processes documents. The server is the authority: an
 * unavailable mode is rejected with 422 rather than silently downgraded, so the client
 * never has to guess what a run actually did.
 */
export type ProcessingMode = "bert_only" | "bert_llm_postprocess";

export const DEFAULT_PROCESSING_MODE: ProcessingMode = "bert_only";

export interface BatchRun {
  run_id: string;
  status: BatchRunStatus;
  total_documents?: number | null;
  processed_count?: number | null;
  skipped_count?: number | null;
  failed_count?: number | null;
  started_at?: string | null;
  completed_at?: string | null;
  model_version?: string | null;
  processing_mode?: ProcessingMode | null;
  postprocess_model?: string | null;
  postprocess_prompt_version?: string | null;
  /** True when the run completed but post-processing was unavailable for some or all
   *  of it — the extraction succeeded, the enhancement did not. */
  postprocess_degraded?: boolean | null;
}

export interface EntityItem {
  id: string;
  run_id: string;
  entity_id: string;
  value: string;
  confidence: number;
  normalized_value?: string | null;
  source_span_id?: string | null;
  review_status: string;
  corrected_value?: string | null;
  corrected_by?: string | null;
  correction_notes?: string | null;
  document_filename?: string | null;
}

export interface EntityListResponse {
  items: EntityItem[];
  total: number;
  page: number;
  per_page: number;
}

export interface EligibleDocument {
  id: string;
  filename: string;
  already_extracted: boolean;
}

export interface EligibleDocumentListResponse {
  documents: EligibleDocument[];
}
