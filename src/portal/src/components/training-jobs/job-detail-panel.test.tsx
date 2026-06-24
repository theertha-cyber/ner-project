import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { JobDetailPanel } from "./job-detail-panel";
import type { TrainingJob } from "@/types/training-jobs";

const baseJob: TrainingJob = {
  id: "job-1",
  status: "pending_approval",
  hyperparams: { learning_rate: 2e-5, num_epochs: 3, batch_size: 8, max_seq_length: 128 },
  current_epoch: null,
  current_loss: null,
  metrics: null,
  error_message: null,
  model_version_id: null,
  mlflow_run_id: null,
  mlflow_run_url: null,
  created_at: "2026-06-23T10:00:00Z",
  started_at: null,
  completed_at: null,
  failed_at: null,
};

describe("JobDetailPanel", () => {
  it("shows spinner when loading", () => {
    render(<JobDetailPanel job={undefined} isLoading={true} isError={false} />);
    expect(screen.getByRole("status")).toBeDefined();
  });

  it("shows not found when error", () => {
    render(<JobDetailPanel job={undefined} isLoading={false} isError={true} />);
    expect(screen.getByText("Job not found")).toBeDefined();
  });

  it("renders hyperparameter grid", () => {
    render(<JobDetailPanel job={baseJob} isLoading={false} isError={false} />);
    expect(screen.getByText("0.00002")).toBeDefined();
    expect(screen.getByText("3")).toBeDefined();
    expect(screen.getByText("8")).toBeDefined();
    expect(screen.getByText("128")).toBeDefined();
  });

  it("renders error alert for failed job", () => {
    const failed = { ...baseJob, status: "failed" as const, error_message: "OOM error" };
    render(<JobDetailPanel job={failed} isLoading={false} isError={false} />);
    expect(screen.getByText("OOM error")).toBeDefined();
  });

  it("renders MLflow link when available", () => {
    const withMlflow = { ...baseJob, status: "completed" as const, mlflow_run_url: "http://mlflow/run/1" };
    render(<JobDetailPanel job={withMlflow} isLoading={false} isError={false} />);
    const link = screen.getByText("View in MLflow");
    expect(link).toBeDefined();
    expect(link.getAttribute("href")).toBe("http://mlflow/run/1");
  });
});
