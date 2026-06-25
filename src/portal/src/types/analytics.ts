export interface EntityCoverageItem {
  entity_type: string;
  coverage_pct: number;
}

export interface ConfidenceBucket {
  label: string;
  count: number;
}

export interface ExtractionVolumePoint {
  date: string;
  count: number;
}

export interface DocumentEntityCountItem {
  entity_type: string;
  avg_per_document: number;
}

export interface DashboardWidgets {
  entity_coverage: EntityCoverageItem[];
  confidence_distribution: { buckets: ConfidenceBucket[] };
  extraction_volume: { data: ExtractionVolumePoint[] };
  document_entity_counts: DocumentEntityCountItem[];
  generated_at: string;
}

export interface QueryResult {
  id: string;
  entity_type: string;
  value: string;
  confidence: number | null;
  document_id: string;
  extracted_at: string | null;
}

export interface QueryResponse {
  results: QueryResult[];
  pagination: {
    next_cursor: string | null;
    has_more: boolean;
    limit: number;
  };
}

export interface AnalyticsFilters {
  entity_types: string[];
  date_from: string;
  date_to: string;
  confidence_min: string;
  confidence_max: string;
}
