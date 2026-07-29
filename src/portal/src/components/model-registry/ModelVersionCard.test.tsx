import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { ModelVersionCard } from "./ModelVersionCard";
import type { ModelVersion } from "@/types/model-registry";

const baseModel: ModelVersion = {
  id: "mv-1",
  version_number: 3,
  status: "completed",
  training_job_id: "tj-1",
  created_at: "2026-06-20T10:00:00Z",
  metrics: { eval_f1: 0.89, eval_precision: 0.91, eval_recall: 0.87, eval_loss: 0.12 },
  mlflow_run_id: null,
  mlflow_run_url: null,
  artifact_path: null,
  run_number: 3,
  run_name: "run-003-20260620",
};

describe("ModelVersionCard", () => {
  it("renders run name for a completed model version", () => {
    render(<ModelVersionCard model={baseModel} isActive={false} isSelected={false} onSelect={vi.fn()} />);
    expect(screen.getByText("run-003-20260620")).toBeDefined();
  });

  it("falls back to v{version_number} when run_name is null (legacy)", () => {
    const legacy: ModelVersion = { ...baseModel, run_number: null, run_name: null };
    render(<ModelVersionCard model={legacy} isActive={false} isSelected={false} onSelect={vi.fn()} />);
    expect(screen.getByText("v3")).toBeDefined();
  });

  it("renders completed badge", () => {
    render(<ModelVersionCard model={baseModel} isActive={false} isSelected={false} onSelect={vi.fn()} />);
    expect(screen.getByText("completed")).toBeDefined();
  });

  it("renders F1 score for completed model", () => {
    render(<ModelVersionCard model={baseModel} isActive={false} isSelected={false} onSelect={vi.fn()} />);
    expect(screen.getByText("F1 0.89")).toBeDefined();
  });

  it("renders F1 as dash for training model", () => {
    const training: ModelVersion = { ...baseModel, status: "training", metrics: null };
    render(<ModelVersionCard model={training} isActive={false} isSelected={false} onSelect={vi.fn()} />);
    expect(screen.getByText("F1 —")).toBeDefined();
  });

  it("renders promoted badge with distinct variant", () => {
    const promoted: ModelVersion = { ...baseModel, status: "promoted" };
    render(<ModelVersionCard model={promoted} isActive={true} isSelected={false} onSelect={vi.fn()} />);
    expect(screen.getByText("promoted")).toBeDefined();
    const dot = document.querySelector(".bg-status-promoted");
    expect(dot).not.toBeNull();
  });

  it("renders archived badge", () => {
    const archived: ModelVersion = { ...baseModel, status: "archived" };
    render(<ModelVersionCard model={archived} isActive={false} isSelected={false} onSelect={vi.fn()} />);
    expect(screen.getByText("archived")).toBeDefined();
  });

  it("applies selected styling when selected", () => {
    const { container } = render(
      <ModelVersionCard model={baseModel} isActive={false} isSelected={true} onSelect={vi.fn()} />,
    );
    const button = container.querySelector("button");
    expect(button?.className).toContain("border-brand-primary");
  });

  it("renders 'Base Model' label for version 0", () => {
    const v0: ModelVersion = {
      id: "v0-base", version_number: 0, status: "promoted",
      training_job_id: "", created_at: "",
      metrics: null, mlflow_run_id: null, mlflow_run_url: null, artifact_path: null, run_number: null, run_name: null,
    };
    render(<ModelVersionCard model={v0} isActive={true} isSelected={false} onSelect={vi.fn()} />);
    expect(screen.getByText("Base Model")).toBeDefined();
    expect(screen.queryByText("v0")).toBeNull();
  });

  it("renders model name instead of F1 for version 0", () => {
    const v0: ModelVersion = {
      id: "v0-base", version_number: 0, status: "promoted",
      training_job_id: "", created_at: "",
      metrics: null, mlflow_run_id: null, mlflow_run_url: null, artifact_path: null, run_number: null, run_name: null,
    };
    render(<ModelVersionCard model={v0} isActive={false} isSelected={false} onSelect={vi.fn()} />);
    expect(screen.getByText("dslim/bert-base-NER")).toBeDefined();
    expect(screen.queryByText(/F1/)).toBeNull();
  });
});
