export type DocumentStatus = "pending" | "processing" | "processed" | "failed" | "deleted";

export interface Document {
  id: string;
  filename: string;
  content_type: string;
  status: DocumentStatus;
  file_size: number;
  created_at: string;
}

export interface DocumentListResponse {
  documents: Document[];
  total: number;
  page: number;
  per_page: number;
}
