import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { JobCard } from "./job-card";
import type { TrainingJob } from "@/types/training-jobs";

const baseJob: TrainingJob = {
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

  it("applies selected styling when selected", () => {
    const { container } = render(
      <JobCard job={baseJob} isSelected={true} onClick={vi.fn()} />,
    );
    const button = container.querySelector("button");
    expect(button?.className).toContain("border-brand-primary");
  });
});
