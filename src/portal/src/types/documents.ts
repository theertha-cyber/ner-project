export type DocumentStatus = "pending" | "processing" | "processed" | "failed" | "deleted";

export type DocumentPurpose = "query" | "training";

export interface Document {
  id: string;
  filename: string;
  content_type: string;
  status: DocumentStatus;
  file_size: number;
  purpose?: DocumentPurpose | null;
  uploaded_by?: string | null;
  uploaded_by_email?: string | null;
  created_at: string;
}

export interface DocumentListResponse {
  documents: Document[];
  total: number;
  page: number;
  per_page: number;
}
