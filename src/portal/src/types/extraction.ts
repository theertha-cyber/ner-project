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
