import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ModelVersionSection } from "./model-version-section";
import type { ModelVersion } from "@/types/model-registry";

const model: ModelVersion = {
  id: "mv-3",
  version_number: 3,
  status: "promoted",
  training_job_id: "job-1",
  created_at: "2026-06-23T10:00:00Z",
  metrics: {
    eval_f1: 0.91,
    eval_precision: 0.9,
    eval_recall: 0.92,
    eval_loss: 0.12,
    "eval_PER_f1": 0.95,
  },
  mlflow_run_id: "run-1",
  mlflow_run_url: "https://mlflow.example/run-1",
  artifact_path: "tenants/acme-corp/models/v3",
  run_number: 3,
  run_name: null,
};

describe("ModelVersionSection", () => {
  it("renders the version label, status badge and artifact path", () => {
    render(<ModelVersionSection model={model} isActive={false} />);
    expect(screen.getByText("v3")).toBeDefined();
    expect(screen.getByText("promoted")).toBeDefined();
    expect(screen.getByText("tenants/acme-corp/models/v3")).toBeDefined();
  });

  it("marks the active version as serving", () => {
    render(<ModelVersionSection model={model} isActive={true} />);
    expect(screen.getByText("serving")).toBeDefined();
  });

  it("lists per-entity metrics and excludes the core metric keys", () => {
    render(<ModelVersionSection model={model} isActive={false} />);
    expect(screen.getByText("eval_PER_f1")).toBeDefined();
    expect(screen.queryByText("eval_f1")).toBeNull();
  });

  it("prefers the run name over the version number", () => {
    render(<ModelVersionSection model={{ ...model, run_name: "run-003-20260623" }} isActive={false} />);
    expect(screen.getByText("run-003-20260623")).toBeDefined();
  });
});
