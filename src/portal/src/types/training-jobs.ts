export type JobStatus =
  | "pending_approval"
  | "queued"
  | "running"
  | "completed"
  | "failed"
  | "cancelled"
  | "rejected";

export interface Hyperparams {
  learning_rate: number;
  num_epochs: number;
  batch_size: number;
  max_seq_length: number;
}

export interface TrainingJob {
  id: string;
  status: JobStatus;
  hyperparams: Hyperparams | null;
  current_epoch: number | null;
  current_loss: number | null;
  metrics: Record<string, number> | null;
  error_message: string | null;
  model_version_id: string | null;
  mlflow_run_id: string | null;
  mlflow_run_url: string | null;
  created_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  failed_at: string | null;
}

export interface TrainingJobListResponse {
  items: TrainingJob[];
  total: number;
  page: number;
  per_page: number;
}

export interface SubmitJobPayload {
  learning_rate: number;
  num_epochs: number;
  batch_size: number;
  max_seq_length: number;
}

export type TimelineState = "completed" | "active" | "pending";

export interface TimelineStep {
  label: string;
  state: TimelineState;
}
