import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { JobDetailPanel } from "./job-detail-panel";
import type { TrainingJob } from "@/types/training-jobs";

const mockFetch = vi.fn();
globalThis.fetch = mockFetch;

vi.mock("@/lib/auth", () => ({
  useAuth: vi.fn(() => ({
    user: { role: "tenant_admin", tenantId: "t1", userId: "u1", email: "a@b.com", tenantSlug: "acme" },
  })),
}));

function createWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  };
}

const baseJob: TrainingJob = {
  id: "job-1",
  tenant_id: "t1",
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
  run_number: null,
  run_name: null,
};

describe("JobDetailPanel", () => {
  beforeEach(() => {
    mockFetch.mockReset();
    mockFetch.mockResolvedValue(
      new Response(JSON.stringify({ items: [] }), { status: 200 }),
    );
  });

  it("shows spinner when loading", () => {
    render(
      <JobDetailPanel job={undefined} isLoading={true} isError={false} />,
      { wrapper: createWrapper() },
    );
    expect(screen.getByRole("status")).toBeDefined();
  });

  it("shows not found when error", () => {
    render(
      <JobDetailPanel job={undefined} isLoading={false} isError={true} />,
      { wrapper: createWrapper() },
    );
    expect(screen.getByText("Job not found")).toBeDefined();
  });

  it("shows a neutral empty state instead of 'Job not found' when nothing is selected yet", () => {
    render(
      <JobDetailPanel job={undefined} isLoading={false} isError={false} hasSelection={false} />,
      { wrapper: createWrapper() },
    );
    expect(screen.getByText("No job selected")).toBeDefined();
    expect(screen.queryByText("Job not found")).toBeNull();
  });

  it("renders hyperparameter grid", () => {
    render(
      <JobDetailPanel job={baseJob} isLoading={false} isError={false} />,
      { wrapper: createWrapper() },
    );
    expect(screen.getByText("0.00002")).toBeDefined();
    expect(screen.getByText("3")).toBeDefined();
    expect(screen.getByText("8")).toBeDefined();
    expect(screen.getByText("128")).toBeDefined();
  });

  it("renders the hyperparameters grid as a single 4-column row", () => {
    render(
      <JobDetailPanel job={baseJob} isLoading={false} isError={false} />,
      { wrapper: createWrapper() },
    );
    const grid = screen.getByText("Learning Rate").closest("div.grid");
    expect(grid?.className).toContain("grid-cols-4");
  });

  it("shows the full job id and creation date in the header", () => {
    render(
      <JobDetailPanel job={baseJob} isLoading={false} isError={false} />,
      { wrapper: createWrapper() },
    );
    expect(screen.getAllByText(baseJob.id).length).toBeGreaterThan(0);
  });

  it("shows the base-model and registry sublabels in the lineage diagram", () => {
    render(
      <JobDetailPanel job={baseJob} isLoading={false} isError={false} />,
      { wrapper: createWrapper() },
    );
    expect(screen.getByText("dslim/bert-base-NER")).toBeDefined();
    expect(screen.getByText("registry")).toBeDefined();
  });

  it("renders error alert for failed job", () => {
    const failed = { ...baseJob, status: "failed" as const, error_message: "OOM error" };
    render(
      <JobDetailPanel job={failed} isLoading={false} isError={false} />,
      { wrapper: createWrapper() },
    );
    expect(screen.getByText("OOM error")).toBeDefined();
  });

  it("renders MLflow link card when available", () => {
    const withMlflow = {
      ...baseJob,
      status: "completed" as const,
      mlflow_run_url: "http://localhost:5000/#/experiments/3/runs/a1b2c3d4e5f6",
    };
    render(
      <JobDetailPanel job={withMlflow} isLoading={false} isError={false} />,
      { wrapper: createWrapper() },
    );
    expect(screen.getByText("MLflow run")).toBeDefined();
    const link = screen.getByText("MLflow run").closest("a");
    expect(link?.getAttribute("href")).toBe(withMlflow.mlflow_run_url);
    expect(link?.getAttribute("target")).toBe("_blank");
  });

  it("renders the lineage diagram with the job id and 'pending' when no model version exists", () => {
    render(
      <JobDetailPanel job={baseJob} isLoading={false} isError={false} />,
      { wrapper: createWrapper() },
    );
    expect(screen.getAllByText("job-1").length).toBeGreaterThan(0);
    expect(screen.getByText("pending")).toBeDefined();
    expect(screen.getByText("Annotated Documents")).toBeDefined();
  });

  it("renders the resolved model version in the lineage diagram", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (String(url).includes("/models/active")) {
        return Promise.resolve(new Response(JSON.stringify({ model: null }), { status: 200 }));
      }
      return Promise.resolve(
        new Response(
          JSON.stringify({
            items: [{ id: "mv-1", version_number: 3, training_job_id: "job-1", status: "promoted" }],
          }),
          { status: 200 },
        ),
      );
    });

    render(
      <JobDetailPanel job={baseJob} isLoading={false} isError={false} />,
      { wrapper: createWrapper() },
    );

    expect(await screen.findByText("v3")).toBeDefined();
  });

  it("passes the job's own tenant_id as a query param when viewed by system_admin", async () => {
    const crossTenantJob = { ...baseJob, tenant_id: "tenant-b" };
    mockFetch.mockImplementation((url: string) => {
      if (String(url).includes("/models/active")) {
        return Promise.resolve(new Response(JSON.stringify({ model: null }), { status: 200 }));
      }
      return Promise.resolve(
        new Response(
          JSON.stringify({
            items: [{ id: "mv-1", version_number: 5, training_job_id: "job-1", status: "promoted" }],
          }),
          { status: 200 },
        ),
      );
    });

    render(
      <JobDetailPanel job={crossTenantJob} isLoading={false} isError={false} viewerRole="system_admin" />,
      { wrapper: createWrapper() },
    );

    expect(await screen.findByText("v5")).toBeDefined();
    const modelsCall = mockFetch.mock.calls.find(([url]) => String(url).includes("/api/v1/models?"));
    expect(modelsCall).toBeDefined();
    expect(String(modelsCall![0])).toContain("tenant_id=tenant-b");
  });

  it("does not fetch model versions for system_admin until a tenant_id is known", () => {
    render(
      <JobDetailPanel job={undefined} isLoading={false} isError={true} viewerRole="system_admin" />,
      { wrapper: createWrapper() },
    );
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("shows the run name as the primary header identifier when present", () => {
    const job = { ...baseJob, run_number: 3, run_name: "run-003-20260729" };
    render(
      <JobDetailPanel job={job} isLoading={false} isError={false} />,
      { wrapper: createWrapper() },
    );
    expect(screen.getAllByText("run-003-20260729").length).toBeGreaterThan(0);
  });

  it("falls back to the full job id in the header when run_name is absent", () => {
    render(
      <JobDetailPanel job={baseJob} isLoading={false} isError={false} />,
      { wrapper: createWrapper() },
    );
    expect(screen.getAllByText(baseJob.id).length).toBeGreaterThan(0);
  });

  it("renders matching run names for the job and its resolved model version in the lineage diagram", async () => {
    const job = { ...baseJob, run_number: 6, run_name: "run-006-20260729" };
    mockFetch.mockImplementation((url: string) => {
      if (String(url).includes("/models/active")) {
        return Promise.resolve(new Response(JSON.stringify({ model: null }), { status: 200 }));
      }
      return Promise.resolve(
        new Response(
          JSON.stringify({
            items: [{ id: "mv-1", version_number: 3, training_job_id: "job-1", status: "promoted", run_name: "run-006-20260729" }],
          }),
          { status: 200 },
        ),
      );
    });

    render(
      <JobDetailPanel job={job} isLoading={false} isError={false} />,
      { wrapper: createWrapper() },
    );

    expect((await screen.findAllByText("run-006-20260729")).length).toBeGreaterThanOrEqual(2);
  });

  it("falls back to job id and v{version_number} in the lineage diagram for legacy entries", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (String(url).includes("/models/active")) {
        return Promise.resolve(new Response(JSON.stringify({ model: null }), { status: 200 }));
      }
      return Promise.resolve(
        new Response(
          JSON.stringify({
            items: [{ id: "mv-1", version_number: 1, training_job_id: "job-1", status: "promoted", run_name: null }],
          }),
          { status: 200 },
        ),
      );
    });

    render(
      <JobDetailPanel job={baseJob} isLoading={false} isError={false} />,
      { wrapper: createWrapper() },
    );

    expect(screen.getAllByText("job-1").length).toBeGreaterThan(0);
    expect(await screen.findByText("v1")).toBeDefined();
  });
});
