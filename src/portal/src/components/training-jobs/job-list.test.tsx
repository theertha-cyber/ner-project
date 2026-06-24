import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { JobList } from "./job-list";
import type { TrainingJob } from "@/types/training-jobs";

const makeJob = (overrides: Partial<TrainingJob> = {}): TrainingJob => ({
  id: "job-1",
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
  ...overrides,
});

describe("JobList", () => {
  it("renders loading spinner when isLoading", () => {
    render(
      <JobList jobs={[]} selectedId={null} onSelect={vi.fn()} isLoading={true} />,
    );
    expect(screen.getByRole("status")).toBeDefined();
  });

  it("renders empty state when no jobs", () => {
    render(
      <JobList jobs={[]} selectedId={null} onSelect={vi.fn()} isLoading={false} />,
    );
    expect(screen.getByText("No training jobs found.")).toBeDefined();
  });

  it("renders job cards", () => {
    const jobs = [makeJob({ id: "job-1", status: "running" })];
    render(
      <JobList jobs={jobs} selectedId={null} onSelect={vi.fn()} isLoading={false} />,
    );
    expect(screen.getByText("running")).toBeDefined();
  });
});
