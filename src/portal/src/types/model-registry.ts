export interface ModelMetrics {
  eval_f1: number;
  eval_precision: number;
  eval_recall: number;
  eval_loss: number;
  [key: string]: number;
}

export interface ModelVersion {
  id: string;
  version_number: number;
  status: "training" | "completed" | "promoted" | "archived";
  training_job_id: string;
  created_at: string;
  metrics: ModelMetrics | null;
  mlflow_run_id: string | null;
  mlflow_run_url: string | null;
  artifact_path: string | null;
}

export interface ModelVersionListResponse {
  items: ModelVersion[];
  total: number;
}

export interface ActiveModelResponse {
  model: ModelVersion | null;
}
