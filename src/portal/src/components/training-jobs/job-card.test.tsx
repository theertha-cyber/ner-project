import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { JobCard } from "./job-card";
import type { TrainingJob } from "@/types/training-jobs";

const baseJob: TrainingJob = {
  id: "job-1",
  tenant_id: "t1",
  status: "pending_approval",
  hyperparams: null,
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
  run_number: null,
  run_name: null,
};

describe("JobCard", () => {
  it("renders job status badge", () => {
    render(<JobCard job={baseJob} isSelected={false} onClick={vi.fn()} />);
    expect(screen.getByText("pending approval")).toBeDefined();
  });

  it("shows animated pulse for running jobs", () => {
    render(
      <JobCard job={{ ...baseJob, status: "running" }} isSelected={false} onClick={vi.fn()} />,
    );
    const pulse = document.querySelector(".animate-pulse");
    expect(pulse).not.toBeNull();
  });

  it("does not show pulse for non-running jobs", () => {
    render(<JobCard job={baseJob} isSelected={false} onClick={vi.fn()} />);
    const pulse = document.querySelector(".animate-pulse");
    expect(pulse).toBeNull();
  });

  it("shows a status-colored dot even when the job is not running", () => {
    const { container } = render(
      <JobCard job={baseJob} isSelected={false} onClick={vi.fn()} />,
    );
    const dot = container.querySelector("span.bg-status-pending_approval");
    expect(dot).not.toBeNull();
  });

  it("applies selected styling when selected", () => {
    const { container } = render(
      <JobCard job={baseJob} isSelected={true} onClick={vi.fn()} />,
    );
    const button = container.querySelector("button");
    expect(button?.style.border).toContain("var(--primary-line)");
    expect(button?.style.background).toBe("var(--primary-soft)");
  });

  it("shows run name, hyperparameter line, and F1 '—' for a running job with no metrics", () => {
    const job: TrainingJob = {
      ...baseJob,
      id: "tj_9f2a",
      run_number: 5,
      run_name: "run-005-20260729",
      status: "running",
      hyperparams: { learning_rate: 2e-5, num_epochs: 3, batch_size: 8, max_seq_length: 128 },
      metrics: null,
    };
    render(<JobCard job={job} isSelected={false} onClick={vi.fn()} />);
    expect(screen.getByText("run-005-20260729")).toBeDefined();
    expect(screen.getByText("lr 0.00002 · 3ep · bs 8")).toBeDefined();
    expect(screen.getByText("F1 —")).toBeDefined();
  });

  it("shows F1 score to two decimal places for a completed job with metrics", () => {
    const job: TrainingJob = {
      ...baseJob,
      id: "tj_7c04",
      run_number: 6,
      run_name: "run-006-20260729",
      status: "completed",
      metrics: { eval_f1: 0.9 },
    };
    render(<JobCard job={job} isSelected={false} onClick={vi.fn()} />);
    expect(screen.getByText("F1 0.90")).toBeDefined();
    expect(document.querySelector(".animate-pulse")).toBeNull();
  });

  it("falls back to job id when run_name is absent (legacy job)", () => {
    const job: TrainingJob = { ...baseJob, id: "tj_1a2b", run_number: null, run_name: null, status: "completed" };
    render(<JobCard job={job} isSelected={false} onClick={vi.fn()} />);
    expect(screen.getByText("tj_1a2b")).toBeDefined();
  });
});
